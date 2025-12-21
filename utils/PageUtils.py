import os
import re
import json
import shutil
from urllib.parse import urlparse
import requests
import yaml
import subprocess
import platform
from moviepy import VideoFileClip
from utils.DataUtils import download_metadata, load_metadata
from db_utils.DatabaseManager import DatabaseManager
import streamlit as st
from typing import Tuple

DEFAULT_STYLE_CONFIG_FILE_PATH = "./static/video_style_config.json"

# LEVEL_LABELS = {
#     0: "BASIC",
#     1: "ADVANCED",
#     2: "EXPERT",
#     3: "MASTER",
#     4: "RE:MASTER",
# }

def get_game_type_text(game_type: str) -> str:
    """Returns a UI label for the game type."""
    if game_type == "maimai":
        return "舞萌DX"
    elif game_type == "chunithm":
        return "中二节奏"
    else:
        return "UNKNOWN"

def auto_set_game_type_from_query():
    """
    根据 URL 查询参数自动设置 game_type。
    如果 URL 中包含 game_type=chunithm 或 game_type=maimai，则设置 session_state.game_type。
    如果查询参数中包含 b30 或 B30，则设置为 chunithm。
    如果查询参数中包含 b50 或 B50，则设置为 maimai。
    """
    try:
        # 尝试从查询参数获取
        query_params = st.query_params
        if 'game_type' in query_params:
            game_type = query_params['game_type']
            if game_type in ['maimai', 'chunithm']:
                st.session_state.game_type = game_type
                return
        
        # 检查 URL 中是否包含 b30 或 b50
        # 注意：Streamlit 可能不支持直接获取完整 URL，所以这个方法可能不可用
        # 作为备选方案，我们可以在页面标题中检查
        # 但由于无法直接获取页面标题，我们使用其他方法
    except:
        pass

def format_chunithm_rank(rank_str: str) -> str:
    """
    格式化中二节奏的RANK显示
    例如: ssp -> SS+, sssp -> SSS+
    """
    if not rank_str:
        return ""
    
    # 转换为大写
    rank_upper = rank_str.upper()
    
    # 如果以P结尾，替换为+
    if rank_upper.endswith('P'):
        return rank_upper[:-1] + '+'
    
    return rank_upper

def remove_invalid_chars(text: str) -> str:
    """Removes characters that are invalid for Windows file paths."""
    return re.sub(r'[\\/:*?"<>|]', '', text)

def process_username(input_username: str) -> Tuple[str, str]:
    """
    Processes the input username to return a raw version and a filesystem-safe version.

    Args:
        input_username: The original username string from user input.

    Returns:
        A tuple containing:
        - raw_username (str): The original, unmodified username.
        - safe_username (str): A version safe for use in file paths.
    """
    raw_username = input_username
    
    # Create a safe username for filesystem paths
    safe_username = remove_invalid_chars(raw_username)
    safe_username = safe_username.replace(' ', '_')
    
    return raw_username, safe_username

def escape_markdown_text(text: str) -> str:
    # 转义Markdown特殊字符 '[]'、'()'、'*'、'`'、'$'、'~'、'_'，使其能在stMarkdownContainer中正常渲染原本内容
    return re.sub(r'([\[\]\(\)\*`#$~_])', r'\\\1', text)

# r/w gloabl_config.yaml
def read_global_config():
    if os.path.exists("global_config.yaml"):
        with open("global_config.yaml", "r", encoding='utf-8') as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    else:
        raise FileNotFoundError("global_config.yaml not found")
    

def write_global_config(config):
    try:
        with open("global_config.yaml", "w", encoding='utf-8') as f:
            yaml.dump(config, f)
    except Exception as e:
        print(f"Error writing global config: {e}")

# r/w video_style_config.json
def load_style_config(game_type, config_file=DEFAULT_STYLE_CONFIG_FILE_PATH):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            style_config = json.load(f)
            return style_config.get(game_type, {})
    else:
        return None


def update_music_metadata():
    for game_type in ['maimai', 'chunithm']:
        metadata_dir = './music_metadata/'
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir, exist_ok=True)
        filename, latest_data = download_metadata(game_type)
        json_path = os.path.join(metadata_dir, filename)
        # 覆盖现有metadata信息
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(latest_data, f, ensure_ascii=False, indent=4)


def load_music_metadata(game_type="maimai"):
    return load_metadata(game_type)


def get_db_manager() -> "DatabaseManager":
    """
    Initializes the database on first run, applies migrations,
    and returns a singleton instance of the DatabaseManager.
    
    Uses st.session_state to cache the manager instance.
    """
    if 'db_manager' not in st.session_state:
        print("Initializing DatabaseManager...")
        db_path = "mai_gen_videob50.db"
        
        # The DatabaseManager's __init__ will handle the initial schema creation.
        db_manager = DatabaseManager(db_path=db_path)
        
        # Apply any pending migrations
        print("Checking for and applying database migrations...")
        db_manager.check_and_apply_migrations()
        
        st.session_state['db_manager'] = db_manager
        print("DatabaseManager initialized and cached.")
        
    return st.session_state['db_manager']


def get_video_duration(video_path):
    """Returns the duration of a video file in seconds"""
    try:
        with VideoFileClip(video_path) as clip:
            return clip.duration
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return -1


def open_file_explorer(path):
    try:
        # Windows
        if platform.system() == "Windows":
            subprocess.run(['explorer', path], check=True)
        # macOS
        elif platform.system() == "Darwin":
            subprocess.run(['open', path], check=True)
        # Linux
        elif platform.system() == "Linux":
            subprocess.run(['xdg-open', path], check=True)
        return True
    except Exception as e:
        return False
    

def change_theme(theme_dict):
    st_config_path = os.path.join(os.getcwd(), ".streamlit", "config.toml")
    if not os.path.exists(st_config_path):
        os.makedirs(os.path.dirname(st_config_path), exist_ok=True)
    
    with open(st_config_path, "w", encoding="utf-8") as f:
        if theme_dict:
            f.write("[theme]\n")
            for key, value in theme_dict.items():
                f.write(f'{key}="{value}"\n')
        else:
            f.write("")  # 清空文件以使用默认主题


def download_temp_image_to_static(image_url, local_dir="./static/thumbnails"):
    """
    下载图片到streamlit静态托管的本地目录。
    """
    if not image_url:
        print("Warning: 图片URL为空，无法下载视频预览图。")
        return None

    try:
        # 确保本地目录存在，如果不存在则创建
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
            print(f"目录 '{local_dir}' 已创建。")

        # 从URL中提取文件名
        parsed_url = urlparse(image_url)
        # 获取路径的最后一部分作为文件名
        filename = os.path.basename(parsed_url.path)

        local_file_path = os.path.join(local_dir, filename)
        ret_file_path = f"/app/static/thumbnails/{filename}"

        # 发送GET请求获取图片内容
        # 添加headers模拟浏览器访问，有时可以避免一些简单的反爬虫机制
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(image_url, stream=True, headers=headers, timeout=10) # 设置超时
        response.raise_for_status()  # 如果请求失败 (例如 404, 403)，则抛出HTTPError异常

        # 以二进制写模式打开本地文件，并将图片内容写入文件
        with open(local_file_path, 'wb') as f:
            # response.raw.decode_content = True # 确保内容被正确解码
            shutil.copyfileobj(response.raw, f)
        return ret_file_path

    except requests.exceptions.RequestException as e:
        print(f"下载图片时发生错误 (URL: {image_url}): {e}")
        return None
    except IOError as e:
        print(f"写入文件时发生错误 (路径: {local_file_path}): {e}")
        return None
    except Exception as e:
        print(f"发生未知错误: {e}")
        return None

def clear_all_user_data(username: str) -> dict:
    """
    清空指定用户的所有个人数据，包括：
    - 数据库中的用户数据（用户、存档、记录、配置等）
    - 本地存档文件夹（b50_datas 和 chunithm_datas）
    - 配置文件中的敏感信息（API Key、Token等）
    - 用户配置目录
    
    Args:
        username: 要清空数据的用户名
        
    Returns:
        dict: 包含清空结果的字典，格式为 {
            'success': bool,
            'deleted_files': list,
            'deleted_db_records': dict,
            'errors': list
        }
    """
    result = {
        'success': True,
        'deleted_files': [],
        'deleted_db_records': {
            'archives': 0,
            'records': 0,
            'configurations': 0,
            'assets': 0
        },
        'errors': []
    }
    
    try:
        # 1. 删除数据库中的用户数据
        db_manager = get_db_manager()
        user = db_manager.get_user(username)
        
        if user:
            user_id = user['id']
            
            # 获取用户的所有存档
            archives = db_manager.get_user_archives(user_id)
            result['deleted_db_records']['archives'] = len(archives)
            
            # 统计记录和配置数量
            for archive in archives:
                archive_id = archive['id']
                records = db_manager.get_records(archive_id)
                result['deleted_db_records']['records'] += len(records)
                
                # 统计配置数量
                with db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) as count FROM configurations WHERE archive_id = ?', (archive_id,))
                    config_count = cursor.fetchone()['count']
                    result['deleted_db_records']['configurations'] += config_count
                    
                    # 统计资源数量
                    cursor.execute('SELECT COUNT(*) as count FROM assets WHERE archive_id = ?', (archive_id,))
                    asset_count = cursor.fetchone()['count']
                    result['deleted_db_records']['assets'] += asset_count
            
            # 删除用户（级联删除所有相关数据）
            if not db_manager.delete_user(username):
                result['errors'].append(f"数据库中没有找到用户: {username}")
        else:
            result['errors'].append(f"数据库中没有找到用户: {username}")
        
        # 2. 删除本地存档文件夹
        data_dirs = [
            os.path.join("b50_datas", username),
            os.path.join("chunithm_datas", username)
        ]
        
        for data_dir in data_dirs:
            if os.path.exists(data_dir):
                try:
                    shutil.rmtree(data_dir)
                    result['deleted_files'].append(data_dir)
                except Exception as e:
                    result['errors'].append(f"删除文件夹 {data_dir} 时出错: {e}")
                    result['success'] = False
        
        # 3. 清空配置文件中的敏感信息
        config_file = "global_config.yaml"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                # 清空敏感信息
                sensitive_keys = ['YOUTUBE_API_KEY', 'CUSTOMER_PO_TOKEN']
                modified = False
                
                for key in sensitive_keys:
                    if key in config:
                        if key == 'CUSTOMER_PO_TOKEN' and isinstance(config[key], dict):
                            config[key] = {'po_token': '', 'visitor_data': ''}
                        else:
                            config[key] = ''
                        modified = True
                
                if modified:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
                    result['deleted_files'].append(f"已清空 {config_file} 中的敏感信息")
            except Exception as e:
                result['errors'].append(f"清空配置文件时出错: {e}")
                result['success'] = False
        
        # 4. 清空用户配置目录（可选，因为可能影响其他用户）
        user_config_dir = Path.home() / ".mai-gen-videob50"
        if user_config_dir.exists():
            try:
                # 只删除与元数据更新相关的文件，保留其他配置
                metadata_file = user_config_dir / "metadata_update.json"
                if metadata_file.exists():
                    metadata_file.unlink()
                    result['deleted_files'].append(str(metadata_file))
            except Exception as e:
                result['errors'].append(f"清空用户配置目录时出错: {e}")
        
    except Exception as e:
        result['success'] = False
        result['errors'].append(f"清空数据时发生未知错误: {e}")
    
    return result