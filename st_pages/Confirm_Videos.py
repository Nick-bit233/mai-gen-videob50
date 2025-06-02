import time
import random
import traceback
import os
import streamlit as st
from datetime import datetime
from utils.PageUtils import load_record_config, save_record_config, read_global_config
from utils.PathUtils import get_data_paths, get_user_versions
from utils.WebAgentUtils import download_one_video

G_config = read_global_config()

st.header("Step 3: 视频信息检查和下载")

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

def st_download_video(placeholder, dl_instance, G_config, b50_config):
    search_wait_time = G_config['SEARCH_WAIT_TIME']
    download_high_res = G_config['DOWNLOAD_HIGH_RES']
    video_download_path = f"./videos/downloads"
    with placeholder.container(border=True, height=560):
        with st.spinner("正在下载视频……"):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            record_len = len(b50_config)
            for song in b50_config:
                i += 1
                if 'video_info_match' not in song or not song['video_info_match']:
                    st.warning(f"没有找到({i}/{record_len}): {song['title']} 的视频信息，无法下载，请检查前置步骤是否完成")
                    write_container.write(f"跳过({i}/{record_len}): {song['title']} ，没有视频信息")
                    continue
                
                video_info = song['video_info_match']
                progress_bar.progress(i / record_len, text=f"正在下载视频({i}/50): {video_info['title']}")
                
                result = download_one_video(dl_instance, song, video_download_path, download_high_res)
                write_container.write(f"【{i}/{record_len}】{result['info']}")

                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0] and result['status'] == 'success':
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

            st.success("下载完成！请点击下一步按钮核对视频素材的详细信息。")

@st.dialog("分p视频指定", width="large")
def change_video_page(config, cur_clip_index, cur_p_index, b50_config_file):
    st.write("分P视频指定")

    page_info = dl_instance.get_video_pages(config[cur_clip_index]['video_info_match']['id'])
    page_options = []
    for i, page in enumerate(page_info):
        if 'part' in page and 'duration' in page:
            page_options.append(f"P{i + 1}: {page['part']} ({page['duration']}秒)")

    selected_p_index = st.radio(
        "请选择:",
        options=range(len(page_options)),
        format_func=lambda x: page_options[x],
        index=cur_p_index,
        key=f"radio_select_page_{song['clip_id']}",
        label_visibility="visible"
    )

    if st.button("确定更新分p", key=f"confirm_selected_page_{song['clip_id']}"):
        config[cur_clip_index]['video_info_match']['p_index'] = selected_p_index
        save_record_config(b50_config_file, config)
        st.rerun()
    

# 在显示数据框之前，将数据转换为兼容的格式
def convert_to_compatible_types(data):
    if isinstance(data, list):
        return [{k: str(v) if isinstance(v, (int, float)) else v for k, v in item.items()} for item in data]
    elif isinstance(data, dict):
        return {k: str(v) if isinstance(v, (int, float)) else v for k, v in data.items()}
    return data

def update_editor(placeholder, config, current_index, dl_instance=None):

    def update_match_info(placeholder, video_info):
        with placeholder.container(border=True):
            st.markdown(f"""<p style="color: #00BFFF;"><b>当前记录的谱面信息 : </b>{song['title']} ({song['type']}) [{song['level_label']}]</p>"""
                        , unsafe_allow_html=True)
            # 使用markdown添加带颜色的标题
            st.markdown("""<p style="color: #28a745;"><b>当前匹配的视频信息 :</b></p>""", unsafe_allow_html=True)
            # 使用封装的函数展示视频信息
            id = video_info['id']
            title = video_info['title']
            st.markdown(f"- 视频标题：{title}")
            st.markdown(f"- 链接：[🔗{id}]({video_info['url']}), 总时长: {video_info['duration']}秒")
            page_info = dl_instance.get_video_pages(id)
            if page_info and 'p_index' in video_info:
                page_count = video_info['page_count']
                p_index = video_info['p_index']
                st.text(f"此视频具有{page_count}个分p，目前确认的分p序号为【{p_index + 1}】，子标题：【{page_info[p_index]['part']}】")

                col_config = {
                    "page": st.column_config.NumberColumn("序号", width="small"),
                    "part": st.column_config.TextColumn("分P标题", width="large"),
                    "duration": st.column_config.NumberColumn("时长(s)", width="small"),
                    "first_frame": st.column_config.ImageColumn("预览图", width="small", help="为了减少对性能的影响，分p数量过多(>5)时，不加载预览图"),
                }
                     
                with st.expander("查看分p信息", expanded=page_count < 2):
                    if isinstance(page_info, list):
                        st.dataframe(
                            page_info, 
                            column_order=['page', 'part', 'duration', 'first_frame'],
                            column_config=col_config,
                            hide_index=True,
                        )
                    else:
                        st.write("没有找到分p信息")
                

    with placeholder.container(border=True):
        song = config[current_index]
        # 获取当前匹配的视频信息
        st.subheader(f"片段ID: {song['clip_id']}，标题名称: {song['clip_name']}")

        match_info_placeholder = st.empty()
        video_info = song['video_info_match']
        update_match_info(match_info_placeholder, video_info=video_info)
        if "p_index" in video_info:
            p_index = video_info['p_index']   
            if st.button("修改分p序号", key=f"change_page_{song['clip_id']}"):
                change_video_page(config, current_index, p_index, b50_config_file)


        # 获取当前所有搜索得到的视频信息
        st.write("请检查上述视频信息与谱面是否匹配。如果有误，请从下方备选结果中选择正确的视频。")
        to_match_videos = song['video_info_list']
        
        # 视频链接指定
        video_options = []
        for i, video in enumerate(to_match_videos):
            page_count_str = f"    【分p总数：{video['page_count']}】" if 'page_count' in video else ""
            video_options.append(
                f"[{i+1}] {video['title']}({video['duration']}秒) [🔗{video['id']}]({video['url']}) {page_count_str}"
            )
        
        selected_index = st.radio(
            "搜索备选结果:",
            options=range(len(video_options)),
            format_func=lambda x: video_options[x],
            key=f"radio_select_{song['clip_id']}",
            label_visibility="visible"
        )

        if st.button("确定使用该信息", key=f"confirm_selected_match_{song['clip_id']}"):
            song['video_info_match'] = to_match_videos[selected_index]
            save_record_config(b50_config_file, config)
            st.toast("配置已保存！")
            update_match_info(match_info_placeholder, song['video_info_match'])
        
        # 如果搜索结果均不符合，手动输入地址：
        with st.container(border=True):
            st.markdown('<p style="color: #ffc107;">以上都不对？手动输入正确的谱面确认视频id：</p>', unsafe_allow_html=True)
            replace_id = st.text_input("谱面确认视频的 youtube ID 或 BV号", 
                                       key=f"replace_id_{song['clip_id']}")

            # 搜索手动输入的id
            to_replace_video_info = None
            extra_search_button = st.button("搜索并替换", 
                                            key=f"search_replace_id_{song['clip_id']}",
                                            disabled=dl_instance is None or replace_id == "")
            if extra_search_button:
                if downloader_type == "youtube":
                    videos = dl_instance.search_video(replace_id)
                    if len(videos) == 0:
                        st.error("未找到有效的视频，请重试")
                    else:
                        to_replace_video_info = videos[0]
                elif downloader_type == "bilibili":
                    # 如果是b站api，不再搜索而是从api中直接获取
                    try:
                        to_replace_video_info = dl_instance.get_video_info(replace_id)
                    except Exception as e:
                        st.error(f"获取视频失败，错误信息: {e.msg}")

                # print(to_replace_video_info)
                if to_replace_video_info:
                    st.success(f"已使用视频{to_replace_video_info['id']}替换匹配信息，详情：")
                    st.markdown(f"【{to_replace_video_info['title']}】({to_replace_video_info['duration']}秒) [🔗{to_replace_video_info['id']}]({to_replace_video_info['url']})")
                    song['video_info_match'] = to_replace_video_info
                    save_record_config(b50_config_file, config)
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

# 读取存档的b50 config文件
if downloader_type == "youtube":
    b50_config_file = current_paths['config_yt']
elif downloader_type == "bilibili":
    b50_config_file = current_paths['config_bi']
if not os.path.exists(b50_config_file):
    st.error(f"未找到配置文件{b50_config_file}，请检查B50存档的数据完整性！")
    st.stop()
b50_config = load_record_config(b50_config_file, username)

if b50_config:
    for song in b50_config:
        if not (song.get('video_info_list') and song.get('video_info_match')):
            st.error(f"未找到有效视频下载信息，请检查上一页步骤是否完成！")
            st.stop()

    # 获取所有视频片段的ID
    record_ids = [f"{item['clip_id']}: {item['title']} ({item['type']}) [{item['level_label']}]" for item in b50_config]
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
        save_record_config(b50_config_file, b50_config)
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
        st.switch_page("st_pages/Edit_Video_Content.py")



