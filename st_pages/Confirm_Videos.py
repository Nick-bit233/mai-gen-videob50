from copy import deepcopy
import time
import random
import traceback
import os
import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from utils.PageUtils import escape_markdown_text, read_global_config, get_game_type_text
from utils.WebAgentUtils import get_keyword
from utils.video_download import download_one_video
from utils.video_confirmation import (
    is_chart_video_matched,
    prioritize_unmatched_charts,
    summarize_chart_video_matches,
)
from utils.DataUtils import get_record_tags_from_data_dict, level_index_to_label
from utils.video_metadata import (
    VideoMetadataError,
    parse_bilibili_reference,
    resolve_maimai_video,
    video_info_platform,
)
from utils.video_source_mode import (
    MAIMAI_METADATA_MODE,
    expected_maimai_platform,
)
from db_utils.DatabaseDataHandler import get_database_handler

G_config = read_global_config()
db_handler = get_database_handler()
G_type = st.session_state.get('game_type', 'maimai')

# Helper functions
def mark_download_dirty():
    st.session_state.download_completed = False
    st.session_state.pop('video_download_summary', None)


def persist_video_selection(chart: dict, video_info: dict) -> bool:
    """Persist same-platform selections; preserve opposite-platform DB history."""
    chart_id = chart['chart_id']
    if G_type == 'maimai':
        overrides = st.session_state.setdefault('video_session_overrides', {})
        overrides[chart_id] = deepcopy(video_info)
        existing = chart.get('video_metadata')
        if existing and video_info_platform(existing) != video_info_platform(video_info):
            return False
    db_handler.update_chart_video_metadata(chart_id, video_info)
    chart['video_metadata'] = deepcopy(video_info)
    return True


def is_video_matching_platform(video: dict, dl_type: str) -> bool:
    platform = video_info_platform(video)
    if dl_type not in {"bilibili", "youtube"}:
        return False
    return platform == dl_type

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

def st_download_video(placeholder, dl_instance, G_config, charts_data, force_redownload=False):
    search_wait_time = G_config['SEARCH_WAIT_TIME']
    download_high_res = G_config['DOWNLOAD_HIGH_RES']
    video_download_path = f"./videos/downloads"
    with placeholder.container(border=True, height=560):
        with st.spinner("正在下载视频……"):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            summary = {"success": [], "skipped": [], "failed": []}
            i = 0
            record_len = len(charts_data)
            for song in charts_data:
                c_id = song['chart_id']
                i += 1
                if 'video_info_match' not in song or not song['video_info_match']:
                    write_container.write(f"跳过({i}/{record_len}): {song['song_id']} ，因为没有视频信息而无法下载，请检查是否至少确定了一条视频信息")
                    summary["failed"].append({"chart_id": c_id, "reason": "没有视频信息"})
                    continue

                video_info = song['video_info_match']
                if not is_video_matching_platform(video_info, st.session_state.downloader_type):
                    write_container.write(f"失败({i}/{record_len}): {song['song_id']} 的视频来源与当前模式不兼容")
                    summary["failed"].append({"chart_id": c_id, "reason": "视频来源与当前模式不兼容"})
                    continue

                # 只持久化同平台信息；跨平台选择保留为本次会话覆盖。
                persist_video_selection(song, video_info)

                title = escape_markdown_text(video_info.get('title', video_info.get('id', '未知视频')))
                progress_bar.progress(i / record_len, text=f"正在下载视频({i}/{record_len}): {title}")
                
                result = download_one_video(
                    dl_instance,
                    db_handler,
                    song,
                    video_download_path,
                    download_high_res,
                    force_redownload=force_redownload,
                )
                write_container.write(f"【{i}/{record_len}】{result['info']}")

                if result['status'] == 'success':
                    summary["success"].append(c_id)
                elif result['status'] == 'skip':
                    summary["skipped"].append(c_id)
                else:
                    summary["failed"].append({"chart_id": c_id, "reason": result['info']})

                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0] and result['status'] == 'success':
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

            progress_bar.progress(1.0, text="下载任务已结束")
            st.write(
                f"成功：{len(summary['success'])}，跳过已有缓存：{len(summary['skipped'])}，失败：{len(summary['failed'])}"
            )
            if summary["failed"]:
                st.error("仍有视频未成功准备，修正失败项后才能进入下一步。")
                st.dataframe(summary["failed"], hide_index=True, width="stretch")
            else:
                st.success("下载完成！请点击下一步按钮核对视频素材的详细信息。")
            return summary

# streamlit component functions
@st.dialog("分p视频指定", width="large")
def change_video_page(cur_chart_data, cur_p_index):
    st.write("分P视频指定")

    cur_c_id = cur_chart_data['chart_id']

    try:
        page_info = dl_instance.get_video_pages(cur_chart_data['video_info_match']['id'])
    except Exception as exc:
        st.error(f"读取分P信息失败：{exc}")
        return
    if not isinstance(page_info, list) or not page_info:
        st.warning("没有读取到可选的分P信息。")
        return
    page_options = []
    for i, page in enumerate(page_info):
        if 'part' in page and 'duration' in page:
            page_options.append(f"P{i + 1}: {page['part']} ({page['duration']}秒)")
    if not page_options:
        st.warning("读取到的分P信息不完整，无法选择。")
        return

    selected_p_index = st.radio(
        "请选择:",
        options=range(len(page_options)),
        format_func=lambda x: page_options[x],
        index=min(max(cur_p_index, 0), len(page_options) - 1),
        key=f"radio_select_page_{cur_c_id}",
        label_visibility="visible"
    )

    if st.button("确定更新分p", key=f"confirm_selected_page_{cur_c_id}"):
        cur_chart_data['video_info_match']['p_index'] = selected_p_index
        cur_chart_data['video_info_match']['page_count'] = len(page_info)
        cur_chart_data['video_info_match']['_page_count_known'] = True
        persist_video_selection(cur_chart_data, cur_chart_data['video_info_match'])
        mark_download_dirty()
        st.rerun()

def _render_editor_contents(placeholder, charts_data: Dict, current_index: int, dl_instance=None):

    def update_match_info(placeholder, video_info):
        with placeholder.container(border=True):
            # 使用封装的函数展示视频信息
            id = video_info.get('id', '未知')
            title = escape_markdown_text(video_info.get('title', id))
            st.markdown(f"- 视频标题：{title}")
            st.markdown(
                f"- 链接：[🔗{id}]({video_info.get('url', '')}), "
                f"总时长: {video_info.get('duration', '未知')}秒"
            )
            if video_info.get('_origin'):
                st.markdown(f"- 来源：`{video_info['_origin']}` / `{video_info_platform(video_info) or 'unknown'}`")
            page_info_empty = st.empty()
            # 只有在视频有分P时才显示分P信息（page_count > 1）
            page_count = int(video_info.get('page_count') or 1)
            p_index = int(video_info.get('p_index') or 0)
            if video_info_platform(video_info) == 'bilibili':
                st.markdown(f"- Bilibili 分P：P{p_index + 1}")
            if page_count > 1 and 'p_index' in video_info and video_info.get('_page_count_known', True):
                try:
                    page_info = dl_instance.get_video_pages(id)
                except Exception as exc:
                    page_info_empty.warning(f"读取分P详情失败：{exc}")
                    return
                p_index = video_info['p_index']
                if not page_info or p_index >= len(page_info):
                    page_info_empty.warning("保存的分P序号超出当前视频的可用范围。")
                    return
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
            elif video_info_platform(video_info) == 'bilibili' and not video_info.get('_page_count_known', True):
                page_info_empty.caption("该条目使用 Metadata 中的分P；如需核对或修改，可手动加载分P列表。")
            # Metadata详情
            if video_info.get('_chart_key') and video_info.get('_metadata_store_version'):
                st.caption(f"chart_key：`{video_info['_chart_key']}` Metadata 版本：`{video_info['_metadata_store_version']}`")

    with placeholder.container(border=True):
        song = charts_data[current_index]
        c_id = song['chart_id']
        source_mode = st.session_state.get('video_source_mode') if G_type == 'maimai' else None
        metadata_mode = G_type == 'maimai' and source_mode == MAIMAI_METADATA_MODE
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
        page_count = int(video_info.get('page_count') or 1) if video_info else 1
        has_multiple_pages = page_count > 1 and has_p_index
        can_load_bilibili_pages = bool(
            video_info
            and dl_instance
            and video_info_platform(video_info) == "bilibili"
        )
        change_video_page_button = st.button(
            "加载/修改分P" if can_load_bilibili_pages else "修改分P视频",
            key=f"change_video_page_{c_id}",
            disabled=not (has_multiple_pages or can_load_bilibili_pages),
        )
        match_list_placeholder = st.empty()
        extra_search_placeholder = st.empty()

        if video_info:
            update_match_info(match_info_placeholder, video_info=video_info)
            if has_multiple_pages or can_load_bilibili_pages:
                p_index = int(video_info.get('p_index') or 0)
                if p_index >= page_count:
                    p_index = page_count - 1  # 重置到最大页数范围内
                    video_info['p_index'] = p_index
                if change_video_page_button:
                    change_video_page(song, p_index)

            # 获取当前所有搜索得到的视频信息
            st.write("请检查上述视频信息与谱面是否匹配。如果有误，请从下方备选结果中选择正确的视频。")

            # 过滤掉非当前下载器平台的视频
            if to_match_videos:
                filtered_videos = [v for v in to_match_videos if is_video_matching_platform(v, st.session_state.downloader_type)]
            else:
                filtered_videos = []

            if filtered_videos:
                with match_list_placeholder.container(border=True):
                    # 视频链接指定
                    video_options = []
                    for i, video in enumerate(filtered_videos):
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
                        selected_video = deepcopy(filtered_videos[selected_index])
                        if G_type == 'maimai':
                            selected_video.setdefault('_platform', st.session_state.downloader_type)
                            selected_video.setdefault('_origin', 'metadata' if metadata_mode else 'search')
                        song['video_info_match'] = selected_video
                        # 将meta信息保存到数据库
                        persisted = persist_video_selection(song, song['video_info_match'])
                        mark_download_dirty()
                        st.toast("配置已保存！")
                        if not persisted:
                            st.caption("已作为本次会话选择使用；原平台数据库记录保持不变。")
                        st.rerun()
            else:
                if metadata_mode:
                    match_list_placeholder.write("没有额外的 Metadata 备选项。可手动输入 Bilibili 链接，或返回切换 YouTube 搜索。")
                else:
                    match_list_placeholder.write("没有备选视频信息（至少需要进行过一次自动搜索）")
        else:
            match_info_placeholder.warning("未找到当前片段的匹配视频信息，请返回上一步，或使用下方组件手动指定视频。")
            match_list_placeholder.write("没有备选视频信息")

        # 如果匹配结果不正确，按当前来源模式手动指定。
        with extra_search_placeholder.container(border=True):
            st.markdown(
                '<p style="color: #08337B;"><b>数据库中没有视频/匹配结果不对？手动指定谱面确认视频</b></p>',
                unsafe_allow_html=True,
            )

            if metadata_mode:
                default_metadata = None
                try:
                    default_metadata = resolve_maimai_video(song)
                except VideoMetadataError as exc:
                    st.warning(f"无法读取 Metadata 默认值：{exc}")
                if st.button(
                    "恢复 Metadata 默认值",
                    key=f"restore_metadata_{c_id}",
                    disabled=default_metadata is None,
                ):
                    song['video_info_match'] = default_metadata
                    persisted = persist_video_selection(song, default_metadata)
                    mark_download_dirty()
                    st.toast("已恢复当前 Metadata 默认值")
                    if not persisted:
                        st.caption("已作为本次会话选择使用；原平台数据库记录保持不变。")
                    st.rerun()

            def extract_youtube_video_id(input_text: str) -> str:
                input_text = (input_text or "").strip()
                if "youtube.com/watch?v=" in input_text:
                    return input_text.split("watch?v=")[1].split("&")[0]
                if "youtu.be/" in input_text:
                    return input_text.split("youtu.be/")[1].split("?")[0].split("&")[0]
                if input_text.startswith("http") and "v=" in input_text:
                    return input_text.split("v=")[1].split("&")[0]
                return input_text

            col1, col2 = st.columns(2)
            with col1:
                if metadata_mode:
                    replace_input = st.text_input(
                        "Bilibili 链接或 BV 号",
                        placeholder="例如：https://www.bilibili.com/video/BV...?p=2",
                        help="此操作只解析 BV 与分P，不调用 Bilibili 搜索或详情接口。",
                        key=f"replace_input_{c_id}",
                    )
                else:
                    replace_input = st.text_input(
                        "YouTube 链接或视频 ID" if G_type == 'maimai' else "视频链接或 ID",
                        key=f"replace_input_{c_id}",
                    )
            with col2:
                search_url = get_web_search_url(chart_data=song, dl_type=st.session_state.downloader_type)
                st.markdown(f"[➡点击跳转到搜索页]({search_url})", unsafe_allow_html=True)
                replace_p_number = st.number_input(
                    "分P序号（可选）",
                    min_value=1,
                    max_value=999,
                    value=1,
                    key=f"replace_p_index_{c_id}",
                    disabled=st.session_state.downloader_type != 'bilibili',
                )

            extra_search_button = st.button(
                "保存手动 Bilibili 链接" if metadata_mode else "获取视频信息并替换",
                key=f"search_replace_id_{c_id}",
                disabled=dl_instance is None or not replace_input,
            )
            if extra_search_button:
                try:
                    if metadata_mode:
                        replacement = parse_bilibili_reference(
                            replace_input,
                            title=song.get('song_name', ''),
                            requested_pid=None if "p=" in replace_input else int(replace_p_number),
                        )
                    else:
                        if st.session_state.downloader_type == 'youtube':
                            extracted_id = extract_youtube_video_id(replace_input)
                        else:
                            extracted_id = parse_bilibili_reference(
                                replace_input,
                                title=song.get('song_name', ''),
                            )['id']
                        if not extracted_id:
                            raise ValueError("无法从输入中提取视频 ID")
                        replacement = dl_instance.get_video_info(extracted_id)
                        if not is_video_matching_platform(replacement, st.session_state.downloader_type):
                            raise ValueError("输入的视频来源与当前来源模式不兼容")
                        if st.session_state.downloader_type == 'bilibili':
                            page_count = int(replacement.get('page_count') or 1)
                            if page_count > 1:
                                replacement['p_index'] = min(
                                    int(replace_p_number) - 1,
                                    page_count - 1,
                                )
                        if G_type == 'maimai':
                            replacement['_origin'] = 'manual'
                            replacement['_platform'] = 'youtube'

                    if not is_video_matching_platform(replacement, st.session_state.downloader_type):
                        raise ValueError("输入的视频来源与当前来源模式不兼容")
                    song['video_info_match'] = replacement
                    persisted = persist_video_selection(song, replacement)
                    mark_download_dirty()
                    st.success(f"已使用 {replacement['id']} 替换匹配信息。")
                    st.toast("配置已保存！")
                    if not persisted:
                        st.caption("已作为本次会话选择使用；原平台数据库记录保持不变。")
                    st.rerun()
                except (VideoMetadataError, ValueError) as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"获取视频信息失败：{exc}")
                    with st.expander("详细错误信息"):
                        st.code(traceback.format_exc())


def update_editor(placeholder, charts_data: Dict, current_index: int, dl_instance=None):
    song = charts_data[current_index]
    matched = is_chart_video_matched(song, st.session_state.downloader_type)
    if matched:
        label = f"✅ {record_ids[current_index]}（已匹配，展开可检查或替换）"
    else:
        label = f"⚠️ {record_ids[current_index]}（未匹配，请展开并手动指定视频）"

    with placeholder.container():
        with st.expander(label, expanded=not matched):
            editor_placeholder = st.empty()
            _render_editor_contents(
                editor_placeholder,
                charts_data,
                current_index,
                dl_instance,
            )

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
                if G_type == 'maimai':
                    for key in (
                        'video_source_mode', 'video_source_results', 'video_session_overrides',
                        'search_results',
                        'downloader', 'downloader_type', 'download_completed',
                        'current_index', 'record_selector',
                    ):
                        st.session_state.pop(key, None)
                    st.switch_page("st_pages/Search_For_Videos.py")
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
    if G_type == 'maimai' and st.button("返回视频匹配页面", type="primary"):
        st.switch_page("st_pages/Search_For_Videos.py")
    st.stop()

source_mode = st.session_state.get('video_source_mode') if G_type == 'maimai' else None
if G_type == 'maimai':
    expected_downloader = expected_maimai_platform(source_mode)
    if expected_downloader is None or downloader_type != expected_downloader:
        st.error("当前 maimai 来源模式或下载器状态无效，请返回匹配页面重新进入。")
        if st.button("返回视频匹配页面", type="primary"):
            st.switch_page("st_pages/Search_For_Videos.py")
        st.stop()
    if source_mode == MAIMAI_METADATA_MODE:
        st.success("当前数据源：Bilibili Metadata")
    else:
        st.info("当前数据源：Youtube（需手动搜索）")

# 读取存档的charts信息（数据库中的，无视频信息或有旧的匹配信息）
chart_list = db_handler.load_charts_of_archive_records(username, archive_name)
record_len = len(chart_list)
if not chart_list:
    st.warning("未找到任何谱面信息。请确认存档是否有效，存档至少需要包含一条谱面信息。")
    st.stop()

to_edit_chart_data = []
session_overrides = st.session_state.get('video_session_overrides', {})
for each in chart_list:
    c_data = deepcopy(each)
    session_override = session_overrides.get(each['chart_id'])
    existing_video = each.get('video_metadata')
    if session_override and is_video_matching_platform(session_override, downloader_type):
        c_data['video_info_match'] = deepcopy(session_override)
    elif existing_video and is_video_matching_platform(existing_video, downloader_type):
        # Metadata 记录应由当前 manifest 刷新；历史/手动记录仍优先。
        if not (
            G_type == 'maimai'
            and source_mode == MAIMAI_METADATA_MODE
            and existing_video.get('_origin') == 'metadata'
        ):
            c_data['video_info_match'] = deepcopy(existing_video)
    to_edit_chart_data.append(c_data)

# 从缓存中读取当前来源模式的结果信息（如果有）。
if G_type == 'maimai' and source_mode == MAIMAI_METADATA_MODE:
    search_result = st.session_state.get("video_source_results")
else:
    search_result = st.session_state.get("search_results")
if search_result:
    for chart in to_edit_chart_data:
        key = chart['chart_id']
        ret_data = search_result.get(key, None)
        if ret_data:  # 如果有，使用缓存的搜索结果
            candidates = [
                item for item in ret_data.get('video_info_list', [])
                if is_video_matching_platform(item, downloader_type)
            ]
            chart['video_info_list'] = candidates
            default_match = ret_data.get('video_info_match')
            if (
                not chart.get('video_info_match')
                and default_match
                and is_video_matching_platform(default_match, downloader_type)
            ):
                chart['video_info_match'] = deepcopy(default_match)
else:
    st.info("没有缓存的当前来源结果，请返回匹配页重新加载，或手动添加视频信息。")

# 未匹配记录优先，组内仍保留存档原始顺序。
to_edit_chart_data = prioritize_unmatched_charts(to_edit_chart_data, downloader_type)
match_summary = summarize_chart_video_matches(to_edit_chart_data, downloader_type)

base_record_ids = get_record_tags_from_data_dict(to_edit_chart_data)
record_ids = [
    (
        f"✅ 已匹配 · {record_tag}"
        if is_chart_video_matched(chart, downloader_type)
        else f"⚠️ 未匹配 · {record_tag}"
    )
    for chart, record_tag in zip(to_edit_chart_data, base_record_ids)
]

order_signature = tuple(chart['chart_id'] for chart in to_edit_chart_data)
if st.session_state.get('video_confirmation_order') != order_signature:
    st.session_state.video_confirmation_order = order_signature
    st.session_state.current_index = 0
    st.session_state.pop('record_selector', None)
st.session_state.current_index = min(
    max(st.session_state.get('current_index', 0), 0),
    len(to_edit_chart_data) - 1,
)


def render_download_controls(unmatched_count: int):
    with st.container(border=True):
        st.markdown("### 📥 下载视频")
        if unmatched_count:
            st.warning(
                f"还有 {unmatched_count} 个谱面未匹配。请先处理检查列表顶部的未匹配项，"
                "全部补齐后即可开始下载。"
            )
        else:
            st.success("全部谱面均已有当前来源的有效视频链接，可以直接开始下载。")

        force_redownload = st.checkbox(
            "覆盖已有视频缓存",
            value=False,
            help="启用后先下载到临时文件，下载成功才替换旧缓存；失败时保留旧文件。",
            key="force_redownload_confirm_videos",
        )
        download_info_placeholder = st.empty()
        st.session_state.setdefault('download_completed', False)
        if st.button(
            "全部已匹配，开始下载视频" if not unmatched_count else "补齐未匹配项后开始下载",
            disabled=not dl_instance or unmatched_count > 0,
            width="stretch",
            type="primary",
            key="start_confirmed_video_download",
        ):
            st.session_state.download_completed = False
            st.session_state.pop('video_download_summary', None)
            try:
                summary = st_download_video(
                    download_info_placeholder,
                    dl_instance,
                    G_config,
                    to_edit_chart_data,
                    force_redownload=force_redownload,
                )
                st.session_state.video_download_summary = summary
                st.session_state.download_completed = not summary['failed']
            except Exception as exc:
                st.session_state.download_completed = False
                st.error(f"下载过程中出现错误: {exc}, 请尝试重新下载")
                st.error(f"详细错误信息: {traceback.format_exc()}")

        failed_downloads = st.session_state.get(
            'video_download_summary', {}
        ).get('failed', [])
        if failed_downloads:
            failed_chart_ids = [item['chart_id'] for item in failed_downloads]
            st.error(f"仍有 {len(failed_chart_ids)} 个失败项，不能进入下一步。")
            if st.button("定位到第一个失败项", key="locate_first_failed_download"):
                for index, chart in enumerate(to_edit_chart_data):
                    if chart['chart_id'] == failed_chart_ids[0]:
                        st.session_state.current_index = index
                        break
                st.rerun()

        if st.button(
            "进行下一步",
            disabled=unmatched_count > 0 or not st.session_state.download_completed,
            key="continue_after_video_download",
        ):
            st.switch_page("st_pages/Edit_Video_Content.py")


with st.container(border=True):
    st.markdown("### ✅ 匹配检查概况")
    metric_columns = st.columns(3)
    metric_columns[0].metric("全部谱面", match_summary['total'])
    metric_columns[1].metric("已有有效匹配", match_summary['matched'])
    metric_columns[2].metric("仍未匹配", match_summary['unmatched'])
    if match_summary['unmatched'] == 0:
        if G_type == 'maimai' and source_mode == MAIMAI_METADATA_MODE:
            st.success(
                "所有谱面均已命中已审核 Metadata 或可用的历史/手动 Bilibili 记录。"
            )
            st.caption(
                f"已审核 Metadata：{match_summary['metadata']}；"
                f"历史/手动记录：{match_summary['history_or_manual']}。"
            )
        else:
            st.success("所有谱面均已有与当前来源模式兼容的视频链接。")
        st.markdown(
            "**如果这些匹配链接均正确，可以跳过逐条检查，直接从下方开始下载。**"
        )
    else:
        st.warning(
            f"有 {match_summary['unmatched']} 个谱面尚未匹配视频。"
            "它们已自动排列在检查列表最前，请逐条展开并按照指引搜索和填写视频链接。"
        )
        if G_type == 'maimai' and source_mode == MAIMAI_METADATA_MODE:
            st.caption(
                "默认模式请粘贴 Bilibili 链接，或输入BV号并指定分P"
            )

# 全部命中时把下载入口前置，用户无需浏览逐条检查区域。
if match_summary['unmatched'] == 0:
    render_download_controls(0)
    st.divider()

# 快速跳转组件的容器
selector_container = st.container(border=True)

# 片段预览和编辑组件，使用empty容器
link_editor_placeholder = st.empty()
update_editor(link_editor_placeholder, 
              to_edit_chart_data, 
              st.session_state.current_index, dl_instance)

with selector_container: 
    st.markdown("### 🔎 逐条检查与替换（可选）")
    if match_summary['unmatched']:
        st.caption("未匹配记录已排在最前；补齐一条后，下一条未匹配记录会继续置顶。")
    else:
        st.caption("所有记录已匹配。只有需要核对或替换时才需使用此区域。")
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

if match_summary['unmatched']:
    st.divider()
    render_download_controls(match_summary['unmatched'])



