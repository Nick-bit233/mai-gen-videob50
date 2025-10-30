from importlib import metadata
from turtle import st
from typing import List
import json
import requests
import base64
import hashlib
import struct
from PIL import Image
from typing import Dict, Union

BUCKET_ENDPOINT = "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com"
FC_PROXY_ENDPOINT = "https://fish-usta-proxy-efexqrwlmf.cn-shanghai.fcapp.run"

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

# TODO：重构数据格式以及工具函数，支持dxrating数据格式和未来的中二数据格式，以下方法均已弃用
# 曲绘数据将尝试从dxrating接口获取
CHART_TYPE_MAP_MAIMAI =  {   
    "SD": 0,
    "DX": 1,
    "宴": 10,
    "协": 11,
}
REVERSE_TYPE_MAP_MAIMAI = {
    0: "SD",
    1: "DX",
    10: "宴",
    11: "协",
}


@DeprecationWarning
def download_metadata(data_type="maimaidx"):
    url = f"{BUCKET_ENDPOINT}/metadata_json/{data_type}/songs.json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to download metadata from {url}. Status code: {response.status_code}")
        raise FileNotFoundError

@DeprecationWarning
def download_image_data(image_path):
    url = f"{BUCKET_ENDPOINT}/{image_path}"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        img = Image.open(response.raw)
        return img
    else:
        print(f"Failed to download image from {url}. Status code: {response.status_code}")
        raise FileNotFoundError

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


def load_songs_metadata(game_type: str) -> dict:
    # metadata已经更换为dxrating数据源
    if game_type == "maimai":
        with open("./music_metadata/maimaidx/dxdata.json", 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        songs_data = songs_data.get('songs', [])
        assert isinstance(songs_data, list), "songs_data should be a list"
        return songs_data
    elif game_type == "chunithm":
        raise NotImplementedError("Chunithm metadata loading not implemented yet.")
        # TODO: implement chunithm metadata loading
    else:
        raise ValueError("Unsupported game type for metadata loading.")


def search_songs(query, songs_data, game_type:str, level_index:int) -> List[tuple[str, dict]]:
    """
    在歌曲数据中搜索匹配的歌曲。输出歌曲元数据格式与数据库Chart表一致。
    
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
            if query.lower() in song.get('songId', '').lower() \
            or query.lower() in song.get('artist', '').lower() \
            or query.lower() in all_acronyms:
                
                sheets = song.get('sheets', [])
                for s in sheets:
                    # 选择难度和查询一致的谱面
                    s_level_index = level_label_to_index(game_type, s['difficulty'])
                    if s_level_index == level_index:
                        type = s.get('type', 'std')
                        result_string = f"{song.get('title', '')} [{type}]"
                        total_notes = s.get('noteCounts', {}).get('total', 0)
                        if not total_notes:  # 防止数据源传入NULL
                            total_notes = 0
                        chart_data = {
                            'game_type': 'maimai',
                            'song_id': song['songId'],
                            'chart_type': chart_type_str2value(type),
                            'level_index': level_index,
                            'difficulty': str(s.get('internalLevelValue', 0.0)),
                            'song_name': song.get('title', ''),
                            'artist': song.get('artist', None),
                            'max_dx_score': total_notes * 3,
                            'video_path': None
                        }
                        results.append((result_string, chart_data))
        return results
    elif game_type == "chunithm":
        raise NotImplementedError("Chunithm search not implemented yet.")
    else:
        raise ValueError("Unsupported game type for search.")

def query_songs_metadata(game_type: str, title: str, artist: Union[str, None]=None) -> Union[dict, None]:
    """查询歌曲元数据（按 title 字段匹配；若存在重名则优先匹配 artist）"""
    songs_data = load_songs_metadata(game_type)  # 读取dxrating data（以maimai为例）
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

def fish_to_new_record_format(fish_record: dict, game_type: str = "maimai") -> dict:
    """
    Convert a Fish-style record to the new unified record format.
    The input fish_record is based on Fish-style API query format.

    Args:
        fish_record (dict): A single record in Fish-style format.

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
    resolved_song_id = fish_record['title']
    if not resolved_song_id:
        raise ValueError("Fish record must have a 'title' field to resolve song_id.")

    # query artist and other metadata from songs metadata
    song = query_songs_metadata(game_type, fish_record.get('title'), fish_record.get('artist', None))
    if not song:
        raise LookupError(f"Cannot find song metadata for song_id: {resolved_song_id} in game_type: {game_type}")
    
    resolved_artist = song.get('artist', None)
    resolved_total_notes = song.get('noteCounts', {}).get('total', 0)
    if not resolved_total_notes:  # 防止数据源传入NULL
        resolved_total_notes = 0
    # check difficulty from metadata if missing
    resolved_ds = fish_record.get('ds', 0.0)
    if resolved_ds is None or resolved_ds == 0.0:
        sheets = song.get('sheets', [])
        for s in sheets:
            s_level_index = level_label_to_index(game_type, s['difficulty'])
            s_type = chart_type_str2value(s.get('type', ''))
            if s_level_index == level_idx and s_type == chart_type:
                resolved_ds = s.get('internalLevelValue', 0.0)

    chart_data = {
        'game_type': game_type,
        'song_id': resolved_song_id,
        'chart_type': chart_type,
        'level_index': level_idx,
        'difficulty': str(resolved_ds) if resolved_ds is not None else '0.0',
        'song_name': fish_record.get('title'),
        'artist': resolved_artist,
        'max_dx_score': resolved_total_notes * 3,
        'video_path': fish_record.get('video_path', None)
    }

    record = {
        'chart_data': chart_data,
        'order_in_archive': 0,
        'achievement': fish_record.get('achievements'),
        'fc_status': fish_record.get('fc'),
        'fs_status': fish_record.get('fs'),
        'dx_score': fish_record.get('dxScore', None),
        'dx_rating': fish_record.get('ra', 0),
        'chuni_rating': fish_record.get('chuni_rating', 0),
        'play_count': fish_record.get('play_count', 0),
        'clip_title_name': fish_record.get('clip_title_name'),
        # Store the original record as JSON string (ensure_ascii=True to escape unicode like the example)
        'raw_data': json.dumps(fish_record, ensure_ascii=True)
    }

    return record

def get_chunithm_ds_next(metadata: dict) -> Union[float, None]:
    raise NotImplementedError("Chunithm DS Next retrieval not implemented yet.")

def download_image_from_url(image_code: str, source: str = "dxrating") -> Image.Image:
    if source == "dxrating":
        url = f"https://shama.dxrating.net/images/cover/v2/{image_code}.jpg"
    else:
        raise ValueError("Unsupported image source.")

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        img = Image.open(response.raw).convert("RGBA").resize((400, 400), Image.LANCZOS)
        return img
    else:
        print(f"Failed to download image from {url}. Status code: {response.status_code}")
        raise FileNotFoundError


# if __name__ == "__main__":
#     # Test download_image_from_url
#     test_image_code = "da8dcd8ae0c0ea46aed773d9ae3b4121da885f1c758d2dd3f9863a72347a014c"
#     img = download_image_from_url(test_image_code)
#     img.show()