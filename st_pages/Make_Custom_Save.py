import streamlit as st
import os
import json
import traceback
from copy import deepcopy
from datetime import datetime
import pandas as pd
from utils.PathUtils import *
from utils.PageUtils import DATA_CONFIG_VERSION, remove_invalid_chars, open_file_explorer
from utils.dxnet_extension import get_rate

# 检查streamlit扩展组件安装情况
try:
    from streamlit_sortables import sort_items
except ImportError:
    st.error("缺少streamlit-sortables库，请安装该库以使用拖拽排序功能。")
    st.stop()

try:
    from streamlit_searchbox import st_searchbox
except ImportError:
    st.error("缺少streamlit-searchbox库，请安装该库以使用搜索功能。")
    st.stop()

st.header("创建自定义乐曲信息存档")

# 加载歌曲数据
@st.cache_data
def load_songs_data():
    try:
        with open("./music_metadata/maimaidx/songs.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载歌曲数据失败: {e}")
        return []

# 创建空白记录模板
def create_empty_record(index, prefix="Number"):
    return {
        "clip_id": f"{prefix}_{index}",
        "song_id": "",
        "title": "",
        "type": "DX",
        "level_label": "Master",
        "level_index": 3,
        "level": "0",
        "ds": 0.0,
        "achievements": 100.0000,
        "fc": "",
        "fs": "",
        "ra": 0,
        "rate": "sss",
        "dxScore": 0,
        "playCount": 0
    }

# 创建空白配置模板
def create_empty_config():
    return {
        "version": DATA_CONFIG_VERSION,
        "type": "maimai",
        "sub_type": "custom",
        "username": "",
        "rating": 0,
        "length_of_content": 0,
        "records": []
    }

# 搜索歌曲
def search_songs(keyword, songs_data):
    if not keyword or len(keyword) < 2:
        return []
    
    keyword = keyword.lower()
    results = []
    
    # 按歌名、艺术家、ID搜索
    for song in songs_data:
        song_id = str(song.get("id", ""))
        title = song.get("title", "").lower()
        artist = song.get("artist", "").lower()
        
        if (keyword in title or
            keyword in artist or
            keyword in song_id):
            results.append(song)
    
    # 限制结果数量
    return results[:20]

# 从歌曲数据创建记录
def create_record_from_song(song, index):
    song_type = "DX" if song.get("dx", False) else "SD"
    record = create_empty_record(index)
    record["song_id"] = song.get("id", "")
    record["title"] = song.get("title", "")
    record["type"] = song_type
    return record


# 读取存档config文件
def load_config_from_file(username, save_id):
    save_paths = get_data_paths(username, save_id)
    config_file = save_paths['data_file']
    
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
            return content
    else:
        return None


# 保存配置到文件
def save_config_to_file(username, save_id, config):
    save_paths = get_data_paths(username, save_id)
    save_dir = os.path.dirname(save_paths['data_file'])
    os.makedirs(save_dir, exist_ok=True)
    
    with open(save_paths['data_file'], 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    return save_paths

# 计算单曲评级
def calculate_record_fields(record):
    # 计算level
    ds_l, ds_p = str(float(record['ds'])).split('.')
    ds_p = int(ds_p[0])
    plus = '+' if ds_p > 6 else ''
    record['level'] = f"{ds_l}{plus}"
    
    # 计算rate
    record['rate'] = get_rate(float(record['achievements']))
    
    # 确保level_index正确
    REVERSE_LEVEL_LABELS = {"BASIC": 0, "ADVANCED": 1, "EXPERT": 2, "MASTER": 3, "RE:MASTER": 4}
    record['level_index'] = REVERSE_LEVEL_LABELS.get(record['level_label'].upper(), 3)
    
    # 确保数值字段是数字类型
    record['ra'] = int(record['ra'])
    record['achievements'] = float(record['achievements'])
    record['ds'] = float(record['ds'])
    record['dxScore'] = int(record['dxScore'])
    record['playCount'] = int(record['playCount'])
    
    return record

# 初始化会话状态
if "custom_config" not in st.session_state:
    st.session_state.custom_config = create_empty_config()

if "records" not in st.session_state:
    st.session_state.records = []

if "username" not in st.session_state:
    st.session_state.username = ""

if "save_id" not in st.session_state:
    st.session_state.save_id = ""

if "current_prefix" not in st.session_state:
    st.session_state.current_prefix = "Number"

# 加载歌曲数据
songs_data = load_songs_data()

@st.dialog("编辑存档基本信息")
def edit_config_info():
    current_config = st.session_state.custom_config
    st.write(f"用户名：{st.session_state.username}，存档时间：{st.session_state.save_id}")
    game_type = st.radio(
        "选择存档游戏类型",
        options=["maimai"],
        index= 0 if current_config["type"] == "maimai" else 0,
        format_func=lambda x: x.capitalize()
    )
    sub_type = st.radio(
        "是否为AP存档（可选，仅影响图片中AP图标的显示）", 
        options=["custom", "ap"],
        index= 1 if current_config["sub_type"] == "ap" else 0,
        format_func=lambda x: x.capitalize()
    )
    rating = st.number_input(
        "Rating 值（可选）",
        value=current_config.get("rating", 0),
        min_value=0,
        max_value=20000
    )
    clip_prefix = st.text_input(
        "每页记录标题的前缀（默认为number）",
        value=current_config.get("clip_prefix", "Number")
    )

    if st.button("保存"):
        current_config["game_type"] = game_type
        current_config["sub_type"] = sub_type
        current_config["rating"] = rating
        current_config["clip_prefix"] = clip_prefix
        
        st.session_state.custom_config = current_config
        st.success("已保存存档基本信息")
        st.rerun()
    if st.button("取消"):
        st.rerun()

def update_record_grid(placeholder):
    with placeholder.container():
        # 显示和编辑现有记录
        if st.session_state.records:
            st.write(f"当前记录数量: {len(st.session_state.records)}")
            
            # 创建数据编辑器
            edited_records = st.data_editor(
                st.session_state.records,
                column_order=["clip_id", "song_id", "title", "type", "level_label",
                            "ds", "achievements", "fc", "fs", "ra", "rate", "dxScore", "playCount"],
                column_config={
                    "clip_id": "编号",
                    "song_id": st.column_config.TextColumn("曲ID"),
                    "title": "曲名",
                    "type": st.column_config.SelectboxColumn(
                        "类型",
                        options=["SD", "DX"],
                        width=60,
                        required=True
                    ),
                    "level_label": st.column_config.SelectboxColumn(
                        "难度",
                        options=["Basic", "Advanced", "Expert", "Master", "Re:MASTER"],
                        width=100,
                        required=True
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
            if edited_records is not None:
                # 处理可能的删除记录情况
                if len(edited_records) < len(st.session_state.records):
                    st.session_state.records = edited_records
                    st.success("已删除记录")
                    st.rerun()
                else:
                    # 更新处理后的记录
                    updated_records = []
                    for i, record in enumerate(edited_records):
                        # 计算和更新相关字段
                        updated_record = calculate_record_fields(record)
                        updated_records.append(updated_record)
                    
                    st.session_state.records = updated_records
            
            # 记录管理按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("自动更新所有记录"):
                    updated_records = []
                    for record in st.session_state.records:
                        updated_record = calculate_record_fields(record)
                        updated_records.append(updated_record)
                    st.session_state.records = updated_records
                    st.success("已更新所有记录")
                    st.rerun()
            
            with col2:
                if st.button("清空所有记录"):
                    st.session_state.records = []
                    st.success("已清空所有记录")
                    st.rerun()
        else:
            st.write("当前没有记录，请添加记录。")

# 用户名输入部分
if not st.session_state.username:
    with st.container(border=True):
        st.subheader("输入用户名")
        input_username = st.text_input(
            "输入用户名（将为此用户名创建存档）",
            value=st.session_state.username if st.session_state.username else ""
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

if st.session_state.username:
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
                        current_config = load_config_from_file(username, selected_save_id)
                        if not current_config:
                            st.warning("此存档内容为空，请先保存存档！")
                        else:
                            st.session_state.custom_config = current_config
                            st.session_state.records = deepcopy(current_config.get("records", []))
                            st.success(f"已加载存档！用户名：{username}，存档时间：{selected_save_id}")
                            st.rerun()
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

if st.session_state.username and st.session_state.save_id:
    # 编辑存档的基本信息
    st.write("点击下面的按钮，编辑本存档的基本信息（如页面抬头标题等)")
    if st.button("编辑存档基本信息"):
        edit_config_info()

    # 编辑存档的记录信息
    st.subheader("编辑歌曲记录信息")
    with st.container(border=True):

        if st.button("搜索并添加一条歌曲记录"):
            pass

        if st.button("添加一条空白记录"):
            new_record = create_empty_record(len(st.session_state.records) + 1)
            st.session_state.records.append(new_record)
            st.success("已添加空白记录")

        record_detail_placeholder = st.empty()
        update_record_grid(record_detail_placeholder)

    st.subheader("编辑歌曲记录排序")
    with st.container(border=True):
        st.write("拖动下面的列表，以调整记录的顺序")
        # 准备简化版的记录数据用于排序显示
        # display_records = []
        # for i, record in enumerate(st.session_state.records):
        #     display_records.append({
        #         "id": i,
        #         "title": record["title"] or f"记录 #{i+1}",
        #         "type": record["type"],
        #         "level": record["level"],
        #         "ds": f"{record['ds']:.1f}",
        #         "achievements": f"{record['achievements']:.4f}",
        #         "ra": record["ra"]
        #     })
        
        # # 使用streamlit_sortables组件实现拖拽排序
        # with st.container(border=True):
        #     sorted_records = sort_items(
        #         display_records,
        #         key="id", 
        #         items_key="sortable_records",
        #         item_style={"padding": "5px", "border": "1px solid #ddd", "background": "#f1f1f1"},
        #         display=["title", "type", "level", "ds", "achievements", "ra"]
        #     )
            
        #     # 如果排序发生变化
        #     if sorted_records and "sortable_records" in st.session_state:
        #         # 根据排序后的顺序重建记录列表
        #         new_records = []
        #         for item in st.session_state.sortable_records:
        #             new_records.append(st.session_state.records[item["id"]])
                
        #         # 更新clip_id
        #         for i, record in enumerate(new_records, 1):
        #             prefix = "NewBest" if i <= 15 else "PastBest"
        #             idx = i if i <= 15 else i - 15
        #             record["clip_id"] = f"{prefix}_{idx}"
                
        #         if st.button("应用排序更改"):
        #             st.session_state.records = new_records
        #             st.success("记录排序已更新")
        #             st.rerun()

    # 保存配置
    with st.container(border=True):
        st.subheader("保存存档")

        if st.session_state.save_id and st.button("打开存档文件夹"):
            version_dir = get_user_version_dir(st.session_state.username, st.session_state.save_id)
            if os.path.exists(version_dir):
                absolute_path = os.path.abspath(version_dir)
                open_file_explorer(absolute_path)
        
        if st.button("保存修改到当前存档", disabled=not st.session_state.save_id):
            # 更新配置
            st.session_state.custom_config["records"] = st.session_state.records
            st.session_state.custom_config["length_of_content"] = len(st.session_state.records)
            
            # 保存到文件
            save_paths = save_config_to_file(st.session_state.username, st.session_state.save_id, st.session_state.custom_config)
            
            st.success(f"已保存到当前存档! 存档ID: {st.session_state.save_id}")
        
        if st.button("继续下一步"):
            st.session_state.data_updated_step1 = True
            st.switch_page("st_pages/Generate_Pic_Resources.py")