import streamlit as st
import os
import json
import subprocess
from utils.PageUtils import *

DEFAULT_VIDEO_MAX_DURATION = 180

G_config = read_global_config()

# 通过向empty容器添加新的container，更新预览
def update_preview(preview_placeholder, config, current_index):
    with preview_placeholder.container(border=True):
        # 获取当前视频片段
        item = config['main'][current_index]

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
            st.video(item['video'])
            # TODO：添加修改视频的按钮

        item['text'] = st.text_area("评论", value=item.get('text', ''), key=f"text_{item['id']}")

        # 从文件中获取视频的时长
        video_path = item['video']
        if os.path.exists(video_path):
            video_duration = int(get_video_duration(video_path))
        else:
            video_duration = DEFAULT_VIDEO_MAX_DURATION

        current_start = int(item.get('start', 0))
        current_duration = int(item.get('duration', 15))

        start_time, end_time = st.select_slider(
            "选择片段的开始和结束时间", 
            options=range(0, video_duration), 
            value=(current_start, current_start + current_duration)
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

st.header("Step 3: 视频内容编辑")

# 加载配置文件
config = load_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json")
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
        print(f"跳转到视频片段: {target_index}")
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