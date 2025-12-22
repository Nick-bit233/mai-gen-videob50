from importlib import metadata
from turtle import st
from typing import List
import json
import os
import requests
import base64
import hashlib
import struct
import random
from PIL import Image
from typing import Dict, Union, Optional

# 服务器bucket用于转存融合过的的metadata
BUCKET_ENDPOINT = "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com"
# 服务器函数计算用于代理获取需要开发者key的查分器api数据
FC_PROXY_ENDPOINT = "https://fish-usta-proxy-efexqrwlmf.cn-shanghai.fcapp.run"

# 第三方原始数据源api用于获取曲绘等CDN资源
LXNS_API_ENDPOINT = "https://assets.lxns.net"  # 落雪查分器api

def get_otoge_db_api_endpoint(game_type) -> str:
    return f"https://otoge-db.net/{game_type}/jacket"  # otoge-db api

def get_dxrating_api_endpoint(game_type: str) -> str:
    return "https://shama.dxrating.net/images/cover/v2"  # dxrating api

# --------------------------------------
# Data format grounding Helper methods
# --------------------------------------
def chart_type_value2str(value: int, game_type: str) -> str:
    """Convert chart type value to string representation."""
    if game_type == "maimai":
        match value:
            case 0:
                return "std"
            case 1:
                return "dx"
            case 2:
                return "utage"
            case _:
                return "unknown"
    elif game_type == "chunithm":
        match value:
            case 0:
                return "normal"
            case 1:
                return "we"
            case _:
                return "unknown"

def chart_type_str2value(str_type: str, fish_record_style: bool = False) -> int:
    """Determine chart type from record data."""
    if fish_record_style:
        match str_type:
            case "SD":
                return 0
            case "DX":
                return 1
            case _:
                return 0
    else:
        match str_type:
            case "std": # maimai
                return 0
            case "standard":
                return 0
            case "dx":
                return 1
            case "utage":
                return 2
            case "normal": # chuni
                return 0
            case "we":
                return 1
            case _:
                return 0

def level_label_to_index(game_type: str, label: str) -> int:
    """Convert level label to index."""
    if game_type == "maimai":
        match label.upper():
            case "BASIC":
                return 0
            case "ADVANCED":
                return 1
            case "EXPERT":
                return 2
            case "MASTER":
                return 3
            case "RE:MASTER":
                return 4
            case "REMASTER": # 兼容dxrating的元数据
                return 4
            case _:
                return 5
    elif game_type == "chunithm":
        match label.upper():
            case "BASIC":
                return 0
            case "ADVANCED":
                return 1
            case "EXPERT":
                return 2
            case "MASTER":
                return 3
            case "ULTIMA":
                return 4
            case _:
                return 5
    else:
        return -1

def level_index_to_label(game_type: str, index: int) -> str:
    """Convert level index to label."""
    if game_type == "maimai":
        match index:
            case 0:
                return "BASIC"
            case 1:
                return "ADVANCED"
            case 2:
                return "EXPERT"
            case 3:
                return "MASTER"
            case 4:
                return "RE:MASTER"
            case 5:
                return "UNKNOWN"
    elif game_type == "chunithm":
        match index:
            case 0:
                return "BASIC"
            case 1:
                return "ADVANCED"
            case 2:
                return "EXPERT"
            case 3:
                return "MASTER"
            case 4:
                return "ULTIMA"
            case 5:
                return "UNKNOWN"
    else:
        return "UNKNOWN"

def get_valid_time_range(s: Optional[int], e: Optional[int], 
                         default_duration: int = 10, default_start_interval = (15, 30) ):
    """ get a range of valid video start and end time, random value returned if null value input """
    if not (s or e) or (s < 0 or e < 0):  # 输入的时间不合法，随机初始化一组时间
        duration = default_duration
        clip_start_interval = default_start_interval
        start = random.randint(clip_start_interval[0], clip_start_interval[1])
        end = start + duration
    else:
        start, end = s, e
        if end <= 0: 
            end = 1
        # 如果起始时间大于等于结束时间，调整起始时间
        if start >= end:
            start = end - 1
    return start, end

def format_record_tag(game_type: str, clip_title_name: str, song_id: str, chart_type: int, level_index: int, song_name: str = None):
    level_label = level_index_to_label(game_type, level_index)
    if game_type == "maimai":
        return f"{clip_title_name}: {song_id} ({chart_type_value2str(chart_type, game_type)}) [{level_label}]"
    else:
        # 对于 Chunithm，优先使用 song_name，如果没有则使用 song_id
        display_name = song_name if song_name else song_id
        return f"{clip_title_name}: {display_name} [{level_label}]"

def get_record_tags_from_data_dict(records_data: List[Dict]) -> List[str]:
    """Get tags from record/chart group query data. These tags are used by st_page compoents for navigation to certain record"""
    ret_tags = []
    for r in records_data:
        game_type = r.get("game_type", "maimai")
        clip_title_name = r.get("clip_title_name", "")
        song_id = r.get("song_id", "")
        chart_type = r.get("chart_type", -1)
        level_index = r.get("level_index", -1)
        song_name = r.get("song_name", None)  # 获取曲名
        ret_tags.append(format_record_tag(game_type, clip_title_name, song_id, chart_type, level_index, song_name))
    return ret_tags

def chunithm_fc_status_to_label(fc_status: int) -> str:
    match fc_status:
        case "fullcombo":
            return "fc"
        case "alljustice":
            return "aj"
        case "alljusticecritical":  # lxns查分器返回的flag
            return "ajc"
        case "AJC":  # TODO: 检测水鱼查分器接口
            return "ajc"
        case _:
            return "none"
        
def chunithm_fs_status_to_label(source, fs_status: str) -> str:
    if source == "lxns":
        match fs_status:
            case "fullchain2":  # 金 FULL CHAIN
                return "fs"
            case "fullchain":   # 铂 FULL CHAIN
                return "ac"
            case _:
                return "none"
    if source == "fish":
        return 'none'  # 水鱼查分器暂时不提供该字段
    return "none"

# 已重构：现在从服务器融合数据源下载metadata
# --------------------------------------
# Metadata Helper methods
# --------------------------------------
def download_metadata(game_type="maimai") -> tuple[str, dict]:
    if game_type == "maimai":
        filename = "mai_fusion_data.json"
    elif game_type == "chunithm":
        filename = "chuni_fusion_data.json"
    else:
        raise ValueError("Unsupported game type for metadata download.")
    url = f"{BUCKET_ENDPOINT}/metadata_json/{filename}"
    response = requests.get(url)
    if response.status_code == 200:
        return filename, response.json()
    else:
        print(f"Failed to download metadata from {url}. Status code: {response.status_code}")
        raise FileNotFoundError
    
def load_metadata(game_type: str) -> dict:
    metadata_dir = './music_metadata/'
    if game_type == "maimai":
        json_path = os.path.join(metadata_dir, f"mai_fusion_data.json")
    elif game_type == "chunithm":
        json_path = os.path.join(metadata_dir, f"chuni_fusion_data.json")
    else:
        raise ValueError(f"Unsupported game type: {game_type}")
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Metadata file not found: {json_path}")

# --------------------------------------
# song_id 编码/解码方法（TODO：暂时弃用，需要重新设计）
# --------------------------------------
@DeprecationWarning
def encode_song_id(name, song_type):
    """
    Args:
        name (str): 歌曲名称
        song_type (int): 歌曲类型 (0, 1, 10, 11) = (SD, DX, 宴, 协)
        
    Returns:
        str: 紧凑的ID字符串
    """
    # 将类型转换为字节序列 (固定长度)
    type_bytes = struct.pack('<I', song_type)
    
    # 将名称转换为字节序列
    name_bytes = name.encode('utf-8')
    
    # 名称长度转为字节序列 (固定长度)
    name_len_bytes = struct.pack('<I', len(name_bytes))
    
    # 按照固定格式拼接字节序列: [类型][名称长度][名称]
    combined_bytes = type_bytes + name_len_bytes + name_bytes
    
    # 对组合后的字节序列进行哈希计算
    hash_object = hashlib.md5(combined_bytes)
    hash_hex = hash_object.hexdigest()
    
    # 只取前12位哈希值作为唯一标识符
    short_hash = hash_hex[:12]

    print("Encoded song id for ", name, song_type, ". Result:", short_hash)
    
    # 创建编码类型前缀
    type_prefix = f"t{song_type}"
    
    # 组合前缀和哈希
    combined_id = f"{type_prefix}_{short_hash}"
    
    # 使用Base64编码使其更紧凑
    encoded_id = base64.urlsafe_b64encode(combined_id.encode('utf-8')).decode('utf-8').rstrip('=')
    
    return encoded_id

@DeprecationWarning
def decode_song_id(encoded_id):
    """
    解码歌曲ID以提取类型和哈希值。
    
    Args:
        encoded_id (str): 编码后的ID字符串
        
    Returns:
        tuple: (song_type, hash_value)
    """
    # 添加回Base64填充字符
    padding = 4 - (len(encoded_id) % 4)
    if padding < 4:
        encoded_id += '=' * padding
    
    # 解码Base64字符串
    decoded = base64.urlsafe_b64decode(encoded_id).decode('utf-8')
    
    # 提取类型和哈希值
    parts = decoded.split('_')
    if len(parts) != 2 or not parts[0].startswith('t'):
        raise ValueError("无效的编码ID格式")
    
    song_type = int(parts[0][1:])
    hash_value = parts[1]
    
    return song_type, hash_value

@DeprecationWarning
def find_song_by_id(encoded_id, songs_data):
    """
    通过编码ID在歌曲数据中查找歌曲。
    
    Args:
        encoded_id (str): 要查找的编码ID
        songs_data (list): 歌曲对象列表
        
    Returns:
        dict or None: 找到的歌曲或None（如果未找到）
    """
    try:
        song_type, hash_value = decode_song_id(encoded_id)
        
        # 搜索匹配类型的歌曲
        for song in songs_data:
            if song.get('type') != song_type:
                continue
                
            # 为此歌曲计算哈希
            name = song.get('name', '')
            
            # 将类型转换为字节序列
            type_bytes = struct.pack('<I', song_type)
            
            # 将名称转换为字节序列
            name_bytes = name.encode('utf-8')
            
            # 名称长度转为字节序列
            name_len_bytes = struct.pack('<I', len(name_bytes))
            
            # 按照固定格式拼接字节序列
            combined_bytes = type_bytes + name_len_bytes + name_bytes
            
            # 对组合后的字节序列进行哈希计算
            hash_object = hashlib.md5(combined_bytes)
            hash_hex = hash_object.hexdigest()
            
            # 只取前12位哈希值
            short_hash = hash_hex[:12]
            
            # 检查哈希是否匹配
            if short_hash == hash_value:
                return song
                
        return None
    except Exception as e:
        print(f"查找歌曲时出错: {e}")
        return None


# --------------------------------------
# Metadata value query methods
# --------------------------------------
def get_level_value_from_chart_meta(chart_info: dict, latest_first=False) -> Union[float, None]:
    """
        从fusion metadata中获取指定谱面的定数，规则如下：
        - 如果level_value_cn字段有效，优先返回该字段，否则返回level_value_latest字段
        - 如果指定了latest_first=True，则优先返回level_value_latest字段，如果无效返回level_value_cn字段
        - 校验：确保返回的定数为float类型，且大于0，否则返回None
    """
    lv_cn = chart_info.get('level_value_cn', 0.0)
    lv_latest = chart_info.get('level_value_latest', 0.0)
    if latest_first:
        if isinstance(lv_latest, (float, int)) and lv_latest > 0:
            return float(lv_latest)
        elif isinstance(lv_cn, (float, int)) and lv_cn > 0:
            return float(lv_cn)
    else:
        if isinstance(lv_cn, (float, int)) and lv_cn > 0:
            return float(lv_cn)
        elif isinstance(lv_latest, (float, int)) and lv_latest > 0:
            return float(lv_latest)
    return None

def search_songs(query, songs_data, game_type:str, level_index:int) -> List[tuple[str, dict]]:
    """
    在fusion metadata中搜索匹配的歌曲。输出歌曲元数据格式与数据库Chart表一致。
    
    Args:
        query (str): 要搜索的查询字符串
        songs_data (dict): 歌曲元数据的json对象
        game_type (str): 游戏类型

    Returns:
        list: 匹配的歌曲列表
    """
    results = []
    if game_type == "maimai":
        for song in songs_data:
            # 合并所有别名为单个字符串
            all_acronyms = ",".join(song.get('searchAcronyms', []))
            # 匹配关键词
            if query.lower() in song.get('title', '').lower() \
            or query.lower() in song.get('artist', '').lower() \
            or query.lower() in all_acronyms:
                
                sheets = song.get('charts_info', [])
                for s in sheets:
                    # 选择难度和查询一致的谱面
                    s_level_index = s.get('difficulty', -1)  # "difficulty": int index
                    if s_level_index == level_index:
                        type = s.get('type', 'standard')  # "type": "dx" or "standard" or "utage"
                        result_string = f"{song.get('title', '')} [{type}]"
                        total_notes = s.get('note_counts', {}).get('total', 0)
                        if not total_notes:  # 防止数据源传入NULL
                            total_notes = 0
                        chart_data = {
                            'game_type': 'maimai',
                            'song_id': song.get('id', ''),
                            'chart_type': chart_type_str2value(type),
                            'level_index': level_index,
                            'difficulty': str(get_level_value_from_chart_meta(s)),
                            'song_name': song.get('title', ''),
                            'artist': song.get('artist', None),
                            'max_dx_score': total_notes * 3,
                            'video_path': None
                        }
                        results.append((result_string, chart_data))
        return results
    elif game_type == "chunithm":
        for song in songs_data:
            title = song.get('title', '')
            artist = song.get('artist', '')
            
            # 匹配关键词（标题、艺术家）# TODO: 支持别名匹配
            if query.lower() in title.lower() \
            or query.lower() in artist.lower():
                
                sheets = song.get('charts_info', [])
                for s in sheets:
                    # 选择难度和查询一致的谱面
                    s_level_index = s.get('difficulty', -1)  # "difficulty": int index
                    if s_level_index == level_index:
                        result_string = f"{title}"
                        chart_data = {
                            'game_type': 'chunithm',
                            'song_id': song.get('id', ''),
                            'chart_type': 0,  # Chunithm默认是normal (0)
                            'level_index': level_index,
                            'difficulty': str(get_level_value_from_chart_meta(s)),
                            'song_name': title,
                            'artist': artist,
                            'max_dx_score': 0,  # Chunithm不使用dx_score
                            'video_path': None
                        }
                        results.append((result_string, chart_data))
        return results
    else:
        raise ValueError("Unsupported game type for search.")

def query_songs_metadata(game_type: str, title: str, artist: Union[str, None]=None) -> Union[dict, None]:
    """查询歌曲元数据（按 title 字段匹配；若存在重名则优先匹配 artist）"""
    songs_data = load_metadata(game_type)  # 读取fusion metadata
    # TODO：使用hash id 匹配
    matches = [song for song in songs_data if song.get('title') == title]
    if not matches:
        return None
    if len(matches) == 1 or not artist:
        return matches[0]
    # 若有多个匹配，尝试按 artist 精确匹配
    for song in matches:
        if song.get('artist') == artist:
            return song
    # 未匹配到指定 artist 时返回第一个找到的
    return matches[0]

def index_songs_metadata(game_type: str, source: str, id: int, chart_type: int=0) -> dict:
    """使用来源id搜索歌曲元数据（按 id 字段匹配）"""
    songs_data = load_metadata(game_type)
    for song in songs_data:
        if source == "fish" and game_type == "maimai":
            idx_key = "id_fish" if chart_type == 0 else "id_fish_dx"
        else:
            idx_key = {
                "fish": "id_fish",
                "lxns": "id_lx",
                "otoge": "id_otoge",
            }.get(source, "id_otoge")
        if idx_key in song and song.get(idx_key) == id:
            return song
    return None

# --------------------------------------
# Formatter for third-party record data to new unified format
# --------------------------------------
def fish_to_new_record_format(fish_record: dict, game_type: str = "maimai") -> dict:
    """
    Convert a Fish-style record to the new unified record format.
    The input fish_record is based on Fish-style API query format.

    Args:
        fish_record (dict): A single record in Fish-style format.
        game_type (str): The game type ("maimai" or "chunithm").

    Returns:
        dict: The converted record in the new unified format.
    """
    # Resolve level index if missing by using level label
    level_idx = fish_record.get('level_index')
    if level_idx is None or level_idx == -1:
        level_label = fish_record.get('level_label')
        if level_label:
            level_idx = level_label_to_index(game_type, level_label)
        else:
            level_idx = 0
    # Resolve chart type
    chart_type = chart_type_str2value(fish_record.get('type', ''), fish_record_style=True)

    # Must have a title as song_id to query songs metadata
    # TODO：改用哈希key作为唯一的song id，统一数据库和元数据的格式
    resolved_song_id = fish_record['title']
    if not resolved_song_id:
        raise ValueError("Fish record must have a 'title' field to resolve song_id.")

    # query artist and other metadata from fusion metadata
    song = query_songs_metadata(game_type, fish_record.get('title'), fish_record.get('artist', None))
    if not song:
        raise LookupError(f"Cannot find song metadata for song_id: {resolved_song_id} in game_type: {game_type}")
    resolved_artist = song.get('artist', None)

    # find matching chart info
    chart_infos = song.get('charts_info', [])
    # print(f"Searching chart infos for song_id: {resolved_song_id}, level_index: {level_idx}, type: {fish_record.get('type', '')}, found {len(chart_infos)} charts.")
    matched_chart_info = None
    for ci in chart_infos:
        ci_level_index = ci.get('difficulty', -1)  # "difficulty": int index
        ci_type = chart_type_str2value(ci.get('type', ''), fish_record_style=False)  # "type": to unified int
        if ci_level_index == level_idx and ci_type == chart_type:
            # found matching chart info
            matched_chart_info = ci
            break
    
    if matched_chart_info:
        # 计算max_dx_score
        total_notes = matched_chart_info.get('note_counts', {}).get('total', 0) or 0  # 防止NULL
        resolved_total_notes = total_notes
    else:
        resolved_total_notes = 0

    resolved_ds = fish_record.get('ds', 0.0)
    # check difficulty from metadata if missing (only for maimai now)
    if resolved_ds is None or resolved_ds == 0.0 and game_type == "maimai":
        resolved_ds = get_level_value_from_chart_meta(matched_chart_info) if matched_chart_info else 0.0

    chart_data = {
        'game_type': game_type,
        'song_id': resolved_song_id,
        'chart_type': chart_type,
        'level_index': level_idx,
        'difficulty': str(resolved_ds) if resolved_ds is not None else '0.0',
        'song_name': fish_record.get('title'),
        'artist': resolved_artist,
        'max_dx_score': resolved_total_notes * 3,
        'video_path': None
    }

    if game_type == "maimai":
        record = {
            'chart_data': chart_data,
            'order_in_archive': 0, # Do not modify order here, will be set when inserting to DB
            'achievement': fish_record.get('achievements'),
            'fc_status': fish_record.get('fc'),
            'fs_status': fish_record.get('fs'),
            'dx_score': fish_record.get('dxScore', None),
            'dx_rating': fish_record.get('ra', 0),
            'chuni_rating': 0,
            'play_count': fish_record.get('play_count', 0),
            'clip_title_name': fish_record.get('clip_title_name'),
            # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
            'raw_data': json.dumps(fish_record, ensure_ascii=True)
        }
    elif game_type == "chunithm":
        record = {
            'chart_data': chart_data,
            'order_in_archive': 0,
            'achievement': fish_record.get('score'),
            'fc_status': chunithm_fc_status_to_label(fish_record.get('fc', None)),
            'fs_status': chunithm_fs_status_to_label("fish", fish_record.get('fs', None)),
            'dx_score': None,
            'dx_rating': 0,
            'chuni_rating': fish_record.get('ra', 0),
            'play_count': fish_record.get('play_count', 0),
            'clip_title_name': fish_record.get('clip_title_name'),
            # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
            'raw_data': json.dumps(fish_record, ensure_ascii=True)
        }
    else:
        raise ValueError("Unsupported game type for record conversion.")

    return record

def lxns_to_new_record_format(lxns_record: dict, game_type: str = "maimai") -> dict:
    """
    Convert a LXNS-style record to the new unified record format.
    The input lxns_record is based on LXNS API query format.

    Args:
        lxns_record (dict): A single record in LXNS-style format.
        game_type (str): The game type ("maimai" or "chunithm").
    Returns:
        dict: The converted record in the new unified format.
    """
    # 获取歌曲信息，并转换字段名称
    song_name = lxns_record.get("song_name", "")
    lxns_id = lxns_record.get("id", -1)
    level_index = lxns_record.get("level_index", 0)
    chart_type = chart_type_str2value(lxns_record.get("type", ""), fish_record_style=False)

    # 通过查询metadata，获得lxns_record中不包含的信息
    song = index_songs_metadata(game_type, "lxns", lxns_id, chart_type)
    if not song:
        # id找不到时，尝试用title查找（重名时可能不准确）
        print(f"[Warning] Cannot find song metadata for LXNS id: {lxns_id} in game_type: {game_type}, trying title search.")
        song = query_songs_metadata(game_type, song_name, None)
        if not song:
            raise LookupError(f"Cannot find song metadata for LXNS id: {lxns_id} or title: {song_name} in game_type: {game_type}")
    resolved_title = song.get('title', song_name)
    resolved_artist = song.get('artist', None)

    chart_infos = song.get('charts_info', [])
    matched_chart_info = None
    for ci in chart_infos:
        ci_level_index = ci.get('difficulty', -1)  # "difficulty": int index
        ci_type = chart_type_str2value(ci.get('type', ''), fish_record_style=False)  # "type": to unified int
        if ci_level_index == level_index and ci_type == chart_type:
            # found matching chart info
            matched_chart_info = ci
            break
    # 解析定数
    resolved_ds = get_level_value_from_chart_meta(matched_chart_info) if matched_chart_info else 0.0
    # 计算max_dx_score
    if matched_chart_info:
        total_notes = matched_chart_info.get('note_counts', {}).get('total', 0) or 0  # 防止NULL
        resolved_total_notes = total_notes
    else:
        resolved_total_notes = 0

    resolved_song_id = song_name  # 暂时使用歌曲名称作为song_id
    chart_data = {
        'game_type': game_type,
        'song_id': resolved_song_id,
        'chart_type': chart_type,
        'level_index': level_index,
        'difficulty': str(resolved_ds) if resolved_ds is not None else '0.0',
        'song_name': resolved_title,
        'artist': resolved_artist,
        'max_dx_score': resolved_total_notes * 3,
        'video_path': None
    }

    # 获取成绩信息，并转换字段名称

    if game_type == "maimai":
        record = {
            'chart_data': chart_data,
            'order_in_archive': 0, # Do not modify order here, will be set when inserting to DB
            'achievement': lxns_record.get('achievements'),
            'fc_status': lxns_record.get('fc'),
            'fs_status': lxns_record.get('fs'),
            'dx_score': lxns_record.get('dx_score', None),
            'dx_rating': int(lxns_record.get('dx_rating', 0)),
            'chuni_rating': 0,
            'play_count': lxns_record.get('play_count', 0),
            'clip_title_name': lxns_record.get('clip_title_name'),
            # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
            'raw_data': json.dumps(lxns_record, ensure_ascii=True)
        }
    elif game_type == "chunithm":
        fc_flag = lxns_record.get('full_combo', None)
        if fc_flag is None:
            fc_flag = 'none'
        fs_flag = lxns_record.get('full_chain', None)
        if fs_flag is None:
            fs_flag = 'none'
        record = {
            'chart_data': chart_data,
            'order_in_archive': 0,
            'achievement': lxns_record.get('score'),
            'fc_status': chunithm_fc_status_to_label(fc_flag),
            'fs_status': chunithm_fs_status_to_label("lxns", fs_flag),
            'dx_score': None,
            'dx_rating': 0,
            'chuni_rating': lxns_record.get('rating', 0),
            'play_count': lxns_record.get('play_count', 0),
            'clip_title_name': lxns_record.get('clip_title_name'),
            # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
            'raw_data': json.dumps(lxns_record, ensure_ascii=True)
        }
    else:
        raise ValueError("Unsupported game type for record conversion.")

    return record


# --------------------------------------
# Image download helpers
# --------------------------------------
def get_jacket_image_from_url(image_code: str, source: str = "otoge", game_type: str = "maimai") -> Image.Image:
    if source == "dxrating":
        url = get_dxrating_api_endpoint(game_type) + f"/{image_code}.jpg"
    elif source == "otoge":
        url = get_otoge_db_api_endpoint(game_type) + f"/{image_code}"  # otoge image_code includes file extension
    else:
        raise ValueError("Unsupported image source.")

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        img = Image.open(response.raw).convert("RGBA").resize((400, 400), Image.LANCZOS)
        return img
    else:
        print(f"Failed to download image from {url}. Status code: {response.status_code}")
        raise FileNotFoundError