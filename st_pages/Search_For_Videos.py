import os
import time
import shutil
import random
import traceback
import streamlit as st
from datetime import datetime
from utils.PageUtils import read_global_config, write_global_config, get_game_type_text
from utils.PathUtils import get_data_paths, get_user_versions
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader
from utils.WebAgentUtils import search_one_video
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
        if not no_credential:
            st.toast("正在尝试登录B站...如果弹出二维码窗口，请使用bilibili客户端扫描进行登录")
        dl_instance = BilibiliDownloader(
            proxy=proxy_address if use_proxy else None,
            no_credential=no_credential,
            credential_path="./cred_datas/bilibili_cred.pkl",
            search_max_results=search_max_results
        )
        bilibili_username = dl_instance.get_credential_username()
        if bilibili_username:
            st.toast(f"登录成功，当前登录账号为：{bilibili_username}")
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
                song_id = chart['song_id']
                i += 1
                progress_bar.progress(i / record_len, text=f"正在搜索({i}/{record_len}): {song_id}")
                # 如果有，从session state中读取缓存搜索结果
                if chart_id in st.session_state.search_results:
                    write_container.write(f"跳过({i}/{record_len}): {song_id} ，已储存有相关视频信息")
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

    st.markdown("### 🔍 开始搜索")
    
    with st.container(border=True):
        st.warning("""
        ⚠️ **提示**: 如果您遇到自动搜索失败，或大多数谱面的默认搜索结果完全不正确的情况，多半与第三方查询接口有关，可能需要更换网络环境，或等待一段时间后重试。
        
        若您不想等待，或反复遇到这样的情况，请考虑使用手动输入谱面视频的BV号的方法：点击下方按钮跳过自动搜索，进入下一个页面进行操作。
        """)
        if st.button("⏭️ 仅登录下载器，跳过自动搜索", use_container_width=True, type="secondary"):
            dl_instance = st_init_downloader()
            # 缓存downloader对象
            st.session_state.downloader = dl_instance
            st.switch_page("st_pages/Confirm_Videos.py")

    st.divider()
    col_search1, col_search2 = st.columns([3, 1])
    with col_search1:
        st.write("点击右侧按钮开始自动搜索谱面确认视频")
    with col_search2:
        if st.button("🚀 开始搜索", use_container_width=True, type="primary"):
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
        if st.button("➡️ 前往下一步", disabled=not search_completed, use_container_width=True, type="primary"):
            st.switch_page("st_pages/Confirm_Videos.py")
else:
    st.warning("⚠️ 请先保存配置！")  # 如果未保存配置，给出提示

