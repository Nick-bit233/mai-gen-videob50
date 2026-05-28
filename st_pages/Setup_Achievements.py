import streamlit as st
import os
import re
import json
import traceback
from datetime import datetime
from utils.user_gamedata_handlers import fetch_user_gamedata, unify_user_gamedata
from utils.PageUtils import process_username, get_game_type_text
from db_utils.DatabaseDataHandler import get_database_handler
from utils.PathUtils import get_user_base_dir

# Get a handler for database operations
db_handler = get_database_handler()
level_label_lists = {
    "maimai": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"],
    "chunithm": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
}

def view_b50_data(username: str, archive_name: str):
    # TODO：完全重构此预览部分，使用更好的视觉和统一的数据源
    """Displays the records of a selected archive in a read-only table."""
    result = db_handler.load_archive_as_old_b50_config(username, archive_name)
    
    if not result:
        st.error("无法加载存档数据。")
        return
    
    # 解包结果
    if isinstance(result, tuple) and len(result) == 2:
        game_type, b50_data = result
    else:
        st.error(f"数据格式错误: {type(result)}")
        with st.expander("调试信息"):
            st.write(f"Result type: {type(result)}")
            st.write(f"Result: {result}")
        return
    
    # 根据游戏类型设置对话框标题和数据名称
    dialog_title = "分表数据查看"
    rating_label = "Rating"
    
    # 使用动态标题创建对话框（Streamlit不支持动态标题，所以我们需要在内容中显示）
    st.markdown(f"### {dialog_title}")
    
    st.markdown(f"""
        - **用户名**: {username}
        - **存档名**: {archive_name}
        """, unsafe_allow_html=True)

    # 处理不同游戏类型的数据格式
    if game_type == "maimai":
        rating = b50_data.get('rating_mai', 0)
        if not rating:
            rating = 0
        st.markdown(f"""**{rating_label}**: {rating}""", unsafe_allow_html=True)
        show_records = b50_data.get('records', [])
    elif game_type == "chunithm":
        # Chunithm数据直接是列表格式（来自load_archive_for_image_generation）
        if isinstance(b50_data, list):
            show_records = b50_data
            # 从archive获取rating
            archive_id = db_handler.load_save_archive(username, archive_name)
            if archive_id:
                archive = db_handler.db.get_archive(archive_id)
                rating = archive.get('rating_chu', 0.0)
                if not rating:
                    rating = 0.0
                st.markdown(f"""**{rating_label}**: {rating:.2f}""", unsafe_allow_html=True)
        else:
            # 兼容旧格式
            show_records = b50_data.get('records', []) if isinstance(b50_data, dict) else []
            rating = b50_data.get('rating_chu', 0.0) if isinstance(b50_data, dict) else 0.0
            if not rating:
                rating = 0.0
            st.markdown(f"""**{rating_label}**: {rating:.2f}""", unsafe_allow_html=True)
    else:
        show_records = []

    if not show_records:
        st.warning("存档中没有记录数据。")
        # 添加调试信息
        with st.expander("调试信息"):
            st.write(f"Game type: {game_type}")
            st.write(f"B50 data type: {type(b50_data)}")
            st.write(f"B50 data: {b50_data}")
            # 检查数据库中是否有记录
            archive_id = db_handler.load_save_archive(username, archive_name)
            if archive_id:
                records = db_handler.db.get_records_with_extented_data(archive_id)
                st.write(f"数据库中的记录数: {len(records)}")
                if records:
                    st.write("第一条记录示例:")
                    st.json(records[0])
        return

    st.info(f"本窗口为只读模式。如需修改，请前往\"编辑/创建自定义分表存档\"页面。")

    # 处理level_label
    for record in show_records:
        level_index = record.get('level_index', 0)
        if 'level_label' not in record:
            level_label_list = level_label_lists.get(game_type, [])
            if level_index < len(level_label_list):
                record['level_label'] = level_label_list[level_index]
            else:
                record['level_label'] = "UNKNOWN"
        
        # 对于chunithm，确保字段名正确
        if game_type == "chunithm":
            # 确保ds字段存在（可能是ds_cur）
            if 'ds' not in record and 'ds_cur' in record:
                record['ds'] = record['ds_cur']
            # 确保score字段存在（可能是achievement）
            if 'score' not in record:
                if 'achievement' in record:
                    record['score'] = int(record['achievement'])
                else:
                    record['score'] = 0
            # 确保ra字段存在（可能是chuni_rating）
            if 'ra' not in record and 'chuni_rating' in record:
                record['ra'] = record['chuni_rating']
            # 处理combo_type和chain_type（可能是fc_status和fs_status）
            if 'combo_type' not in record and 'fc_status' in record:
                record['combo_type'] = record['fc_status']
            if 'chain_type' not in record and 'fs_status' in record:
                record['chain_type'] = record['fs_status']
            # 处理clip_name
            if 'clip_name' not in record and 'clip_title_name' in record:
                record['clip_name'] = record['clip_title_name']

    if game_type == "maimai":
        st.dataframe(
            show_records,
            column_order=["clip_name",  "title", "type", "level_label",
                        "ds", "achievements", "fc", "fs", "ra", "dx_score", "play_count"],
            column_config={
                "clip_name": "抬头标题",
                "title": "曲名",
                "type": st.column_config.TextColumn("类型", width=40),
                "level_label": st.column_config.TextColumn("难度", width=60),
                "ds": st.column_config.NumberColumn("定数", format="%.1f", width=60),
                "achievements": st.column_config.NumberColumn("达成率", format="%.4f"),
                "fc": st.column_config.TextColumn("FC", width=40),
                "fs": st.column_config.TextColumn("FS", width=40),
                "ra": st.column_config.NumberColumn("单曲Ra", format="%d", width=75),
                "dx_score": st.column_config.NumberColumn("DX分数", format="%d", width=75),
                "play_count": st.column_config.NumberColumn("游玩次数", format="%d")
            }
        )
    elif game_type == "chunithm":
        # 使用math.floor截断ra到两位小数，格式化rank
        import math
        for record in show_records:
            if 'ra' in record and isinstance(record['ra'], (int, float)):
                record['ra'] = math.floor(record['ra'] * 100) / 100.0
            # 确保play_count字段存在（可能是playCount）
            if 'play_count' not in record and 'playCount' in record:
                record['play_count'] = record['playCount']
        
        st.dataframe(
            show_records,
            column_order=["clip_name",  "title", "artist", "level_label",
                          "ds", "score", "combo_type", "chain_type", "ra", "play_count"],
            column_config={
                "clip_name": "抬头标题",
                "title": "曲名",
                "artist": "曲师",
                "level_label": st.column_config.TextColumn("难度", width=80),
                "ds": st.column_config.NumberColumn("定数", format="%.1f", width=60),
                "score": st.column_config.NumberColumn("分数", format="%d"),
                "combo_type": st.column_config.TextColumn("FullCombo标", width=80),
                "chain_type": st.column_config.TextColumn("FullChain标", width=100),
                "ra": st.column_config.NumberColumn("单曲Ra", format="%.2f", width=75),
                "play_count": st.column_config.NumberColumn("游玩次数", format="%d")
            }
        )

@st.dialog("落雪查分器配置说明")
def lxns_api_instructions():
    """Displays instructions for obtaining and using the Luoxue Score Checker personal API key."""
    st.markdown("""
    
    首先，打开[落雪查分器官网](https://maimai.lxns.net/)并登录您的账号。
                
    ### 如何获取好友码？
                
    1. 进入“账号详情”页面。
    2. 在页面中找到“好友码”一栏，复制您的好友码，粘贴到输入框即可。
    """)

    st.warning("关于个人API密钥：通常情况下，您不需要使用个人API密钥即可从落雪查分器获取数据，\
               如果常规查询失败或遇到访问限制时，参考下方说明使用个人API密钥。")

    st.markdown("""
    ### 如何获取落雪查分器的个人API密钥？

    1. 进入“账号详情”页面。
    2. 找到“第三方应用”选项，点击下方生成个人 API 密钥按钮，生成并复制个人API密钥。
    3. 将该密钥粘贴到输入框中，点击保存凭证按钮。
    
    **注意**：请妥善保管您的API密钥，不要泄露给他人，本项目仅将此密钥保存在本地，不会上传或分享给任何第三方。
    """)

@st.dialog("删除存档确认")
def confirm_delete_archive(username: str, archive_name: str):
    """Asks for confirmation and deletes an archive from the database."""
    st.warning(f"是否确认删除存档：**{username} - {archive_name}**？此操作不可撤销！")
    if st.button("确认删除"):
        if db_handler.delete_save_archive(username, archive_name):
            st.toast(f"已删除存档！{username} - {archive_name}")
            # Clear session state to avoid using the deleted archive
            if st.session_state.get('archive_name') == archive_name:
                st.session_state.archive_name = None
            st.rerun()
        else:
            st.error("删除存档失败。")
    if st.button("取消"):
        st.rerun()

def handle_new_data(username: str, source: str, params: dict = None):
    """
    Fetches new data from a source, then creates a new archive in the database.
    This function is a placeholder for the actual data fetching logic.
    """
    st.session_state.data_created_step1 = False
    # 原始数据缓存路径
    raw_file_path = f"{get_user_base_dir(username)}/{username}_{source}_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        # 重构：查分，并创建存档，原始数据缓存于raw_file_path
        if source in ["mmbl", "html"]: #, "json"]:
            new_archive_data = unify_user_gamedata(
                raw_file_path=raw_file_path,
                source=source,
                username=username,
                params=params,
            )
        # elif source == "intl":
        #     new_archive_data = update_b50_data_int(
        #         b50_raw_file=raw_file_path,
        #         username=username,
        #         params=params
        #     )
        elif source in ["fish", "lxns"]:
            new_archive_data = fetch_user_gamedata(
                raw_file_path=raw_file_path,
                source=source,
                username=username,
                params=params,
            )
        else:
            st.error(f"不支持的数据源: {source}")
            return
        
        # debug: 存储new_archive_data
        # debug_path = f"./b50_datas/debug_new_archive_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # with open(debug_path, "w", encoding="utf-8") as f:
        #     json.dump(new_archive_data, f, ensure_ascii=False, indent=4)

        # 调试信息：检查initial_records
        initial_records = new_archive_data.get('initial_records', [])
        if not initial_records:
            st.warning(f"警告: initial_records 为空！数据可能未正确转换。")
            with st.expander("调试信息"):
                st.write(f"new_archive_data keys: {list(new_archive_data.keys())}")
                st.write(f"initial_records length: {len(initial_records)}")
                if 'data' in new_archive_data:
                    st.write(f"data keys: {list(new_archive_data['data'].keys()) if isinstance(new_archive_data.get('data'), dict) else 'N/A'}")
        else:
            st.info(f"准备保存 {len(initial_records)} 条记录到数据库")
        
        archive_id, archive_name = db_handler.create_new_archive(
            username=username,
            game_type=new_archive_data.get('game_type', 'maimai'),
            sub_type=new_archive_data.get('sub_type', 'best'),
            rating_mai=new_archive_data.get('rating_mai', 0),
            rating_chu=new_archive_data.get('rating_chu', 0),
            game_version=new_archive_data.get('game_version', 'N/A'),
            initial_records=initial_records
        )
        
        # 验证记录是否已保存
        saved_records = db_handler.db.get_records_with_extented_data(archive_id)
        if len(saved_records) != len(initial_records):
            st.warning(f"警告: 保存的记录数 ({len(saved_records)}) 与预期 ({len(initial_records)}) 不匹配！")
        
        st.session_state.archive_name = archive_name
        print(f"成功创建新存档: {archive_name}， ID: {archive_id}，保存了 {len(saved_records)} 条记录")
        st.session_state.data_created_step1 = True
        st.rerun()

    except Exception as e:
        st.error(f"创建新存档时发生错误: {e}")
        st.expander("错误详情").write(traceback.format_exc())

# =============================================================================
# Page layout starts here
# ==============================================================================

# Start with getting G_type from session state
G_type = st.session_state.get('game_type', 'maimai')

# 页面头部
st.header(f"📊 获取和管理分表数据")
st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

# --- 1. Username Input ---
st.markdown("### 👤 用户设置")
with st.container(border=True):
    col_user1, col_user2 = st.columns([3, 1])
    with col_user1:
        input_username = st.text_input(
            "输入您的用户名",
            value=st.session_state.get("username", ""),
            help="如果你从水鱼等查分器获取数据，请输入在对应平台的用户名，否则请自拟用户名。",
            placeholder="请输入用户名"
        )
    with col_user2:
        st.write("")  # 占位
        st.write("")  # 占位
        if st.button("✅ 确定用户名", use_container_width=True, type="primary"):
            if not input_username:
                st.error("❌ 用户名不能为空！")
                st.session_state.config_saved = False
            else:
                raw_username, safe_username = process_username(input_username)
                st.session_state.username = raw_username
                st.session_state.safe_username = safe_username
     
                # Set user in database
                db_handler.set_current_user(raw_username)
                st.session_state.config_saved = True
                st.rerun()
    
    # 显示当前用户名状态
    if st.session_state.get("username"):
        st.info(f"当前用户名: **{st.session_state.get('username')}**")
    if st.session_state.get("username") != st.session_state.get("safe_username"):
        st.warning(f"⚠️ 您的用户名包含特殊字符，在查找文件目录时请使用此名称：**{st.session_state.get('safe_username')}**")

# Only proceed if a username has been set
if st.session_state.get('config_saved', False):
    username = st.session_state.username

    # Create user base directory if not exists
    user_base_dir = get_user_base_dir(username)
    os.makedirs(user_base_dir, exist_ok=True)

    tab1, tab2 = st.tabs(["🗃️ 管理已有存档", "📦 创建新存档"])

    # --- 2. Manage Existing Archives ---
    with tab1:
        archives = db_handler.get_user_save_list(username, game_type=G_type)
        
        if not archives:
            st.info("💡 您还没有任何本地存档，请选择右侧「创建新存档」页签来创建第一个存档。")
        else:
            # 按创建时间排序，最新的在前
            archives_sorted = sorted(archives, key=lambda x: x.get('created_at', ''), reverse=True)
            archive_names = [a['archive_name'] for a in archives_sorted]
            
            # 自动加载最新存档（如果还没有加载存档）
            if not st.session_state.get('archive_name') or st.session_state.get('archive_name') not in archive_names:
                # 自动选择并加载最新的存档
                latest_archive_name = archive_names[0]
                archive_id = db_handler.load_save_archive(username, latest_archive_name)
                if archive_id:
                    st.session_state.archive_id = archive_id
                    st.session_state.archive_name = latest_archive_name
                    st.session_state.data_updated_step1 = True
                    st.success(f"✅ 已自动加载最新存档: **{latest_archive_name}**")
                    st.rerun()
            
            st.success(f"找到 **{len(archives)}** 个存档")
            
            # Determine default index for selectbox
            try:
                current_archive_index = archive_names.index(st.session_state.get('archive_name'))
            except (ValueError, TypeError):
                current_archive_index = 0

            selected_archive_name = st.selectbox(
                "选择存档",
                archive_names,
                index=current_archive_index,
                format_func=lambda name: f"📁 {name}",
                help="从下拉列表中选择要操作的存档"
            )

            # 显示选中存档的详细信息
            selected_archive = next((a for a in archives_sorted if a['archive_name'] == selected_archive_name), None)
            if selected_archive:
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    # 修复Rating显示：正确处理None值，根据游戏类型选择正确的rating字段
                    rating_value = None
                    if G_type == "maimai":
                        rating_value = selected_archive.get('rating_mai')
                    else:
                        rating_value = selected_archive.get('rating_chu')
                    
                    if rating_value is not None:
                        if G_type == "maimai":
                            st.metric("Rating", f"{rating_value:.0f}")
                        else:
                            st.metric("Rating", f"{rating_value:.2f}")
                    else:
                        st.metric("Rating", "N/A")
                with col_info2:
                    st.metric("游戏类型", get_game_type_text(selected_archive.get('game_type', G_type)))
                with col_info3:
                    created_at = selected_archive.get('created_at', '')
                    if created_at:
                        # 处理时间戳格式
                        if isinstance(created_at, str):
                            display_time = created_at[:10] if len(created_at) >= 10 else created_at
                        else:
                            display_time = str(created_at)[:10]
                        st.metric("创建时间", display_time)
                    else:
                        st.metric("创建时间", "N/A")

            st.divider()
            
            # 显示当前加载状态
            current_loaded = st.session_state.get('archive_name')
            if current_loaded == selected_archive_name:
                st.info(f"✅ 当前已加载: **{selected_archive_name}**")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                # 如果已加载当前选中的存档，按钮显示为已加载状态
                if current_loaded == selected_archive_name:
                    st.button("✅ 已加载", key=f"load_{selected_archive_name}", use_container_width=True, disabled=True)
                else:
                    if st.button("✅ 加载此存档", key=f"load_{selected_archive_name}", use_container_width=True, type="primary"):
                        archive_id = db_handler.load_save_archive(username, selected_archive_name)
                        st.session_state.archive_id = archive_id
                        st.session_state.archive_name = selected_archive_name
                        st.success(f"✅ 已加载存档: **{selected_archive_name}**")
                        st.session_state.data_updated_step1 = True
                        st.rerun()
            with col2:
                if st.button("👀 查看数据", key=f"view_data_{selected_archive_name}", use_container_width=True):
                    # 使用dialog装饰器包装函数
                    @st.dialog(f"分表数据查看", width="large")
                    def show_data_dialog():
                        view_b50_data(username, selected_archive_name)
                    show_data_dialog()
            with col3:
                if st.button("❌ 删除此存档", key=f"delete_{selected_archive_name}", use_container_width=True, type="secondary"):
                    confirm_delete_archive(username, selected_archive_name)

    # --- 3. Create New Archives ---
    with tab2:
        st.info(f"💡 从外部数据源获取您的分表成绩，并创建一个新的本地存档。")
        st.caption(f"当前用户名: **{username}**")
        
        # Data from FISH (CN Server)
        with st.expander("🌊 从水鱼查分器获取（国服）", expanded=True):
            st.markdown(f"**数据源**: [水鱼查分器](https://www.diving-fish.com/maimaidx/prober) | **用户名**: {username}")
            
            if G_type == "maimai":
                col_fish1, col_fish2 = st.columns(2)
                with col_fish1:
                    if st.button("📥 获取 B50 数据", key="fish_maimai_b50", use_container_width=True, type="primary"):
                        with st.spinner("正在从水鱼查分器获取B50数据..."):
                            handle_new_data(username, source="fish", 
                                            params={"type": "maimai", "query": "best"})
                with col_fish2:
                    if st.button("⭐ 获取 AP B50 数据", key="fish_maimai_ap", use_container_width=True):
                        with st.spinner("正在从水鱼查分器获取AP B50数据..."):
                            handle_new_data(username, source="fish",
                                            params={"type": "maimai", "query": "all", "filter": {"tag": "ap", "top": 50}})
            
            elif G_type == "chunithm":
                if st.button("📥 获取 B50 数据", key="fish_chunithm_b50", use_container_width=True, type="primary"):
                    with st.spinner("正在从水鱼查分器获取B50数据..."):
                        handle_new_data(username, source="fish", 
                                        params={"type": "chunithm", "query": "best"})
                # TODO: 添加中二仅获取b30的选项
            else:
                st.error(f"❌ 错误的游戏类型: {G_type}，请返回首页刷新重试。")

        # Data from Luoxue Score Checker (落雪查分器)
        with st.expander(":snowflake: 从落雪查分器获取"):

            # 加载保存的凭证（个人api密钥）
            lxns_credentials_file = f"{user_base_dir}/lxns_credentials.json"
            saved_friend_code = ""
            saved_api_key = ""
            
            if os.path.exists(lxns_credentials_file):
                try:
                    with open(lxns_credentials_file, 'r', encoding='utf-8') as f:
                        credentials = json.load(f)
                        saved_friend_code = credentials.get('friend_code', '')
                        saved_api_key = credentials.get('api_key', '')
                except:
                    pass
            
            friend_code_input = st.text_input(
                "好友码",
                value=saved_friend_code,
                help="您的落雪查分器好友码，填写后点击下方保存凭证，后续使用则无需重复填写。"
            )
            local_user_api = st.checkbox(
                "使用个人API密钥",
                value=False,
                help="启用后需要使用落雪查分器的个人API密钥进行数据获取，建议在常规查询失败时使用。"
            )
            if local_user_api:
                api_key_input = st.text_input(
                    "API密钥",
                    value=saved_api_key,
                    type="password",
                    help="落雪查分器的个人API密钥，您在这里填写过一次后，此密钥将会保存在对于用户名的本地文件中, 后续使用无需重复填写。"
                )
            else:
                api_key_input = saved_api_key  # 如果不使用个人API密钥，则保持为空或之前保存的值
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("保存凭证", key="save_lxns_credentials"):
                    if friend_code_input:
                        credentials = {
                            "friend_code": friend_code_input,
                            "api_key": api_key_input
                        }
                        with open(lxns_credentials_file, 'w', encoding='utf-8') as f:
                            json.dump(credentials, f, ensure_ascii=False, indent=2)
                        st.success("凭证已保存！")
                    else:
                        st.warning("最少需要填写好友码才能保存凭证。")
            with col2:
                if st.button("落雪查分器使用指南", key="read_lxns_api_instructions"):
                    lxns_api_instructions()

            st.divider() 
            
            if friend_code_input:
                if G_type == "maimai":
                    col1_lxns, col2_lxns = st.columns(2)
                    with col1_lxns: 
                        if st.button("📥 获取 B50 数据", key="lxns_maimai_b50", use_container_width=True, type="primary"):
                            with st.spinner("正在从落雪查分器获取B50数据..."):
                                handle_new_data(username, source="lxns",
                                                params={
                                                    "type": "maimai",
                                                    "query": "best",
                                                    "friend_code": friend_code_input,
                                                    "local_user_api": local_user_api,
                                                    "api_key": api_key_input if local_user_api else None
                                                })
                    with col2_lxns:
                        if st.button("⭐ 获取 AP B50 数据", key="lxns_maimai_ap", use_container_width=True):
                            query_type = "all" if local_user_api else "best_ap"  # 如果使用开发者API，指定特殊的查询类型（有待测试AP B50的查询接口）
                            query_filter = {"tag": "ap", "top": 50} if query_type == "all" else {}
                            with st.spinner("正在从落雪查分器获取AP B50数据..."):
                                handle_new_data(username, source="lxns",
                                                params={
                                                    "type": "maimai",
                                                    "query": query_type,
                                                    "filter": query_filter,
                                                    "friend_code": friend_code_input,
                                                    "local_user_api": local_user_api,
                                                    "api_key": api_key_input if local_user_api else None
                                                    
                                                })

                elif G_type == "chunithm":
                    if st.button("📥 获取 B50 数据", key="lxns_chunithm_b50", use_container_width=True, type="primary"):
                        with st.spinner("正在从落雪查分器获取B50数据..."):
                            handle_new_data(username, source="lxns",
                                            params={
                                                "type": "chunithm",
                                                "query": "best",
                                                "friend_code": friend_code_input,
                                                "local_user_api": local_user_api,
                                                "api_key": api_key_input if local_user_api else None
                                            })
            else:
                st.warning("请先填写好友码后再获取数据。")
                

        # Data from DX Web (INTL/JP Server)
        with st.expander("🌏 从官网手动导入数据 (国际服/日服)"):
            st.warning("✅ 国际服/日服数据已更新MMBL导入支持，绝赞测试中！")
            if G_type == "maimai":
                st.write("请将获取的数据文本粘贴到下方输入框中，并选择对应的数据源类型和其他信息。")

                if st.toggle("💡 展开查看数据获取指南"):
                    # TODO: Claude写的分段加载markdown图片/文本，后续可以封装成工具方法
                    _guide_path = os.path.join(os.path.dirname(__file__), "..", "docs", "DataImportGuide.md")
                    _res_dir = os.path.join(os.path.dirname(__file__), "..", "md_res")

                    with open(_guide_path, "r", encoding="utf-8") as f:
                        _guide_md = f.read()

                    st.divider()
                    # 按图片行拆分
                    pattern = re.compile(r"(!\[([^\]]*)\]\(([^)]+)\))") # ![alt](path) 正则
                    last_end = 0
                    for match in pattern.finditer(_guide_md):
                        # 图片前的文本
                        before = _guide_md[last_end:match.start()]
                        if before.strip():
                            st.markdown(before)
                        # 图片
                        img_path = os.path.join(_res_dir, os.path.basename(match.group(3)))
                        st.image(img_path)
                        last_end = match.end()
                    # 最后一张图片后的文本
                    remaining = _guide_md[last_end:]
                    if remaining.strip():
                        st.markdown(remaining)
                    st.divider()

                DATA_SOURCE_OPTIONS = ["Maimai Booklet (MMBL, 推荐)", "maimai DX Net (HTML, 不含FC状态等信息)"] #, "dxrating (JSON)"]
                MMBL_VERSION_OPTIONS = ["国际服 (PRiSM PLUS & CiRCLE)", "日服 (CiRCLE & CiRCLE PLUS)", "全版本 (取全曲最高50条成绩，生成AP50/FC50时推荐)"]
                FILTER_TAG_OPTIONS = ["无筛选 (根据版本筛选B35+B15或整体B50)", "极50 (只筛选FC以上成绩)", "神50 (只筛选AP以上成绩)"]

                data_source = st.radio("选择导入的数据源类型：", options=DATA_SOURCE_OPTIONS, key="data_source")
                if data_source == DATA_SOURCE_OPTIONS[0]:
                    mmbl_version = st.radio("B15对应版本 (仅影响MMBL数据源)", options=MMBL_VERSION_OPTIONS, key="mmbl_version")
                    filter_tag = st.radio("特殊筛选条件 (仅影响MMBL数据源)", options=FILTER_TAG_OPTIONS, key="filter_tag")

                data_input = st.text_area("请粘贴获取到的原始数据", height=200)

                if st.button("从粘贴内容创建新存档"):
                    if data_input:
                        query = "best"
                        filter = {}
                        if data_source == DATA_SOURCE_OPTIONS[0]:
                            file_type = "mmbl"
                            query = "all" # MMBL固定返回全部数据

                            # 用户指明自己的数据源服务器
                            if mmbl_version == MMBL_VERSION_OPTIONS[0]:
                                filter["b15_versions"] = 0
                            elif mmbl_version == MMBL_VERSION_OPTIONS[1]:
                                filter["b15_versions"] = 1
                            else:
                                filter["b15_versions"] = -1
                            # AP50需要修改filter
                            if filter_tag == FILTER_TAG_OPTIONS[1]:
                                filter["tag"] = "fc"
                            elif filter_tag == FILTER_TAG_OPTIONS[2]:
                                filter["tag"] = "ap"
                        elif data_source == DATA_SOURCE_OPTIONS[1]:
                            file_type = "html"
                        else:
                            file_type = "json"

                        handle_new_data(username, source=file_type,
                                        params={"type": "maimai", "query": query,
                                                "data_input": data_input,
                                                "filter": filter})
                    else:
                        st.warning("输入框内容为空。")
            else:
                st.warning(f"暂未支持从国际服/日服数据导入中二节奏数据，如有需要请在左侧导航栏使用自定义分表功能手动配置。")
        with st.expander("💡 数据在神秘的服务器里？加入交流群，说不定就能实装呢？"):
            st.write("加入QQ群：[994702414](https://qm.qq.com/q/ogt02jHEjK)")
    # --- Navigation ---
    st.divider()
    if st.session_state.get('data_updated_step1', False) and st.session_state.get('archive_name'):
        if st.session_state.get('data_created_step1', False):
            st.success(f"已成功创建新存档：**{st.session_state.get('archive_name')}**！")
        elif st.session_state.get('data_updated_step1', False):
            st.success(f"已加载存档：**{st.session_state.get('archive_name')}**！")

        with st.container(border=True):
            col_nav1, col_nav2 = st.columns([3, 1])
            with col_nav1:
                st.write("确认存档无误后，请点击右侧按钮进入下一步。")
            with col_nav2:
                if st.button("➡️ 前往第二步", use_container_width=True, type="primary"):
                    st.switch_page("st_pages/Generate_Pic_Resources.py")
else:
    if not st.session_state.get('config_saved', False):
        st.warning("⚠️ 请先在上方设定您的用户名。")
    else:
        st.info("💡 请先加载一个存档或创建新存档。")
