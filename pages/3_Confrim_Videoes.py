import streamlit as st
from utils.PageUtils import *

G_config = read_global_config()

st.header("Step 3: 谱面视频详情确认")

# 在显示数据框之前，将数据转换为兼容的格式
def convert_to_compatible_types(data):
    if isinstance(data, list):
        return [{k: str(v) if isinstance(v, (int, float)) else v for k, v in item.items()} for item in data]
    elif isinstance(data, dict):
        return {k: str(v) if isinstance(v, (int, float)) else v for k, v in data.items()}
    return data

def update_editor(placeholder, config, current_index):
    with placeholder.container(border=True):
        song = config[current_index]
        # 获取当前匹配的视频信息
        st.subheader(f"当前记录: {song['clip_id']}")
        st.write("当前匹配的视频信息:")
        # 只取id, title, url, duration
        show_match_info = {k: song['video_info_match'][k] for k in ['id', 'title', 'url', 'duration']}
        current_match_info = st.dataframe(convert_to_compatible_types(show_match_info), width=800)
        # 获取当前所有搜索得到的视频信息
        st.write("当前所有搜索得到的视频信息:")
        to_match_videos = song['video_info_list']
        for video in to_match_videos:
            video['index'] = str(to_match_videos.index(video) + 1)
        st.dataframe(to_match_videos, column_order=["index", "id", "title", "url", "duration", "aid", "cid"])

        selected_index = st.number_input("选择正确匹配的谱面确认视频信息（选择序号）", 
                                         min_value=1, 
                                         max_value=len(to_match_videos), 
                                         value=1,
                                         key=f"selected_index_{song['clip_id']}")

        if st.button("确定使用该信息", key=f"confirm_selected_match_{song['clip_id']}"):
            song['video_info_match'] = to_match_videos[selected_index - 1]
            save_config(b50_config_file, b50_config)
            st.toast("配置已保存！")
        
        # 如果搜索结果均不符合，手动输入地址：
        st.write("以上都不对？输入正确的谱面确认视频地址：")
        replace_id = st.text_input("谱面确认视频ID (youtube视频ID 或 BV号)", key=f"replace_id_{song['clip_id']}")
        replace_url = st.text_input("谱面确认视频地址", key=f"replace_url_{song['clip_id']}")

        if st.button("手动替换信息", key=f"replace_match_info_{song['clip_id']}"):
            new_match_info = {
                "id": replace_id,
                "url": replace_url,
            }
            song['video_info_match'] = new_match_info
            save_config(b50_config_file, b50_config)
            # current_match_info = st.dataframe(convert_to_compatible_types(song['video_info_match']), width=800)
            st.toast("配置已保存！")

b50_config_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{G_config['USER_ID']}.json")
b50_config = load_config(b50_config_file)

if b50_config:
    # 获取所有视频片段的ID
    record_ids = [f"{item['clip_id']} : {item['title']} {item['level_label']}" for item in b50_config]
    # 使用session_state来存储当前选择的视频片段索引
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # 快速跳转组件的容器
    selector_container = st.container(border=True)

    # 片段预览和编辑组件，使用empty容器
    link_editor_placeholder = st.empty()
    update_editor(link_editor_placeholder, b50_config, st.session_state.current_index)

    # 快速跳转组件的实现
    def on_jump_to_record():
        target_index = record_ids.index(clip_selector)
        if target_index != st.session_state.current_index:
            # 保存当前配置
            save_config(f"./b50_datas/b50_config_{G_config['USER_ID']}.json", b50_config)
            st.toast("配置已保存！")
            # 更新session_state
            st.session_state.current_index = target_index
            update_editor(link_editor_placeholder, b50_config, st.session_state.current_index)
        else:
            st.toast("已经是当前记录！")
    
    with selector_container: 
        # 显示当前视频片段的选择框
        clip_selector = st.selectbox(
            label="快速跳转到B50记录", 
            options=record_ids, 
            key="record_selector"  # 添加唯一的key
        )
        if st.button("确定"):
            on_jump_to_record()

    # 上一个和下一个按钮
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("上一个"):
            if st.session_state.current_index > 0:
                # 保存当前配置
                save_config(f"./b50_datas/b50_config_{G_config['USER_ID']}.json", b50_config)
                st.toast("配置已保存！")
                # 切换到上一个视频片段
                st.session_state.current_index -= 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index)
            else:
                st.toast("已经是第一个记录！")
    with col2:
        if st.button("下一个"):
            if st.session_state.current_index < len(record_ids) - 1:
                # 保存当前配置
                save_config(f"./b50_datas/b50_config_{G_config['USER_ID']}.json", b50_config)
                st.toast("配置已保存！")
                # 切换到下一个视频片段
                st.session_state.current_index += 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index)
            else:
                st.toast("已经是最后一个记录！")
    
    # 保存配置按钮
    if st.button("保存配置"):
        save_config(f"./b50_datas/b50_config_{G_config['USER_ID']}.json", b50_config)
        st.success("配置已保存！")

if st.button("确认当前配置，开始下载视频"):
    pass

if st.button("进行下一步"):
    st.switch_page("pages/4_Edit_Video_Content.py")

