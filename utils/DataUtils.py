from importlib import metadata
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
from functools import lru_cache
from lxml import etree

# 服务器bucket用于转存融合过的的metadata
BUCKET_ENDPOINT = "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com"
# 服务器函数计算用于代理获取需要开发者key的查分器api数据
FC_PROXY_ENDPOINT = "https://fish-usta-proxy-efexqrwlmf.cn-shanghai.fcapp.run"

# 第三方原始数据源api用于获取曲绘等CDN资源
LXNS_API_ENDPOINT = "https://assets.lxns.net"  # 落雪查分器api

# Version tags from MTBL, used for filtering B15 records from MBL exported data.
DEFAULT_B15_VERSION = [
    ["PRiSM PLUS", "CiRCLE"],
    ["CiRCLE", "CiRCLE PLUS"],
    []
]

def get_otoge_db_api_endpoint(game_type) -> str:
    return f"https://otoge-db.net/{game_type}/jacket"  # otoge-db api

def get_dxrating_api_endpoint(game_type: str) -> str:
    return "https://shama.dxrating.net/images/cover/v2"  # dxrating api

# --------------------------
# Rating computing methods
# --------------------------

def safe_parse_difficulty(ds) -> float:
    """
    安全解析定数值，支持字符串或数值输入
    
    Args:
        ds: 定数值，可以是 float、int 或字符串（如 "14.9", "?", "暂无"）
    
    Returns:
        解析成功返回浮点数，失败返回 0.0
    """
    if ds is None:
        return 0.0
    
    # 已经是数值类型
    if isinstance(ds, (int, float)):
        return float(ds) if ds > 0 else 0.0
    
    # 字符串解析
    try:
        val = float(str(ds).strip())
        return val if val > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0


# Parse achievement to rate name
def get_rate(achievement):
    rates = [
        (100.5, "sssp"),
        (100, "sss"),
        (99.5, "ssp"),
        (99, "ss"),
        (98, "sp"),
        (97, "s"),
        (94, "aaa"),
        (90, "aa"),
        (80, "a"),
        (75, "bbb"),
        (70, "bb"),
        (60, "b"),
        (50, "c"),
        (0, "d")
    ]
    
    for threshold, rate in rates:
        if achievement >= threshold:
            return rate
    return "d"

# DX rating factors
def get_factor(achievement):
    factors = [
        (100.5, 0.224),
        (100.4999, 0.222),
        (100, 0.216),
        (99.9999, 0.214),
        (99.5, 0.211),
        (99, 0.208),
        (98.9999, 0.206),
        (98, 0.203),
        (97, 0.2),
        (96.9999, 0.176),
        (94, 0.168),
        (90, 0.152),
        (80, 0.136),
        (79.9999, 0.128),
        (75, 0.12),
        (70, 0.112),
        (60, 0.096),
        (50, 0.08),
        (0, 0.016)
    ]
    
    for threshold, factor in factors:
        if achievement >= threshold:
            return factor
    return 0

# Compute DX rating for a single song
def compute_rating(ds, score):
    """
    计算 maimai DX 单曲 Rating
    
    Args:
        ds: 定数（可以是数字或字符串，非数字时返回 0）
        score: 达成率 (0-100.5)
    
    Returns:
        Rating 整数值
    """
    ds_val = safe_parse_difficulty(ds)
    if ds_val <= 0:
        return 0
    return int(ds_val * min(score, 100.5) * get_factor(score))

# Compute Chunithm rating for a single song
def compute_chunithm_rating(ds, score):
    """
    计算 Chunithm 单曲 Rating
    
    Args:
        ds: 定数（可以是数字或字符串，非数字时返回 0.0）
        score: 分数 (0-1010000)
    
    Returns:
        Rating 浮点数值
    """
    ds_val = safe_parse_difficulty(ds)
    if ds_val <= 0:
        return 0.0
    
    try:
        s = int(float(score))
    except Exception:
        raise ValueError("Failed to parse chunithm score.")

    tiers = [
        (1_009_000, None,        ('fixed', 2.15)),
        (1_007_500, 1_009_000,   ('step',  2.00, 100, 0.01, 2.15)),
        (1_005_000, 1_007_500,   ('step',  1.50, 50,  0.01, 2.00)),
        (1_000_000, 1_005_000,   ('step',  1.00, 100, 0.01, 1.50)),
        (990_000,   1_000_000,   ('step',  0.60, 250, 0.01, 1.00)),
        (975_000,   990_000,     ('step',  0.00, 250, 0.01, 0.60)),
        (950_000,   975_000,     ('fixed', -1.5)),
        (925_000,   950_000,     ('fixed', -3.0)),
        (900_000,   925_000,     ('fixed', -5.0)),
        (800_000,   900_000,     ('func',  lambda ds, s: (ds - 5.0) / 2.0)),
    ]

    for mn, mx, rule in tiers:
        if s >= mn and (mx is None or s < mx):
            typ = rule[0]
            if typ == 'fixed':
                return round(ds_val + rule[1], 2)
            if typ == 'func':
                return round(rule[1](ds_val, s), 2)
            # 'step'
            base, step_pts, step_val, cap = rule[1], rule[2], rule[3], rule[4]
            steps = max(0, (s - mn) // step_pts)
            extra = min(steps * step_val, cap - base)
            return round(ds_val + base + extra, 2)

    return 0.0

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

def format_record_tag(game_type: str, clip_title_name: str, song_id: str, chart_type: int, level_index: int, 
                      song_name: str = None, chart_id: int = -1) -> str:  # TODO: 弃用song_id, 使用chart_id
    level_label = level_index_to_label(game_type, level_index)
    display_name = song_name if song_name else song_id
    if game_type == "maimai":
        return f"{clip_title_name}: {display_name}({chart_type_value2str(chart_type, game_type)}) [{level_label}] c({chart_id}) "
    else:
        return f"{clip_title_name}: {display_name}[{level_label}] c({chart_id}) "

def get_record_tags_from_data_dict(records_data: List[Dict]) -> List[str]:
    """Get tags from record/chart group query data. These tags are used by st_page compoents for navigation to certain record"""
    ret_tags = []
    for r in records_data:
        game_type = r.get("game_type", "maimai")
        clip_title_name = r.get("clip_title_name", "")
        song_id = r.get("song_id", "")
        chart_id = r.get("chart_id", -1)
        chart_type = r.get("chart_type", -1)
        level_index = r.get("level_index", -1)
        song_name = r.get("song_name", None)  # 获取曲名
        ret_tags.append(format_record_tag(game_type, clip_title_name, song_id, chart_type, level_index, song_name, chart_id))
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
                return "fc"
            case "fullchain":   # 铂 FULL CHAIN
                return "fcr"
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
    
@lru_cache(maxsize=2)
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
            title = song.get('title', '')
            artist = song.get('artist', '')
            if not title or not artist:
                continue

            # 合并所有别名为单个字符串
            all_aliases = ",".join(song.get('aliases', []))
            # 匹配关键词
            if query.lower() in title.lower() \
            or query.lower() in artist.lower() \
            or query.lower() in all_aliases:
                
                charts = song.get('charts_info', [])
                for c in charts:
                    # 选择难度和查询一致的谱面
                    c_level_index = c.get('difficulty', -1)  # "difficulty": int index
                    if c_level_index == level_index:
                        type = c.get('type', 'standard')  # "type": "dx" or "standard" or "utage"
                        result_string = f"{song.get('title', '')} [{type}]"
                        total_notes = c.get('note_counts', {}).get('total', 0)
                        if not total_notes:  # 防止数据源传入NULL
                            total_notes = 0
                        chart_data = {
                            'game_type': 'maimai',
                            'song_id': song.get('title', ''),  # 暂时使用title作为song_id, TODO: 替换为hash id
                            'chart_type': chart_type_str2value(type),
                            'level_index': level_index,
                            'difficulty': str(get_level_value_from_chart_meta(c)),
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
            if not title or not artist:
                continue
            
            all_aliases = ",".join(song.get('aliases', []))
            if query.lower() in title.lower() \
            or query.lower() in artist.lower() \
            or query.lower() in all_aliases:
                
                charts = song.get('charts_info', [])
                for c in charts:
                    # 选择难度和查询一致的谱面
                    c_level_index = c.get('difficulty', -1)  # "difficulty": int index
                    if c_level_index == level_index:
                        result_string = f"{title}"
                        chart_data = {
                            'game_type': 'chunithm',
                            'song_id': song.get('title', ''),
                            'chart_type': 0,  # Chunithm默认是normal (0)
                            'level_index': level_index,
                            'difficulty': str(get_level_value_from_chart_meta(c)),
                            'song_name': title,
                            'artist': artist,
                            'max_dx_score': 0,  # 不使用dx_score
                            'video_path': None
                        }
                        results.append((result_string, chart_data))
        return results
    else:
        raise ValueError("Unsupported game type for search.")
    
def exact_match_chart(query, songs_data, game_type="maimai") -> dict:
    """
    Match exact chart with given song_data, which should contain title, level_index, chart_type, and usually from HTML source with complete metadata. This is used for matching the exact chart when generating video for a specific record, to ensure we get the correct difficulty and max score information.

    Args:
        query: dict, example
        {
            "title": "FFT", # Must be exactly matching the title in metadata
            "level_index": 3, # Master
            "chart_type": 0,  # standard
        }
        songs_data: list of dict, the loaded metadata for the game type
        game_type: str, only "maimai" used currently, as this is a method for parsing HTML source.
    """
    chart_data = {}
    if game_type == "maimai":
        # Don't use 'get' here to ensure we raise error if any of the required fields is missing
        for song in songs_data:
            title = song.get('title', '')
            if query["title"] == title: # Must be exact match
                charts = song.get('charts_info', [])
                for c in charts:
                    c_level_index = c.get('difficulty', -1)
                    c_chart_type = chart_type_str2value(c.get('type', ''), fish_record_style=False)
                    if c_level_index == query["level_index"] and c_chart_type == query["chart_type"]:
                        chart_data = {
                            'game_type': 'maimai',
                            'song_id': song.get('title', ''),  # TODO: 替换为hash id
                            'chart_type': query["chart_type"],
                            'level_index': query["level_index"],
                            'difficulty': str(get_level_value_from_chart_meta(c)),
                            'song_name': query["title"],
                            'artist': song.get('artist', None),
                            'max_dx_score': c.get('note_counts', {}).get('total', 0) * 3,  # 防止NULL
                            'video_path': None
                        }
                        return chart_data
                if title == "Help me, ERINNNNNN!!":
                    continue # SBGA把旧的歌名改了，导致第一次可能把DX查成SD
                raise ValueError(f"Error: exactly matched song {query['title']}, but didn't find chart with level index {query['level_index']} with chart type {query['chart_type']}")
        # 国际服独占曲不在数据库中，可能会掉到这里
        print(f"Warning: can't exactly match song with name {query['title']}")
        return None
    else:
        raise NotImplementedError("Unsupported game type for exact chart matching.")

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
            'fc_status': fish_record.get('fc','none'),  # use string 'none' for null value, consistent with DB format
            'fs_status': fish_record.get('fs','none'),
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
            'fc_status': lxns_record.get('fc', 'none'),  # use string 'none' for null value, consistent with DB format
            'fs_status': lxns_record.get('fs', 'none'),
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

# ---------------------------
# MGBL data parsing methods
# ---------------------------

@DeprecationWarning
def filter_mgbl_b50(mgbl_scores: list, filter: dict) -> List[dict]:
    """
    Filter and parse B50 entries from raw MGBL exported data.

    Args:
        mgbl_scores: list of dict, raw MGBL score entries, example
            [
                {
                    "songName": "Xaleid◆scopiX",
                    "difficulty": "Re:MASTER",
                    "level": "15",
                    "achievement": "99.7325%",
                    "dxScore": 4396,
                    "maxDxScore": 6666,
                    "sync": "sync",
                    "combo": "fc",
                    "type": "DX",
                    "difficultyId": 4,
                    "isNew": true
                },
                {...}
            ]
        filter: dict, see unify_user_gamedata function for detail
    
    Returns:
        record_data: list of dict, will be stored in database
    """
    MGBL_FILTER_FUNCTIONS = {
        "ap": lambda score: score.get("combo", "") in ["ap", "app"],
        "fc": lambda score: score.get("combo", "") in ["fc", "fcp", "ap", "app"],
    }
    SONGS_METADATA = load_metadata("maimai")

    def mgbl_to_record(i, score):
        """
        Search constant, compute rating, format record.
        """
        query = {
            "title": score["songName"],
            "level_index": score["difficultyId"],
            "chart_type": chart_type_str2value(score["type"].lower(), fish_record_style=False)
        }
        chart_data = exact_match_chart(query, SONGS_METADATA, game_type="maimai")
        if not chart_data:
            print(f"Warning: 无法匹配谱面{query}, 已自动跳过。如果缺失的数据是\"全世界共通リズム感テスト\"属正常现象。")
            return None
        achievement = score.get("achievement", "101.0000%").rstrip("%")
        dx_rating = compute_rating(chart_data["difficulty"], float(achievement))
        record = {
            'chart_data': chart_data,
            'order_in_archive': 0, # Do not modify order here, will be set when inserting to DB
            'achievement': achievement,
            'fc_status': score["combo"],
            'fs_status': score["sync"],
            'dx_score': score["dxScore"],
            'dx_rating': dx_rating,
            'chuni_rating': 0,
            'play_count': 0,
            'clip_title_name': "", # Fill this later
            # Store the original HTML div as raw data for potential future use
            'raw_data': score
        }
        return (i, record)
    
    def mgbl_sort_key(item):
        i, record = item
        # 降序，单曲rating > 定数 > 完成度 > 原始顺序
        return (-record['dx_rating'], -safe_parse_difficulty(record["chart_data"]["difficulty"]), -float(record['achievement']), i)

    if not filter:
        match_b15 = False
        best_past_len = 50
        best_new_len = 0
        tag = ""
    else:
        match_b15 = filter.get("b15_versions", -1) >= 0
        best_past_len = filter.get("best_past_len", 35 if match_b15 else 50)
        best_new_len = filter.get("best_new_len", 15 if match_b15 else 0)
        tag = filter.get("tag", "").lower()

    # Filter with tag if applicable
    if tag:
        if tag not in MGBL_FILTER_FUNCTIONS:
            raise ValueError(f"Error: MGBL数据源仅支持tag为{list(MGBL_FILTER_FUNCTIONS.keys())}的筛选，当前tag: {tag}")
        tagged_scores = [(i, score) for i, score in enumerate(mgbl_scores) if MGBL_FILTER_FUNCTIONS[tag](score)]
    else:
        tagged_scores = list(enumerate(mgbl_scores))

    # Match version and sort
    new_records = [result for result in
                    (mgbl_to_record(i, score) for i, score
                    in tagged_scores if score["isNew"])
                    if result is not None] if match_b15 else []
    past_records = [result for result in 
                    (mgbl_to_record(i, score) for i, score in tagged_scores
                    if (not match_b15 or not score["isNew"]))
                    if result is not None]
    new_records = sorted(new_records, key=mgbl_sort_key)[:best_new_len]
    past_records = sorted(past_records, key=mgbl_sort_key)[:best_past_len]
    # Fill clip_title_name
    record_data = []
    best_prefix = "Best" if not tag else tag.upper()
    for clip_number, (_, record) in enumerate(new_records):
        record["clip_title_name"] = f"New{best_prefix}{clip_number + 1}"
        record_data.append(record)
    past_prefix = "Past" if best_new_len > 0 else ""
    for clip_number, (_, record) in enumerate(past_records):
        record["clip_title_name"] = f"{past_prefix}{best_prefix}{clip_number + 1}"
        record_data.append(record)
    return record_data

# ---------------------------
# MTBL data parsing methods
# ---------------------------

def read_mtbl_tsv(data_input, params):
    """
    MTBL exports TSV data with a header row and multiple chart data rows.
    Read the header row first, then parse every entry into a dict with the header fields as keys.

    Args:
        data_input: raw TSV string exported from MTBL
        params: no params will be used here
    
    Returns:
        Rough processed JSON-like list of dict mtbl_data
    """
    lines = data_input.strip().split('\n')
    if not lines:
        return []
    
    headers = lines[0].split('\t') # Song	Genre	Version	Chart	Difficulty	Level	Achv	Rank	FC/AP	Sync	DX ✦	DX %	DX Score	Chart Constant
    mtbl_dicts = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split('\t')
        row = {headers[i]: values[i] if i < len(values) else '' for i in range(len(headers))}
        mtbl_dicts.append(row)
    
    return mtbl_dicts

@DeprecationWarning
def parse_mtbl_tsv(chart_entry: dict, game_type="maimai") -> dict:
    """
    Parsing a single entry of MTBL chart data to internal record format.

    Args:
        chart_entry: converted dict of MTBL chart entry
    """
    chart_type = chart_entry.get("Chart", "")
    chart_type = chart_type_str2value(chart_type.lower())

    level_idx = 0
    level_label = chart_entry.get("Difficulty", "")
    if level_label:
        level_idx = level_label_to_index(game_type, level_label)

    ds = safe_parse_difficulty(chart_entry.get("Chart Constant", "0.0"))
    song_name = chart_entry.get("Song", "NO_TITLE")
    song_id = song_name # TODO: 改用哈希id
    
    total_dx_score = chart_entry.get("DX Score", "0/0")
    # 将dx_score以/分隔，取最后一个部分
    dx_score = int(total_dx_score.split("/")[0])
    max_dx_score = int(total_dx_score.split("/")[1])

    achivement = chart_entry.get("Achv", "101.0000%").rstrip("%")

    def normalize_flag(value):
        s = value.lower().replace("+", "p")
        if s == "-":
            return "none"
        return s

    fc_ap = normalize_flag(chart_entry.get("FC/AP", "-"))
    sync = normalize_flag(chart_entry.get("Sync", "-"))
    rating = chart_entry.get("Rating", 0)
    
    chart_data = {
        'game_type': game_type,
        'song_id': song_id,
        'chart_type': chart_type,
        'level_index': level_idx,
        'difficulty': ds,
        'song_name': song_name,
        'artist': None,
        'max_dx_score': max_dx_score,
        'video_path': None
    }
    record = {
            'chart_data': chart_data,
            'order_in_archive': 0, # Do not modify order here, will be set when inserting to DB
            'achievement': achivement,
            'fc_status': fc_ap,  # use string 'none' for null value, consistent with DB format
            'fs_status': sync,
            'dx_score': dx_score,
            'dx_rating': rating,
            'chuni_rating': 0,
            'play_count': 0, # MTBL doesn't export play count
            'clip_title_name': "", # Keep empty for further editing
            # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
            'raw_data': json.dumps(chart_entry, ensure_ascii=True)
        }
    return record

@DeprecationWarning
def filter_mtbl_b50(mtbl_data, filter: dict = None):
    """
    Filter and parse B50 entries from raw MTBL exported data
    """

    def mtbl_rating(i, entry):
        achv = float(entry["Achv"].rstrip("%"))
        rating = compute_rating(entry["Chart Constant"], achv)
        return ({**entry, "Rating": rating}, i)

    def best_sort_key(item):
        entry, original_index = item
        return (-entry["Rating"], -safe_parse_difficulty(entry["Chart Constant"]), -float(entry["Achv"].rstrip("%")), original_index)

    MTBL_FILTER_FUNCTIONS = {
        "ap": lambda entry: entry.get("FC/AP", "") in ["AP", "AP+"],
        "fc": lambda entry: entry.get("FC/AP", "") in ["FC", "FC+", "AP", "AP+"],
    }

    # Parse filter params
    if not filter:
        b15_versions = []
        best_past_len = 50
        best_new_len = 0
        tag = ""
    else:
        #print("DEBUG: filter = ", filter)
        b15_versions = DEFAULT_B15_VERSION[filter.get("b15_versions", -1)]
        best_past_len = filter.get("best_past_len", 35 if b15_versions else 50)
        best_new_len = filter.get("best_new_len", 15 if b15_versions else 0)
        tag = filter.get("tag", "").lower()

    # 如果有筛选需求，排除不满足tag要求的谱面
    if tag:
        if tag not in MTBL_FILTER_FUNCTIONS:
            raise ValueError(f"Error: MTBL数据源仅支持tag为{list(MTBL_FILTER_FUNCTIONS.keys())}的筛选，当前tag: {tag}")
        tagged_charts = [(i, entry) for i, entry in enumerate(mtbl_data)
                         if MTBL_FILTER_FUNCTIONS[tag](entry)]
    else:
        tagged_charts = list(enumerate(mtbl_data))
    # 筛选谱面版本，计算rating并排序
    new_charts = [mtbl_rating(i, entry) for i, entry in tagged_charts
                  if entry.get("Version", "") in b15_versions] if b15_versions else []
    past_charts = [mtbl_rating(i, entry) for i, entry in tagged_charts
                   if (not b15_versions or entry.get("Version", "") not in b15_versions)]
    new_charts = sorted(new_charts, key=best_sort_key)[:best_new_len]
    past_charts = sorted(past_charts, key=best_sort_key)[:best_past_len]
    # 将筛选后的谱面转译为数据库格式，并添加clip_title_name
    new_records = []
    for i, (_, entry) in enumerate(new_charts):
        record = parse_mtbl_tsv(entry)
        record['clip_title_name'] = f"NewBest{i + 1}"
        new_records.append(record)
    past_records = []
    past_prefix = "PastBest" if best_new_len > 0 else "Best"
    for i, (_, entry) in enumerate(past_charts):
        record = parse_mtbl_tsv(entry)
        record['clip_title_name'] = f"{past_prefix}{i + 1}"
        past_records.append(record)
    return new_records + past_records

# -------------------------------------------------
# Unify data input and filtering (MGBL, MTBL)
# -------------------------------------------------

def mgbl_to_unified(mgbl_scores: list, params: dict = None) -> list:
    """
    Unify data format from mai=gen booklet output

    Args:
        mgbl_scores: list of dict, raw MGBL score entries, example
            [
                {
                    "songName": "Xaleid◆scopiX",
                    "difficulty": "Re:MASTER",
                    "level": "15",
                    "achievement": "99.7325%",
                    "dxScore": 4396,
                    "maxDxScore": 6666,
                    "sync": "sync",
                    "combo": "fc",
                    "type": "DX",
                    "difficultyId": 4,
                    "isNew": true
                },
                {...}
            ]
        params: no params needed here
    
    Returns:
        unified: list of dict, will be used for querying charts and filtering b50
    """
    unified = []
    for score in mgbl_scores:
        unified.append({
            "query": {
                "title": score["songName"],
                "level_index": score["difficultyId"],
                "chart_type": chart_type_str2value(score["type"].lower(), fish_record_style=False)
            },
            "achievement": score.get("achievement", "101.0000%").rstrip("%"),
            "fc_status": score.get("combo", "none"),
            "fs_status": score.get("sync", "none"),
            "dx_score": score.get("dxScore", 0),
            "max_dx_score": score.get("maxDxScore", 0),
            "is_new": score.get("isNew", False),
            "ds": None,
            "raw_data": score
        })
    return unified

def dxjs_to_unified(dxjs_data: list, params: dict = None) -> list:
    """
    Unify data format from output of DXJS API

    Args:
        dxjs_data: list of dict,
            An example b50 element
            {
                "sheetId":"FFT__dxrt__std__dxrt__remaster",
                "achievementRate":99.8338
            }
            An example ALL element
            {
                "sheetId":"月面基地__dxrt__dx__dxrt__basic",
                "identity":{"songId":"月面基地","type":"dx","difficulty":"basic"},
                "achievementRate":15.8075,
                "comboFlag":null,
                "syncFlag":"sync",
                "source":{"provider":"maimai-net","providerSongName":"月面基地"}
            }
        params: check "query" and detected data format consistency, warn user if needed

    Returns:
        Unified: list of dict, will be used for querying charts and filtering b50
    """
    DXRT_SPLIT = "__dxrt__"
    query = params["query"]
    is_all_data = dxjs_data[0] and "identity" in dxjs_data[0]
    if (query == "all") != is_all_data:
        print("Warning: dxrating JSON处理时数据不一致, 可能选择了错误的JSON类型, 这有概率导致异常的B50数据.")

    unified = []
    for entry in dxjs_data:
        # B50 export mode, less info
        sheet_id_split = entry["sheetId"].split(DXRT_SPLIT) # song_name DXRT_SPLIT chart_type DXRT_SPLIT level_label
        title = sheet_id_split[0]
        chart_type = sheet_id_split[1]
        level_label = sheet_id_split[2]
        achievement = entry["achievementRate"] # float
        combo = entry.get("comboFlag", "none") # only in all data export
        sync = entry.get("syncFlag", "none") # only in all data export
        unified.append({
            "query": {
                "title": title,
                "level_index": level_label_to_index("maimai", level_label),
                "chart_type": chart_type_str2value(chart_type.lower())
            },
            "achievement": f"{achievement}",
            "fc_status": combo,
            "fs_status": sync,
            "is_new": (not is_all_data) and len(unified) >= 35, # don't match version if parsing all data
            # no ds provided, so leave it blank and wait filter_unified to query from metadata
            "raw_data": entry
        })
    return unified

def mtbl_to_unified(mtbl_data: list, params: dict = None) -> list:
    """
    Unify data format from output of read_mtbl_tsv

    Args:
        mtbl_data: list of dict, see read_mtbl_tsv output for example
        params: params["filter"]["b15_versions"] is required for matching version of b15 songs
    
    Returns:
        unified: list of dict, will be used for querying charts and filtering b50
    """
    def normalize_flag(value):
        s = value.lower().replace("+", "p")
        return "none" if s == "-" else s

    filter = params.get("filter", {}) if params else {}
    b15_versions = DEFAULT_B15_VERSION[filter.get("b15_versions", -1)] if filter else []

    unified = []
    for entry in mtbl_data:
        total_dx = entry.get("DX Score", "0/0").split("/")
        version = entry.get("Version", "")
        unified.append({
            "query": {
                "title": entry.get("Song", ""),
                "level_index": level_label_to_index("maimai", entry.get("Difficulty", "")),
                "chart_type": chart_type_str2value(entry.get("Chart", "").lower())
            },
            "achievement": entry.get("Achv", "101.0000%").rstrip("%"),
            "fc_status": normalize_flag(entry.get("FC/AP", "-")),
            "fs_status": normalize_flag(entry.get("Sync", "-")),
            "dx_score": int(total_dx[0].strip()),
            "max_dx_score": int(total_dx[1].strip()),
            "is_new": version in b15_versions if b15_versions else False,
            "ds": entry.get("Chart Constant", None),
            "raw_data": entry
        })
    return unified

def filter_unified_b50(unified_data: list, filter: dict, game_type="maimai") -> list:
    SONGS_METADATA = load_metadata(game_type)

    FILTER_FUNCTIONS = {
        "ap": lambda e: e.get("fc_status", "") in ["ap", "app"],
        "fc": lambda e: e.get("fc_status", "") in ["fc", "fcp", "ap", "app"],
    }

    if not filter:
        match_b15 = False
        best_past_len = 50
        best_new_len = 0
        tag = ""
    else:
        b15_versions = DEFAULT_B15_VERSION[filter.get("b15_versions", -1)]
        match_b15 = bool(b15_versions)
        best_past_len = filter.get("best_past_len", 35 if match_b15 else 50)
        best_new_len = filter.get("best_new_len", 15 if match_b15 else 0)
        tag = filter.get("tag", "").lower()

    if tag:
        if tag not in FILTER_FUNCTIONS:
            raise ValueError(f"Error: 仅支持tag为{list(FILTER_FUNCTIONS.keys())}的筛选，当前tag: {tag}")
        tagged = [(i, e) for i, e in enumerate(unified_data) if FILTER_FUNCTIONS[tag](e)]
    else:
        tagged = list(enumerate(unified_data))

    def to_record(i, entry):
        chart_data = exact_match_chart(entry["query"], SONGS_METADATA, game_type=game_type)
        if not chart_data:
            print(f"Warning: 无法匹配谱面 {entry['query']}，已跳过。")
            return None
        difficulty = entry["ds"] if entry.get("ds") else chart_data["difficulty"]
        dx_rating = compute_rating(difficulty, float(entry["achievement"]))
        record = {
            "chart_data": chart_data,
            "order_in_archive": 0,
            "achievement": entry["achievement"],
            "fc_status": entry["fc_status"],
            "fs_status": entry["fs_status"],
            "dx_score": entry.get("dx_score", 0),
            "dx_rating": dx_rating,
            "chuni_rating": 0,
            "play_count": 0,
            "clip_title_name": "",
            "raw_data": json.dumps(entry["raw_data"], ensure_ascii=True)
        }
        return (i, record)

    def sort_key(item):
        i, record = item
        return (-record["dx_rating"], -safe_parse_difficulty(record["chart_data"]["difficulty"]), -float(record["achievement"]), i)

    new_results = [r for r in (to_record(i, e) for i, e in tagged if e["is_new"]) if r] if match_b15 else []
    past_results = [r for r in (to_record(i, e) for i, e in tagged if not match_b15 or not e["is_new"]) if r]

    new_results = sorted(new_results, key=sort_key)[:best_new_len]
    past_results = sorted(past_results, key=sort_key)[:best_past_len]

    record_data = []
    best_prefix = "Best" if not tag else tag.upper()
    new_prefix = "New"
    past_prefix = "Past" if best_new_len > 0 else ""
    for clip_number, (_, record) in enumerate(new_results):
        record["clip_title_name"] = f"{new_prefix}{best_prefix}{clip_number + 1}"
        record_data.append(record)
    for clip_number, (_, record) in enumerate(past_results):
        record["clip_title_name"] = f"{past_prefix}{best_prefix}{clip_number + 1}"
        record_data.append(record)

    return record_data


# --------------------------------------
# HTML parsing methods
# --------------------------------------

def read_maimai_html(data_input, params=None):
    """
    Read B50 data from raw HTML input (from maimai DX NET page), parse it and collect basic information to new record format.

    Args:
        data_input: HTML string input from the streamlit page
        params: no params will be used
    Returns:
        raw_html_records: list of records (dict). Some details (曲师artist, 定数chart constant, 单曲评分rating, 总评分overall dx rating) are still missing and need to be processed again.
    """
    try:
        html_tree = etree.HTML(data_input)
    except Exception as e:
        raise ValueError(f"Error: 解析HTML数据时发生错误，请检查输入数据是否为有效的HTML格式。错误详情: {e}")

    # Locate B35 and B15
    b35_div_names = [
        "Songs for Rating(Others)",
        "RATING対象曲（ベスト）"
    ]
    b15_div_names = [
        "Songs for Rating(New)",
        "RATING対象曲（新曲）"
    ]
    b35_screw, html_languange = locate_html_screw(html_tree, b35_div_names)
    b15_screw, _ = locate_html_screw(html_tree, b15_div_names)

    # html_screws = html_tree.xpath('//div[@class="screw_block m_15 f_15 p_s"]')
    # if not html_screws:
    #     raise Exception("Error: B35/B15 screw not found. Please check HTML input!")
    # b35_screw = html_screws[1]
    # b15_screw = html_screws[0]

    # Iterate songs and save as JSON
    raw_html_records = []
    new_clip_number = 0
    for song_div in iterate_songs(b15_screw):
        new_clip_number += 1
        record = parse_maimai_html(song_div)
        record['clip_title_name'] = f"NewBest_{new_clip_number}"
        raw_html_records.append(record)
    past_clip_number = 0
    for song_div in iterate_songs(b35_screw):
        past_clip_number += 1
        record = parse_maimai_html(song_div)
        record['clip_title_name'] = f"PastBest_{past_clip_number}"
        raw_html_records.append(record)

    html_data = {
        "raw_records": raw_html_records,
        "html_language": html_languange,
    }
    return html_data

def locate_html_screw(html_tree, div_names):
    for i, name in enumerate(div_names):
        screw = html_tree.xpath(f'//div[text()="{name}"]')
        if screw:
            return screw[0], i
    raise Exception(f"Error: 未找到类似\"{div_names[0]}\")的HTML screw，请检查选择的数据源类型或复制的HTML内容完整性。")

def iterate_songs(div_screw):
    current_div = div_screw
    while True:
        current_div = current_div.xpath('following-sibling::div[1]')[0]
        if len(current_div) == 0:
            break
        yield current_div

def parse_maimai_html(song_div):
    """
    Parse a HTML div from maimai DX Net B50 page into a JSON record in new record formatting
    """
    LEVEL_DIV_LABEL = ["_basic", "_advanced", "_expert", "_master", "_remaster"]
    score_text = ""
    level_index = -1
    title = ""
    chart_type = -1
    # Initialise chart JSON (Depracated fish style JSON)
    # chart = {
    #     "achievements": 0,
    #     "ds": 0,
    #     "dxScore": 0,
    #     "fc": "",
    #     "fs": "",
    #     "level": "0",
    #     "level_index": -1,
    #     "level_label": "easy",
    #     "ra": 0,
    #     "rate": "",
    #     "song_id": song_id_placeholder,
    #     "title": "",
    #     "chart_type": -1,
    # }

    # Get achievements
    score_div = song_div.xpath('.//div[contains(@class, "music_score_block")]')
    if score_div:
        score_text = score_div[0].text
        score_text = score_text.strip().replace('\xa0', '').replace('\n', '').replace('\t', '')
        score_text = score_text.rstrip('%')

    # Get song level
    # level_div = song_div.xpath('.//div[contains(@class, "music_lv_block")]')
    # if level_div:
    #     level_text = level_div[0].text
    #     chart["level"] = level_text

    # Get song level index
    div_class = song_div.get("class", "")
    for idx, level in enumerate(LEVEL_DIV_LABEL):
        if level.lower() in div_class.lower():
            level_index = idx
            break

    # Get song title
    title_div = song_div.xpath('.//div[contains(@class, "music_name_block")]')
    if title_div:
        title = title_div[0].text

    # Get chart type
    kind_icon_img = song_div.xpath('.//img[contains(@class, "music_kind_icon")]')
    if kind_icon_img:
        img_src = kind_icon_img[0].get("src", "")
        chart_type = chart_type_str2value("dx") if img_src.endswith("dx.png") else chart_type_str2value("sd")
    
    query = {
        "title": title,
        "level_index": level_index,
        "chart_type": chart_type
    }
    raw_record = {
        "query": query,
        "achievement": score_text,
        "raw_data": etree.tostring(song_div, encoding='unicode'),
        'clip_title_name': "" # Edit later
    }
    return raw_record

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
        raise RuntimeError("图像下载失败，检查URL或网络连接。详细信息：" + response.text)
