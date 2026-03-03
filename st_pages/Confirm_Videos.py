from copy import deepcopy
import time
import random
import traceback
import os
import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from utils.PageUtils import escape_markdown_text, read_global_config, get_game_type_text
from utils.WebAgentUtils import download_one_video, get_keyword
from utils.DataUtils import get_record_tags_from_data_dict, level_index_to_label
from db_utils.DatabaseDataHandler import get_database_handler

G_config = read_global_config()
db_handler = get_database_handler()
G_type = st.session_state.get('game_type', 'maimai')

# Helper functions
def get_web_search_url(chart_data, dl_type):
    game_type = chart_data['game_type']
    title_name = chart_data['song_name']
    difficulty_name = level_index_to_label(game_type, chart_data['level_index'])
    type = chart_data['chart_type']
    keyword = get_keyword(dl_type, game_type, title_name, difficulty_name, type)
    # 将keyword中的非unicode字符转化为url参数形式
    from urllib.parse import quote
    keyword = quote(keyword)
    if dl_type == "youtube":
        return f"https://www.youtube.com/results?search_query={keyword}"
    elif dl_type == "bilibili":
        return f"https://search.bilibili.com/all?keyword={keyword}"
    else:
        raise ValueError(f"Unsupported download type: {dl_type}")

def convert_to_compatible_types(data):
    """ 在显示数据框之前，将数据转换为兼容的格式 """
    if isinstance(data, list):
        return [{k: str(v) if isinstance(v, (int, float)) else v for k, v in item.items()} for item in data]
    elif isinstance(data, dict):
        return {k: str(v) if isinstance(v, (int, float)) else v for k, v in data.items()}
    return data

def st_download_video(placeholder, dl_instance, G_config, charts_data):
    search_wait_time = G_config['SEARCH_WAIT_TIME']
    download_high_res = G_config['DOWNLOAD_HIGH_RES']
    video_download_path = f"./videos/downloads"
    with placeholder.container(border=True, height=560):
        with st.spinner("正在下载视频……"):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            record_len = len(charts_data)
            for song in charts_data:
                c_id = song['chart_id']
                i += 1
                if 'video_info_match' not in song or not song['video_info_match']:
                    write_container.write(f"跳过({i}/{record_len}): {song['song_id']} ，因为没有视频信息而无法下载，请检查是否至少确定了一条视频信息")
                    continue
                else:
                    # 自动进行一次数据库保存
                    db_handler.update_chart_video_metadata(c_id, song['video_info_match'])
                
                video_info = song['video_info_match']
                title = escape_markdown_text(video_info['title'])
                progress_bar.progress(i / record_len, text=f"正在下载视频({i}/{record_len}): {title}")
                
                result = download_one_video(dl_instance, db_handler, song, video_download_path, download_high_res)
                write_container.write(f"【{i}/{record_len}】{result['info']}")

                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0] and result['status'] == 'success':
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

            st.success("下载完成！请点击下一步按钮核对视频素材的详细信息。")

# streamlit component functions
@st.dialog("分p视频指定", width="large")
def change_video_page(cur_chart_data, cur_p_index):
    st.write("分P视频指定")

    cur_c_id = cur_chart_data['chart_id']

    page_info = dl_instance.get_video_pages(cur_chart_data['video_info_match']['id'])
    page_options = []
    for i, page in enumerate(page_info):
        if 'part' in page and 'duration' in page:
            page_options.append(f"P{i + 1}: {page['part']} ({page['duration']}秒)")

    selected_p_index = st.radio(
        "请选择:",
        options=range(len(page_options)),
        format_func=lambda x: page_options[x],
        index=cur_p_index,
        key=f"radio_select_page_{cur_c_id}",
        label_visibility="visible"
    )

    if st.button("确定更新分p", key=f"confirm_selected_page_{cur_c_id}"):
        cur_chart_data['video_info_match']['p_index'] = selected_p_index
        db_handler.update_chart_video_metadata(cur_c_id, cur_chart_data['video_info_match'])
        st.rerun()

def update_editor(placeholder, charts_data: Dict, current_index: int, dl_instance=None):

    def update_match_info(placeholder, video_info):
        with placeholder.container(border=True):
            # 使用封装的函数展示视频信息
            id = video_info['id']
            title = escape_markdown_text(video_info['title'])
            st.markdown(f"- 视频标题：{title}")
            st.markdown(f"- 链接：[🔗{id}]({video_info['url']}), 总时长: {video_info['duration']}秒")
            page_info_empty = st.empty()
            # 只有在视频有分P时才显示分P信息（page_count > 1）
            page_count = video_info.get('page_count', 1)
            if page_count > 1 and 'p_index' in video_info:
                page_info = dl_instance.get_video_pages(id)
                p_index = video_info['p_index']
                with page_info_empty.container(border=False):
                    st.text(f"此视频具有{page_count}个分p，目前确认的分p序号为【{p_index + 1}】，子标题：【{page_info[p_index]['part']}】")

                    col_config = {
                        "page": st.column_config.NumberColumn("序号", width="small"),
                        "part": st.column_config.TextColumn("分P标题", width="large"),
                        "duration": st.column_config.NumberColumn("时长(s)", width="small"),
                        "first_frame": st.column_config.ImageColumn("预览图", width="small", help="为了减少对性能的影响，分p数量过多(>5)时，不加载预览图"),
                    }
                        
                    with st.expander("查看分p信息", expanded=page_count < 5):
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
        song = charts_data[current_index]
        c_id = song['chart_id']
        # 获取当前匹配的视频信息
        # st.subheader(f"当前正在确认的记录信息 \n {record_ids[current_index]}")
        st.markdown(f"""<p style="color: #08337B;"><b>当前正在检查的谱面是: </b></p> <h4>{record_ids[current_index]} </h4>"""
                    , unsafe_allow_html=True)
        st.markdown(f"""<p style="color: #08337B;"><b>该谱面目前已确认的视频信息是: </b></p>"""
                            , unsafe_allow_html=True)

        video_info = song.get('video_info_match', None)
        to_match_videos = song.get('video_info_list', None)
        has_p_index = "p_index" in video_info if video_info else False

        match_info_placeholder = st.empty()
        # 只有在有多个分P时才显示"修改分P视频"按钮
        page_count = video_info.get('page_count', 1) if video_info else 1
        has_multiple_pages = page_count > 1 and has_p_index
        change_video_page_button = st.button("修改分P视频", key=f"change_video_page_{c_id}", disabled=not has_multiple_pages)
        match_list_placeholder = st.empty()
        extra_search_placeholder = st.empty()

        if video_info:
            page_count = video_info.get('page_count', 1)
            p_index = video_info['p_index'] 
            if p_index >= page_count:
                p_index = page_count - 1  # 重置到最大页数范围内
                video_info['p_index'] = p_index
            update_match_info(match_info_placeholder, video_info=video_info)
            if has_multiple_pages:  
                if change_video_page_button:
                    change_video_page(song, p_index)

            # 获取当前所有搜索得到的视频信息
            st.write("请检查上述视频信息与谱面是否匹配。如果有误，请从下方备选结果中选择正确的视频。")

            if to_match_videos:
                with match_list_placeholder.container(border=True):
                    # 视频链接指定
                    video_options = []
                    for i, video in enumerate(to_match_videos):
                        title = escape_markdown_text(video['title'])
                        page_count_str = f"    【分p总数：{video['page_count']}】" if 'page_count' in video else ""
                        video_options.append(
                            f"[{i+1}] {title}({video['duration']}秒) [🔗{video['id']}]({video['url']}) {page_count_str}"
                        )
                    
                    selected_index = st.radio(
                        "搜索备选结果:",
                        options=range(len(video_options)),
                        format_func=lambda x: video_options[x],
                        key=f"radio_select_{c_id}",
                        label_visibility="visible"
                    )

                    if st.button("【确认】保存此信息", key=f"confirm_selected_match_{c_id}", type="primary"):
                        song['video_info_match'] = to_match_videos[selected_index]
                        # 将meta信息保存到数据库
                        db_handler.update_chart_video_metadata(c_id, song['video_info_match'])
                        st.toast("配置已保存！")
                        update_match_info(match_info_placeholder, song['video_info_match'])
            else:
                match_list_placeholder.write("没有备选视频信息（至少需要进行过一次自动搜索）")
        else:
            match_info_placeholder.warning("未找到当前片段的匹配视频信息，请尝试重新进行上一步，或使用下方组件手动搜索！")
            match_list_placeholder.write("没有备选视频信息")

        # 如果搜索结果均不符合，手动输入地址：
        with extra_search_placeholder.container(border=True): 
            search_url = get_web_search_url(chart_data=song, dl_type=st.session_state.downloader_type)
            
            st.markdown('<p style="color: #08337B;"><b>以上都不对？手动输入谱面确认视频信息<b></p>', unsafe_allow_html=True)
            
            # 辅助函数：从URL中提取视频ID
            def extract_video_id(input_text: str, dl_type: str) -> str:
                """从URL或直接输入中提取视频ID"""
                if not input_text:
                    return ""
                
                input_text = input_text.strip()
                
                # 如果是YouTube
                if dl_type == "youtube":
                    # 检查是否是完整URL
                    if "youtube.com/watch?v=" in input_text:
                        # 提取v=后面的ID
                        video_id = input_text.split("watch?v=")[1].split("&")[0].split("?")[0]
                        return video_id
                    elif "youtu.be/" in input_text:
                        # 短链接格式
                        video_id = input_text.split("youtu.be/")[1].split("?")[0].split("&")[0]
                        return video_id
                    elif input_text.startswith("http"):
                        # 其他YouTube URL格式
                        if "v=" in input_text:
                            video_id = input_text.split("v=")[1].split("&")[0].split("?")[0]
                            return video_id
                    # 如果已经是ID格式（11位字符），直接返回
                    if len(input_text) == 11 and input_text.replace('-', '').replace('_', '').isalnum():
                        return input_text
                    # 否则假设是ID
                    return input_text
                
                # 如果是Bilibili
                elif dl_type == "bilibili":
                    # 检查是否是完整URL
                    if "bilibili.com/video/" in input_text:
                        # 提取BV号
                        if "BV" in input_text:
                            bv_start = input_text.find("BV")
                            bv_end = bv_start + 12  # BV号是12位
                            if bv_end <= len(input_text):
                                return input_text[bv_start:bv_end]
                        # 或者从URL路径中提取
                        parts = input_text.split("/video/")
                        if len(parts) > 1:
                            bv_part = parts[1].split("?")[0].split("/")[0]
                            if bv_part.startswith("BV"):
                                return bv_part
                    # 如果已经是BV号格式
                    if input_text.startswith("BV") and len(input_text) == 12:
                        return input_text
                    # 否则假设是BV号
                    return input_text
                
                # 默认返回原输入
                return input_text
            
            col1, col2 = st.columns(2)
            with col1:
                replace_input = st.text_input(
                    "视频链接或ID", 
                    placeholder="支持输入完整链接或视频ID\n例如: https://youtube.com/watch?v=XXXXX 或 XXXXX",
                    help="可以输入完整的视频链接（YouTube或Bilibili），系统会自动提取视频ID；也可以直接输入视频ID或BV号",
                    key=f"replace_input_{c_id}"
                )
                st.caption(f"💡 提示：也可以直接输入视频ID（YouTube: 11位字符，B站: BV号）")
            with col2:
                st.markdown(f"[➡点击跳转到搜索页]({search_url})", unsafe_allow_html=True)
                replace_p_number = st.number_input("分P序号（可选）", 
                                            help="如果视频来源是bilibili且有分P，可以选择直接填写分P序号（分p序号可从网页端查询，当谱面确认视频的p数较多时，直接输入序号加载更快），否则请忽略",
                                            min_value=1, max_value=999, value=1, key=f"replace_p_index_{c_id}")

            # 搜索手动输入的id
            to_replace_video_info = None
            extra_search_button = st.button("获取视频信息并替换", 
                                            key=f"search_replace_id_{c_id}",
                                            disabled=dl_instance is None or not replace_input)
            if extra_search_button:
                try:
                    # 从输入中提取视频ID
                    extracted_id = extract_video_id(replace_input, downloader_type)
                    
                    if not extracted_id:
                        st.error("无法从输入中提取视频ID，请检查输入格式")
                    else:
                        # 显示提取的ID
                        if extracted_id != replace_input:
                            st.info(f"已从链接中提取视频ID: **{extracted_id}**")
                        
                        # 对于YouTube和Bilibili，都使用get_video_info直接通过ID获取视频信息
                        to_replace_video_info = dl_instance.get_video_info(extracted_id)
                except Exception as e:
                    error_msg = str(e)
                    st.error(f"获取视频信息失败: {error_msg}")
                    if "400" in error_msg or "Bad Request" in error_msg:
                        st.warning("""
                        **可能的解决方案：**
                        1. **检查视频ID是否正确**：确保输入的是有效的YouTube视频ID（11位字符）或B站BV号
                        2. **更新库**：尝试更新相关库 `pip install --upgrade pytubefix bilibili-api-python`
                        3. **配置认证**：在搜索配置页面启用 OAuth 或 PO Token 认证
                        4. **使用代理**：如果网络受限，尝试配置代理服务器
                        5. **检查视频可用性**：确保视频未被删除或设为私密
                        """)
                    with st.expander("详细错误信息"):
                        st.code(traceback.format_exc())

                if to_replace_video_info:
                    to_replace_video_p_index = replace_p_number - 1 # 从1开始计数的用户输入转换为从0开始的索引
                    to_replace_video_page_count = to_replace_video_info.get('page_count', 1)
                    if to_replace_video_page_count > 1:  
                        if to_replace_video_p_index >= to_replace_video_page_count:
                            st.warning(f"输入的分P序号超出范围，当前视频只有{to_replace_video_page_count}个分P，将自动调整为最大可用分P")
                            to_replace_video_p_index = to_replace_video_page_count - 1
                        to_replace_video_info['p_index'] = to_replace_video_p_index
                    
                    st.success(f"已使用视频{to_replace_video_info['id']}替换匹配信息，详情：")
                    
                    # 构建详情文本，如果有分P信息则显示
                    p_info = f", p{to_replace_video_p_index + 1}" if to_replace_video_page_count > 1 else ""
                    st.markdown(f"【{to_replace_video_info['title']}】({to_replace_video_info['duration']}秒{p_info}) \
                                [🔗{to_replace_video_info['id']}]({to_replace_video_info['url']})")
                    song['video_info_match'] = to_replace_video_info
                    db_handler.update_chart_video_metadata(c_id, song['video_info_match'])
                    st.toast("配置已保存！")
                    update_match_info(match_info_placeholder, song['video_info_match'])

# 快速跳转组件的实现
def on_jump_to_record():
    target_index = record_ids.index(clip_selector)
    if target_index != st.session_state.current_index:
        st.session_state.current_index = target_index
        update_editor(link_editor_placeholder, 
                      to_edit_chart_data, 
                      st.session_state.current_index, dl_instance)
    else:
        st.toast("已经是当前记录！")

# =============================================================================
# Page layout starts here
# =============================================================================
st.header("📥 确认视频信息和下载视频")

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

data_name = "B30" if G_type == "chunithm" else "B50"
with st.expander(f"更换{data_name}存档"):
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

# 尝试读取缓存下载器
if 'downloader' in st.session_state and 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
    dl_instance = st.session_state.downloader
else:
    downloader_type = ""
    dl_instance = None
    st.error("未找到缓存的下载器，无法进行手动搜索和下载视频！请在上一页保存配置！")
    st.stop()

# 读取存档的charts信息（数据库中的，无视频信息或有旧的匹配信息）
chart_list = db_handler.load_charts_of_archive_records(username, archive_name)
record_len = len(chart_list)
if not chart_list:
    st.warning("未找到任何谱面信息。请确认存档是否有效，存档至少需要包含一条谱面信息。")
    st.stop()

to_edit_chart_data = []
for each in chart_list:
    c_data = deepcopy(each)
    if each.get('video_metadata', None):  # 优先查找数据库中是否包含每个谱面的过往匹配信息
        # print(f"{each['chart_id']}: type: {type(each['video_metadata'])} content: {each['video_metadata']}")
        c_data['video_info_match'] = each['video_metadata']
    to_edit_chart_data.append(c_data)

# 从缓存中读取（本次会话的）搜索结果信息（如果有）
search_result = st.session_state.get("search_results", None)
if search_result:
    for chart in to_edit_chart_data:
        key = chart['chart_id']
        ret_data = search_result.get(key, None)
        if ret_data:  # 如果有，使用缓存的搜索结果
            chart['video_info_list'] = ret_data['video_info_list']
            if not chart.get('video_info_match', None):  # 如果未从数据库中查找到过往匹配信息，使用默认搜索结果的第一位
                chart['video_info_match'] = ret_data['video_info_match']
else:
    st.info("没有缓存的搜索结果，请尝试手动添加匹配视频信息！")

# 获取所有视频片段的ID
record_ids = get_record_tags_from_data_dict(to_edit_chart_data)
# 使用session_state来存储当前选择的视频片段索引
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

# 快速跳转组件的容器
selector_container = st.container(border=True)

# 片段预览和编辑组件，使用empty容器
link_editor_placeholder = st.empty()
update_editor(link_editor_placeholder, 
              to_edit_chart_data, 
              st.session_state.current_index, dl_instance)

with selector_container: 
    # 显示当前视频片段的选择框
    clip_selector = st.selectbox(
        label=f"快速跳转到{data_name}记录", 
        options=record_ids, 
        key="record_selector"  # 添加唯一的key
    )
    if st.button("确定"):
        on_jump_to_record()

# 上一个和下一个按钮
col1, _, _, col2 = st.columns([1, 1, 1, 1]) # 调整列宽比例，增加中间空白列
with col1:
    if st.button("上一个", width="stretch"):
        if st.session_state.current_index > 0:
            # 切换到上一个视频片段
            st.session_state.current_index -= 1
            update_editor(link_editor_placeholder,
                          to_edit_chart_data, 
                          st.session_state.current_index, dl_instance)
        else:
            st.toast("已经是第一个记录！")
with col2:
    if st.button("下一个", width="stretch"):
        if st.session_state.current_index < len(record_ids) - 1:
            # 切换到下一个视频片段
            st.session_state.current_index += 1
            update_editor(link_editor_placeholder, 
                          to_edit_chart_data, 
                          st.session_state.current_index, dl_instance)
        else:
            st.toast("已经是最后一个记录！")

download_info_placeholder = st.empty()
st.session_state.download_completed = False
if st.button("确认当前配置，开始下载视频", disabled=not dl_instance, width="stretch", type="primary"):
    try:
        st_download_video(download_info_placeholder, dl_instance, G_config, to_edit_chart_data)
        st.session_state.download_completed = True  # Reset error flag if successful
    except Exception as e:
        st.session_state.download_completed = False
        st.error(f"下载过程中出现错误: {e}, 请尝试重新下载")
        st.error(f"详细错误信息: {traceback.format_exc()}")

if st.button("进行下一步", disabled=not st.session_state.download_completed):
    st.switch_page("st_pages/Edit_Video_Content.py")



