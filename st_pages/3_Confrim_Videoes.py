import time
import random
import traceback
import os
import streamlit as st
from utils.PageUtils import *
from pre_gen import search_one_video, download_one_video

G_config = read_global_config()

st.header("Step 3: 视频信息检查和下载")

def st_download_video(placeholder, dl_instance, G_config, b50_config):
    search_wait_time = G_config['SEARCH_WAIT_TIME']
    download_high_res = G_config['DOWNLOAD_HIGH_RES']
    video_download_path = f"./videos/downloads"
    with placeholder.container(border=True, height=560):
        with st.spinner("正在下载视频……"):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            for song in b50_config:
                i += 1
                if 'video_info_match' not in song or not song['video_info_match']:
                    st.warning(f"没有找到({i}/50): {song['title']} 的视频信息，无法下载，请检查前置步骤是否完成")
                    write_container.write(f"跳过({i}/50): {song['title']} ，没有视频信息")
                    continue
                
                video_info = song['video_info_match']
                progress_bar.progress(i / 50, text=f"正在下载视频({i}/50): {video_info['title']}")
                
                result = download_one_video(dl_instance, song, video_download_path, download_high_res)
                write_container.write(f"【{i}/50】{result['info']}")

                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0]:
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

            st.success("下载完成！请点击下一步按钮核对视频素材的详细信息。")

# 在显示数据框之前，将数据转换为兼容的格式
def convert_to_compatible_types(data):
    if isinstance(data, list):
        return [{k: str(v) if isinstance(v, (int, float)) else v for k, v in item.items()} for item in data]
    elif isinstance(data, dict):
        return {k: str(v) if isinstance(v, (int, float)) else v for k, v in data.items()}
    return data

def update_editor(placeholder, config, current_index, dl_instance=None):
    def show_video_info(video_info: dict, width: int = 800) -> None:
        # 只取需要展示的字段
        show_info = {k: video_info[k] for k in ['id', 'title', 'url', 'duration']}
        
        # 转换数据类型以确保兼容性
        converted_info = {k: str(v) if isinstance(v, (int, float)) else v 
                        for k, v in show_info.items()}
        
        # 使用streamlit的dataframe组件展示数据
        st.dataframe(convert_to_compatible_types(converted_info), width=width)

    def update_match_info(placeholder, v_info_match):
        with placeholder.container(border=True):
            # 使用markdown添加带颜色的标题
            st.markdown('<p style="color: #28a745;">当前匹配的视频信息:</p>', unsafe_allow_html=True)
            # 使用封装的函数展示视频信息
            show_video_info(v_info_match)

    with placeholder.container(border=True):
        song = config[current_index]
        # 获取当前匹配的视频信息
        st.subheader(f"当前记录: {song['clip_id']}")

        match_info_placeholder = st.empty()
        update_match_info(match_info_placeholder, song['video_info_match'])

        # 获取当前所有搜索得到的视频信息
        st.write("当前所有搜索得到的视频信息:")
        to_match_videos = song['video_info_list']
        
        # 为每个视频创建一个格式化的标签，包含可点击的链接
        video_options = [
            f"[{i+1}] 【{video['title']}】({video['duration']}秒) [🔗{video['id']}]({video['url']})"
            for i, video in enumerate(to_match_videos)
        ]
        
        selected_index = st.radio(
            "选择正确匹配的谱面确认视频:",
            options=range(len(video_options)),
            format_func=lambda x: video_options[x],
            key=f"radio_select_{song['clip_id']}",
            label_visibility="visible"
        )

        # 显示选中视频的详细信息
        if selected_index is not None:
            st.write("已选择视频的详细信息:")
            show_video_info(to_match_videos[selected_index])

        if st.button("确定使用该信息", key=f"confirm_selected_match_{song['clip_id']}"):
            song['video_info_match'] = to_match_videos[selected_index]
            save_config(b50_config_file, config)
            st.toast("配置已保存！")
            update_match_info(match_info_placeholder, song['video_info_match'])
        
        # 如果搜索结果均不符合，手动输入地址：
        with st.container(border=True):
            st.markdown('<p style="color: #ffc107;">以上都不对？手动搜索正确的谱面确认视频：</p>', unsafe_allow_html=True)
            replace_id = st.text_input("搜索关键词 (建议为谱面确认视频的 youtube ID 或 BV号)", 
                                       key=f"replace_id_{song['clip_id']}")

            # 搜索手动输入的id
            to_replace_video_info = None
            extra_search_button = st.button("搜索并替换", 
                                            key=f"search_replace_id_{song['clip_id']}",
                                            disabled=dl_instance is None or replace_id == "")
            if extra_search_button:
                videos = dl_instance.search_video(replace_id)
                if len(videos) == 0:
                    st.error("未找到有效的视频，请重试")
                else:
                    to_replace_video_info = videos[0]
                    st.success(f"已使用视频{to_replace_video_info['id']}替换匹配信息，详情：")
                    st.markdown(f"【{to_replace_video_info['title']}】({to_replace_video_info['duration']}秒) [🔗{to_replace_video_info['id']}]({to_replace_video_info['url']})")
                    song['video_info_match'] = to_replace_video_info
                    save_config(b50_config_file, config)
                    st.toast("配置已保存！")
                    update_match_info(match_info_placeholder, song['video_info_match'])

# 尝试读取缓存下载器
if 'downloader' in st.session_state and 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
    dl_instance = st.session_state.downloader
else:
    downloader_type = ""
    dl_instance = None
    st.error("未找到缓存的下载器，无法进行手动搜索和下载视频！请回到上一页先进行一次搜索！")
    st.stop()

b50_config_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{G_config['USER_ID']}_{downloader_type}.json")
b50_config = load_config(b50_config_file)

if b50_config:
    for song in b50_config:
        if not song['video_info_match'] or not song['video_info_list'] or not song['clip_id']:
            st.error(f"未找到有效视频下载信息，请检查上一页步骤是否完成！")
            st.stop()

    # 获取所有视频片段的ID
    record_ids = [f"{item['clip_id']} : {item['title']} {item['level_label']}" for item in b50_config]
    # 使用session_state来存储当前选择的视频片段索引
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # 快速跳转组件的容器
    selector_container = st.container(border=True)

    # 片段预览和编辑组件，使用empty容器
    link_editor_placeholder = st.empty()
    update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)

    # 快速跳转组件的实现
    def on_jump_to_record():
        target_index = record_ids.index(clip_selector)
        if target_index != st.session_state.current_index:
            st.session_state.current_index = target_index
            update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
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
                # # 保存当前配置
                # save_config(b50_config_file, b50_config)
                # st.toast("配置已保存！")
                # 切换到上一个视频片段
                st.session_state.current_index -= 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
            else:
                st.toast("已经是第一个记录！")
    with col2:
        if st.button("下一个"):
            if st.session_state.current_index < len(record_ids) - 1:
                # # 保存当前配置
                # save_config(b50_config_file, b50_config)
                # st.toast("配置已保存！")
                # 切换到下一个视频片段
                st.session_state.current_index += 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
            else:
                st.toast("已经是最后一个记录！")
    
    # 保存配置按钮
    if st.button("保存配置"):
        save_config(b50_config_file, b50_config)
        st.success("配置已保存！")

    download_info_placeholder = st.empty()
    st.session_state.download_completed = False
    if st.button("确认当前配置，开始下载视频", disabled=not dl_instance):
        try:
            st_download_video(download_info_placeholder, dl_instance, G_config, b50_config)
            st.session_state.download_completed = True  # Reset error flag if successful
        except Exception as e:
            st.session_state.download_completed = False
            st.error(f"下载过程中出现错误: {e}, 请尝试重新下载")
            st.error(f"详细错误信息: {traceback.format_exc()}")

    if st.button("进行下一步", disabled=not st.session_state.download_completed):
        st.switch_page("st_pages/4_Edit_Video_Content.py")

    with st.container(border=True):
        video_config_file = f"./b50_datas/video_configs_{G_config['USER_ID']}.json"
        video_download_path = f"./videos/downloads"
        st.warning("危险区域 Danger Zone")
        st.write("如果你在使用过程中更换了下载器，你可能希望删除已生成的配置文件，以及在本地缓存文件中下载的视频。")
        st.markdown(f"`./videos/downloads` 目录中是已下载的视频")
        st.markdown(f"`./b50_datas/video_configs_{G_config['USER_ID']}.json` 是生成视频的配置文件")
        st.write("你可以手动检查、修改这些文件，或者点击下面按钮删除已生成的配置文件或视频。")

        @st.dialog("删除配置确认")
        def delete_video_config_dialog(file):
            st.warning("确定要执行删除操作吗？此操作不可撤销！")
            if st.button("确认删除", key=f"confirm_delete_video_config"):
                try:
                    os.remove(file)
                    st.toast("文件已删除！")
                    st.rerun()
                except Exception as e:
                    st.error(f"删除文件失败: 详细错误信息: {traceback.format_exc()}")

        if os.path.exists(video_config_file):
            if st.button("删除视频生成配置文件", key=f"delete_btn_video_config"):
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



