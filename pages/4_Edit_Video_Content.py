import streamlit as st
import os
import json
import traceback
from utils.PageUtils import *
from pre_gen import st_gene_resource_config

DEFAULT_VIDEO_MAX_DURATION = 180

st.header("Step 4-1: 视频内容编辑")

G_config = read_global_config()
image_output_path = f"./b50_images/{G_config['USER_ID']}"
video_download_path = f"./videos/downloads"
config_output_file = f"./b50_datas/video_configs_{G_config['USER_ID']}.json"

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
            song_name, song_level, song_type = item['achievement_title'].split('-')
            st.text(f"谱面名称：{song_name}")
        with info_col2:
            st.text(f"谱面确认：({song_type}) {song_level}")
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

        item['text'] = st.text_area("评论", value=item.get('text', ''), key=f"text_{item['id']}")

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

        # 在使用select_slider之前，先获取有效的时间范围
        start_time, end_time = get_valid_time_range(config['main'][current_index])
        # 然后再传入select_slider
        start_time, end_time = st.select_slider(
            "选择视频片段的起始和结束时间",
            options=range(0, video_duration),
            value=(start_time, end_time)
        )
        
        # 计算总秒数并更新config
        item['start'] = start_time
        item['end'] = end_time
        item['duration'] = end_time - start_time

        new_start_minutes = int(start_time // 60)
        new_start_seconds = int(start_time % 60)
        new_end_minutes = int(end_time // 60)
        new_end_seconds = int(end_time % 60)

        time_col1, time_col2 = st.columns(2)
        with time_col1:
            st.write(f"开始时间: {new_start_minutes:02d}:{new_start_seconds:02d}")
        with time_col2:
            st.write(f"结束时间: {new_end_minutes:02d}:{new_end_seconds:02d}")
        st.write(f"持续时间: {item['duration']}")

# 加载配置文件
config = load_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json")
if not config or 'main' not in config:
    st.toast("未找到视频生成配置或当前视频生成配置无效，正在重新生成……")
    b50_config_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{G_config['USER_ID']}.json")
    b50_config = load_config(b50_config_file) # TODO: B50 config 区分 yt 和 bilibili
    try:
        config = st_gene_resource_config(b50_config, 
                                         image_output_path, video_download_path, config_output_file,
                                         G_config['CLIP_START_INTERVAL'], G_config['CLIP_PLAY_TIME'], G_config['DEFAULT_COMMENT_PLACEHOLDERS'])
        st.success("视频配置生成完成！")
    except Exception as e:
        st.error(f"视频配置生成失败，错误信息: {traceback.format_exc()}")
        config = None

if config:
    # 获取所有视频片段的ID
    video_ids = [item['id'] + " : " + item['achievement_title'] for item in config['main']]
    # 使用session_state来存储当前选择的视频片段索引
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # 快速跳转组件的容器
    selector_container = st.container(border=True)

    # 片段预览和编辑组件，使用empty容器
    preview_placeholder = st.empty()
    update_preview(preview_placeholder, config, st.session_state.current_index)

    # 快速跳转组件的实现
    def on_jump_to_clip():
        target_index = video_ids.index(clip_selector)
        # print(f"跳转到视频片段: {target_index}")
        if target_index != st.session_state.current_index:
            # 保存当前配置
            save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
            st.toast("配置已保存！")
            # 更新session_state
            st.session_state.current_index = target_index
            update_preview(preview_placeholder, config, st.session_state.current_index)
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
            on_jump_to_clip()

    # 上一个和下一个按钮
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("上一个"):
            if st.session_state.current_index > 0:
                # 保存当前配置
                save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                st.toast("配置已保存！")
                # 切换到上一个视频片段
                st.session_state.current_index -= 1
                update_preview(preview_placeholder, config, st.session_state.current_index)
            else:
                st.toast("已经是第一个视频片段！")
    with col2:
        if st.button("下一个"):
            if st.session_state.current_index < len(video_ids) - 1:
                # 保存当前配置
                save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                st.toast("配置已保存！")
                # 切换到下一个视频片段
                st.session_state.current_index += 1
                update_preview(preview_placeholder, config, st.session_state.current_index)
            else:
                st.toast("已经是最后一个视频片段！")
    
    # 保存配置按钮
    if st.button("保存配置"):
        save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
        st.success("配置已保存！")

if st.button("进行下一步"):
    st.switch_page("pages/5_Edit_OpEd_Content.py")