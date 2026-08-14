import os
import time
import shutil
import random
import traceback
import streamlit as st
from datetime import datetime
from utils.PageUtils import read_global_config, write_global_config, get_game_type_text
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader, streamlit_login_bilibili, load_credential
from utils.WebAgentUtils import search_one_video
from utils.video_metadata import (
    VideoMetadataError,
    get_video_manifest_status,
    resolve_maimai_video_sources,
)
from utils.video_source_mode import (
    BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES,
    MAIMAI_METADATA_MODE,
    MAIMAI_SOURCE_RESET_KEYS,
    MAIMAI_YOUTUBE_MODE,
    build_authenticated_bilibili_downloader,
    build_metadata_bilibili_downloader,
    classify_bilibili_login_result,
    register_bilibili_login_failure,
)
from db_utils.DatabaseDataHandler import get_database_handler

G_config = read_global_config()
_downloader = G_config.get('DOWNLOADER', 'bilibili')
_use_proxy = G_config.get('USE_PROXY', False)
_proxy_address = G_config.get('PROXY_ADDRESS', '127.0.0.1:7890')
_no_credential = G_config.get('NO_BILIBILI_CREDENTIAL', False)
_use_custom_po_token = G_config.get('USE_CUSTOM_PO_TOKEN', False)
_use_auto_po_token = G_config.get('USE_AUTO_PO_TOKEN', False)
_use_oauth = G_config.get('USE_OAUTH', False)
_customer_po_token = G_config.get('CUSTOMER_PO_TOKEN', '')

db_handler = get_database_handler()
G_type = st.session_state.get('game_type', 'maimai')


def _reset_maimai_source_state(mode):
    for key in MAIMAI_SOURCE_RESET_KEYS:
        st.session_state.pop(key, None)
    st.session_state.video_source_mode = mode
    st.session_state.video_sources_ready = False


def _clear_bilibili_qr_attempt():
    for key in (
        "metadata_bilibili_show_qr",
        "bilibili_login_session",
        "bilibili_qr_image",
    ):
        st.session_state.pop(key, None)


def _mark_youtube_result(ret_data):
    for video in ret_data.get("video_info_list", []) or []:
        video["_origin"] = "search"
        video["_platform"] = "youtube"
    match = ret_data.get("video_info_match")
    if match:
        match["_origin"] = "search"
        match["_platform"] = "youtube"
    return ret_data


def _render_maimai_archive_selector(username, archive_name):
    archives = db_handler.get_user_save_list(username, game_type="maimai")
    with st.expander("更换 B50 存档"):
        if not archives:
            st.warning("未找到任何存档。请先新建或加载存档。")
            st.stop()
        archive_names = [archive["archive_name"] for archive in archives]
        try:
            current_index = archive_names.index(archive_name)
        except (ValueError, TypeError):
            current_index = 0
        selected_archive_name = st.selectbox(
            "选择存档进行加载",
            archive_names,
            index=current_index,
            key="maimai_video_archive_selector",
        )
        if st.button("加载此存档（只需要点击一次！）", key="load_maimai_video_archive"):
            archive_id = db_handler.load_save_archive(username, selected_archive_name)
            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if not archive_id or not archive_data:
                st.error("加载存档数据失败。")
                return archive_name
            st.session_state.archive_id = archive_id
            st.session_state.archive_name = selected_archive_name
            st.session_state.video_source_archive_key = f"maimai:{username}:{selected_archive_name}"
            _reset_maimai_source_state(MAIMAI_METADATA_MODE)
            st.success(f"已加载存档 **{selected_archive_name}**")
            st.rerun()
    return archive_name


def _render_maimai_mode_switch(mode):
    if mode == MAIMAI_METADATA_MODE:
        st.success("当前来源：Bilibili Metadata（默认数据源，11+及以上谱面无需搜索）")
        if st.button("改用 YouTube 搜索", key="request_youtube_mode"):
            st.session_state.pending_video_source_mode = MAIMAI_YOUTUBE_MODE
    else:
        st.info("当前来源：YouTube 搜索（本次会话仅接受 YouTube 来源）")
        if st.button("恢复默认 Bilibili Metadata", key="request_metadata_mode"):
            st.session_state.pending_video_source_mode = MAIMAI_METADATA_MODE

    pending_mode = st.session_state.get("pending_video_source_mode")
    if pending_mode == MAIMAI_YOUTUBE_MODE:
        with st.container(border=True):
            st.warning(
                "切换后，本次流程将停用数据库 Metadata 和所有 Bilibili 来源，"
                "只能搜索、输入和下载 YouTube 视频。"
            )
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("确认切换到 YouTube", type="primary", use_container_width=True):
                    _reset_maimai_source_state(MAIMAI_YOUTUBE_MODE)
                    st.session_state.pop("pending_video_source_mode", None)
                    st.rerun()
            with cancel_col:
                if st.button("取消", key="cancel_youtube_mode", use_container_width=True):
                    st.session_state.pop("pending_video_source_mode", None)
                    st.rerun()
    elif pending_mode == MAIMAI_METADATA_MODE:
        with st.container(border=True):
            st.warning("返回默认模式将清除本次会话中的 YouTube 搜索结果。")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("确认恢复默认模式", type="primary", use_container_width=True):
                    _reset_maimai_source_state(MAIMAI_METADATA_MODE)
                    st.session_state.pop("pending_video_source_mode", None)
                    st.rerun()
            with cancel_col:
                if st.button("取消", key="cancel_metadata_mode", use_container_width=True):
                    st.session_state.pop("pending_video_source_mode", None)
                    st.rerun()


def _render_maimai_metadata_mode(username, archive_name):
    chart_list = db_handler.load_charts_of_archive_records(username, archive_name)
    if not chart_list:
        st.warning("未找到任何谱面信息。请确认存档至少包含一条谱面记录。")
        return

    st.markdown("### 📚 Metadata 匹配结果")
    try:
        status = get_video_manifest_status()
        st.caption(
            f"版本：{status['metadata_store_version']} · "
            f"生成时间：{status['generated_at']} · "
            f"可用条目：{status['usable_asset_count']}"
        )
    except VideoMetadataError as exc:
        st.error(f"无法加载视频 metadata：{exc}")
    results, counts = resolve_maimai_video_sources(chart_list)

    st.session_state.video_source_results = results
    metric_cols = st.columns(4)
    metric_cols[0].metric("数据库命中", counts["metadata"])
    metric_cols[1].metric("已缓存（Bilibili）", counts["history"])
    metric_cols[2].metric("非当前源缓存（YouTube）", counts["incompatible"])
    metric_cols[3].metric("未命中", counts["missing"])
    if counts["missing"] or counts["incompatible"]:
        st.warning(
            "⚠️ 存在未解决的谱面，可在下一页手动填写 Bilibili 链接补充，或切换到 YouTube 搜索模式。"
        )
    else:
        st.success(
            "✅ 所有谱面均匹配到有效来源，可以直接进入下一页下载！"
        )

    st.markdown("### 📥 下载设置")
    use_proxy = st.checkbox(
        "启用代理",
        value=G_config.get("USE_PROXY", False),
        key="metadata_bilibili_use_proxy",
    )
    proxy_address = st.text_input(
        "代理地址",
        value=G_config.get("PROXY_ADDRESS", "127.0.0.1:7890"),
        disabled=not use_proxy,
        key="metadata_bilibili_proxy",
    )
    high_res_key = "metadata_bilibili_high_res"
    high_res_fallback = st.session_state.get(
        "metadata_bilibili_high_res_fallback",
        False,
    )
    if high_res_key not in st.session_state:
        st.session_state[high_res_key] = G_config.get("DOWNLOAD_HIGH_RES", True)
    if high_res_fallback:
        st.session_state[high_res_key] = False
    download_high_res = st.checkbox(
        "下载高清视频（需要 Bilibili 二维码登录）",
        key=high_res_key,
        disabled=high_res_fallback,
        help="普通画质可匿名下载；高清流需要有效的 Bilibili 登录。",
    )

    authenticated_credential = st.session_state.get(
        "metadata_bilibili_authenticated_credential"
    )
    authenticated_username = st.session_state.get(
        "metadata_bilibili_authenticated_username"
    )
    if download_high_res:
        if not st.session_state.get("metadata_bilibili_cached_credential_checked"):
            st.session_state.metadata_bilibili_cached_credential_checked = True
            try:
                cached_credential, cached_username = load_credential(
                    "./cred_datas/bilibili_cred.pkl"
                )
                if cached_credential is not None:
                    st.session_state.metadata_bilibili_authenticated_credential = cached_credential
                    st.session_state.metadata_bilibili_authenticated_username = cached_username
                    authenticated_credential = cached_credential
                    authenticated_username = cached_username
            except Exception as exc:
                st.session_state.metadata_bilibili_cached_credential_error = str(exc)

        if authenticated_credential is not None:
            account_text = f"，账号：{authenticated_username}" if authenticated_username else ""
            st.success(f"✅ 登录凭证有效{account_text}")
            st.session_state.metadata_bilibili_login_failures = 0
            _clear_bilibili_qr_attempt()
        else:
            failures = st.session_state.get("metadata_bilibili_login_failures", 0)
            remaining = BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES - failures
            st.warning(
                "请使用哔哩哔哩客户端扫描二维码登录"
            )
            cached_error = st.session_state.get("metadata_bilibili_cached_credential_error")
            if cached_error:
                st.caption(f"未能复用本地登录凭证：{cached_error}")

            login_label = "生成登录二维码" if failures == 0 else "重新生成登录二维码"
            if st.button(
                login_label,
                key="metadata_bilibili_login_btn",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.metadata_bilibili_show_qr = True
                st.rerun()

            if st.session_state.get("metadata_bilibili_show_qr", False):
                success, credential, message, username = streamlit_login_bilibili(
                    "./cred_datas/bilibili_cred.pkl"
                )
                login_state = classify_bilibili_login_result(
                    success,
                    credential,
                    message,
                )
                if login_state == "success":
                    st.session_state.metadata_bilibili_authenticated_credential = credential
                    st.session_state.metadata_bilibili_authenticated_username = username
                    st.session_state.metadata_bilibili_login_failures = 0
                    _clear_bilibili_qr_attempt()
                    st.rerun()
                elif login_state == "pending":
                    time.sleep(2)
                    st.rerun()
                else:
                    failures, should_fallback = register_bilibili_login_failure(failures)
                    st.session_state.metadata_bilibili_login_failures = failures
                    _clear_bilibili_qr_attempt()
                    if should_fallback:
                        st.session_state.metadata_bilibili_high_res_fallback = True
                        st.warning(
                            "连续三次登录失败，已自动回退到普通画质。"
                        )
                        st.rerun()
                    st.error(
                        f"❌ {message}（第 {failures}/"
                        f"{BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES} 次失败）"
                    )
    else:
        _clear_bilibili_qr_attempt()
        if not high_res_fallback:
            st.session_state.metadata_bilibili_login_failures = 0
        else:
            st.warning("因连续三次登录失败切换为普通画质下载，如需再次尝试登录请重启应用。")

    high_res_ready = not download_high_res or authenticated_credential is not None
    if st.button(
        "继续下一步（使用当前匹配）",
        type="primary",
        use_container_width=True,
        disabled=not high_res_ready,
    ):
        G_config["USE_PROXY"] = use_proxy
        G_config["PROXY_ADDRESS"] = proxy_address
        G_config["DOWNLOAD_HIGH_RES"] = download_high_res
        write_global_config(G_config)
        try:
            downloader_kwargs = {
                "proxy": proxy_address if use_proxy else None,
                "credential_path": "./cred_datas/bilibili_cred.pkl",
                "search_max_results": G_config.get("SEARCH_MAX_RESULTS", 3),
            }
            if download_high_res:
                downloader_instance = build_authenticated_bilibili_downloader(
                    BilibiliDownloader,
                    authenticated_credential,
                    authenticated_username,
                    **downloader_kwargs,
                )
            else:
                downloader_instance, credential_exc = build_metadata_bilibili_downloader(
                    BilibiliDownloader,
                    **downloader_kwargs,
                )
                if credential_exc is not None:
                    st.warning(f"缓存凭证不可用，本次将匿名下载：{credential_exc}")
            st.session_state.downloader = downloader_instance
            st.session_state.downloader_type = "bilibili"
            st.session_state.video_sources_ready = True
            st.switch_page("st_pages/Confirm_Videos.py")
        except Exception as exc:
            st.error(f"初始化 Bilibili 下载器失败：{exc}")


def _build_youtube_downloader(settings):
    use_api = settings["use_youtube_api"]
    if use_api:
        return PurePytubefixDownloader(
            proxy=settings["proxy_address"] if settings["use_proxy"] else None,
            use_potoken=False,
            use_oauth=False,
            auto_get_potoken=False,
            search_max_results=settings["search_max_results"],
            use_api=True,
            api_key=settings["youtube_api_key"],
        )
    use_potoken = settings["use_custom_po_token"] or settings["use_auto_po_token"]
    return PurePytubefixDownloader(
        proxy=settings["proxy_address"] if settings["use_proxy"] else None,
        use_potoken=use_potoken,
        use_oauth=settings["use_oauth"] if not use_potoken else False,
        auto_get_potoken=settings["use_auto_po_token"],
        search_max_results=settings["search_max_results"],
        use_api=False,
        api_key=None,
    )


def _search_maimai_youtube(username, archive_name, downloader_instance, wait_range):
    chart_list = db_handler.load_charts_of_archive_records(username, archive_name)
    results = st.session_state.setdefault("search_results", {})
    progress = st.progress(0)
    output = st.container(border=True, height=400)
    for index, chart in enumerate(chart_list, start=1):
        chart_id = chart["chart_id"]
        progress.progress(
            index / len(chart_list),
            text=f"正在搜索 ({index}/{len(chart_list)}): {chart['song_name']}",
        )
        if chart_id in results and results[chart_id].get("video_info_list"):
            output.write(f"跳过：{chart['song_name']}，本次会话已有 YouTube 结果")
            continue
        ret_data, output_info = search_one_video(downloader_instance, chart)
        results[chart_id] = _mark_youtube_result(ret_data)
        output.write(f"【{index}/{len(chart_list)}】{output_info}")
        if index < len(chart_list) and wait_range[0] > 0 and wait_range[1] > wait_range[0]:
            time.sleep(random.randint(wait_range[0], wait_range[1]))


def _render_maimai_youtube_mode(username, archive_name):
    st.markdown("### ⚙️ YouTube 搜索设置")
    customer_token = G_config.get("CUSTOMER_PO_TOKEN") or {}
    use_proxy = st.checkbox("启用代理", value=G_config.get("USE_PROXY", False), key="yt_use_proxy")
    proxy_address = st.text_input(
        "代理地址",
        value=G_config.get("PROXY_ADDRESS", "127.0.0.1:7890"),
        disabled=not use_proxy,
        key="yt_proxy_address",
    )
    use_youtube_api = st.checkbox(
        "使用 YouTube Data API v3 搜索",
        value=G_config.get("USE_YOUTUBE_API", False),
        key="yt_use_api",
    )
    youtube_api_key = ""
    use_oauth = False
    use_custom_po_token = False
    use_auto_po_token = False
    po_token = ""
    visitor_data = ""
    if use_youtube_api:
        youtube_api_key = st.text_input(
            "YouTube API Key",
            value=G_config.get("YOUTUBE_API_KEY") or "",
            type="password",
            key="yt_api_key",
        )
        if not youtube_api_key:
            st.warning("请填写 YouTube API Key 后再保存配置。")
    else:
        use_oauth = st.checkbox(
            "使用 OAuth 登录",
            value=G_config.get("USE_OAUTH", False),
            key="yt_use_oauth",
        )
        po_mode = st.radio(
            "PO Token 设置",
            ["不使用", "使用自定义 PO Token", "自动获取 PO Token"],
            index=(
                1
                if G_config.get("USE_CUSTOM_PO_TOKEN", False)
                else 2 if G_config.get("USE_AUTO_PO_TOKEN", False) else 0
            ),
            disabled=use_oauth,
            key="yt_po_mode",
        )
        use_custom_po_token = po_mode == "使用自定义 PO Token"
        use_auto_po_token = po_mode == "自动获取 PO Token"
        if use_custom_po_token:
            po_token = st.text_input(
                "自定义 PO Token",
                value=customer_token.get("po_token", ""),
                type="password",
                key="yt_po_token",
            )
            visitor_data = st.text_input(
                "Visitor Data",
                value=customer_token.get("visitor_data", ""),
                type="password",
                key="yt_visitor_data",
            )

    search_max_results = st.number_input(
        "备选搜索结果数量",
        min_value=1,
        max_value=10,
        value=int(G_config.get("SEARCH_MAX_RESULTS", 3)),
        key="yt_search_max_results",
    )
    configured_wait = tuple(G_config.get("SEARCH_WAIT_TIME", (1, 3)))
    search_wait_time = st.select_slider(
        "搜索间隔时间（秒）",
        options=range(1, 60),
        value=configured_wait,
        key="yt_search_wait_time",
    )
    download_high_res = st.checkbox(
        "下载高分辨率视频",
        value=G_config.get("DOWNLOAD_HIGH_RES", True),
        key="yt_download_high_res",
    )
    settings = {
        "use_proxy": use_proxy,
        "proxy_address": proxy_address,
        "use_youtube_api": use_youtube_api,
        "youtube_api_key": youtube_api_key,
        "use_oauth": use_oauth,
        "use_custom_po_token": use_custom_po_token,
        "use_auto_po_token": use_auto_po_token,
        "search_max_results": int(search_max_results),
    }

    save_disabled = use_youtube_api and not youtube_api_key
    if st.button("保存 YouTube 配置", type="primary", disabled=save_disabled):
        G_config["USE_PROXY"] = use_proxy
        G_config["PROXY_ADDRESS"] = proxy_address
        G_config["USE_YOUTUBE_API"] = use_youtube_api
        G_config["YOUTUBE_API_KEY"] = youtube_api_key
        G_config["USE_OAUTH"] = use_oauth
        G_config["USE_CUSTOM_PO_TOKEN"] = use_custom_po_token
        G_config["USE_AUTO_PO_TOKEN"] = use_auto_po_token
        G_config["CUSTOMER_PO_TOKEN"] = {"po_token": po_token, "visitor_data": visitor_data}
        G_config["SEARCH_MAX_RESULTS"] = int(search_max_results)
        G_config["SEARCH_WAIT_TIME"] = tuple(search_wait_time)
        G_config["DOWNLOAD_HIGH_RES"] = download_high_res
        write_global_config(G_config)
        st.session_state.youtube_mode_settings = settings
        st.session_state.config_saved_step2 = True
        st.success("YouTube 配置已保存。")

    if st.session_state.get("config_saved_step2"):
        if st.button("开始 YouTube 搜索", type="primary", use_container_width=True):
            try:
                active_settings = st.session_state.get("youtube_mode_settings", settings)
                downloader_instance = _build_youtube_downloader(active_settings)
                st.session_state.downloader = downloader_instance
                st.session_state.downloader_type = "youtube"
                _search_maimai_youtube(
                    username,
                    archive_name,
                    downloader_instance,
                    tuple(search_wait_time),
                )
                st.session_state.search_completed = True
                st.success("YouTube 搜索完成，请进入下一步确认结果。")
            except Exception as exc:
                st.session_state.search_completed = False
                st.error(f"YouTube 搜索失败：{exc}")
                with st.expander("错误详情"):
                    st.code(traceback.format_exc())
    if st.session_state.get("search_completed"):
        if st.button("进入视频确认和下载", type="primary", use_container_width=True):
            st.switch_page("st_pages/Confirm_Videos.py")


def _render_maimai_video_source_page():
    st.header("🎬 匹配谱面确认视频")
    st.markdown(f"> 您正在使用 **{get_game_type_text('maimai')}** 视频生成模式。")
    username = st.session_state.get("username")
    archive_name = st.session_state.get("archive_name")
    if not username or not archive_name:
        st.warning("请先在存档管理页面指定用户名并加载存档。")
        return
    st.write(f"当前用户名：**{username}**")
    _render_maimai_archive_selector(username, archive_name)

    archive_key = f"maimai:{username}:{st.session_state.get('archive_name')}"
    if st.session_state.get("video_source_archive_key") != archive_key:
        st.session_state.video_source_archive_key = archive_key
        _reset_maimai_source_state(MAIMAI_METADATA_MODE)
    mode = st.session_state.get("video_source_mode", MAIMAI_METADATA_MODE)
    st.markdown("### 🎚️ 视频来源模式")
    _render_maimai_mode_switch(mode)
    if st.session_state.get("pending_video_source_mode"):
        return
    if mode == MAIMAI_YOUTUBE_MODE:
        _render_maimai_youtube_mode(username, st.session_state.get("archive_name"))
    else:
        _render_maimai_metadata_mode(username, st.session_state.get("archive_name"))


if G_type == "maimai":
    _render_maimai_video_source_page()
    st.stop()

# =============================================================================
# Page layout starts here
# ==============================================================================

st.header("🔍 谱面确认视频搜索和抓取")
st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

### Savefile Management - Start ###
username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)
current_paths = None
data_loaded = False

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
### Savefile Management - End ###

st.markdown("### ⚙️ 视频抓取设置")

# 选择下载器
default_index = ["bilibili", "youtube"].index(_downloader)
downloader = st.selectbox(
    "选择下载器",
    ["bilibili", "youtube"],
    index=default_index,
    help="选择视频来源平台：Bilibili（推荐）或 YouTube"
)
# 选择是否启用代理
use_proxy = st.checkbox("启用代理", value=_use_proxy, help="如果无法直接访问视频平台，请启用代理")
# 输入代理地址，默认值为127.0.0.1:7890
proxy_address = st.text_input(
    "代理地址",
    value=_proxy_address,
    disabled=not use_proxy,
    help="代理服务器地址，格式：IP:端口（如：127.0.0.1:7890）",
    placeholder="127.0.0.1:7890"
)

# 初始化下载器变量
no_credential = _no_credential
use_oauth = _use_oauth
use_custom_po_token = _use_custom_po_token
use_auto_po_token = _use_auto_po_token
po_token = _customer_po_token.get('po_token', '')
visitor_data = _customer_po_token.get('visitor_data', '')

extra_setting_container = st.container(border=True)
with extra_setting_container:
    st.markdown("#### 🔐 下载器认证设置")
    # 初始化变量
    use_youtube_api = False
    youtube_api_key = ''
    use_oauth = False
    use_custom_po_token = False
    use_auto_po_token = False
    po_token = ''
    visitor_data = ''
    
    if downloader == "bilibili":
        no_credential = st.checkbox(
            "不使用B站账号登录",
            value=_no_credential,
            help="不登录可能导致无法下载高分辨率视频或受到风控"
        )

        # 登录状态管理
        if 'bilibili_logged_in' not in st.session_state or 'bilibili_username' not in st.session_state:
            # 检查是否有缓存的凭证
            cached_cred, cached_username = load_credential("./cred_datas/bilibili_cred.pkl")
            if cached_cred:
                st.session_state.bilibili_logged_in = True
                st.session_state.bilibili_username = cached_username
            else:
                st.session_state.bilibili_logged_in = False
                st.session_state.bilibili_username = None
        
        if not no_credential:
            st.markdown("---")
            if st.session_state.bilibili_logged_in and st.session_state.bilibili_username:
                st.success(f"✅ 已成功登录 Bilibili ，账号: {st.session_state.bilibili_username}")
                if st.button("退出登录", key="bilibili_logout"):
                    # 删除凭证文件
                    cred_path = "./cred_datas/bilibili_cred.pkl"
                    if os.path.exists(cred_path):
                        os.remove(cred_path)
                    st.session_state.bilibili_logged_in = False
                    st.session_state.bilibili_username = None
                    st.rerun()
            else:
                st.warning("⚠️ 尚未登录 Bilibili 账号")
                if st.button("🔐 登录 Bilibili", key="bilibili_login_btn", type="primary", use_container_width=True):
                    st.session_state.bilibili_show_qr = True
                    st.rerun()
                
                # 显示二维码登录流程
                if st.session_state.get('bilibili_show_qr', False):
                    success, credential, message, username = streamlit_login_bilibili("./cred_datas/bilibili_cred.pkl")
                    
                    if success:
                        st.session_state.bilibili_logged_in = True
                        st.session_state.bilibili_show_qr = False
                        st.session_state.bilibili_username = username
                        st.rerun()
                    elif credential is None and ("等待" in message or "扫描" in message or "确认" in message):
                        # 需要继续轮询
                        time.sleep(2)
                        st.rerun()
                    else:
                        # 出错或超时
                        if "过期" in message or "失败" in message:
                            st.session_state.bilibili_show_qr = False
                            st.error(f"❌ {message}")
                            st.info("请重新点击登录按钮")
    elif downloader == "youtube":
        _use_youtube_api = G_config.get('USE_YOUTUBE_API', False)
        _youtube_api_key = G_config.get('YOUTUBE_API_KEY', '')
        
        use_youtube_api = st.checkbox(
            "使用 YouTube Data API v3 搜索",
            value=_use_youtube_api,
            help="使用官方 API 进行搜索，更稳定可靠。需要配置 API Key。"
        )
        
        if use_youtube_api:
            youtube_api_key = st.text_input(
                "YouTube API Key",
                value=_youtube_api_key,
                type="password",
                help="在 Google Cloud Console 创建 API Key。参考: https://developers.google.com/youtube/v3/getting-started"
            )
            if not youtube_api_key:
                st.warning("⚠️ 请配置 YouTube API Key 以使用 API 搜索功能")
        else:
            youtube_api_key = ''
            use_oauth = st.checkbox(
                "使用OAuth登录",
                value=_use_oauth,
                help="使用OAuth认证可以避免被识别为机器人"
            )
            po_token_mode = st.radio(
                "PO Token 设置",
                options=["不使用", "使用自定义PO Token", "自动获取PO Token"],
                index=0 if not (_use_custom_po_token or _use_auto_po_token) 
                      else 1 if _use_custom_po_token 
                      else 2,
                disabled=use_oauth,
                help="PO Token用于避免YouTube的风控检测"
            )
            use_custom_po_token = (po_token_mode == "使用自定义PO Token")
            use_auto_po_token = (po_token_mode == "自动获取PO Token")
            if use_custom_po_token:
                _po_token = _customer_po_token.get('po_token', '')
                _visitor_data = _customer_po_token.get('visitor_data', '')
                po_token = st.text_input("自定义 PO Token", value=_po_token, type="password")
                visitor_data = st.text_input("自定义 Visitor Data", value=_visitor_data, type="password")
            else:
                use_oauth = False
                use_custom_po_token = False
                use_auto_po_token = False
                po_token = ''
                visitor_data = ''

search_setting_container = st.container(border=True)
with search_setting_container:
    st.markdown("#### 🔍 搜索设置")
    _search_max_results = G_config.get('SEARCH_MAX_RESULTS', 3)
    _search_wait_time = G_config.get('SEARCH_WAIT_TIME', [5, 10])
    search_max_results = st.number_input(
        "备选搜索结果数量",
        value=_search_max_results,
        min_value=1,
        max_value=10,
        help="每个谱面搜索到的备选视频数量"
    )
    search_wait_time = st.select_slider(
        "搜索间隔时间（秒）",
        options=range(1, 60),
        value=_search_wait_time,
        help="每次搜索之间的等待时间，避免被识别为机器人"
    )

download_setting_container = st.container(border=True)
with download_setting_container:
    st.markdown("#### 📥 下载设置")
    _download_high_res = G_config.get('DOWNLOAD_HIGH_RES', True)
    download_high_res = st.checkbox(
        "下载高分辨率视频",
        value=_download_high_res,
        help="开启后将尽可能下载1080p视频，否则最高下载480p"
    )


col_save1, col_save2 = st.columns([3, 1])
with col_save1:
    st.caption("💡 请先保存配置，然后再开始搜索")
with col_save2:
    if st.button("💾 保存配置", use_container_width=True, type="primary"):
        G_config['DOWNLOADER'] = downloader
        G_config['USE_PROXY'] = use_proxy
        G_config['PROXY_ADDRESS'] = proxy_address
        G_config['NO_BILIBILI_CREDENTIAL'] = no_credential
        if downloader == "youtube":
            G_config['USE_YOUTUBE_API'] = use_youtube_api
            G_config['YOUTUBE_API_KEY'] = youtube_api_key
            if not use_youtube_api:
                G_config['USE_OAUTH'] = use_oauth
                if not use_oauth:
                    G_config['USE_CUSTOM_PO_TOKEN'] = use_custom_po_token
                    G_config['USE_AUTO_PO_TOKEN'] = use_auto_po_token
                    G_config['CUSTOMER_PO_TOKEN'] = {
                        'po_token': po_token,
                        'visitor_data': visitor_data
                    }
        G_config['SEARCH_MAX_RESULTS'] = search_max_results
        G_config['SEARCH_WAIT_TIME'] = search_wait_time
        G_config['DOWNLOAD_HIGH_RES'] = download_high_res
        write_global_config(G_config)
        st.success("✅ 配置已保存！")
        st.session_state.config_saved_step2 = True  # 添加状态标记
        st.session_state.downloader_type = downloader
        st.rerun()

def st_init_downloader():
    """初始化下载器实例（不处理登录逻辑）"""
    global downloader, no_credential, use_oauth, use_custom_po_token, use_auto_po_token, po_token, visitor_data, use_youtube_api, youtube_api_key

    if downloader == "youtube":
        st.toast("正在初始化YouTube下载器...")
        if use_youtube_api:
            st.toast("使用 YouTube Data API v3 进行搜索...")
            dl_instance = PurePytubefixDownloader(
                proxy=proxy_address if use_proxy else None,
                use_potoken=False,
                use_oauth=False,
                auto_get_potoken=False,
                search_max_results=search_max_results,
                use_api=True,
                api_key=youtube_api_key
            )
        else:
            use_potoken = use_custom_po_token or use_auto_po_token
            if use_oauth and not use_potoken:
                st.toast("使用OAuth登录...请点击控制台窗口输出的链接进行登录")
            dl_instance = PurePytubefixDownloader(
                proxy=proxy_address if use_proxy else None,
                use_potoken=use_potoken,
                use_oauth=use_oauth,
                auto_get_potoken=use_auto_po_token,
                search_max_results=search_max_results,
                use_api=False,
                api_key=None
            )

    elif downloader == "bilibili":
        st.toast("正在初始化Bilibili下载器...")
        dl_instance = BilibiliDownloader(
            proxy=proxy_address if use_proxy else None,
            no_credential=no_credential,
            credential_path="./cred_datas/bilibili_cred.pkl",
            search_max_results=search_max_results,
            skip_login=True  # 登录已在上层处理
        )
        
        bilibili_username = dl_instance.get_credential_username()
        if bilibili_username:
            st.toast(f"登录账号：{bilibili_username}")
    else:
        st.error(f"未配置正确的下载器，请重新确定上方配置！")
        return None
    
    return dl_instance

def st_search_b50_videoes(dl_instance, placeholder, search_wait_time):
    # read b50_data
    chart_list = db_handler.load_charts_of_archive_records(username, archive_name)
    record_len = len(chart_list)

    with placeholder.container(border=True, height=560):
        with st.spinner("正在搜索b50视频信息..."):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            for chart in chart_list:
                chart_id = chart['chart_id']
                song_name = chart['song_name']
                i += 1
                progress_bar.progress(i / record_len, text=f"正在搜索({i}/{record_len}): {song_name}")
                # 如果有，从session state中读取缓存搜索结果
                if chart_id in st.session_state.search_results and len(st.session_state.search_results[chart_id]) > 0:
                    write_container.write(f"跳过({i}/{record_len}): {song_name} ，已储存有相关视频信息")
                    continue
                
                ret_data, ouput_info = search_one_video(dl_instance, chart)
                write_container.write(f"【{i}/{record_len}】{ouput_info}")

                # 搜索结果缓存在session state中）
                st.session_state.search_results[chart_id] = ret_data
                
                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0]:
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

# 仅在配置已保存时显示搜索控件
if st.session_state.get('config_saved_step2', False):
    info_placeholder = st.empty()

    if 'search_results' not in st.session_state:
        st.session_state.search_results = {}
    
    # 初始化搜索完成状态
    if 'search_completed' not in st.session_state:
        st.session_state.search_completed = False
    
    # 检查是否可以开始搜索（Bilibili 需要登录，或选择不使用账号）
    can_search = True
    if downloader == "bilibili" and not no_credential:
        if not st.session_state.get('bilibili_logged_in', False):
            can_search = False

    st.markdown("### 🔍 启动自动搜索")
    
    # 显示登录提示（如果需要）
    if not can_search:
        st.warning("⚠️ 需要先登录才能搜索，请在上方配置区域登录 Bilibili 账号，或勾选「不使用B站账号登录」")
    
    col_search1, col_search2 = st.columns([1, 2])
    with col_search1:
        with st.container(border=True):
            st.info("点击下方按钮开始自动搜索，搜索过程中请勿关闭或刷新页面。")
            if st.button("🚀 开始搜索", use_container_width=True, type="primary", disabled=not can_search):
                try:
                    dl_instance = st_init_downloader()
                    # 缓存downloader对象
                    st.session_state.downloader = dl_instance
                    st_search_b50_videoes(dl_instance, info_placeholder, search_wait_time)
                    st.session_state.search_completed = True  # Reset error flag if successful
                    st.success("✅ 搜索完成！请点击下一步按钮检查搜索到的视频信息，以及下载视频。")
                    # print(st.session_state.search_results)  # debug：打印搜索结果
                except Exception as e:
                    st.session_state.search_completed = False
                    error_msg = str(e)
                    if "400" in error_msg or "Bad Request" in error_msg:
                        st.error(f"❌ 搜索过程中出现错误: HTTP Error 400: Bad Request,请尝试重新搜索")
                        st.warning("""
                        **可能的解决方案：**
                        1. **更新 pytubefix 库**：在终端运行 `pip install --upgrade pytubefix`
                        2. **配置认证**：在搜索配置中启用 OAuth 或 PO Token 认证
                        3. **使用代理**：如果网络受限，尝试配置代理服务器
                        4. **手动输入**：点击"跳过自动搜索"按钮，手动输入视频ID
                        5. **检查网络**：确保可以正常访问 YouTube
                        """)
                    else:
                        st.error(f"❌ 搜索过程中出现错误: {error_msg}, 请尝试重新搜索")
                    with st.expander("详细错误信息"):
                        st.code(traceback.format_exc())
    with col_search2:
        with st.container(border=True):
            st.warning("""
            ⚠️ **提示**: 自动搜索并非100%准确率，如果遇到失败，或多数谱面的默认搜索结果完全不正确的情况，请尝试更换网络环境，或等待一段时间后重试。
            
            - 若您不想等待，或反复出现失败，请考虑点击下方按钮跳过自动搜索，在下一个页面，您可以通过输入视频BV号手动搜索。
            """)
            
            skip_btn_disabled = not can_search
            if st.button("⏭️ 仅登录下载器，跳过自动搜索", use_container_width=True, type="secondary", disabled=skip_btn_disabled):
                dl_instance = st_init_downloader()
                # 缓存downloader对象
                st.session_state.downloader = dl_instance
                st.switch_page("st_pages/Confirm_Videos.py")
    
    st.divider()
    st.markdown("### ➡️ 下一步")
    col_next1, col_next2 = st.columns([3, 1])
    with col_next1:
        if st.session_state.get('search_completed', False):
            st.success("✅ 搜索已完成，可以进入下一步")
        else:
            st.info("ℹ️ 请先完成搜索或跳过搜索")
    with col_next2:
        search_completed = st.session_state.get('search_completed', False)
        next_btn_disabled = not (search_completed and can_search)
        if st.button("➡️ 前往下一步", disabled=next_btn_disabled, use_container_width=True, type="primary"):
            st.switch_page("st_pages/Confirm_Videos.py")
else:
    st.warning("⚠️ 请先保存配置！")  # 如果未保存配置，给出提示

