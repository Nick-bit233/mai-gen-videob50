import os
import json
import time
import random
import traceback
import streamlit as st
from utils.PageUtils import load_config, save_config, read_global_config, write_global_config
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader
from pre_gen import search_one_video

G_config = read_global_config()
username = G_config.get('USER_ID', '')
_downloader = G_config.get('DOWNLOADER', 'bilibili')
_use_proxy = G_config.get('USE_PROXY', False)
_proxy_address = G_config.get('PROXY_ADDRESS', '127.0.0.1:7890')
_no_credential = G_config.get('NO_BILIBILI_CREDENTIAL', False)
_use_custom_po_token = G_config.get('USE_CUSTOM_PO_TOKEN', False)
_use_auto_po_token = G_config.get('USE_AUTO_PO_TOKEN', False)
_use_oauth = G_config.get('USE_OAUTH', False)
_customer_po_token = G_config.get('CUSTOMER_PO_TOKEN', '')


st.header("Step 2: 搜索视频和下载")

st.write("请先确认视频抓取设置")

# 选择下载器
default_index = ["bilibili", "youtube"].index(_downloader)
downloader = st.selectbox("选择下载器", ["bilibili", "youtube"], index=default_index)
# 选择是否启用代理
use_proxy = st.checkbox("启用代理", value=_use_proxy)
# 输入代理地址，默认值为127.0.0.1:7890
proxy_address = st.text_input("输入代理地址", value=_proxy_address, disabled=not use_proxy)

# 初始化下载器变量
no_credential = _no_credential
use_oauth = _use_oauth
use_custom_po_token = _use_custom_po_token
use_auto_po_token = _use_auto_po_token
po_token = _customer_po_token.get('po_token', '')
visitor_data = _customer_po_token.get('visitor_data', '')

extra_setting_container = st.container(border=True)
with extra_setting_container:
    st.write("下载器设置")
    if downloader == "bilibili":
        no_credential = st.checkbox("不使用B站账号登录", value=_no_credential)
    elif downloader == "youtube":
        use_oauth = st.checkbox("使用OAuth登录", value=_use_oauth)
        po_token_mode = st.radio(
            "PO Token 设置",
            options=["不使用", "使用自定义PO Token", "自动获取PO Token"],
            index=0 if not (_use_custom_po_token or _use_auto_po_token) 
                  else 1 if _use_custom_po_token 
                  else 2,
            disabled=use_oauth
        )
        use_custom_po_token = (po_token_mode == "使用自定义PO Token")
        use_auto_po_token = (po_token_mode == "自动获取PO Token")
        if use_custom_po_token:
            _po_token = _customer_po_token.get('po_token', '')
            _visitor_data = _customer_po_token.get('visitor_data', '')
            po_token = st.text_input("输入自定义 PO Token", value=_po_token)
            visitor_data = st.text_input("输入自定义 Visitor Data", value=_visitor_data)

search_setting_container = st.container(border=True)
with search_setting_container:
    st.write("搜索设置")
    _search_max_results = G_config.get('SEARCH_MAX_RESULTS', 3)
    _search_wait_time = G_config.get('SEARCH_WAIT_TIME', [5, 10])
    search_max_results = st.number_input("备选搜索结果数量", value=_search_max_results, min_value=1, max_value=10)
    search_wait_time = st.select_slider("搜索间隔时间（随机范围）", options=range(1, 60), value=_search_wait_time)

download_setting_container = st.container(border=True)
with download_setting_container:
    st.write("下载设置")
    _download_high_res = G_config.get('DOWNLOAD_HIGH_RES', True)
    download_high_res = st.checkbox("下载高分辨率视频", value=_download_high_res)


if st.button("保存配置"):
    G_config['DOWNLOADER'] = downloader
    G_config['USE_PROXY'] = use_proxy
    G_config['PROXY_ADDRESS'] = proxy_address
    G_config['NO_BILIBILI_CREDENTIAL'] = no_credential
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
    st.success("配置已保存！")
    st.session_state.config_saved_step2 = True  # 添加状态标记

def st_init_downloader():
    global downloader, no_credential, use_oauth, use_custom_po_token, use_auto_po_token, po_token, visitor_data

    if downloader == "youtube":
        st.toast("正在初始化YouTube下载器...")
        use_potoken = use_custom_po_token or use_auto_po_token
        if use_oauth and not use_potoken:
            st.toast("使用OAuth登录...请点击控制台窗口输出的链接进行登录")
        dl_instance = PurePytubefixDownloader(
            proxy=proxy_address if use_proxy else None,
            use_potoken=use_potoken,
            use_oauth=use_oauth,
            auto_get_potoken=use_auto_po_token,
            search_max_results=search_max_results
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

# b50 config文件位置
b50_data_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{username}.json")

def st_search_b50_videoes(dl_instance, placeholder, search_wait_time):
    # read b50_data
    b50_data = load_config(b50_data_file)

    with placeholder.container(border=True, height=600):
        with st.spinner("正在搜索b50视频信息..."):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            for song in b50_data:
                i += 1
                progress_bar.progress(i / 50, text=f"正在搜索({i}/50): {song['title']}")
                if 'video_info_match' in song and song['video_info_match']:
                    write_container.write(f"跳过({i}/50): {song['title']} ，已储存有相关视频信息")
                    continue
                
                song_data, ouput_info = search_one_video(dl_instance, song)
                write_container.write(f"【{i}/50】{ouput_info}")

                # 每次搜索后都写入b50_data_file
                with open(b50_data_file, "w", encoding="utf-8") as f:
                    json.dump(b50_data, f, ensure_ascii=False, indent=4)
                
                # 等待几秒，以减少被检测为bot的风险
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0]:
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved_step2', False):
    info_placeholder = st.empty()

    button_label = "开始搜索"
    st.session_state.search_completed = False
    
    if st.button(button_label):
        try:
            dl_instance = st_init_downloader()
            # 缓存downloader对象
            st.session_state.downloader = dl_instance
            st_search_b50_videoes(dl_instance, info_placeholder, search_wait_time)
            st.session_state.search_completed = True  # Reset error flag if successful
            st.success("搜索完成！请点击下一步按钮检查搜索到的视频信息，以及下载视频。")
        except Exception as e:
            st.session_state.search_completed = False
            st.error(f"搜索过程中出现错误: {e}, 请尝试重新搜索")
            st.error(f"详细错误信息: {traceback.format_exc()}")
    if st.button("进行下一步", disabled=not st.session_state.search_completed):
        st.switch_page("st_pages/3_Confrim_Videoes.py")
else:
    st.warning("请先保存配置！")  # 如果未保存配置，给出提示

