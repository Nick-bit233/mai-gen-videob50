import streamlit as st
import os
import traceback
from copy import deepcopy
from datetime import datetime
from utils.ImageUtils import generate_single_image, check_mask_waring
from utils.PageUtils import get_game_type_text, load_style_config, open_file_explorer
from db_utils.DatabaseDataHandler import get_database_handler
from utils.PathUtils import get_user_media_dir

# Initialize database handler
db_handler = get_database_handler()

def st_generate_b50_images(placeholder, user_id, archive_id, save_paths):
    # get data format for image generation scripts
    game_type, records = db_handler.load_archive_for_image_generation(archive_id)

    # read style_config
    style_config = load_style_config()

    with placeholder.container(border=True):
        pb = st.progress(0, text="正在生成B50成绩背景图片...")
        for index, record_detail in enumerate(records):
            chart_id = record_detail['chart_id']
            pb.progress((index + 1) / len(records), text=f"正在生成B50成绩背景图片({index + 1}/{len(records)})")
            record_for_gene_image = deepcopy(record_detail)
            clip_name = record_for_gene_image['clip_name']
            # 标题名称与配置文件中的clip_name一致
            if "_" in clip_name:
                prefix = clip_name.split("_")[0]
                suffix_number = clip_name.split("_")[1]
                title_text = f"{prefix} {suffix_number}"
            else:
                title_text = record_for_gene_image['clip_name']
            # 按照顺序命名生成图片为 gametype_0_标题.png, gametype_1_标题.png ...
            image_save_path = os.path.join(save_paths['image_dir'], f"{game_type}_{index}_{title_text}.png")
            generate_single_image(
                game_type,
                style_config,
                record_for_gene_image,
                image_save_path,
                title_text
            )
            # TODO：默认保存曲绘图片到background_image_path字段，便于视频生成调用
            # default_bg_img = record_for_gene_image['jacket']
            # bg_save_path = os.path.join(save_paths['image_dir'], f"{game_type}_{index}_{title_text}_bg.png")
            # from PIL import Image
            # if default_bg_img:
            #    default_bg_img.save(bg_save_path)
            db_handler.update_image_config_for_record(
                archive_id,
                chart_id=chart_id,
                image_path_data={
                    'achievement_image_path': image_save_path
                }
            )


# =============================================================================
# Page layout starts here
# ==============================================================================
st.set_page_config(
    page_title="Step 1: 生成B50成绩背景图片",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Start with getting G_type from session state
G_type = st.session_state.get('game_type', 'maimai')

st.title("Step 1: 生成B50成绩背景图片")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

### Save Archive Management - Start ###

username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("请先在存档管理页面指定用户名。")
    st.stop()
st.write(f"当前用户名: **{username}**")
archives = db_handler.get_user_save_list(username, game_type=G_type)

with st.expander("更换B50存档"):
    if not archives:
        st.warning("未找到任何存档。请先新建或加载存档。")
        st.stop()
    else:
        archive_names = [a['archive_name'] for a in archives]
        try:
            current_archive_index = archive_names.index(st.session_state.get('archive_name'))
        except (ValueError, TypeError):
            current_archive_index = 0
        
        st.markdown("##### 加载本地存档")
        selected_archive_name = st.selectbox(
            "选择存档进行加载",
            archive_names,
            index=current_archive_index
        )
        if st.button("加载此存档（只需要点击一次！）"):

            archive_id = db_handler.load_save_archive(username, selected_archive_name)
            st.session_state.archive_id = archive_id
        
            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                st.session_state.archive_name = selected_archive_name
                st.success(f"已加载存档 **{selected_archive_name}**")
                st.rerun()
            else:
                st.error("加载存档数据失败。")

### Savefile Management - End ###

if archive_id:
    current_paths = get_user_media_dir(username)
    image_path = current_paths['image_dir']
    st.text("生成成绩背景图片")
    with st.container(border=True):
        st.write("确认你的存档数据无误后，请点击下面的按钮，生成成绩背景图片：")
        if st.button("生成成绩背景图片"):
            generate_info_placeholder = st.empty()
            try:
                if not os.path.exists(image_path):
                    os.makedirs(image_path, exist_ok=True)
                st_generate_b50_images(
                    generate_info_placeholder, 
                    user_id=username, 
                    archive_id=archive_id, 
                    save_paths=current_paths
                )
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