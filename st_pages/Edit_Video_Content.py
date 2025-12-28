import streamlit as st
import os
import traceback
from datetime import datetime
from utils.PageUtils import load_style_config, open_file_explorer, get_video_duration, read_global_config, get_game_type_text
from utils.PathUtils import get_user_media_dir
from utils.DataUtils import get_valid_time_range
from utils.VideoUtils import render_one_video_clip, get_video_preview_frame
from db_utils.DatabaseDataHandler import get_database_handler

DEFAULT_VIDEO_MAX_DURATION = 240

G_config = read_global_config()
G_type = st.session_state.get('game_type', 'maimai')
db_handler = get_database_handler()
style_config = load_style_config(game_type=G_type)

global video_download_path
video_download_path = f"./videos/downloads"

# Helper functions
def get_output_video_name_with_timestamp(clip_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{clip_id}_{timestamp}.mp4"


def try_update_default_configs(video_configs, archive_id=None):
    for config in video_configs:
        start = config.get('start', None)
        end = config.get('end', None)
        text = config.get('text', None)
        if not text:
            config['text'] = ""
        s, e = get_valid_time_range(start, end, G_config['CLIP_PLAY_TIME'], G_config['CLIP_START_INTERVAL'])
        config['start'] = s
        config['end'] = e

    db_handler.save_video_config(video_configs=video_configs, archive_id=archive_id)
    return video_configs

# streamlit component functions
def update_preview(preview_placeholder, config, current_index):
    @st.dialog("删除视频确认")
    def delete_video_dialog(c_id, v_path):
        st.warning("确定要删除这个视频吗？此操作不可撤销！")
        if st.button("确认删除", key=f"confirm_delete_{c_id}"):
            try:
                os.remove(v_path)
                st.toast("视频已删除！")
                st.rerun()
            except Exception as e:
                st.error(f"删除视频失败: 详细错误信息: {traceback.format_exc()}")

    # 通过向empty容器添加新的container，更新预览
    with preview_placeholder.container(border=True):
        # 获取当前视频的配置信息
        item = config[current_index]
        chart_id = item['chart_id']
        achievement_image_path = item['main_image']
        video_path = item['video']

        # 检查是否存在图片和视频：
        if not os.path.exists(achievement_image_path):
            st.error(f"图片文件不存在: {achievement_image_path}，请检查前置步骤是否正常完成！")
            return

        # 显示当前视频片段的内容
        clip_name = item.get('clip_title_name', "[未命名片段]")
        st.subheader(f"当前预览: {clip_name}")

        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.text(f"谱面信息：{item.get('record_tag')}")
        with info_col2:
            open_video_dir_btn = st.button("打开源视频所在文件夹", key=f"open_folder_{chart_id}", disabled=not video_path)
            if video_path:
                absolute_path = os.path.abspath(os.path.dirname(video_path))
                st.text(f"谱面确认视频文件：{os.path.basename(video_path)}")
                if open_video_dir_btn:
                    open_file_explorer(absolute_path)
        main_col1, main_col2 = st.columns(2)
        with main_col1:
            st.image(achievement_image_path, caption="成绩图片")
        with main_col2:
            if not video_path:
                st.warning("⚠️ 未找到视频路径信息，请检查下载步骤是否正常完成！")
            else:
                # 确保使用绝对路径
                if not os.path.isabs(video_path):
                    video_path = os.path.abspath(video_path)
                
                # 验证文件是否存在
                if not os.path.exists(video_path):
                    st.warning(f"⚠️ 视频文件不存在: {video_path}\n请检查下载步骤是否正常完成！")
                else:
                    try:
                        # 验证文件扩展名
                        if not video_path.lower().endswith(('.mp4', '.mov', '.avi', '.webm')):
                            st.warning(f"⚠️ 不支持的视频格式: {video_path}")
                        else:
                            # 使用 with 语句打开文件，确保文件句柄正确关闭
                            # 并捕获 Streamlit 媒体文件存储错误
                            try:
                                with open(video_path, 'rb') as f:
                                    # 验证文件可读
                                    pass
                                st.video(video_path)
                            except (OSError, IOError) as e:
                                st.error(f"❌ 无法读取视频文件: {e}")
                                st.caption(f"文件路径: {video_path}")
                            except Exception as e:
                                # 捕获 Streamlit MediaFileStorageError 和其他异常
                                error_msg = str(e)
                                if "MediaFileStorageError" in error_msg or "No media file with id" in error_msg:
                                    st.warning("⚠️ 视频文件引用已失效，请刷新页面或重新加载存档")
                                    st.caption(f"文件路径: {video_path}")
                                    st.info("💡 提示：如果问题持续存在，请尝试重新下载视频或检查文件是否被移动/删除")
                                else:
                                    st.error(f"❌ 无法加载视频: {e}")
                                    st.caption(f"文件路径: {video_path}")
                                    with st.expander("错误详情"):
                                        st.code(traceback.format_exc())
                    except Exception as e:
                        st.error(f"❌ 无法加载视频: {e}")
                        st.caption(f"文件路径: {video_path}")
                        with st.expander("错误详情"):
                            st.code(traceback.format_exc())
        v_tool_col1, v_tool_col2 = st.columns(2)
        with v_tool_col1:
            st.divider()
        with v_tool_col2:
            # Widget for replace video
            replace_help_text = f"互联网上实在找不到这个谱面确认视频？可以上传您自行录制的本地视频，选择文件后点击替换按钮。"
            uploaded_file = st.file_uploader(
                                "替换谱面确认视频：选择本地文件",
                                help=replace_help_text,
                                accept_multiple_files=False,
                                type=["mp4", "mov", "avi"],
                                key=f"replace_video_{chart_id}")
            if st.button(
                "替换为本地视频",
                key=f"replace_btn_{chart_id}"
            ):
                # 将上传的文件另存到下载文件夹
                if uploaded_file:
                    file_name = os.path.basename(uploaded_file.name)
                    save_path = os.path.join(video_download_path, file_name)
                    try:
                        with open(save_path, "wb") as f:
                            # 从内存中读取文件内容
                            f.write(uploaded_file.getbuffer())
                    except Exception as e:
                        st.error(f"保存文件时出错: {e}")
                        with st.expander("错误详情"):
                            st.error(traceback.format_exc())
                    absolute_save_path = os.path.abspath(save_path)
                    st.toast(f"文件 '{file_name}' 已成功保存到下载目录！")
                    # 更新绝对路径信息到数据库chart table
                    db_handler.update_chart_video_path(chart_id=chart_id, video_path=absolute_save_path)
            
            # Widget for delete video
            del_help_text = f"谱面确认视频不对？可能在下载视频的时候弄错了什么…… \n 点击按钮可以删除此视频，然后请回到上一步重新下载。"
            if st.button(
                "删除该视频",
                help=del_help_text,
                key=f"delete_btn_{chart_id}",
                disabled=not video_path
            ):
                delete_video_dialog(chart_id, video_path)
                
        st.subheader("编辑评论")
        item['text'] = st.text_area("心得体会", value=item.get('text', ''), key=f"text_{chart_id}",
                                    placeholder="请填写b50评价")

        # 获取视频的时长，片段起终点信息
        video_duration = item['duration']
        start_time = item['start']
        end_time = item['end']
        if not video_duration or video_duration <= 0:
            # 尝试直接从文件中获取时长
            if video_path and os.path.exists(video_path):
                video_duration = int(get_video_duration(video_path))
                if video_duration <= 0:
                    st.error("获取视频总时长失败，请手动检查视频文件以填写时间。")
                    video_duration = DEFAULT_VIDEO_MAX_DURATION
            else:
                video_duration = DEFAULT_VIDEO_MAX_DURATION

        # 计算分/秒显示的起止时间
        show_start_minutes = int(start_time // 60)
        show_start_seconds = int(start_time % 60)
        show_end_minutes = int(end_time // 60)
        show_end_seconds = int(end_time % 60)
        
        scol1, scol2, scol3 = st.columns(3, vertical_alignment="bottom")
        with scol1:
            st.subheader("开始时间")
        with scol2:
            start_min = st.number_input("分钟", min_value=0, value=show_start_minutes, step=1, key=f"start_min_{chart_id}")
        with scol3:
            start_sec = st.number_input("秒", min_value=0, max_value=59, value=show_start_seconds, step=1, key=f"start_sec_{chart_id}")
            
        ecol1, ecol2, ecol3 = st.columns(3, vertical_alignment="bottom")
        with ecol1:
            st.subheader("结束时间")
        with ecol2:
            end_min = st.number_input("分钟", min_value=0, value=show_end_minutes, step=1, key=f"end_min_{chart_id}")
        with ecol3:
            end_sec = st.number_input("秒", min_value=0, max_value=59, value=show_end_seconds, step=1, key=f"end_sec_{chart_id}")

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
            start_time = end_time - 5 if end_time > 5 else 0
        
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


# =============================================================================
# Page layout starts here
# =============================================================================

st.header("Step 4-1: 视频内容编辑")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

### Savefile Management - Start ###
username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("请先在存档管理页面指定用户名。")
    st.stop()
st.write(f"当前用户名: **{username}**")
archives = db_handler.get_user_save_list(username, game_type=G_type)

with st.expander(f"更换分表存档"):
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
if not archive_id:
    st.stop()
### Savefile Management - End ###

user_media_paths = get_user_media_dir(username, game_type=G_type)
image_output_path = user_media_paths['image_dir']
video_output_path = user_media_paths['output_video_dir']

# 读取下载器配置
if 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
else:
    downloader_type = G_config['DOWNLOADER']

# 读取存档的 video_config 查询（包含存储在chart表中的配置）
try:
    video_configs = db_handler.load_video_configs(archive_id=archive_id)
    video_configs = try_update_default_configs(video_configs, archive_id=archive_id)  # 如果是新存档，将会生成默认配置
except Exception as e:
    st.error(f"读取存档配置失败: {e}")
    with st.expander("错误详情"):
        st.error(traceback.format_exc())
    st.stop()

st.info("在编辑前，您可以选择前往视频模板样式设置页面配置背景图片、背景音乐和字体等素材。")
if st.button("视频模板样式设置", key="style_button"):
    st.switch_page("st_pages/Custom_Video_Style_Config.py")

if video_configs:
    # 获取每条记录的tag索引
    tags = [entry.get('record_tag') for entry in video_configs]
    # 使用session_state来存储当前选择的视频片段索引
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # 快速跳转组件的容器
    selector_container = st.container(border=True)

    # 片段预览和编辑组件，使用empty容器
    preview_placeholder = st.empty()
    update_preview(preview_placeholder, video_configs, st.session_state.current_index)

    # 快速跳转组件的实现
    def on_jump_to_clip(target_index):
        # print(f"跳转到视频片段: {target_index}")
        if target_index != st.session_state.current_index:
            # 保存当前配置到数据库
            db_handler.save_video_config(video_configs=video_configs, archive_id=archive_id)
            st.toast("配置已保存！")
            # 更新session_state
            st.session_state.current_index = target_index
            update_preview(preview_placeholder, video_configs, st.session_state.current_index)
        else:
            st.toast("已经是当前视频片段！")
    
    with selector_container: 
        # 显示当前视频片段的选择框
        clip_selector = st.selectbox(
            label="快速跳转到视频片段", 
            options=tags, 
            key="video_selector"  # 添加唯一的key
        )
        if st.button("确定"):
            on_jump_to_clip(tags.index(clip_selector))

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
            if st.session_state.current_index < len(tags) - 1:
                on_jump_to_clip(st.session_state.current_index + 1)
            else:
                st.toast("已经是最后一个视频片段！")
    
    # 保存配置按钮
    if st.button("保存配置"):
        db_handler.save_video_config(video_configs=video_configs, archive_id=archive_id)
        st.success("配置已保存！")

    with st.expander("片段预览与单独导出", expanded=True):
        col1, col2 = st.columns(2)
        st.info("如需修改视频生成参数，请在【5.合成视频】页面中设置")
        if not os.path.exists(video_output_path):
            os.makedirs(video_output_path, exist_ok=True)
        v_res = G_config['VIDEO_RES']
        v_bitrate_kbps = f"{G_config['VIDEO_BITRATE']}k"
        target_config = video_configs[st.session_state.current_index]
        target_video_filename = get_output_video_name_with_timestamp(target_config['clip_title_name'])
        with col1:
            if st.button("生成当前片段的预览帧"):
                with st.spinner(f"正在生成帧预览 ……"):
                    preview_frame = get_video_preview_frame(
                        game_type=target_config['game_type'],
                        clip_config=target_config,
                        style_config=style_config,
                        resolution=v_res,
                        part="content"
                    )
                st.image(preview_frame, caption="视频预览帧")
        with col2:
            if st.button("导出当前片段视频"):
                db_handler.save_video_config(video_configs=video_configs, archive_id=archive_id)
                with st.spinner(f"正在导出视频片段{target_video_filename} ……"):
                    res = render_one_video_clip(
                        game_type=target_config['game_type'],
                        config=target_config,
                        style_config=style_config,
                        video_file_name=target_video_filename,
                        video_output_path=video_output_path,
                        video_res=v_res,
                        video_bitrate=v_bitrate_kbps
                    )
                if res['status'] == 'success':
                    st.success(res['info'])
                else:
                    st.error(res['info'])
            absolute_path = os.path.abspath(video_output_path)
            if st.button("打开导出视频所在文件夹"):
                open_file_explorer(absolute_path)

with st.expander("[DEBUG区域]其他操作"):
    st.write("如果需要检查原始配置，点击下方按钮读取数据库原始信息。")
    if st.button("读取当前存档原始信息", key=f"load_full_config_raw"):
        st.json(db_handler.load_archive_complete_config(username, archive_name))

    with st.container(border=True):
        st.write("如果无法正常读取图片、视频或评论，请尝试使用下方按钮刷新。")
        
        # @st.dialog("删除配置确认")
        # def delete_video_config_dialog(file):
        #     st.warning("确定要执行强制配置刷新操作吗？此操作不可撤销！")
        #     if st.button("确认删除并刷新", key=f"confirm_delete_video_config"):
        #         try:
        #             os.remove(file)
        #             st.rerun()
        #         except Exception as e:
        #             st.error(f"删除当前配置文件失败: 详细错误信息: {traceback.format_exc()}")
        if st.button("刷新媒体文件读取", key=f"delete_btn_video_config"):
            st.rerun()
            # delete_video_config_dialog(video_config_file)

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
    st.switch_page("st_pages/Edit_OpEd_Content.py")