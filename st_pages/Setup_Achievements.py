import streamlit as st
import os
import json
import traceback
from datetime import datetime
from utils.user_gamedata_handlers import fetch_user_gamedata, update_b50_data_int
from utils.PageUtils import get_db_manager, process_username, get_game_type_text
from db_utils.DatabaseDataHandler import get_database_handler
from utils.PathUtils import get_user_base_dir
import glob

# Get a handler for database operations
db_handler = get_database_handler()
level_label_lists = {
    "maimai": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"],
    "chunithm": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
}

@st.dialog("b50数据查看", width="large")
def view_b50_data(username: str, archive_name: str):
    """Displays the records of a selected archive in a read-only table."""
    b50_data = db_handler.load_archive_as_old_b50_config(username, archive_name)
    
    if not b50_data:
        st.error("无法加载存档数据。")
        return

    st.markdown(f"""
    - **用户名**: {b50_data.get('username')}
    - **存档名**: {archive_name}
    - **DX Rating**: {b50_data.get('rating_mai', 0)}
    """, unsafe_allow_html=True)
    
    st.info("本窗口为只读模式。如需修改，请前往“编辑/创建自定义B50存档”页面。")

    game_type = b50_data.get('type', 'maimai')
    show_records = b50_data.get('records', [])
    for record in show_records:
        level_index = record.get('level_index', 0)
        record['level_label'] = level_label_lists.get(game_type, [])[level_index]

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

    if st.button("返回"):
        st.rerun()

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

def handle_new_data(username: str, source: str, raw_file_path: str, params: dict = None, parser: str = "json"):
    """
    Fetches new data from a source, then creates a new archive in the database.
    This function is a placeholder for the actual data fetching logic.
    """
    try:
        # 重构：查分，并创建存档，原始数据缓存于raw_file_path
        if source == "intl":
            new_archive_data = update_b50_data_int(
                b50_raw_file=raw_file_path,
                username=username,
                params=params,
                parser=parser
            )
        elif source in ["fish"]:
            new_archive_data = fetch_user_gamedata(
                raw_file_path=raw_file_path,
                source=source,
                username=username,
                params=params,
        )
        else:
            st.error(f"不支持的数据源: {source}")
            return
        
        ## debug: 存储new_archive_data
        # debug_path = f"./b50_datas/debug_new_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # with open(debug_path, "w", encoding="utf-8") as f:
        #     json.dump(new_archive_data, f, ensure_ascii=False, indent=4)

        archive_id, archive_name = db_handler.create_new_archive(
            username=username,
            game_type=new_archive_data.get('game_type', 'maimai'),
            sub_type=new_archive_data.get('sub_type', 'best'),
            rating_mai=new_archive_data.get('rating_mai', 0),
            rating_chu=new_archive_data.get('rating_chu', 0),
            game_version=new_archive_data.get('game_version', 'N/A'),
            initial_records=new_archive_data.get('initial_records', [])
        )
        
        st.session_state.archive_name = archive_name
        print(f"成功创建新存档: {archive_name}， ID: {archive_id}")
        st.success(f"成功创建新存档: {archive_name}")
        st.session_state.data_updated_step1 = True
        st.rerun()

    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"创建新存档时发生错误: {e}")
        st.expander("错误详情").write(traceback.format_exc())

# =============================================================================
# Page layout starts here
# ==============================================================================

# Start with getting G_type from session state
G_type = st.session_state.get('game_type', 'maimai')

st.header("从第三方查分器获取分表")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

# --- 1. Username Input ---
with st.container(border=True):
    st.subheader("设置用户名")
    input_username = st.text_input(
        "输入您的用户名",
        value=st.session_state.get("username", ""),
        help="如果你从水鱼等查分器获取数据，请输入在对应平台的用户名，否则请自拟用户名。"
    )

    if st.button("确定用户名"):
        if not input_username:
            st.error("用户名不能为空！")
            st.session_state.config_saved = False
        else:
            raw_username, safe_username = process_username(input_username)
            st.session_state.username = raw_username
            st.session_state.safe_username = safe_username
            
            # Set user in database
            db_handler.set_current_user(raw_username)
            
            st.success(f"用户名 **{raw_username}** 已设定！")
            st.session_state.config_saved = True
            st.rerun()

# Only proceed if a username has been set
if st.session_state.get('config_saved', False):
    username = st.session_state.username
    safe_username = st.session_state.safe_username

    # Create user base directory if not exists
    # 备注：b50_datas/username 目录现只用于缓存b50_raw.json等文件，数据管理迁移至数据库
    user_base_dir = get_user_base_dir(safe_username)
    os.makedirs(user_base_dir, exist_ok=True)

    tab1, tab2 = st.tabs(["🗃 管理已有存档", "📦 创建新存档"])

    # --- 2. Manage Existing Archives ---
    with tab1:
        archives = db_handler.get_user_save_list(username, game_type=G_type)
        
        if not archives:
            st.info("您还没有任何本地存档，请选择右侧“创建新存档”页签。")
        else:
            archive_names = [a['archive_name'] for a in archives]
            
            # Determine default index for selectbox
            try:
                current_archive_index = archive_names.index(st.session_state.get('archive_name'))
            except (ValueError, TypeError):
                current_archive_index = 0

            selected_archive_name = st.selectbox(
                "选择一个存档进行操作",
                archive_names,
                index=current_archive_index,
                format_func=lambda name: f"{name}"
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ 加载此存档"):
                    st.session_state.archive_name = selected_archive_name
                    st.success(f"已加载存档: **{selected_archive_name}**")
                    st.session_state.data_updated_step1 = True
            with col2:
                if st.button("👀 查看数据"):
                    view_b50_data(username, selected_archive_name)
            with col3:
                if st.button("❌ 删除此存档"):
                    confirm_delete_archive(username, selected_archive_name)

    # --- 3. Create New Archives ---
    with tab2:
        st.info("从外部数据源获取您的B50成绩，并创建一个新的本地存档。")
        
        # Data from FISH (CN Server)
        with st.expander("从水鱼查分器获取（国服）"):
            st.write(f"将以用户名 **{username}** 从查分器获取数据。")
            
            if G_type == "maimai":
                b50_raw_file = f"{user_base_dir}/maimai_b50_raw.json"
                if st.button("获取 B50 数据"):
                    handle_new_data(username, source="fish", 
                                    raw_file_path=b50_raw_file,
                                    params={"type": "maimai", "query": "best"})
                if st.button("获取 AP B50 数据"):
                    handle_new_data(username, source="fish",
                                    raw_file_path=b50_raw_file,
                                    params={"type": "maimai", "query": "all", "filter": {"tag": "ap", "top": 50}})
            
            elif G_type == "chunithm":
                b50_raw_file = f"{user_base_dir}/chunithm_b50_raw.json"
                st.info("注意：水鱼中二节奏国服数据源目前无法获取N20数据，将默认仅获取B30数据。")
                if st.button("获取 B30 数据"):
                    handle_new_data(username, source="fish", 
                                    raw_file_path=b50_raw_file,
                                    params={"type": "chunithm", "query": "best"})
            else:
                st.error(f"错误的游戏类型: {G_type}，请返回首页刷新重试。")

        # Data from DX Web (INTL/JP Server)
        with st.expander("从 DX Rating Net 导入（国际服/日服）"):
            if G_type == "maimai":
                st.write("请将maimai DX NET(官网)获取的源代码，或 DX Rating 网站导出的JSON代码粘贴到下方。")
                data_input = st.text_area("粘贴源代码或JSON", height=200)
                
                if st.button("从粘贴内容创建新存档"):
                    if data_input:
                        file_type = "json" if data_input.strip().startswith("[{") else "html"
                        b50_raw_file = f"{user_base_dir}/b50_raw.{file_type}"
                        handle_new_data(username, source="intl",
                                        raw_file_path=b50_raw_file,
                                        params={"type": "maimai", "query": "best"}, parser=file_type)
                    else:
                        st.warning("输入框内容为空。")
            else:
                st.warning("暂未支持从国际服/日服数据导入中二节奏数据，如有需要请在左侧导航栏使用自定义B50功能手动配置。")

    # --- Navigation ---
    st.divider()
    if st.session_state.get('data_updated_step1', False) and st.session_state.get('archive_name'):
        st.success(f"当前已加载存档: **{st.session_state.archive_name}**")
        st.write("确认存档无误后，请点击按钮进入下一步。")
        if st.button("➡️ 前往第二步：生成图片资源"):
            st.switch_page("st_pages/Generate_Pic_Resources.py")
else:
    st.warning("请先在上方设定您的用户名。")
