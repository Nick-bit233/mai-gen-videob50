import streamlit as st
import os
import json
import traceback
from datetime import datetime
from utils.PageUtils import *
from utils.PathUtils import get_data_paths, get_user_versions
from pre_gen import st_gene_resource_config

DEFAULT_VIDEO_MAX_DURATION = 180

st.header("Step 4-1: 视频内容编辑")

G_config = read_global_config()

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
if not save_id:
    st.stop()
### Savefile Management - End ###

image_output_path = current_paths['image_dir']
video_config_output_file = current_paths['video_config']
video_download_path = f"./videos/downloads"

# 通过向empty容器添加新的container，更新预览
def update_preview(preview_placeholder, config, current_index):
    with preview_placeholder.container(border=True):
        # 获取当前视频的配置信息
        item = config['main'][current_index]

        # 检查是否存在图片和视频：
        if not os.path.exists(item['main_image']):
            st.error(f"图片文件不存在: {item['main_image']}，请检查前置步骤是否正常完成！")
            return

        # 显示当前视频片段的内容
        st.subheader(f"当前预览: {item['id']}")
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.text(f"谱面名称：{item['achievement_title']} ({item['type']}) [{LEVEL_LABELS[item['level_index']]}]")
        with info_col2:
            absolute_path = os.path.abspath(os.path.dirname(item['video']))
            st.text(f"谱面确认视频文件：{os.path.basename(item['video'])}")
            if st.button("打开视频所在文件夹", key=f"open_folder_{item['id']}"):
                open_file_explorer(absolute_path)
        main_col1, main_col2 = st.columns(2)
        with main_col1:
            st.image(item['main_image'], caption="成绩图片")
        with main_col2:
            
            @st.dialog("删除视频确认")
            def delete_video_dialog():
                st.warning("确定要删除这个视频吗？此操作不可撤销！")
                if st.button("确认删除", key=f"confirm_delete_{item['id']}"):
                    try:
                        os.remove(item['video'])
                        st.toast("视频已删除！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除视频失败: 详细错误信息: {traceback.format_exc()}")

            if os.path.exists(item['video']):
                st.video(item['video'])         
                st.info(f"谱面确认视频不是想要的那个？可能刚才在检查下载链接的时候弄错了什么…… \n 点击下面按钮可以删除此视频，然后请回到上一步重新下载。")
                if st.button("删除该视频", key=f"delete_btn_{item['id']}"):
                    delete_video_dialog()
            else:
                st.warning("谱面确认视频文件不存在，请检查下载步骤是否正常完成！")

        st.subheader("编辑评论")
        item['text'] = st.text_area("心得体会", value=item.get('text', ''), key=f"text_{item['id']}",
                                    placeholder="请填写b50评价")

        # 从文件中获取视频的时长
        video_path = item['video']
        if os.path.exists(video_path):
            video_duration = int(get_video_duration(video_path))
        else:
            video_duration = DEFAULT_VIDEO_MAX_DURATION

        def get_valid_time_range(config_item):
            start = config_item.get('start', 0)
            end = config_item.get('end', 0) 
            # 如果起始时间大于等于结束时间，调整起始时间
            if start >= end:
                start = end - 1
            return start, end

        # 获取有效的时间范围
        start_time, end_time = get_valid_time_range(config['main'][current_index])
        show_start_minutes = int(start_time // 60)
        show_start_seconds = int(start_time % 60)
        show_end_minutes = int(end_time // 60)
        show_end_seconds = int(end_time % 60)
        
        scol1, scol2, scol3 = st.columns(3, vertical_alignment="bottom")
        with scol1:
            st.subheader("开始时间")
        with scol2:
            start_min = st.number_input("分钟", min_value=0, value=show_start_minutes, step=1, key=f"start_min_{item['id']}")
        with scol3:
            start_sec = st.number_input("秒", min_value=0, max_value=59, value=show_start_seconds, step=1, key=f"start_sec_{item['id']}")
            
        ecol1, ecol2, ecol3 = st.columns(3, vertical_alignment="bottom")
        with ecol1:
            st.subheader("结束时间")
        with ecol2:
            end_min = st.number_input("分钟", min_value=0, value=show_end_minutes, step=1, key=f"end_min_{item['id']}")
        with ecol3:
            end_sec = st.number_input("秒", min_value=0, max_value=59, value=show_end_seconds, step=1, key=f"end_sec_{item['id']}")

        # 转换为总秒数
        start_time = start_min * 60 + start_sec
        end_time = end_min * 60 + end_sec

        # 确保结束时间大于开始时间
        if end_time <= start_time:
            st.warning("结束时间必须大于开始时间")
            end_time = start_time + 5

        # 确保结束时间不超过视频时长
        if end_time > video_duration:
            st.warning(f"结束时间不能超过视频时长: {int(video_duration // 60)}分{int(video_duration % 60)}秒")
            end_time = video_duration
            start_time = end_time - 5
        
        # 计算总秒数并更新config
        item['start'] = start_time
        item['end'] = end_time
        item['duration'] = end_time - start_time

        time_col1, time_col2 = st.columns(2)
        with time_col1:
            st.write(f"开始时间: {int(item['start'] // 60):02d}:{int(item['start'] % 60):02d}")
        with time_col2:
            st.write(f"结束时间: {int(item['end'] // 60):02d}:{int(item['end'] % 60):02d}")
        st.write(f"持续时间: {item['duration']}s")

# 读取下载器配置
if 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
else:
    downloader_type = G_config['DOWNLOADER']

# 读取存档的b50 config文件
if downloader_type == "youtube":
    b50_config_file = current_paths['config_yt']
elif downloader_type == "bilibili":
    b50_config_file = current_paths['config_bi']
if not os.path.exists(b50_config_file):
    st.error(f"未找到配置文件{b50_config_file}，请检查B50存档的数据完整性！")
    st.stop()
b50_config = load_config(b50_config_file)
video_config = load_config(video_config_output_file)

if not video_config or 'main' not in video_config:
    st.warning("该存档还没有视频内容的配置文件。请先点击下方按钮，生成配置后方可编辑。")
    if st.button("生成视频内容配置"):
        st.toast("正在生成……")
        try:
            video_config = st_gene_resource_config(b50_config, 
                                            image_output_path, video_download_path, video_config_output_file,
                                            G_config['CLIP_START_INTERVAL'], G_config['CLIP_PLAY_TIME'], G_config['DEFAULT_COMMENT_PLACEHOLDERS'])
            st.success("视频配置生成完成！")
            st.rerun()
        except Exception as e:
            st.error(f"视频配置生成失败，请检查步骤1-3是否正常完成！")
            st.error(f"详细错误信息: {traceback.format_exc()}")
            video_config = None

if video_config:
    # 获取所有视频片段的ID
    video_ids = [f"{item['id']}: {item['achievement_title']} ({item['type']}) [{LEVEL_LABELS[item['level_index']]}]" \
                 for item in video_config['main']]
    # 使用session_state来存储当前选择的视频片段索引
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # 快速跳转组件的容器
    selector_container = st.container(border=True)

    # 片段预览和编辑组件，使用empty容器
    preview_placeholder = st.empty()
    update_preview(preview_placeholder, video_config, st.session_state.current_index)

    # 快速跳转组件的实现
    def on_jump_to_clip(target_index):
        print(f"跳转到视频片段: {target_index}")
        if target_index != st.session_state.current_index:
            # 保存当前配置
            save_config(video_config_output_file, video_config)
            st.toast("配置已保存！")
            # 更新session_state
            st.session_state.current_index = target_index
            update_preview(preview_placeholder, video_config, st.session_state.current_index)
        else:
            st.toast("已经是当前视频片段！")
    
    with selector_container: 
        # 显示当前视频片段的选择框
        clip_selector = st.selectbox(
            label="快速跳转到视频片段", 
            options=video_ids, 
            key="video_selector"  # 添加唯一的key
        )
        if st.button("确定"):
            on_jump_to_clip(video_ids.index(clip_selector))

    # 上一个和下一个按钮
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("上一个"):
            if st.session_state.current_index > 0:
                on_jump_to_clip(st.session_state.current_index - 1)
            else:
                st.toast("已经是第一个视频片段！")
    with col2:
        if st.button("下一个"):
            if st.session_state.current_index < len(video_ids) - 1:
                on_jump_to_clip(st.session_state.current_index + 1)
            else:
                st.toast("已经是最后一个视频片段！")
    
    # 保存配置按钮
    if st.button("保存配置"):
        save_config(video_config_output_file, video_config)
        st.success("配置已保存！")

with st.container(border=True):
    video_config_file = current_paths['video_config']
    video_download_path = f"./videos/downloads"
    st.write("如果因为手动更新b50等原因而需要检查和修改配置，点击下方按钮打开配置文件夹。")
    if st.button("打开配置文件夹", key=f"open_folder_video_config"):
        absolute_path = os.path.abspath(os.path.dirname(video_config_file))
        open_file_explorer(absolute_path)
    st.markdown(f"""其中，`b50_configs_{downloader_type}.json` 是你当前使用平台的b50数据文件，
                `video_configs.json` 是生成视频的配置文件
                """)
    with st.container(border=True):
        st.error("危险区域 Danger Zone")
        st.write("如果本页面无法正常读取图片、视频或评论，请尝试使用下方按钮强制刷新配置。")
        st.warning("警告：此操作将清空所有已填写的评论或时间配置，如有需要请自行备份video_config文件！")
        @st.dialog("删除配置确认")
        def delete_video_config_dialog(file):
            st.warning("确定要执行强制配置刷新操作吗？此操作不可撤销！")
            if st.button("确认删除并刷新", key=f"confirm_delete_video_config"):
                try:
                    os.remove(file)
                    st.rerun()
                except Exception as e:
                    st.error(f"删除当前配置文件失败: 详细错误信息: {traceback.format_exc()}")

        if os.path.exists(video_config_file):
            if st.button("强制刷新视频配置文件", key=f"delete_btn_video_config"):
                delete_video_config_dialog(video_config_file)
        else:
            st.info("当前还没有创建视频生成配置文件")

        @st.dialog("删除视频确认")
        def delete_videoes_dialog(file_path):
            st.warning("确定要执行删除操作吗？此操作不可撤销！")
            if st.button("确认删除", key=f"confirm_delete_videoes"):
                try:
                    for file in os.listdir(file_path):
                        os.remove(os.path.join(file_path, file))
                    st.toast("所有已下载视频已清空！")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除视频失败: 详细错误信息: {traceback.format_exc()}")

        if os.path.exists(video_download_path):
            if st.button("删除所有已下载视频", key=f"delete_btn_videoes"):
                delete_videoes_dialog(video_download_path)
        else:
            st.info("当前还没有下载任何视频")

if st.button("进行下一步"):
    st.switch_page("st_pages/5_Edit_OpEd_Content.py")