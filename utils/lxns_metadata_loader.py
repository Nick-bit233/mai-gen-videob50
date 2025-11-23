"""
落雪查分器曲目列表获取和更新工具
用于从落雪查分器API获取中二节奏曲目列表并保存为metadata文件
"""
import requests
import json
import os
from typing import Optional, Dict, List


LXNS_API_BASE_URL = "https://maimai.lxns.net"
LXNS_SONG_LIST_ENDPOINT = "/api/v0/chunithm/song/list"
CHUNITHM_METADATA_DIR = "./music_metadata/chunithm"
CHUNITHM_METADATA_FILE = os.path.join(CHUNITHM_METADATA_DIR, "lxns_songs.json")


def fetch_song_list_from_lxns(api_key: Optional[str] = None, version: Optional[int] = None, notes: bool = False) -> Optional[Dict]:
    """
    从落雪查分器API获取曲目列表
    
    Args:
        api_key: 开发者API密钥（可选）
        version: 游戏版本（可选，默认23000）
        notes: 是否包含谱面物量（可选，默认False）
    
    Returns:
        包含songs, genres, versions的字典，如果失败则返回None
    """
    url = f"{LXNS_API_BASE_URL}{LXNS_SONG_LIST_ENDPOINT}"
    
    # 构建查询参数
    params = {}
    if version is not None:
        params['version'] = version
    if notes:
        params['notes'] = 'true'
    
    # 构建请求头
    headers = {}
    if api_key:
        headers['Authorization'] = api_key
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"获取曲目列表失败: 状态码 {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return None
    except Exception as e:
        print(f"发生未知错误: {e}")
        return None


def convert_lxns_song_to_metadata_format(lxns_song: Dict) -> Dict:
    """
    将落雪查分器API返回的歌曲数据转换为系统内部使用的metadata格式
    
    Args:
        lxns_song: 落雪API返回的歌曲对象
    
    Returns:
        转换后的歌曲metadata对象
    """
    # 提取基本信息
    song_id = lxns_song.get('id')
    title = lxns_song.get('title', '')
    artist = lxns_song.get('artist', '')
    genre = lxns_song.get('genre', '')
    bpm = lxns_song.get('bpm', 0)
    version = lxns_song.get('version', 0)
    
    # 转换difficulties为sheets格式（与maimai格式类似）
    sheets = []
    difficulties = lxns_song.get('difficulties', [])
    
    for diff in difficulties:
        difficulty_index = diff.get('difficulty', 0)  # 0=Basic, 1=Advanced, 2=Expert, 3=Master, 4=Ultima
        level_str = diff.get('level', '0')  # 例如 "13+", "14"
        level_value = diff.get('level_value', 0.0)  # 例如 13.7, 14.0
        note_designer = diff.get('note_designer', '')
        diff_version = diff.get('version', version)
        
        # 将difficulty索引转换为level_label
        level_labels = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
        level_label = level_labels[difficulty_index] if difficulty_index < len(level_labels) else "EXPERT"
        
        sheet = {
            'difficulty': level_label,
            'level': level_str,
            'internalLevelValue': level_value,  # 定数值
            'noteDesigner': note_designer,
            'version': diff_version
        }
        sheets.append(sheet)
    
    # 构建metadata对象
    metadata = {
        'id': song_id,
        'title': title,
        'artist': artist,
        'genre': genre,
        'bpm': bpm,
        'version': version,
        'sheets': sheets
    }
    
    return metadata


def save_lxns_metadata_to_file(data: Dict, output_file: Optional[str] = None) -> bool:
    """
    将落雪查分器获取的数据保存到文件
    
    Args:
        data: 从API获取的数据（包含songs, genres, versions）
        output_file: 输出文件路径（可选，默认使用CHUNITHM_METADATA_FILE）
    
    Returns:
        是否保存成功
    """
    if output_file is None:
        output_file = CHUNITHM_METADATA_FILE
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 转换songs格式
        songs = data.get('songs', [])
        converted_songs = [convert_lxns_song_to_metadata_format(song) for song in songs]
        
        # 构建保存的数据结构
        metadata = {
            'songs': converted_songs,
            'genres': data.get('genres', []),
            'versions': data.get('versions', []),
            'source': 'lxns',
            'api_endpoint': LXNS_SONG_LIST_ENDPOINT
        }
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 曲目列表已保存到: {output_file}")
        print(f"  - 曲目数量: {len(converted_songs)}")
        print(f"  - 分类数量: {len(metadata['genres'])}")
        print(f"  - 版本数量: {len(metadata['versions'])}")
        
        return True
    except Exception as e:
        print(f"✗ 保存文件失败: {e}")
        return False


def update_chunithm_metadata_from_lxns(api_key: Optional[str] = None, version: Optional[int] = None, notes: bool = False) -> bool:
    """
    从落雪查分器API获取曲目列表并更新本地metadata文件
    
    Args:
        api_key: 开发者API密钥（可选）
        version: 游戏版本（可选）
        notes: 是否包含谱面物量（可选，默认False）
    
    Returns:
        是否更新成功
    """
    print("=" * 60)
    print("从落雪查分器更新中二节奏曲目列表")
    print("=" * 60)
    
    # 获取数据
    print("正在从落雪查分器API获取曲目列表...")
    data = fetch_song_list_from_lxns(api_key=api_key, version=version, notes=notes)
    
    if data is None:
        print("✗ 获取曲目列表失败")
        return False
    
    # 保存数据
    print("\n正在保存曲目列表到本地文件...")
    success = save_lxns_metadata_to_file(data)
    
    if success:
        print("\n✓ 曲目列表更新成功!")
        return True
    else:
        print("\n✗ 曲目列表更新失败")
        return False


if __name__ == "__main__":
    # 测试代码
    import sys
    
    # 默认API密钥（可以从环境变量或配置文件读取）
    DEFAULT_API_KEY = os.getenv("LXNS_API_KEY", None)
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = DEFAULT_API_KEY
    
    print("落雪查分器曲目列表更新工具")
    print("=" * 60)
    
    if not api_key:
        print("警告: 未提供API密钥，某些端点可能需要认证")
        print("可以通过环境变量 LXNS_API_KEY 或命令行参数提供")
        print()
    
    # 更新metadata
    success = update_chunithm_metadata_from_lxns(api_key=api_key, version=None, notes=False)
    
    if success:
        print("\n下一步:")
        print(f"1. 检查生成的文件: {CHUNITHM_METADATA_FILE}")
        print("2. 确保 load_songs_metadata 函数使用此文件")
    else:
        print("\n更新失败，请检查:")
        print("1. API密钥是否正确")
        print("2. 网络连接是否正常")
        print("3. API端点是否可访问")

