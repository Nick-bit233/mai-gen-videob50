import streamlit as st
import os
import json
import traceback
import csv
import io
from collections import defaultdict
from datetime import datetime
from utils.user_gamedata_handlers import fetch_user_gamedata, update_b50_data_int
from utils.PageUtils import get_db_manager, process_username, get_game_type_text
from db_utils.DatabaseDataHandler import get_database_handler
from utils.PathUtils import get_user_base_dir
from utils.lxns_metadata_loader import update_chunithm_metadata_from_lxns
import glob

# Get a handler for database operations
db_handler = get_database_handler()
level_label_lists = {
    "maimai": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"],
    "chunithm": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
}

def import_playcount_from_csv(username: str, archive_name: str):
    """从CSV文件导入游玩次数"""
    st.info("💡 上传落雪备份的CSV成绩文件，系统将根据 song_name 和 level_index 自动统计并填写游玩次数。")
    
    uploaded_file = st.file_uploader(
        "选择CSV文件",
        type=['csv'],
        help="请上传落雪备份的CSV成绩文件，必须包含 song_name 和 level_index 列"
    )
    
    if uploaded_file is not None:
        try:
            # 读取CSV文件
            content = uploaded_file.read().decode('utf-8-sig')  # 使用utf-8-sig处理BOM
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # 检查必需的列
            required_columns = ['song_name', 'level_index']
            if not all(col in csv_reader.fieldnames for col in required_columns):
                st.error(f"❌ CSV文件缺少必需的列。需要包含: {', '.join(required_columns)}")
                st.info(f"当前CSV文件的列: {', '.join(csv_reader.fieldnames)}")
                return
            
            # 统计游玩次数：根据 (song_name, level_index) 组合计数
            play_count_map = defaultdict(int)
            total_rows = 0
            for row in csv_reader:
                song_name = row.get('song_name', '').strip()
                level_index_str = row.get('level_index', '').strip()
                
                if song_name and level_index_str:
                    try:
                        level_index = int(level_index_str)
                        key = (song_name, level_index)
                        play_count_map[key] += 1
                        total_rows += 1
                    except ValueError:
                        continue
            
            if not play_count_map:
                st.warning("⚠️ CSV文件中没有找到有效的游玩记录。")
                return
            
            st.success(f"✅ 成功解析CSV文件，共找到 {total_rows} 条记录，涉及 {len(play_count_map)} 个不同的谱面。")
            
            # 显示统计信息预览
            with st.expander("📊 游玩次数统计预览（前10条）", expanded=False):
                preview_items = list(play_count_map.items())[:10]
                for (song_name, level_index), count in preview_items:
                    st.write(f"- **{song_name}** (难度索引: {level_index}): {count} 次")
                if len(play_count_map) > 10:
                    st.caption(f"... 还有 {len(play_count_map) - 10} 个谱面")
            
            # 获取存档ID和所有记录
            archive_id = db_handler.load_save_archive(username, archive_name)
            if not archive_id:
                st.error("❌ 无法加载存档，请重试。")
                return
            
            # 获取存档中的所有记录（包含song_name和level_index）
            records = db_handler.db.get_records_with_extented_data(archive_id)
            
            if not records:
                st.warning("⚠️ 存档中没有找到任何记录。")
                return
            
            # 匹配并更新游玩次数
            updated_count = 0
            matched_count = 0
            unmatched_items = []
            
            for record in records:
                record_song_name = record.get('song_name', '').strip()
                record_level_index = record.get('level_index')
                record_id = record.get('record_id')
                
                if record_song_name and record_level_index is not None:
                    key = (record_song_name, record_level_index)
                    if key in play_count_map:
                        play_count = play_count_map[key]
                        # 更新数据库
                        db_handler.db.update_record(record_id, {'play_count': play_count})
                        updated_count += 1
                        matched_count += 1
                    else:
                        unmatched_items.append((record_song_name, record_level_index))
            
            # 显示结果
            if updated_count > 0:
                st.success(f"✅ 成功更新 {updated_count} 条记录的游玩次数！")
                
                if unmatched_items:
                    with st.expander(f"⚠️ 未匹配的记录（{len(unmatched_items)} 条）", expanded=False):
                        st.info("以下记录在CSV文件中未找到匹配项，游玩次数未更新：")
                        for song_name, level_index in unmatched_items[:20]:  # 只显示前20条
                            st.write(f"- **{song_name}** (难度索引: {level_index})")
                        if len(unmatched_items) > 20:
                            st.caption(f"... 还有 {len(unmatched_items) - 20} 条未匹配记录")
                
                # 添加刷新按钮
                if st.button("🔄 刷新数据并关闭", use_container_width=True, type="primary"):
                    st.rerun()
            else:
                st.warning("⚠️ 没有找到任何匹配的记录。请检查CSV文件中的 song_name 和 level_index 是否与存档中的记录一致。")
                
                # 显示存档中的一些示例记录
                with st.expander("📋 存档中的记录示例（前5条）", expanded=True):
                    for record in records[:5]:
                        st.write(f"- **{record.get('song_name', 'N/A')}** (难度索引: {record.get('level_index', 'N/A')})")
        
        except Exception as e:
            st.error(f"❌ 处理CSV文件时发生错误: {str(e)}")
            with st.expander("详细错误信息"):
                st.code(traceback.format_exc())

def view_b50_data(username: str, archive_name: str):
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
    if game_type == "chunithm":
        dialog_title = "B30数据查看"
        data_name = "B30"
        rating_label = "Rating"
    else:
        dialog_title = "B50数据查看"
        data_name = "B50"
        rating_label = "DX Rating"
    
    # 使用动态标题创建对话框（Streamlit不支持动态标题，所以我们需要在内容中显示）
    st.markdown(f"### {dialog_title}")
    
    st.markdown(f"""
        - **用户名**: {username}
        - **存档名**: {archive_name}
        """, unsafe_allow_html=True)

    # 处理不同游戏类型的数据格式
    if game_type == "maimai":
        st.markdown(f"""**{rating_label}**: {b50_data.get('rating_mai', 0)}""", unsafe_allow_html=True)
        show_records = b50_data.get('records', [])
    elif game_type == "chunithm":
        # Chunithm数据直接是列表格式（来自load_archive_for_image_generation）
        if isinstance(b50_data, list):
            show_records = b50_data
            # 移除jacket字段（PIL Image对象），因为dataframe无法显示
            for record in show_records:
                if 'jacket' in record:
                    del record['jacket']
            # 从archive获取rating
            archive_id = db_handler.load_save_archive(username, archive_name)
            if archive_id:
                archive = db_handler.db.get_archive(archive_id)
                rating = archive.get('rating_chu', 0.0) if archive else 0.0
                st.markdown(f"""**{rating_label}**: {rating:.2f}""", unsafe_allow_html=True)
        else:
            # 兼容旧格式
            show_records = b50_data.get('records', []) if isinstance(b50_data, dict) else []
            rating = b50_data.get('rating_chu', 0.0) if isinstance(b50_data, dict) else 0.0
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
        from utils.PageUtils import format_chunithm_rank
        for record in show_records:
            if 'ra' in record and isinstance(record['ra'], (int, float)):
                record['ra'] = math.floor(record['ra'] * 100) / 100.0
            # 确保play_count字段存在（可能是playCount）
            if 'play_count' not in record and 'playCount' in record:
                record['play_count'] = record['playCount']
            # 格式化rank显示
            if 'rank' in record:
                record['rank_display'] = format_chunithm_rank(record['rank'])
            else:
                record['rank_display'] = ''
            # 确保xv_ds字段存在（如果不存在则设为0.0）
            if 'xv_ds' not in record:
                record['xv_ds'] = 0.0
            # 确保combo_type字段存在（如果不存在或为空，设为'none'）
            if 'combo_type' not in record:
                record['combo_type'] = 'none'
            elif not record.get('combo_type'):
                record['combo_type'] = 'none'
            # 确保chain_type字段存在（如果不存在或为空，设为'none'）
            if 'chain_type' not in record:
                record['chain_type'] = 'none'
            elif not record.get('chain_type'):
                record['chain_type'] = 'none'
            else:
                chain_value = str(record.get('chain_type')).lower().strip()
                if chain_value in ('ac', 'fullchain', 'fc'):
                    record['chain_type'] = 'fc'
                elif chain_value in ('fs', 'fullchainrainbow', 'fcr'):
                    record['chain_type'] = 'fcr'
        
        st.dataframe(
            show_records,
            column_order=["clip_name",  "title", "artist", "level_label",
                        "ds", "xv_ds", "note_designer", "score", "rank_display", "combo_type", "chain_type", "ra", "play_count"],
            column_config={
                "clip_name": "抬头标题",
                "title": "曲名",
                "artist": "曲师",
                "level_label": st.column_config.TextColumn("难度", width=80),
                "ds": st.column_config.NumberColumn("定数", format="%.1f", width=60),
                "xv_ds": st.column_config.NumberColumn("新定数", format="%.1f", width=60),
                "note_designer": "谱师",
                "score": st.column_config.NumberColumn("分数", format="%d"),
                "rank_display": st.column_config.TextColumn("RANK", width=60),
                "combo_type": st.column_config.TextColumn("FC标", width=80),
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

def handle_new_data(username: str, source: str, raw_file_path: str, params: dict = None, parser: str = "json"):
    """
    Fetches new data from a source, then creates a new archive in the database.
    This function is a placeholder for the actual data fetching logic.
    """
    st.session_state.data_created_step1 = False
    try:
        # 重构：查分，并创建存档，原始数据缓存于raw_file_path
        if source == "intl":
            new_archive_data = update_b50_data_int(
                b50_raw_file=raw_file_path,
                username=username,
                params=params,
                parser=parser
            )
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
        debug_path = f"./b50_datas/debug_new_archive_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(new_archive_data, f, ensure_ascii=False, indent=4)

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
        st.session_state.archive_id = archive_id
        print(f"成功创建新存档: {archive_name}， ID: {archive_id}，保存了 {len(saved_records)} 条记录")
        st.session_state.data_created_step1 = True
        st.session_state.data_updated_step1 = True  # 同时设置，以便显示下一步按钮
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
                
                st.success(f"✅ 用户名 **{raw_username}** 已设定！")
                st.session_state.config_saved = True
                st.rerun()
    
    # 显示当前用户名状态
    if st.session_state.get("username"):
        st.info(f"当前用户名: **{st.session_state.get('username')}**")

# Only proceed if a username has been set
if st.session_state.get('config_saved', False):
    username = st.session_state.username
    safe_username = st.session_state.safe_username

    # Create user base directory if not exists
    user_base_dir = get_user_base_dir(safe_username)
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
            
            col1, col2, col3, col4 = st.columns(4)
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
                if st.button("📊 导入游玩次数", key=f"import_playcount_{selected_archive_name}", use_container_width=True):
                    # 使用dialog装饰器包装函数
                    @st.dialog("从CSV导入游玩次数", width="large")
                    def import_playcount_dialog():
                        import_playcount_from_csv(username, selected_archive_name)
                    import_playcount_dialog()
            with col4:
                if st.button("❌ 删除此存档", key=f"delete_{selected_archive_name}", use_container_width=True, type="secondary"):
                    confirm_delete_archive(username, selected_archive_name)

    # --- 3. Create New Archives ---
    with tab2:
        st.info(f"💡 从外部数据源获取您的分表成绩，并创建一个新的本地存档。")
        st.caption(f"当前用户名: **{username}**")

        # 获得原始数据缓存路径
        # 如果还没有存档名，使用时间戳作为临时文件名
        if st.session_state.get('archive_name'):
            archive_name_for_file = st.session_state.archive_name
        else:
            # 生成临时文件名（实际创建存档时会使用数据库生成的存档名）
            archive_name_for_file = datetime.now().strftime('%Y%m%d_%H%M%S')
        b50_raw_file = f"{user_base_dir}/{archive_name_for_file}_raw.json"
        
        # Data from FISH (CN Server)
        with st.expander("🌊 从水鱼查分器获取（国服）", expanded=True):
            st.markdown(f"**数据源**: [水鱼查分器](https://www.diving-fish.com/maimaidx/prober) | **用户名**: {username}")
            
            if G_type == "maimai":
                col_fish1, col_fish2 = st.columns(2)
                with col_fish1:
                    if st.button("📥 获取 B50 数据", key="fish_maimai_b50", use_container_width=True, type="primary"):
                        with st.spinner("正在从水鱼查分器获取B50数据..."):
                            handle_new_data(username, source="fish", 
                                            raw_file_path=b50_raw_file,
                                            params={"type": "maimai", "query": "best"})
                with col_fish2:
                    if st.button("⭐ 获取 AP B50 数据", key="fish_maimai_ap", use_container_width=True):
                        with st.spinner("正在从水鱼查分器获取AP B50数据..."):
                            handle_new_data(username, source="fish",
                                            raw_file_path=b50_raw_file,
                                            params={"type": "maimai", "query": "all", "filter": {"tag": "ap", "top": 50}})
            
            elif G_type == "chunithm":
                if st.button("📥 获取 B50 数据", key="fish_chunithm_b50", use_container_width=True, type="primary"):
                    with st.spinner("正在从水鱼查分器获取B50数据..."):
                        handle_new_data(username, source="fish", 
                                        raw_file_path=b50_raw_file,
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
                                                raw_file_path=b50_raw_file,
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
                                                raw_file_path=b50_raw_file,
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
                                            raw_file_path=b50_raw_file,
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
                st.warning(f"暂未支持从国际服/日服数据导入中二节奏数据，如有需要请在左侧导航栏使用自定义分表功能手动配置。")

    # --- Navigation ---
    st.divider()
    # 检查是否有存档已创建或加载（支持两种状态）
    has_archive = (st.session_state.get('data_created_step1', False) or 
                   st.session_state.get('data_updated_step1', False)) and \
                  st.session_state.get('archive_name')
    
    if has_archive:
        if st.session_state.get('data_created_step1', False):
            st.success(f"✅ 已成功创建新存档：**{st.session_state.get('archive_name')}**！")
        elif st.session_state.get('data_updated_step1', False):
            st.success(f"✅ 已加载存档：**{st.session_state.get('archive_name')}**！")

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
