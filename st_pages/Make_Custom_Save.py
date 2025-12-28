import streamlit as st
import os
import re
import json
import ast
import traceback
from copy import deepcopy
from utils.PathUtils import *
from utils.PageUtils import get_db_manager, process_username, get_game_type_text
from db_utils.DatabaseDataHandler import get_database_handler
from utils.DataUtils import load_metadata, search_songs, level_label_to_index, chart_type_value2str
from utils.dxnet_extension import compute_chunithm_rating, compute_rating

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

# 加载歌曲数据（根据游戏类型）
@st.cache_data
def get_songs_data(game_type="maimai"):
    return load_metadata(game_type=game_type)

# 获取当前游戏类型（从session_state或默认值）
def get_current_game_type():
    """获取当前游戏类型"""
    # 优先从session_state的game_type获取
    if 'game_type' in st.session_state:
        return st.session_state.game_type
    # 尝试从archive_meta获取
    elif 'archive_meta' in st.session_state:
        return st.session_state.archive_meta.get('game_type', 'maimai')
    # 尝试从数据库加载
    elif 'username' in st.session_state and 'archive_name' in st.session_state:
        try:
            archive_meta = db_handler.load_archive_metadata(
                st.session_state.username, 
                st.session_state.archive_name
            )
            return archive_meta.get('game_type', 'maimai')
        except:
            return 'maimai'
    else:
        return 'maimai'  # 默认值


@st.cache_data
def get_chart_info_from_db(chart_id):
    """从数据库中获取乐曲（谱面）信息"""
    return db_handler.load_chart_by_id(chart_id=chart_id)

# --- Data Helper Functions ---

def augment_records_with_chart_data(simple_records):
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
    # 将records按order_in_archive排序
    expanded_records.sort(key=lambda r: r.get('order_in_archive', 0))
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
    
    # 自动填充理论值成绩
    try:
        ds = float(chart_data.get('difficulty', 0))
    except (ValueError, TypeError):
        ds = 0.0

    match game_type:
        case "maimai":
            max_acc, max_dx_score = (101.0, chart_data.get('max_dx_score', 0)) if auto_all_perfect else (0.0, 0)
            record_template.update({
                "achievement": max_acc,
                "fc_status": "app" if auto_all_perfect else "",
                "fs_status": "fsdp" if auto_all_perfect else "",
                "dx_rating": compute_rating(ds=ds, score=max_acc) if auto_all_perfect else 0,
                "dx_score": max_dx_score,
            })
        case "chunithm":
            max_score = 1010000 if auto_all_perfect else 0
            record_template.update({
                "achievement": max_score,
                "fc_status": "ajc" if auto_all_perfect else "",
                "fs_status": "fcr" if auto_all_perfect else "",
                "chuni_rating": compute_chunithm_rating(ds=ds, score=max_score) if auto_all_perfect else 0.0,
            })
        case _:
            raise ValueError(f"Unsupported game type: {game_type}")
    
    return record_template


def save_current_metadata():
    """Saves the current archive metadata to the database."""
    # 检查：是否修改了存档类型
    if 'username' in st.session_state and 'archive_name' in st.session_state and 'archive_meta' in st.session_state:
        cur_game_type = db_handler.load_archive_metadata(
            st.session_state.username, st.session_state.archive_name
        ).get("game_type", "maimai")
        to_save_game_type = st.session_state.archive_meta.get("game_type", "maimai")
        if cur_game_type != to_save_game_type:
            confirm_alter_game_type(cur_game_type, to_save_game_type)
        else:
            update_metadata_to_db()
    else:
        st.error("无法保存，未加载有效的用户或存档。")

def save_current_archive():
    """Saves the current archive records to the database."""
    # 更新所有记录
    update_records_to_db()


def update_metadata_to_db():
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


def update_records_to_db():
    """Saves the current state of records in the session to the database."""
    if 'username' in st.session_state and 'archive_name' in st.session_state:
        try:
            to_save_records = deepcopy(st.session_state.records)
            # 按照点击保存按钮时的记录顺序更新order_in_archive
            for i, record in enumerate(to_save_records):
                record['order_in_archive'] = i
            db_handler.update_archive_records(
                st.session_state.username,
                to_save_records,
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
    st.write(f"确定要{title}吗？此操作在点击“提交存档修改”前不会影响数据库。")
    if st.button("确认清空"):
        clear_function()
        st.rerun()
    if st.button("取消"):
        st.rerun()

@st.dialog("修改存档类型确认")
def confirm_alter_game_type(cur_game_type, to_save_game_type):
    st.write(f"确定要将存档类型从 **{cur_game_type}** 修改为 **{to_save_game_type}** 吗？此修改将清空当前存档的所有记录，且不可撤销！")
    if st.button("确认修改"):
        st.session_state.records = []
        update_metadata_to_db()
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
    if game_type == "maimai":
        return f"{title} {split} {level_label} [{chart_type}]"
    else: 
        return f"{title} {split} {level_label}"


def get_showing_records(records, game_type="maimai"):
    """ 为记录添加字段，主要为chart_info，目的是为了在页面中显示曲目的相关信息 """
    ret_records = deepcopy(records)
    for r in ret_records:
        r['chart_info'] = get_chart_info_str(r, game_type=game_type, split='|')

    return ret_records

# --- Streamlit Page Components ---

def update_records_count(placeholder):
    placeholder.write(f"当前记录数量: {len(st.session_state.records)}")


def update_record_grid(grid, external_placeholder):

    def recover_edited_records(edited_df, game_type="maimai"):
        # 由于 st.data_editor 会将dict对象序列化，从组件df数据更新时需要反序列化chart_data
        to_update_records = deepcopy(edited_df)
        for r in to_update_records:
            # 还原chart_data
            r.pop('chart_info', None) # 清理chart_info

            chart_data = r.get('chart_data', {})
            if isinstance(chart_data, str):  # 反序列化解析chart_data
                try:
                    # 使用 ast.literal_eval 处理可能包含单引号的字符串
                    chart_data = ast.literal_eval(chart_data)
                    r['chart_data'] = chart_data
                except (ValueError, SyntaxError):
                    return "Invalid chart data occurs when trying to save edited records."

            # 自动计算和填充成绩相关信息
            difficulty_val = chart_data.get('difficulty')
            try:
                ds = float(difficulty_val)
            except (ValueError, TypeError):
                ds = 0.0
            if game_type == "maimai":
                # 计算dx_rating
                r['dx_rating'] = compute_rating(ds=ds, score=r.get('achievement', 0.0))
                # 如果是理论值成绩，填充dx_score
                if r.get('achievement', 0) >= 101.0:
                    r['dx_score'] = chart_data.get('max_dx_score', 0)
            if game_type == "chunithm":
                # 计算chuni_rating
                r['chuni_rating'] = compute_chunithm_rating(ds=ds, score=r.get('achievement', 0))
            
            # 确保play_count字段被保留（deepcopy应该已经保留了，但这里明确确保）
            if 'play_count' not in r and 'playCount' in r:
                r['play_count'] = r.get('playCount', 0)

        return to_update_records
        
    with grid.container(border=True):
        game_type = st.session_state.archive_meta.get("game_type", "maimai")

        # 显示和编辑现有记录
        if st.session_state.records:
            # 初始化显示数据：只在没有缓存时才调用 get_showing_records
            # 这样避免每次编辑都重新计算，导致 st.data_editor 状态重置
            if '_editor_showing_records' not in st.session_state or st.session_state.get('_force_refresh_editor', False):
                records_to_show = st.session_state.get('_pending_edited_records', st.session_state.records)
                st.session_state._editor_showing_records = get_showing_records(records_to_show, game_type=game_type)
                st.session_state._force_refresh_editor = False
            
            st.write("在此表格中编辑记录")
            st.warning("注意：添加、删除和修改记录内容后，请务必点击'提交存档修改'按钮！未保存修改的情况下刷新页面将导致修改内容丢失！")
            
            # 创建数据编辑器，使用稳定的 key 保持状态
            editor_key = f"record_editor_{game_type}"
            
            if game_type == "maimai":
                edited_records = st.data_editor(
                    st.session_state._editor_showing_records,
                    key=editor_key,
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
                            disabled=True,
                            help="你不需要填写此字段，它会根据达成率自动计算",
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
                    height=400
                )
            elif game_type == "chunithm":
                edited_records = st.data_editor(
                    st.session_state._editor_showing_records,
                    key=editor_key,
                    column_order=["clip_title_name", "chart_info", "score", "combo_type", "chain_type", "chuni_rating", "play_count"],
                    column_config={
                        "clip_title_name": "抬头标题",
                        "chart_info": "乐曲信息",
                        "score": st.column_config.NumberColumn(
                            "分数",
                            min_value=0,
                            max_value=1010000,
                            format="%d",
                            required=True
                        ),
                        "combo_type": st.column_config.TextColumn("FC标", width=80),
                        "chain_type": st.column_config.TextColumn("FullChain标", width=100),
                        "chuni_rating": st.column_config.NumberColumn(
                            "单曲Ra",
                            format="%.2f",
                            disabled=True,
                            width=75,
                            help="你不需要填写此字段，它会根据分数自动计算",
                            required=True
                        ),
                        "play_count": st.column_config.NumberColumn(
                            "游玩次数",
                            format="%d",
                            required=False
                        )
                    },
                    num_rows="dynamic",
                    height=400
                )
            else:
                raise ValueError(f"Unsupported game type: {game_type}")
            
            # st.data_editor 会自动管理状态，edited_records 就是最新的编辑结果
            # 不需要在这里做任何处理，只在提交时才处理

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

            # 确认提交按钮
            if st.button("提交存档修改"):
                # 从 st.data_editor 获取最终编辑结果并转换回内部格式
                if edited_records is not None and len(edited_records) > 0:
                    try:
                        recovered = recover_edited_records(edited_records, game_type=game_type)
                        if isinstance(recovered, list):
                            st.session_state.records = recovered
                            # 清除编辑器缓存，下次加载时重新生成显示数据
                            if '_editor_showing_records' in st.session_state:
                                del st.session_state._editor_showing_records
                            if '_pending_edited_records' in st.session_state:
                                del st.session_state._pending_edited_records
                    except Exception as e:
                        st.error(f"处理编辑数据时出错: {e}")
                        import traceback
                        st.error(traceback.format_exc())
                        return
                
                save_current_archive()
                update_records_count(external_placeholder)  # 更新外部记录数量的显示
                st.session_state._force_refresh_editor = True  # 标记需要刷新编辑器
                st.rerun()  # 只在提交时才刷新页面
        else:
            st.write("当前没有记录，请添加记录。")


def sort_session_records_partially(cur_game_type):
    """
    交换分表中Past和New两组记录的顺序。
    要求：records中必须恰好有两组连续的记录，一组以Past开头，另一组以New开头。
    返回：True表示成功交换，False表示格式不符合要求。
    """
    records = st.session_state.records
    if not records:
        return False
    
    # 获取前缀类型，不符合格式返回None
    def get_prefix(name):
        return "Past" if name.startswith("Past") else ("New" if name.startswith("New") else None)
    
    # 检查所有记录的前缀
    prefixes = [get_prefix(r.get("clip_title_name", "")) for r in records]
    if None in prefixes:
        return False
    
    # 找到第一个前缀变化的位置
    split_idx = next((i for i in range(1, len(prefixes)) if prefixes[i] != prefixes[0]), None)
    
    # 检查是否恰好分为两组且包含Past和New
    if split_idx is None or set(prefixes) != {"Past", "New"} or prefixes[split_idx:].count(prefixes[split_idx]) != len(prefixes) - split_idx:
        return False
    
    # 交换两组顺序
    st.session_state.records = records[split_idx:] + records[:split_idx]
    return True


def sort_session_records_standard(cur_game_type, sort_scope, sort_method, sort_order):
    """
    按选项对分表记录进行排序。
    参数：
        sort_scope: 0=仅PastBest, 1=仅NewBest, 2=整个分表
        sort_method: 0=达成率, 1=单曲Rating, 2=定数
        sort_order: 0=降序, 1=升序
    返回：True表示成功，False表示格式不符合要求（仅部分排序时）
    """
    records = st.session_state.records
    if not records:
        return False
    
    # 确定排序键
    def get_sort_key(record):
        if sort_method == 0:  # 达成率
            return record.get('achievement', 0)
        elif sort_method == 1:  # 单曲Rating
            return record.get('dx_rating' if cur_game_type == 'maimai' else 'chuni_rating', 0)
        else:  # 定数
            return record.get('chart_data', {}).get('difficulty', 0)
    
    reverse = (sort_order == 0)  # 0=降序
    
    # 整个分表排序
    if sort_scope == 2:
        st.session_state.records = sorted(records, key=get_sort_key, reverse=reverse)
        return True
    
    # 部分排序：检查格式并找到分组
    target_prefix = "Past" if sort_scope == 0 else "New"
    
    def get_prefix(name):
        return "Past" if name.startswith("Past") else ("New" if name.startswith("New") else None)
    
    prefixes = [get_prefix(r.get("clip_title_name", "")) for r in records]
    if None in prefixes:
        return False
    
    # 找到目标前缀的连续区间
    start_idx = end_idx = None
    for i, p in enumerate(prefixes):
        if p == target_prefix:
            if start_idx is None:
                start_idx = i
            end_idx = i + 1
        elif start_idx is not None:
            # 目标组已结束，检查后续是否还有目标前缀（不连续）
            if target_prefix in prefixes[i:]:
                return False
            break
    
    # 检查是否找到至少2条目标记录
    if start_idx is None or (end_idx - start_idx) < 2:
        return False
    
    # 对目标区间排序
    target_group = sorted(records[start_idx:end_idx], key=get_sort_key, reverse=reverse)
    st.session_state.records = records[:start_idx] + target_group + records[end_idx:]
    return True


def update_sortable_items(sort_grid):

    with sort_grid.container(border=True):
        st.write("手动排序")
        st.write("拖动下面的列表，以调整分表中记录的展示顺序")
        st.warning("注意：确认排序修改后请点击“应用排序更改”按钮，否则更改不会生效！")
        # 用于排序显示的记录（字符串）
        display_tags = []
        for i, record in enumerate(st.session_state.records):
            read_string = get_chart_info_str(record, game_type=cur_game_type)
            clip_name = record.get("clip_title_name", "")
            display_tags.append(f"{clip_name} | {read_string} (#{i+1})")

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
        with st.container():
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

            col1, col2 = st.columns(2)
            with col1:
                if st.button("应用排序更改", key="apply_sort_changes_manual"):
                    st.session_state.records = sorted_records
                    st.session_state._force_refresh_editor = True
                    save_current_archive()
                    st.rerun()
            with col2:
                if st.button("同步标题后缀与当前排序一致",
                            help="仅在勾选了自动编号的情况下生效",
                            disabled=not st.session_state.generate_setting.get("auto_index", False)):
                    st.session_state.records = sorted_records
                    # （手动）同步clip name
                    for i, record in enumerate(st.session_state.records):
                        record["clip_title_name"] = f"{st.session_state.generate_setting['clip_prefix']}_{i+1}"
                    st.session_state._force_refresh_editor = True
                    save_current_archive()
                    st.rerun()

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

def clear_all_records_achievement():    
    if st.session_state.archive_meta.get("game_type", "maimai") == "maimai":
        for record in st.session_state.records:
            record["achievements"] = 0.0
            record["fc_status"] = ""
            record["fs_status"] = ""
            record["dx_rating"] = 0
            record["dx_score"] = 0
    elif st.session_state.archive_meta.get("game_type", "maimai") == "chunithm":
        for record in st.session_state.records:
            record["score"] = 0
            record["combo_type"] = ""
            record["chain_type"] = ""
            record["chuni_rating"] = 0.0
    else:
        pass
    # 清除编辑器缓存，强制重新生成显示数据
    if '_editor_showing_records' in st.session_state:
        del st.session_state._editor_showing_records
    st.session_state._force_refresh_editor = True


def clear_all_records():
    st.session_state.records = []
    # 清除编辑器缓存
    if '_editor_showing_records' in st.session_state:
        del st.session_state._editor_showing_records

# =============================================================================
# Page layout starts here
# ==============================================================================

# Start with getting G_type from session state
G_type = st.session_state.get('game_type', 'maimai')

st.header("编辑自定义分表")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

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
    archives = db_handler.get_user_save_list(username, game_type=G_type)
    
    # 读取已有存档
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
            st.session_state.records = augment_records_with_chart_data(simple_record_data)

            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                updated_game_type = archive_data.get("game_type", "maimai")
                st.session_state.archive_meta = {
                    "game_type": updated_game_type,
                    "sub_type": archive_data.get("sub_type", "custom"),
                    "game_version": archive_data.get("game_version", "latest"),
                }
                st.session_state.archive_name = selected_archive_name
                st.success(f"已加载存档 **{selected_archive_name}** ，共 {len(st.session_state.records)} 条记录。")
                st.rerun()
            else:
                st.error("加载存档数据失败。")

    st.markdown("##### 从0开始新建存档")
    st.markdown("> 注意：新建存档会刷新本页面中任何未保存的修改，如有正在编辑的存档，请先保存更改！")

    with st.container(border=True):
        with st.expander("新建存档选项", expanded=False):
            st.session_state.archive_meta['game_version'] = st.selectbox(
                "存档游戏版本（默认与数据库保持最新）",
                options=["latest"],
                index=0
            )

        if st.button("新建空白存档"):
            archive_id, archive_name = db_handler.create_new_archive(username, sub_type="custom", game_type=G_type)
            st.session_state.archive_meta['game_type'] = G_type
            st.session_state.archive_name = archive_name
            st.session_state.records = []
            st.success(f"已创建并加载新的空白存档: **{archive_name}**")
            st.rerun()

# 存档记录编辑部分
if 'archive_name' in st.session_state and st.session_state.archive_name:
    st.subheader(f"正在编辑: {st.session_state.archive_name}")
    cur_game_type = G_type
    # st.markdown(f"> 当前存档游戏类型: **{cur_game_type}**")

    tab1, tab2, tab3 = st.tabs(["添加或修改记录", "更改分表排序", "修改存档其他信息"])

    with tab1:
        st.markdown("#### 添加新记录")
        with st.expander("添加记录设置", expanded=True):
            st.session_state.generate_setting['clip_prefix'] = st.text_input("抬头标题前缀", 
                                                                             help="生成视频时，此标题将展示在对应乐曲的画面上",
                                                                             value="Clip")
            st.session_state.generate_setting['auto_index'] = st.checkbox("自动为标题添加后缀序号", value=True)
            st.session_state.generate_setting['auto_all_perfect'] = st.checkbox("自动填充理论值成绩", value=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            # Search and Add
            level_label_options = level_label_lists.get(cur_game_type,
                                                        ["BASIC", "ADVANCED", "EXPERT", "MASTER", "RE:MASTER"])
            level_label = st.radio("选择难度", level_label_options, index=3, horizontal=True)
            level_index = level_label_to_index(cur_game_type, level_label)
            # 根据当前游戏类型动态加载歌曲数据
            current_songs_data = get_songs_data(cur_game_type)
            search_result = st_searchbox(
                lambda q: search_songs(q, current_songs_data, cur_game_type, level_index),
                placeholder="输入关键词搜索歌曲 (支持：歌曲名 / 曲师名 / 歌曲别名)",
                key="searchbox"
            )
        with col2:
            st.write("") # Spacer
            st.write("") # Spacer
            if st.button("➕ 添加选中歌曲", disabled=not search_result):
                print(f"Search result: {search_result}")
                new_index = len(st.session_state.records) + 1
                new_record = create_empty_record(search_result, game_type=cur_game_type, index=new_index)
                st.session_state.records.append(new_record)
                # 清除编辑器缓存，下次显示时会包含新添加的记录
                if '_editor_showing_records' in st.session_state:
                    del st.session_state._editor_showing_records
                st.session_state._force_refresh_editor = True
                st.success("已添加空白记录")

        record_count_placeholder = st.empty()
        update_records_count(record_count_placeholder)  # 更新记录数量的显示

        st.markdown("#### 修改当前分表")
        record_grid = st.container()
        update_record_grid(record_grid, record_count_placeholder)  # 更新记录表格的显示

    with tab2:
        def apply_sort_and_save():
            st.session_state._force_refresh_editor = True
            save_current_archive()
            st.rerun()
        text_pastbest = "B35" if cur_game_type == "maimai" else "B30"
        text_newbest = "B15" if cur_game_type == "maimai" else "N20"
        error_text = f"""当前分表格式无法应用快速排序，要应用{text_pastbest}/{text_newbest}排序 \
            需要保留自动生成的标题名称(PastBest/NewBest)，否则请选择对象为整个分表。"""
        sort_options = [f"仅{text_pastbest}", f"仅{text_newbest}", f"整个分表（可能打乱{text_pastbest}和{text_newbest}分组）"]
        sort_method_options = ["🎯 达成率", "⭐ 单曲Rating", "🎚️ 定数"]
        sort_up_options = ["降序", "升序"]
        with st.container(border=True):
            st.write("快速排序")
            with st.container(border=True):  
                sort_option = st.radio("选择排序对象", options=sort_options, index=0, horizontal=True)
                sort_method = st.radio("排序依据", options=sort_method_options, index=0, horizontal=True)
                sort_up = st.radio("排序顺序", options=sort_up_options, index=0, horizontal=True)
                if st.button("应用快速排序"):
                    success = sort_session_records_standard(
                        cur_game_type,
                        sort_options.index(sort_option),
                        sort_method_options.index(sort_method),
                        sort_up_options.index(sort_up)
                    )
                    if not success:
                        st.error(error_text)
                    else:
                        apply_sort_and_save()
                # col1, col2, col3 = st.columns(3)
                # with col1:
                #     if st.button("🎯 按达成率降序排序"):
                #         st.session_state.records.sort(key=lambda r: r.get('achievement', 0), reverse=True)
                #         apply_sort_and_save()
                # with col2:
                #     if st.button("⭐ 按rating降序排序"):
                #         ra_key = 'dx_rating' if cur_game_type == 'maimai' else 'chuni_rating'
                #         st.session_state.records.sort(key=lambda r: r.get(ra_key, 0), reverse=True)
                #         apply_sort_and_save()
                # with col3:
                #     if st.button("🎚️ 按定数降序排序"):
                #         st.session_state.records.sort(key=lambda r: r.get('chart_data', {}).get('difficulty', 0), reverse=True)
                #         apply_sort_and_save()

            col4, col5 = st.columns(2)
            with col4:
                if st.button("🔁 反转整个分表排序"):
                    st.session_state.records.reverse()
                    apply_sort_and_save()
            with col5:
                if st.button(f"🔃 交换{text_pastbest}/{text_newbest}顺序"):
                    success = sort_session_records_partially(cur_game_type)
                    if not success:
                        st.error(error_text)
                    else:
                        apply_sort_and_save()

        st.divider() # 添加分割线
        sort_grid = st.container()
        update_sortable_items(sort_grid)

    with tab3:
        st.warning("更改存档类型会清空当前存档的所有记录，您需要重新在首页切换模式后编辑，请谨慎操作！")
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
        if st.button("提交修改"):
            save_current_metadata()

    # 导航功能按钮
    with st.container(border=True):       
        if st.button("继续下一步"):
            save_current_archive() # 导航离开页面前保存更改
            st.session_state.data_updated_step1 = True
            st.switch_page("st_pages/Generate_Pic_Resources.py")
