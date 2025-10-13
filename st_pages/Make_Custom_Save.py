from importlib.metadata import metadata
import streamlit as st
import os
import re
import json
import ast
import traceback
from copy import deepcopy
from datetime import datetime
import pandas as pd
from utils.PathUtils import *
from utils.PageUtils import get_db_manager, process_username
from db_utils.DatabaseDataHandler import get_database_handler
from utils.DataUtils import search_songs, level_label_to_index, chart_type_value2str
from utils.dxnet_extension import get_rate, parse_level, compute_rating

# 检查streamlit扩展组件安装情况
try:
    from streamlit_sortables import sort_items
except ImportError:
    st.error("缺少streamlit-sortables库，请更新软件发布包的运行环境，否则无法正常使用拖拽排序功能。")
    st.stop()

try:
    from streamlit_searchbox import st_searchbox
except ImportError:
    st.error("缺少streamlit-searchbox库，请更新软件发布包的运行环境，否则无法正常使用搜索功能。")
    st.stop()

# Initialize database handler
db_handler = get_database_handler()
level_label_lists = {
    "maimai": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"],
    "chunithm": ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
}

# 加载歌曲数据
# TODO：实现中二的metadata加载
@st.cache_data
def load_songs_data():
    # metadata已经更换为dxrating数据源
    try:
        with open("./music_metadata/maimaidx/dxdata.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载歌曲数据失败: {e}")
        return []

songs_data = load_songs_data().get('songs', [])
assert isinstance(songs_data, list), "songs_data should be a list"

@st.cache_data
def get_chart_info_from_db(chart_id):
    """从数据库中获取乐曲（谱面）信息"""
    return db_handler.load_chart_by_id(chart_id=chart_id)

# --- Data Helper Functions ---

def expand_records_data(simple_records):
    """Expand simple record data by fetching chart metadata from the database."""
    expanded_records = []
    for record in simple_records:
        chart_id = record.get('chart_id')
        if chart_id is not None:
            chart_data = get_chart_info_from_db(chart_id)
            assert isinstance(chart_data, dict), f"Chart_data should be a dict, got {type(chart_data)}"
            if chart_data:
                expanded_record = deepcopy(record)
                expanded_record['chart_data'] = chart_data
                expanded_records.append(expanded_record)
            else:
                raise LookupError(f"Can not find chart data for chart_id {chart_id} in database!")
        else:
            raise KeyError("No chart_id found in record!")
    return expanded_records


def create_empty_archive_meta(game_type="maimai", sub_type="custom"):
    """创建一个临时空白存档元配置，该配置在页面会话中使用，未保存前不会写入数据库"""
    return {
        "game_type": game_type,
        "sub_type": sub_type,
        "game_version": "latest",
    }


def create_empty_record(chart_data, index, game_type="maimai"):
    """Creates a blank template for a new record."""
    prefix = st.session_state.get("generate_setting", {}).get("clip_prefix", "Clip")
    add_name_index = st.session_state.get("generate_setting", {}).get("auto_index", True)
    auto_all_perfect = st.session_state.get("generate_setting", {}).get("auto_all_perfect", True)

    record_template =  {
                "chart_data": chart_data,
                "order_in_archive": index - 1,
                "clip_title_name": f"{prefix}_{index}" if add_name_index else prefix,
                "play_count": 0
            }

    match game_type:
        case "maimai":
            record_template.update({
                "achievement": 101.0000 if auto_all_perfect else 0.0,
                "fc_status": "app" if auto_all_perfect else "",
                "fs_status": "fsdp" if auto_all_perfect else "",
                "dx_rating": 0,
                "dx_score": 0,
            })
        case "chunithm":
            record_template.update({
                "achievement": 1010000 if auto_all_perfect else 0,
                "fc_status": "ajc" if auto_all_perfect else "",
                "fs_status": "fcr" if auto_all_perfect else "",
                "chuni_rating": 0.0,
            })
            
        case _:
            raise ValueError(f"Unsupported game type: {game_type}")
    
    return record_template


def save_current_archive():
    # 更新当前存档的元信息到数据库
    if 'username' in st.session_state and 'archive_name' in st.session_state:
        try:
            db_handler.update_archive_metadata(
                st.session_state.username,
                st.session_state.archive_name,
                st.session_state.archive_meta
            )
            st.toast("存档信息已保存到数据库！")
        except Exception as e:
            st.error(f"保存失败: {e}, {traceback.format_exc()}")
    else:
        st.error("无法保存，未加载有效的用户或存档。")

    # 更新所有记录
    update_records_to_db()


def update_records_to_db():
    """Saves the current state of records in the session to the database."""
    # TODO:保存时处理order in archives
    if 'username' in st.session_state and 'archive_name' in st.session_state:
        try:
            db_handler.update_archive_records(
                st.session_state.username,
                st.session_state.records,
                st.session_state.archive_name
            )
            st.toast("更改已保存到数据库！")
        except Exception as e:
            st.error(f"保存失败: {e}, {traceback.format_exc()}")
    else:
        st.error("无法保存，未加载有效的用户或存档。")

# --- UI Dialogs ---

@st.dialog("清空数据确认")
def confirm_clear_records(title, clear_function):
    st.write(f"确定要清空“{title}”的所有记录吗？此操作在点击“保存更改”前不会影响数据库。")
    if st.button("确认清空"):
        clear_function()
        st.rerun()
    if st.button("取消"):
        st.rerun()


# --- Other Helper Functions ---

def get_chart_info_str(record: dict, game_type="maimai", split='|'):
    """根据record中的chart_data，返回乐曲信息的字符串表示"""
    chart_data = record.get('chart_data', {})
    title = chart_data.get('song_name', '')
    chart_type = chart_type_value2str(chart_data.get('chart_type', -1), game_type=game_type)
    level_label = level_label_lists[game_type][chart_data.get('level_index', '3')] # default to MASTER
    return f"{title} {split} {level_label} [{chart_type}]"


def get_showing_records(records, game_type="maimai"):
    """根据存档类型，返回排序后的记录列表"""
    ret_records = deepcopy(records)
    for r in ret_records:
        r['chart_info'] = get_chart_info_str(r, game_type=game_type, split='|')

    return ret_records

# --- Streamlit Page Components ---

def update_records_count(placeholder):
    placeholder.write(f"当前记录数量: {len(st.session_state.records)}")


def update_record_grid(grid, external_placeholder):

    def recover_edited_records(edited_df):
        # 由于 st.data_editor 会将dict对象序列化，从组件df数据更新时需要反序列化chart_data
        to_update_records = deepcopy(edited_df)
        for r in to_update_records:
            r.pop('chart_info', None) # 清理chart_info
            chart_data = r.get('chart_data', {})
            if isinstance(chart_data, str):
            # 反序列化解析chart_data
                try:
                    # 使用 ast.literal_eval 处理可能包含单引号的字符串
                    chart_data = ast.literal_eval(chart_data)
                    r['chart_data'] = chart_data
                except (ValueError, SyntaxError):
                    return "Invalid chart data occurs when trying to save edited records."
        return to_update_records
        
    with grid.container(border=True):
        game_type = st.session_state.archive_meta.get("game_type", "maimai")

        # 显示和编辑现有记录
        if st.session_state.records:
            showing_records = get_showing_records(st.session_state.records, game_type=game_type)
            st.write("在此表格中编辑记录")
            st.warning("注意：修改表格中的记录内容后，请务必点击‘保存编辑’按钮！未保存修改的情况下使用上方按钮添加新记录将会导致修改内容丢失！")
            
            # 创建数据编辑器
            if game_type == "maimai":
                edited_records = st.data_editor(
                    showing_records,
                    column_order=["clip_title_name", "chart_info", "achievement", "fc_status", "fs_status", "dx_rating", "dx_score", "play_count"],
                    column_config={
                        "clip_title_name": "抬头标题",
                        "chart_info": "乐曲信息",
                        "achievement": st.column_config.NumberColumn(
                            "达成率",
                            min_value=0.0,
                            max_value=101.0,
                            format="%.4f",
                            required=True
                        ),
                        "fc_status": st.column_config.SelectboxColumn(
                            "FC标",
                            options=["", "fc", "fcp", "ap", "app"],
                            width=60,
                            required=False
                        ),
                        "fs_status": st.column_config.SelectboxColumn(
                            "Sync标",
                            options=["", "sync", "fs", "fsp", "fsd", "fsdp"],
                            width=60,
                            required=False
                        ),
                        "dx_rating": st.column_config.NumberColumn(
                            "单曲Ra",
                            format="%d",
                            width=65,
                            required=True
                        ),
                        "dx_score": st.column_config.NumberColumn(
                            "DX分数",
                            format="%d",
                            width=80,
                            required=True
                        ),
                        "play_count": st.column_config.NumberColumn(
                            "游玩次数",
                            format="%d",
                            required=False
                        )
                    },
                    num_rows="dynamic",
                    height=400,
                    width='stretch'
                )
            elif game_type == "chunithm":
                raise NotImplementedError("Chunithm record editing not implemented yet.")
            else:
                raise ValueError(f"Unsupported game type: {game_type}")

            # 更新记录
            if st.button("保存编辑"):
                if edited_records is not None:
                    st.session_state.records = recover_edited_records(edited_records)
                    save_current_archive()
                    update_records_count(external_placeholder)  # 更新外部记录数量的显示

            # 记录管理按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("重置所有记录的成绩数据"):
                    confirm_clear_records(
                        "清零所有记录的成绩数据", 
                        clear_all_records_achievement
                    )
            
            with col2:
                if st.button("清空所有记录"):
                    confirm_clear_records(
                        "清空所有记录",
                        clear_all_records
                    )
        else:
            st.write("当前没有记录，请添加记录。")

def clear_all_records_achievement():    
    # TODO: 修改格式和处理中二
    if st.session_state.archive_meta.get("game_type", "maimai") == "maimai":
        for record in st.session_state.records:
            record["achievements"] = 0.0
            record["fc_status"] = ""
            record["fs_status"] = ""
            record["dx_rating"] = 0
            record["dx_score"] = 0
        save_current_archive()


def clear_all_records():
    st.session_state.records = []
    save_current_archive()

# =============================================================================
# Page layout starts here
# ==============================================================================

# 用户名输入和校验
if not st.session_state.get("username", None):
    with st.container(border=True):
        st.subheader("设置用户名")
        input_username = st.text_input(
            "您还没有设置用户名，请自拟一个用户名以创建存档",
            value=st.session_state.get("username", "")
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

# 初始化会话状态
# """
#     本页面的会话状态包含：
#     - username: 当前用户名
#     - archive_name: 当前存档名，用于从数据库加载和保存存档
#     - archive_meta: 当前存档的元配置（临时缓存，未保存前不会写入数据库）
#     - records: 当前存档的所有记录（列表，临时缓存，未保存前不会写入数据库）
# """
if "archive_meta" not in st.session_state:
    st.session_state.archive_meta = create_empty_archive_meta()
if "records" not in st.session_state:
    st.session_state.records = []
if "generate_setting" not in st.session_state:
    st.session_state.generate_setting = {
        "clip_prefix": "Clip",
        "auto_index": True,
        "auto_all_perfect": True
    }

# 存档加载或新建存档部分
if 'username' not in st.session_state:
    st.warning("请先在上方设定您的用户名。")
    st.stop()
else:
    username = st.session_state.username

with st.container(border=True):
    st.write(f"当前用户名: **{username}**")
    archives = db_handler.get_user_save_list(username)
    
    if not archives:
        st.warning("未找到任何存档。请先新建一个存档。")
    else:
        archive_names = [a['archive_name'] for a in archives]
        try:
            current_archive_index = archive_names.index(st.session_state.get('archive_name'))
        except (ValueError, TypeError):
            current_archive_index = 0
        
        st.markdown("##### 加载本地存档")
        selected_archive_name = st.selectbox(
            "选择一个存档进行编辑",
            archive_names,
            index=current_archive_index
        )
        if st.button("加载此存档进行编辑"):
        
            simple_record_data = db_handler.load_archive_records(username, selected_archive_name)           
            st.session_state.records = expand_records_data(simple_record_data)

            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                updated_game_type = archive_data.get("game_type", "maimai")
                st.session_state.archive_meta = {
                    "game_type": updated_game_type,
                    "sub_type": archive_data.get("sub_type", "custom"),
                    "game_version": archive_data.get("game_version", "latest"),
                    "rating": archive_data.get("rating_mai", 0) if updated_game_type == "maimai" else archive_data.get("rating_chu", 0.0)
                }
                st.session_state.archive_name = selected_archive_name
                st.success(f"已加载存档 **{selected_archive_name}** ，共 {len(st.session_state.records)} 条记录。")
                st.rerun()
            else:
                st.error("加载存档数据失败。")

    st.markdown("##### 从0开始新建存档")
    st.markdown("> 注意：新建存档会刷新本页面中任何未保存的修改，如有正在编辑的存档，请先保存更改！")

    with st.container(border=True):
        st.write("新建存档选项")
        st.session_state.archive_meta['game_type'] = st.radio(
            "选择存档游戏类型",
            options=["maimai", "chunithm"],
            index=0,
            horizontal=True
        )
        st.session_state.archive_meta['sub_type'] = st.radio(
            "存档记录顺序（best：倒序， custom：正序）", 
            options=["custom", "best"],
            index=1,
            horizontal=True
        )
        with st.expander("其他选项", expanded=False):
            st.session_state.archive_meta['game_version'] = st.selectbox(
                "存档游戏版本（默认与数据库保持最新）",
                options=["latest"],
                index=0
            )
            st.session_state.archive_meta['rating'] = st.text_input(
                "存档Rating值（可选）",
                value=st.session_state.archive_meta.get('rating', 0)
            )

    if st.button("新建空白存档"):
        archive_id, archive_name = db_handler.create_new_archive(username, sub_type="custom")
        st.session_state.archive_name = archive_name
        st.session_state.records = []
        st.success(f"已创建并加载新的空白存档: **{archive_name}**")
        st.rerun()

# 存档记录编辑部分
if 'archive_name' in st.session_state and st.session_state.archive_name:
    st.subheader(f"正在编辑: {st.session_state.archive_name}")
    cur_game_type = st.session_state.archive_meta.get("game_type", "maimai")
    st.markdown(f"> 当前存档游戏类型: **{cur_game_type}**")

    with st.expander("添加或修改记录", expanded=True):
        st.markdown("#### 添加新记录")
        with st.expander("添加记录设置", expanded=False):
            st.session_state.generate_setting['clip_prefix'] = st.text_input("抬头标题前缀", value="Clip")
            st.session_state.generate_setting['auto_index'] = st.checkbox("自动添加序号", value=True)
            st.session_state.generate_setting['auto_all_perfect'] = st.checkbox("自动AP", value=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            # Search and Add
            level_label_options = level_label_lists.get(cur_game_type,
                                                        ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"])
            level_label = st.radio("选择难度", level_label_options, index=3, horizontal=True)
            level_index = level_label_to_index(cur_game_type, level_label)
            search_result = st_searchbox(
                lambda q: search_songs(q, songs_data, cur_game_type, level_index),
                placeholder="输入关键词搜索歌曲 (支持：歌曲名 / 曲师名 / 歌曲别名)",
                key="searchbox"
            )
        with col2:
            st.write("") # Spacer
            st.write("") # Spacer
            if st.button("➕ 添加选中歌曲", disabled=not search_result, width='stretch'):
                print(f"Search result: {search_result}")
                new_index = len(st.session_state.records) + 1
                new_record = create_empty_record(search_result, game_type=cur_game_type, index=new_index)
                st.session_state.records.append(new_record)
                st.success("已添加空白记录")

        record_count_placeholder = st.empty()
        update_records_count(record_count_placeholder)  # 更新记录数量的显示

        st.markdown("#### 修改当前记录")
        record_grid = st.container()
        update_record_grid(record_grid, record_count_placeholder)  # 更新记录表格的显示
    
    with st.expander("修改存档基本信息", expanded=False):
        st.session_state.archive_meta['sub_type'] = st.radio(
            "修改存档记录顺序（best：倒序， custom：正序）", 
            options=["custom", "best"],
            index=1 if st.session_state.archive_meta["sub_type"] == "custom" else 0,
            horizontal=True
        )
        with st.expander("其他选项", expanded=False):
            st.warning("修改存档类型会清空当前存档的所有记录，请谨慎操作！")
            st.session_state.archive_meta['game_type'] = st.radio(
                "修改存档类型",
                options=["maimai", "chunithm"],
                index=0 if st.session_state.archive_meta["game_type"] == "maimai" else 1,
                horizontal=True
            )
            st.session_state.archive_meta['game_version'] = st.selectbox(
                "修改存档游戏版本（默认与数据库保持最新）",
                options=["latest"],
                index=0
            )
            st.session_state.archive_meta['rating'] = st.text_input(
                "修改存档Rating值",
                value=st.session_state.archive_meta.get('rating', 0)
            )
        if st.button("保存更改"):
            save_current_archive()
            st.success("存档信息已保存")
            st.rerun()

    with st.expander("更改记录排序", expanded=True):
        st.write("拖动下面的列表，以调整记录的顺序")
        # 用于排序显示的记录（字符串）
        display_tags = []
        for i, record in enumerate(st.session_state.records):
            read_string = get_chart_info_str(record, game_type=cur_game_type)
            display_tags.append(f"(#{i+1}) {read_string}")

        simple_style = """
        .sortable-component {
            background-color: #F6F8FA;
            font-size: 16px;
            counter-reset: item;
        }
        .sortable-item {
            background-color: black;
            color: white;
        }
        """
        
        # 使用streamlit_sortables组件实现拖拽排序
        with st.container(border=True):
            sorted_tags = sort_items(
                display_tags,
                direction="vertical",
                custom_style=simple_style
            )

        if sorted_tags:
            st.session_state.sortable_records = sorted_tags
            sorted_records = []
            for tag in sorted_tags:
                # 提取索引
                match = re.search(r'\(#(\d+)\)', tag)
                if not match:
                    raise ValueError(f"Unable to match index from string {tag}")
                index = int(match.group(1)) - 1
                # 根据索引获取记录
                sorted_records.append(st.session_state.records[index])

            # st.write("Debug: sorted records")
            # st.write(sorted_records)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("应用排序更改"):
                    st.session_state.records = sorted_records
                    # 更改排序后需要保存到文件
                    save_current_archive()
                    st.rerun()
            with col2:
                if st.button("同步抬头标题后缀与当前排序一致",
                            help="仅在勾选了自动编号的情况下生效（请先应用排序更改，再点击按钮同步）",
                            disabled=not st.session_state.generate_setting.get("auto_index", False)):
                    # （手动）同步clip name
                    for i, record in enumerate(st.session_state.records):
                        record["clip_name"] = f"{st.session_state.generate_setting['clip_prefix']}_{i+1}"
                    save_current_archive()
                    st.rerun()

    # 导航功能按钮
    with st.container(border=True):       
        if st.button("继续下一步"):
            save_current_archive()
            st.session_state.data_updated_step1 = True
            st.switch_page("st_pages/Generate_Pic_Resources.py")