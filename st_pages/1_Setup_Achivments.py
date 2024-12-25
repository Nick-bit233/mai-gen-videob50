import streamlit as st
import os
import json
import subprocess
import traceback
from copy import deepcopy
from pre_gen import update_b50_data, st_init_cache_pathes
from pre_gen_int import update_b50_data_int
from gene_images import generate_single_image, check_mask_waring
from utils.PageUtils import *

def show_b50_dataframe(info_placeholder, user_id, data):
    with info_placeholder.container(border=True):
        st.write(f"{user_id}的B50数据预览: ")
        st.dataframe(data, column_order=["clip_id", "title", "level_label", "level",  "ds", "achievements", "fc", "fs", "ra", "dxScore"])

G_config = read_global_config()
username = G_config.get('USER_ID', '')
image_path = f"./b50_images/{username}"

st.header("Step 1: 配置生成器参数和B50成绩数据")

with st.container(border=True):
    # 配置输入
    username = st.text_input("输入水鱼查分器用户名（国服查询）或一个您喜欢的用户名（国际服）", value=username)

    if st.button("确定"):
        if not username:
            st.error("用户名不能为空！")
            st.session_state.config_saved = False
        else:   
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

def update_b50(replace_b50_data, update_function, b50_raw_file, b50_data_file, username):
    update_info_placeholder = st.empty()  
    try:
        if replace_b50_data:
            b50_data = update_function(b50_raw_file, b50_data_file, username)
            st.success("已更新B50数据！")
            st.session_state.data_updated_step1 = True
        else:
            b50_data = load_config(b50_data_file)
            st.success("已加载缓存的B50数据")
            st.session_state.data_updated_step1 = True
        show_b50_dataframe(update_info_placeholder, username, b50_data)
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取B50数据时发生错误: {e}")
        st.error(traceback.format_exc())

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):

    st_init_cache_pathes()

    b50_raw_file = f"./b50_datas/b50_raw_{username}.json"
    b50_data_file = f"./b50_datas/b50_config_{username}.json"
    config_output_file = f"./b50_datas/video_configs_{username}.json"
    b50_data = None

    if 'data_updated_step1' not in st.session_state:
        st.session_state.data_updated_step1 = False

    if os.path.exists(b50_data_file):
        st.warning("检测到用户已缓存有B50数据，是否确认获取最新的数据？这将会覆盖当前已有数据。")
        options = ["使用缓存数据（无视服务器）", "更新并替换当前数据"]
        replace_confirm = st.radio("请选择", options, index=0)
        replace_b50_data = replace_confirm == options[1]
    else:
        replace_b50_data = True

    if st.button("从水鱼获取B50数据（国服）"):
        with st.spinner("正在获取B50数据更新..."):
            update_b50(replace_b50_data, update_b50_data, b50_raw_file, b50_data_file, username)
    
    if st.button("从本地HTML读取B50（国际服）"):
        with st.spinner("正在读取HTML数据..."):
            update_b50(replace_b50_data, update_b50_data_int, b50_raw_file, b50_data_file, username)

    if st.button("导入B50数据源代码（开发中，暂不可用）"):
        # TODO: 按这个按钮之后绘制输入框和确认按钮；确认按钮把输入框内容写入{username}.html，然后调用update_b50
        # 当前的写法似乎并不符合streamlit的逻辑，需要修改
        html_input = st.text_input("请将复制的网页源代码粘贴到这里：")
        if st.button("确认保存"):
            with open(f"./{username}.html", 'w', encoding="utf-8") as f:
               f.write(user_input)
            with st.spinner("正在读取HTML数据..."):
                update_b50(True, update_b50_data_int, b50_raw_file, b50_data_file, username)

    if st.session_state.get('data_updated_step1', False):
        with st.container(border=True):
            st.write("确认你的B50数据无误后，请点击下面的按钮，生成成绩背景图片：")
            if st.button("生成成绩背景图片"):
                generate_info_placeholder = st.empty()
                try:
                    st_generate_b50_images(generate_info_placeholder, username)
                    st.success("生成成绩背景图片完成！")
                except Exception as e:
                    st.error(f"生成成绩背景图片时发生错误: {e}")
                    st.error(traceback.format_exc())
            if os.path.exists(image_path):
                absolute_path = os.path.abspath(image_path)
            else:
                absolute_path = os.path.abspath(os.path.dirname(image_path))
            if st.button("打开成绩图片文件夹", key=f"open_folder_{username}"):
                open_file_explorer(absolute_path)
            st.info("如果你已经生成过背景图片，且无需更新，可以跳过，请点击进行下一步按钮。")
            if st.button("进行下一步"):
                st.switch_page("st_pages/2_Search_For_Videoes.py")

else:
    st.warning("请先确定配置！")  # 如果未保存配置，给出提示