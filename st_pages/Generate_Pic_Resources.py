import streamlit as st
import os
import traceback
from copy import deepcopy
from datetime import datetime
from utils.ImageUtils import generate_single_image, check_mask_waring
from utils.PageUtils import get_game_type_text, load_style_config, open_file_explorer
from db_utils.DatabaseDataHandler import get_database_handler
from utils.PathUtils import get_user_media_dir
from utils.VideoUtils import save_jacket_background_image

# Initialize database handler
db_handler = get_database_handler()
# Start with getting G_type from session state
G_type = st.session_state.get('game_type', 'maimai')

# Postprocessing function to generate B50 images

def st_generate_b50_images(placeholder, user_id, archive_id, save_paths):
    # get data format for image generation scripts
    # maimai可能需要在此处下载曲绘资源，需要处理可能的等待时间
    with st.spinner("正在获取资源数据，请稍等（此过程可能需要1-2分钟）……"):
        game_type, records = db_handler.load_archive_for_image_generation(archive_id)

    # read style_config - 使用从数据库加载的game_type，而不是session_state的G_type
    style_config = load_style_config(game_type=game_type)
    
    with placeholder.container(border=True):
        pb = st.progress(0, text=f"正在生成成绩背景图片...")
        for index, record_detail in enumerate(records):
            chart_id = record_detail['chart_id']
            pb.progress((index + 1) / len(records), text=f"正在生成成绩背景图片({index + 1}/{len(records)})")
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
            if game_type == "maimai":
                # 生成曲绘图片的模糊背景
                jacket_img_data = record_for_gene_image['jacket']  # type - PIL.Image
                bg_save_path = os.path.join(save_paths['image_dir'], f"{game_type}_{chart_id}_bg.png")
                # 如果已经存在背景图片（同一首曲目），则跳过生成
                if not os.path.exists(bg_save_path):
                    save_jacket_background_image(jacket_img_data, bg_save_path)
                # 保存背景图片路径到background_image_path字段，便于视频生成调用
                db_handler.update_image_config_for_record(
                    archive_id,
                    chart_id=chart_id,
                    image_path_data={
                        'achievement_image_path': image_save_path,
                        'background_image_path': bg_save_path
                    }
                )
            else:
                db_handler.update_image_config_for_record(
                    archive_id,
                    chart_id=chart_id,
                    image_path_data={
                        'achievement_image_path': image_save_path
                    }
                )


# =============================================================================
# Page layout starts here
# =============================================================================
# 根据游戏类型动态设置标题
page_title = f"Step 1: 生成成绩背景图片"

# 页面头部
st.header(f"🖼️ 生成成绩背景图片")
st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

### Save Archive Management - Start ###

username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("⚠️ 请先在存档管理页面指定用户名。")
    st.stop()

# 用户信息显示
with st.container(border=True):
    col_user1, col_user2 = st.columns(2)
    with col_user1:
        st.metric("当前用户名", username)
    with col_user2:
        if archive_name:
            st.metric("当前存档", archive_name)
        else:
            st.warning("⚠️ 未加载存档")

archives = db_handler.get_user_save_list(username, game_type=G_type)

# 自动加载最新存档（如果还没有加载存档）
if archives and not archive_id:
    # 按创建时间排序，最新的在前
    archives_sorted = sorted(archives, key=lambda x: x.get('created_at', ''), reverse=True)
    latest_archive_name = archives_sorted[0]['archive_name']
    archive_id = db_handler.load_save_archive(username, latest_archive_name)
    if archive_id:
        st.session_state.archive_id = archive_id
        archive_data = db_handler.load_archive_metadata(username, latest_archive_name)
        if archive_data:
            st.session_state.archive_name = latest_archive_name
            st.session_state.data_updated_step1 = True
            st.success(f"✅ 已自动加载最新存档: **{latest_archive_name}**")
            st.rerun()

# 更新archive_id和archive_name（如果已自动加载）
if not archive_id and st.session_state.get('archive_id'):
    archive_id = st.session_state.archive_id
    archive_name = st.session_state.get('archive_name')

# 根据游戏类型动态设置存档名称
with st.expander(f"🔄 更换分表存档", expanded=False):
    if not archives:
        st.warning("⚠️ 未找到任何存档。请先新建或加载存档。")
        st.stop()
    else:
        # 按创建时间排序
        archives_sorted = sorted(archives, key=lambda x: x.get('created_at', ''), reverse=True)
        archive_names = [a['archive_name'] for a in archives_sorted]
        try:
            current_archive_index = archive_names.index(st.session_state.get('archive_name'))
        except (ValueError, TypeError):
            current_archive_index = 0
        
        st.markdown("##### 选择存档")
        selected_archive_name = st.selectbox(
            "选择存档进行加载",
            archive_names,
            index=current_archive_index,
            format_func=lambda name: f"📁 {name}"
        )
        if st.button("✅ 加载此存档", use_container_width=True, type="primary"):
            archive_id = db_handler.load_save_archive(username, selected_archive_name)
            st.session_state.archive_id = archive_id
        
            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                st.session_state.archive_name = selected_archive_name
                st.success(f"✅ 已加载存档 **{selected_archive_name}**")
                st.rerun()
            else:
                st.error("❌ 加载存档数据失败。")

### Savefile Management - End ###

if archive_id:
    current_paths = get_user_media_dir(username, game_type=G_type, archive_id=archive_id)
    image_path = current_paths['image_dir']
    
    st.markdown("### 🎨 生成成绩背景图片")
    with st.container(border=True):
        st.markdown("""
        **说明**:
        - 本步骤将根据您的存档数据生成所有成绩的背景图片
        - 生成过程可能需要一些时间，请耐心等待
        - 如果已经生成过图片且无需更新，可以跳过此步骤
        """)
        
        col_gen1, col_gen2 = st.columns([2, 1])
        with col_gen1:
            if st.button("🎨 开始生成成绩背景图片", use_container_width=True, type="primary"):
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
                    st.success("✅ 生成成绩背景图片完成！")
                except Exception as e:
                    st.error(f"❌ 生成成绩背景图片时发生错误: {e}")
                    with st.expander("错误详情"):
                        st.code(traceback.format_exc())
        
        with col_gen2:
            if os.path.exists(image_path):
                absolute_path = os.path.abspath(image_path)
            else:
                absolute_path = os.path.abspath(os.path.dirname(image_path))
            if st.button("📂 打开图片文件夹", key=f"open_folder_{username}", use_container_width=True):
                open_file_explorer(absolute_path)
        
        # 检查是否已有图片
        # if os.path.exists(image_path):
        #     existing_images = [f for f in os.listdir(image_path) if f.endswith('.png')]
        #     if existing_images:
        #         st.info(f"ℹ️ 检测到已有 {len(existing_images)} 张图片。如需重新生成，请点击上方按钮。")
    
    st.divider()
    st.markdown("### ➡️ 下一步")
    col_next1, col_next2 = st.columns([3, 1])
    with col_next1:
        st.write("完成图片生成后，请点击右侧按钮进入下一步：搜索谱面确认视频")
    with col_next2:
        if st.button("➡️ 前往下一步", use_container_width=True, type="primary"):
            st.switch_page("st_pages/Search_For_Videos.py")
else:
    st.warning("⚠️ 请先加载一个存档。")
