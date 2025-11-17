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
from utils.DataUtils import download_metadata, encode_song_id, CHART_TYPE_MAP_MAIMAI
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
    # TODO: 替换为新的更新源
    for game_type in ['maimaidx']:
        metadata_dir = './music_metadata/maimaidx'
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir, exist_ok=True)
        # json_path = os.path.join(metadata_dir, f"songs.json")
        # latest = download_metadata(game_type)
        # # 覆盖现有metadata信息
        # with open(json_path, 'w', encoding='utf-8') as f:
        #     json.dump(latest, f, ensure_ascii=False, indent=4)


def load_music_metadata(game_type="maimaidx"):
    metadata_dir = f'./music_metadata/{game_type}'
    if game_type == "maimaidx":
        json_path = os.path.join(metadata_dir, f"dxdata.json")
    elif game_type == "chunithm":
        # TODO: 支持chunithm数据
        json_path = os.path.join(metadata_dir, f"chunithm_data.json")
    else:
        raise ValueError(f"Unsupported game type: {game_type}")
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Metadata file not found: {json_path}")


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
