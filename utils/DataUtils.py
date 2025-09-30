from typing import List
import requests
import base64
import hashlib
import struct
from PIL import Image

BUCKET_ENDPOINT = "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com"
FC_PROXY_ENDPOINT = "https://fish-usta-proxy-efexqrwlmf.cn-shanghai.fcapp.run"

# --------------------------------------
# Data format grounding Helper methods
# --------------------------------------
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

@DeprecationWarning
def search_songs(query, songs_data) -> List[tuple[str, dict]]:
    """
    在歌曲数据中搜索匹配的歌曲。
    
    Args:
        query (str): 要搜索的查询字符串
        songs_data (dict): 歌曲元数据的json对象
        
    Returns:
        list: 匹配的歌曲列表
    """
    results = []
    for song in songs_data:
        if query.lower() in song.get('name', '').lower() \
           or query.lower() in song.get('artist', '').lower() \
           or query.lower() in str(song.get('id', '')):
            song_type = REVERSE_TYPE_MAP_MAIMAI.get(song.get('type'), '-')
            index = songs_data.index(song)
            result_string = f"{song.get('name', '')} [{song_type}]"
            results.append((result_string, song))
    return results
