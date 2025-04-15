import streamlit as st
import os
import re
import json
from json import JSONEncoder
import traceback
from copy import deepcopy
from datetime import datetime
import pandas as pd
from utils.PathUtils import *
from utils.PageUtils import DATA_CONFIG_VERSION, LEVEL_LABELS, format_record_songid, load_full_config_safe, remove_invalid_chars, open_file_explorer
from utils.DataUtils import search_songs
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

st.header("创建自定义乐曲信息存档")

class IntKeepingEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, int):
            return int(obj)
        return super().default(obj)

# 加载歌曲数据
@st.cache_data
def load_songs_data():
    try:
        with open("./music_metadata/maimaidx/songs.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载歌曲数据失败: {e}")
        return []
    
# 加载歌曲数据
songs_data = load_songs_data()
maimai_level_label_list = list(LEVEL_LABELS.values())

# 创建空白记录模板
def create_empty_record(index):
    prefix = st.session_state.generate_setting.get("clip_prefix", "Clip")
    add_name_index = st.session_state.generate_setting.get("auto_index", True)
    auto_all_perfect = st.session_state.generate_setting.get("auto_all_perfect", True)
    return {
        "clip_id": f"clip_{index}",
        "clip_name": f"{prefix}_{index}" if add_name_index else prefix,
        "song_id": -1,
        "title": "",
        "type": "DX",
        "level_label": "Master",
        "level_index": 3,
        "level": "0",
        "ds": 0.0,
        "achievements": 101.0000 if auto_all_perfect else 0.0,
        "fc": "app" if auto_all_perfect else "",
        "fs": "fsdp" if auto_all_perfect else "",
        "ra": 0,
        "rate": "sssp" if auto_all_perfect else "d",
        "dxScore": 0,
        "playCount": 0
    }


# 创建空白配置模板
def create_empty_config(username):
    return {
        "version": DATA_CONFIG_VERSION,
        "type": "maimai",
        "sub_type": "custom",
        "username": username,
        "rating": 0,
        "length_of_content": 0,
        "records": []
    }


# 从歌曲数据创建记录
def create_record_from_song(metadata, level_label, index, game_type="maimaidx"):
    song_type = metadata.get("type", "1")
    song_level_index = maimai_level_label_list.index(level_label)
    auto_all_perfect = st.session_state.generate_setting.get("auto_all_perfect", True)

    # if index is out of bounds(For Re:MASTER), use last item(MASTER)
    if song_level_index < len(metadata["charts"]):
        song_charts_metadata = metadata["charts"][song_level_index]
    else:
        song_charts_metadata = metadata["charts"][-1]
        song_level_index = 3
        level_label = maimai_level_label_list[song_level_index]
    song_ds = song_charts_metadata.get("level", 0)
    notes_list = [note for note in song_charts_metadata.get("notes", [0]) if note is not None]
    record = create_empty_record(index)
    match song_type:
        case 1:
            record["type"] = "DX"
        case 0:
            record["type"] = "SD"
        case _:
            song_type = "DX"
    record["title"] = metadata.get("name", "")
    record["level_label"] = level_label
    record["level_index"] = song_level_index
    record["level"] = parse_level(song_ds)
    record["ds"] = song_ds
    record["ra"] = compute_rating(song_ds, record.get("achievements", 0))
    record["dxScore"] = sum(notes_list) * 3 if auto_all_perfect else 0

    # 处理 song_id
    song_id = metadata["id"]
    print(song_id)
    record["song_id"] = format_record_songid(record, song_id)
    # print(record)
    return record


# 读取存档config文件
def load_config_from_file(username, save_id):
    save_paths = get_data_paths(username, save_id)
    config_file = save_paths['data_file']
    try:
        # 读取存档时，检查存档文件版本，若为旧版本尝试自动更新
        content = load_full_config_safe(config_file, username)
        return content
    except FileNotFoundError:
        return None


# 保存配置到文件
def save_config_to_file(username, save_id, config):
    save_paths = get_data_paths(username, save_id)
    save_dir = os.path.dirname(save_paths['data_file'])
    os.makedirs(save_dir, exist_ok=True)
    
    with open(save_paths['data_file'], 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4, cls=IntKeepingEncoder)
    
    return save_paths


def save_custom_config():
    # 更新配置
    st.session_state.custom_config["records"] = st.session_state.records
    st.session_state.custom_config["length_of_content"] = len(st.session_state.records)
    # 保存当前配置到文件
    save_paths = save_config_to_file(st.session_state.username, st.session_state.save_id, st.session_state.custom_config)
    st.success(f"已保存到当前存档! ")
    return save_paths


@st.dialog("编辑存档基本信息")
def edit_config_info():
    current_config = st.session_state.custom_config
    st.write(f"用户名：{st.session_state.username}，存档时间：{st.session_state.save_id}")
    game_type = st.radio(
        "选择存档游戏类型",
        options=["maimai"],
        index= 0 if current_config["type"] == "maimai" else 0,
    )
    sub_type = st.radio(
        "是否为BestXX存档（若选择为best，则视频渲染将倒序进行）", 
        options=["custom", "best"],
        index= 1 if current_config["sub_type"] in ["ap", "best"] else 0,
    )
    rating = st.number_input(
        "Rating 值（可选）",
        value=current_config.get("rating", 0),
        min_value=0,
        max_value=20000
    )

    if st.button("保存"):
        current_config["game_type"] = game_type
        current_config["sub_type"] = sub_type
        current_config["rating"] = rating
        
        st.session_state.custom_config = current_config
        save_custom_config()
        st.rerun()
    if st.button("取消"):
        st.rerun()


@st.dialog("清空数据确认")
def clear_data_confirmation(opration_name, opration_func):
    st.write(f"确定要{opration_name}吗？此操作不可撤销！")
    if st.button("确认"):
        opration_func()
        st.rerun()
    if st.button("取消"):
        st.rerun()

def update_records_count(placeholder):
    placeholder.write(f"当前记录数量: {len(st.session_state.records)}")


def update_record_grid(grid, external_placeholder):
    with grid.container(border=True):
        # 显示和编辑现有记录
        if st.session_state.records:
            st.write("编辑记录表格")
            st.warning("注意：修改表格中的记录内容后，请务必点击‘保存编辑’按钮！未保存修改的情况下使用上方按钮添加新记录将会导致修改内容丢失！")
            
            # 创建数据编辑器
            edited_records = st.data_editor(
                st.session_state.records,
                column_order=["clip_name", "song_id", "title", "type", "level_label",
                            "ds", "achievements", "fc", "fs", "ra", "rate", "dxScore", "playCount"],
                column_config={
                    "clip_name": "抬头标题",
                    "song_id": "曲ID",
                    "title": "曲名",
                    "type": st.column_config.SelectboxColumn(
                        "类型",
                        options=["SD", "DX"],
                        width=60,
                        required=True
                    ),
                    "level_label": st.column_config.SelectboxColumn(
                        "难度",
                        options=maimai_level_label_list,
                        width=100,
                        required=True,
                    ),
                    "ds": st.column_config.NumberColumn(
                        "定数",
                        min_value=1.0,
                        max_value=15.0,
                        format="%.1f",
                        width=60,
                        required=True
                    ),
                    "achievements": st.column_config.NumberColumn(
                        "达成率",
                        min_value=0.0,
                        max_value=101.0,
                        format="%.4f",
                        required=True
                    ),
                    "fc": st.column_config.SelectboxColumn(
                        "FC标",
                        options=["", "fc", "fcp", "ap", "app"],
                        width=60,
                        required=False
                    ),
                    "fs": st.column_config.SelectboxColumn(
                        "Sync标",
                        options=["", "sync", "fs", "fsp", "fsd", "fsdp"],
                        width=60,
                        required=False
                    ),
                    "ra": st.column_config.NumberColumn(
                        "单曲Ra",
                        format="%d",
                        width=65,
                        required=True
                    ),
                    "rate": st.column_config.SelectboxColumn(
                        "评级",
                        options=["d", "c", "b", "bb", "bbb", "a", "aa", "aaa", "s", "sp", "ss", "ssp", "sss", "sssp"],
                        width=65,
                        required=True
                    ),
                    "dxScore": st.column_config.NumberColumn(
                        "DX分数",
                        format="%d",
                        width=80,
                        required=True
                    ),
                    "playCount": st.column_config.NumberColumn(
                        "游玩次数",
                        format="%d",
                        required=False
                    )
                },
                num_rows="dynamic",
                height=400,
                use_container_width=True
            )
            
            # 更新记录
            if st.button("保存编辑"):
                if edited_records is not None:
                    st.session_state.records = edited_records
                    save_custom_config()
                    update_records_count(external_placeholder)  # 更新外部记录数量的显示

            # 记录管理按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("重置所有记录的成绩数据"):
                    clear_data_confirmation(
                        "清零所有记录的成绩数据", 
                        clear_all_records_achievement
                    )
            
            with col2:
                if st.button("清空所有记录"):
                    clear_data_confirmation(
                        "清空所有记录",
                        clear_all_records
                    )
        else:
            st.write("当前没有记录，请添加记录。")


def search_music_metadata(search_keyword):
    return search_songs(search_keyword, songs_data)


def search_and_add_record() -> list:
    with st.container():
        level_label = st.radio(
            "要搜索谱面的难度分类",
            help="请注意，如果搜索到的乐曲没有Re:MASTER谱面，将使用其MASTER谱面数据填充记录",
            options=maimai_level_label_list,
            index=3,
            horizontal=True,
        )

    selected_value = st_searchbox(
        search_music_metadata,
        placeholder="输入歌曲名称关键词或ID进行搜索",
        key="searchbox",
        rerun_scope="app"
    )
    song_metadata = selected_value
    
    if st.button("添加此记录", disabled=not selected_value):
        try:
            new_record = create_record_from_song(
                song_metadata,
                level_label,
                len(st.session_state.records) + 1
            )
            st.session_state.records.append(new_record)
            st.toast(f"已添加歌曲{song_metadata['name']}的记录")
            st.rerun()
        except ValueError as e:
            st.error(f"添加记录失败: {e}")
            traceback.print_exc()


def clear_all_records_achievement():
    for record in st.session_state.records:
        record["achievements"] = 0.0
        record["fc"] = ""
        record["fs"] = ""
        record["ra"] = 0
        record["rate"] = "d"
        record["dxScore"] = 0
    save_custom_config()


def clear_all_records():
    st.session_state.records = []
    save_custom_config()


# 用户名输入部分
if not st.session_state.get("username", None):
    with st.container(border=True):
        st.subheader("输入用户名")
        input_username = st.text_input(
            "输入用户名（将为此用户名创建存档）"
        )
        
        if st.button("确定"):
            if not input_username:
                st.error("用户名不能为空！")
            else:
                # 处理用户名中的非法字符
                safe_username = remove_invalid_chars(input_username)
                if safe_username != input_username:
                    st.warning(f"用户名包含非法字符，已自动转换为: {safe_username}")
                root_save_dir = get_user_base_dir(safe_username)
                if not os.path.exists(root_save_dir):
                    os.makedirs(root_save_dir, exist_ok=True)
                # 创建一个文本文件用于保存raw_username
                raw_username_file = os.path.join(root_save_dir, "raw_username.txt")
                if not os.path.exists(raw_username_file):
                    with open(raw_username_file, 'w', encoding='utf-8') as f:
                        f.write(input_username)
                st.success("用户名已保存！")
                st.session_state.username = safe_username

# 初始化会话状态
if "custom_config" not in st.session_state:
    st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))

if "records" not in st.session_state:
    st.session_state.records = []

if "save_id" not in st.session_state:
    st.session_state.save_id = ""

if "generate_setting" not in st.session_state:
    st.session_state.generate_setting = {}

if st.session_state.get("username", None):
    username = st.session_state.username
    with st.container(border=True):
        st.write(f"当前用户名: {st.session_state.username}")
        # 选择当前用户的存档列表
        st.write("选择一个已有存档进行编辑")
        versions = get_user_versions(username)
        if versions:
            with st.container(border=True):
                st.write(f"新获取的存档可能无法立刻显示在下拉栏中，单击任一其他存档即可进行刷新。")
                selected_save_id = st.selectbox(
                    "选择存档",
                    versions,
                    format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
                )
                if st.button("加载此存档（只需要点击一次！）"):
                    if selected_save_id:
                        st.session_state.save_id = selected_save_id
                        g_setting = load_config_from_file(username, selected_save_id)
                        if not g_setting:
                            st.warning("此存档内容为空，请先保存存档！")
                            st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))
                            st.session_state.records = []
                        else:
                            st.session_state.custom_config = g_setting
                            st.session_state.records = deepcopy(g_setting.get("records", []))
                            st.success(f"已加载存档！用户名：{username}，存档时间：{selected_save_id}")
                    else:
                        st.error("无效的存档路径！")
        else:
            st.warning("未找到本用户的任何存档，请尝试获取存档或新建空白存档！")

        st.write("或者，新建一个空白存档")
        if st.button("新建空白存档"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # 从存档路径得到新存档的时间戳
            os.makedirs(save_dir, exist_ok=True) # 新建存档文件夹
            st.session_state.save_id = save_id
            st.success(f"已新建空白存档！用户名：{username}，存档时间：{save_id}")
            st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))
            st.session_state.records = []

if st.session_state.get("username", None) and st.session_state.get("save_id", None):
    # 编辑存档的基本信息
    st.write("点击下面的按钮，编辑本存档的基本信息")
    if st.button("编辑存档基本信息"):
        edit_config_info()

    # 编辑存档的记录信息
    st.subheader("编辑歌曲记录信息")
    with st.container(border=True):

        with st.expander("添加记录设置", expanded=True):
            g_setting = st.session_state.generate_setting
            clip_prefix = st.text_input(
                "自定义记录的抬头标题（显示在视频页右上方，默认为Clip）",
                value=g_setting.get("clip_prefix", "Clip")
            )
            auto_index = st.checkbox(
                "自动编号",
                help="勾选后自动为记录的抬头添加尾缀编号，如Clip 1, Clip 2 ...",
                value=g_setting.get("auto_index", False)
            )
            auto_all_perfect = st.checkbox(
                "自动填充理论值成绩",
                value=g_setting.get("auto_all_perfect", True)
            )
            st.session_state.generate_setting["clip_prefix"] = clip_prefix
            st.session_state.generate_setting["auto_index"] = auto_index
            st.session_state.generate_setting["auto_all_perfect"] = auto_all_perfect

        with st.container(border=True):
            st.write("搜索歌曲并添加记录")
            search_and_add_record()

        with st.container(border=True):
            st.write("添加空白记录")
            if st.button("添加一条空白记录"):
                new_record = create_empty_record(len(st.session_state.records) + 1)
                st.session_state.records.append(new_record)
                st.success("已添加空白记录")

        record_count_placeholder = st.empty()
        update_records_count(record_count_placeholder)  # 更新记录数量的显示

        record_grid = st.container()
        update_record_grid(record_grid, record_count_placeholder)  # 更新记录表格的显示

    with st.expander("更改记录排序", expanded=True):
        st.write("拖动下面的列表，以调整记录的顺序")
        # 用于排序显示的记录（字符串）
        display_tags = []
        for i, record in enumerate(st.session_state.records):
            read_string = f"{record['title'] or '无曲目'} | {record['level_label'] or '无难度'} [{record['type'] or '-'}]"
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
                    # 需要同步clip id
                    for i, record in enumerate(sorted_records):
                        record["clip_id"] = f"clip_{i+1}"
                    st.session_state.records = sorted_records
                    # 更改排序后需要保存到文件
                    save_custom_config()
                    st.rerun()
            with col2:
                if st.button("同步抬头标题后缀与当前排序一致",
                            help="仅在勾选了自动编号的情况下生效（请先应用排序更改，再点击按钮同步）",
                            disabled=not st.session_state.generate_setting.get("auto_index", False)):
                    # （手动）同步clip name
                    for i, record in enumerate(st.session_state.records):
                        record["clip_name"] = f"{st.session_state.generate_setting['clip_prefix']}_{i+1}"
                    save_custom_config()
                    st.rerun()

    # 导航功能按钮
    with st.container(border=True):
        if st.session_state.save_id and st.button("打开存档文件夹"):
            version_dir = get_user_version_dir(st.session_state.username, st.session_state.save_id)
            if os.path.exists(version_dir):
                absolute_path = os.path.abspath(version_dir)
                open_file_explorer(absolute_path)
        
        if st.button("继续下一步"):
            st.session_state.data_updated_step1 = True
            st.switch_page("st_pages/Generate_Pic_Resources.py")