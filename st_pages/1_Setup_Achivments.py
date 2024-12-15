import streamlit as st
import os
import json
import subprocess
import traceback
from copy import deepcopy
from pre_gen import st_update_b50_data, st_init_cache_pathes
from gene_images import generate_single_image, check_mask_waring
from utils.PageUtils import *

def show_b50_dataframe(info_placeholder, user_id, data):
    with info_placeholder.container(border=True):
        st.write(f"{user_id}的B50数据预览: ")
        st.dataframe(data, column_order=["clip_id", "title", "level_label", "level",  "ds", "achievements", "fc", "fs", "ra", "dxScore"])

G_config = read_global_config()
username = G_config.get('USER_ID', '')

st.header("Step 1: 配置生成器参数和B50成绩数据")

# 配置输入
username = st.text_input("输入水鱼查分器用户名", value=username)

if st.button("确定"):
    # 更新配置字典
    G_config['USER_ID'] = username
    # 写入配置文件
    write_global_config(G_config)
    st.success("配置已保存！")
    st.session_state.config_saved = True  # 添加状态标记

def st_generate_b50_images(placeholder, user_id):
    b50_data_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{user_id}.json")
    # read b50_data
    b50_data = load_config(b50_data_file)
    # make folder for user's b50_images
    os.makedirs(f"./b50_images/{user_id}", exist_ok=True)
    with placeholder.container(border=True):
        pb = st.progress(0, text="正在生成B50成绩背景图片...")
        mask_check_cnt = 0
        mask_warn = False
        warned = False
        for index, record_detail in enumerate(b50_data):
            pb.progress((index + 1) / len(b50_data), text=f"正在生成B50成绩背景图片({index + 1}/{len(b50_data)})")
            acc_string = f"{record_detail['achievements']:.4f}"
            mask_check_cnt, mask_warn = check_mask_waring(acc_string, mask_check_cnt, mask_warn)
            if mask_warn and not warned:
                st.warning("检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
                warned = True
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            prefix = "PastBest" if index < 35 else "NewBest"
            image_name_index = index if index < 35 else index - 35
            generate_single_image(
                "./images/B50ViedoBase.png",
                record_for_gene_image,
                user_id,
                prefix,
                image_name_index,
            )

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):
    if st.button("获取B50数据"):
        with st.spinner("正在获取B50数据更新..."):
            update_info_placeholder = st.empty()

            st_init_cache_pathes()
            
            # 执使用你现有的pre_gen.py代码）
            res = st_update_b50_data()
            info = res.get("info", "unknown")
            b50_data = res.get("data", None)
            if info == "updated":
                st.success(f"B50数据更新完成，共更新了{len(b50_data)}条数据")
                st.session_state.data_updated_step1 = True
            elif info == "keep":
                st.success(f"B50数据已存在，共更新了{len(b50_data)}条数据")
                st.session_state.data_updated_step1 = True
            else:
                st.error("B50数据更新失败！请点击按钮重试")
                update_info_placeholder.write(f"错误信息: {b50_data}")
                st.session_state.data_updated_step1 = False
            if info == "updated" or info == "keep":
                show_b50_dataframe(update_info_placeholder, username, b50_data)

    if st.session_state.get('data_updated_step1', False):
        st.write("确认你的B50数据无误后，点击下面按钮生成成绩背景图片")
        st.info("如果你已经生成过背景图片，且无需更新，可以跳过，请点击“进行下一步”按钮。")
        if st.button("生成成绩背景图片"):
            generate_info_placeholder = st.empty()
            try:
                st_generate_b50_images(generate_info_placeholder, username)
                st.success("生成成绩背景图片完成！")
            except Exception as e:
                st.error(f"生成成绩背景图片时发生错误: {e}")
                st.error(traceback.format_exc())
        if st.button("进行下一步"):
            st.switch_page("pages/2_Search_For_Videoes.py")

else:
    st.warning("请先确定配置！")  # 如果未保存配置，给出提示