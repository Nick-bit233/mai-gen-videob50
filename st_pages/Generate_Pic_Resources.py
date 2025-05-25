import streamlit as st
import os
import traceback
from copy import deepcopy
from datetime import datetime
from utils.ImageUtils import generate_single_image, check_mask_waring
from utils.PageUtils import open_file_explorer, load_record_config
from utils.PathUtils import get_data_paths, get_user_versions


def st_generate_b50_images(placeholder, user_id, save_paths):
    # read b50_data
    b50_data = load_record_config(save_paths['data_file'], user_id)
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
                st.warning("检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。如为AP B50或自定义数据请忽略。")
                warned = True
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            clip_name = record_detail['clip_name']
            # 标题名称与配置文件中的clip_name一致
            if "_" in clip_name:
                prefix = clip_name.split("_")[0]
                suffix_number = clip_name.split("_")[1]
                title_text = f"{prefix} {suffix_number}"
            else:
                title_text = record_detail['clip_name']
            # 图片名称与配置文件中的clip_id一致（唯一key）
            image_save_path = os.path.join(save_paths['image_dir'], f"{record_detail['clip_id']}.png")
            # TODO：base image path should be configurable
            generate_single_image(
                "./images/B50ViedoBase.png",
                record_for_gene_image,
                image_save_path,
                title_text
            )

st.title("Step 1: 生成B50成绩背景图片")

### Savefile Management - Start ###
if "username" in st.session_state:
    st.session_state.username = st.session_state.username

if "save_id" in st.session_state:
    st.session_state.save_id = st.session_state.save_id

username = st.session_state.get("username", None)
save_id = st.session_state.get("save_id", None)
current_paths = None
data_loaded = False

if not username:
    st.error("请先获取指定用户名的B50存档！")
    st.stop()

if save_id:
    # load save data
    current_paths = get_data_paths(username, save_id)
    data_loaded = True
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write("当前存档")
        with col2:
            st.write(f"用户名：{username}，存档时间：{save_id} ")
else:
    st.warning("未索引到存档，请先加载存档数据！")

with st.expander("更换B50存档"):
    st.info("如果要更换用户，请回到存档管理页面指定其他用户名。")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            selected_save_id = st.selectbox(
                "选择存档",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            if st.button("使用此存档（只需要点击一次！）"):
                if selected_save_id:
                    st.session_state.save_id = selected_save_id
                    st.rerun()
                else:
                    st.error("无效的存档路径！")
    else:
        st.warning("未找到任何存档，请先在存档管理页面获取存档！")
        st.stop()
### Savefile Management - End ###

if data_loaded:
    image_path = current_paths['image_dir']
    st.text("生成成绩背景图片")
    with st.container(border=True):
        st.write("确认你的存档数据无误后，请点击下面的按钮，生成成绩背景图片：")
        if st.button("生成成绩背景图片"):
            generate_info_placeholder = st.empty()
            try:
                if not os.path.exists(image_path):
                    os.makedirs(image_path, exist_ok=True)
                st_generate_b50_images(generate_info_placeholder, username, current_paths)
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
            st.switch_page("st_pages/Search_For_Videos.py")