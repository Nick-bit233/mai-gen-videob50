import os
import re
import json
import yaml
import subprocess
import platform
from moviepy import VideoFileClip
from utils.DataUtils import download_metadata, encode_song_id, CHART_TYPE_MAP_MAIMAI

DATA_CONFIG_VERSION = "0.5"
LEVEL_LABELS = {
    0: "BASIC",
    1: "ADVANCED",
    2: "EXPERT",
    3: "MASTER",
    4: "RE:MASTER",
}

def remove_invalid_chars(text: str) -> str:
    # 去除非法字符，使用re.sub
    return re.sub(r'[\\/:*?"<>|]', '', text)

# 验证和编码song_id（重要：song_id涉及远程获取歌曲的有效曲绘数据）
def format_record_songid(record, raw_song_id):
    if raw_song_id and type(raw_song_id) == int and raw_song_id > 0:
        # song_id exist and vaild (for past versions in maimai)
        return raw_song_id
    else:
        # song_id is unknown (null or negative value), encode a music tag by song_name and song_type instead
        song_name = record.get("title", None)
        song_type = record.get("type", None)
        if song_name and song_type is not None:
            encoded_id = encode_song_id(song_name, CHART_TYPE_MAP_MAIMAI[song_type])
            return encoded_id
        else:
            raise ValueError("Invalid song_id or song_name/song_type in record detail.")

def try_update_config_json(content, username=""):
    # v0.4以下
    if type(content) == list:
        print("存档版本过旧，转换存档到最新版本...")
        for item in content:
            index = content.index(item)
            item["clip_name"] = item.get("clip_id", "Clip")
            item["clip_id"] = f"clip_{index + 1}"
            # 将item["level_label"]转换为全大写
            item["level_label"] = item.get("level_label", "").upper()
            # 检查song_id
            item["song_id"] = format_record_songid(item, item.get("song_id", None))
        new_content = {
            "version": DATA_CONFIG_VERSION,
            "type": "maimai",
            "sub_type": "best",
            "username": username,
            "rating": 0,
            "length_of_content": len(content),
            "records": content,
        }
        return new_content
    # v0.4
    elif type(content) == dict and 'version' in content and content['version'] == "0.4":
        print("转换v0.4存档到最新版本...")
        content["version"] = DATA_CONFIG_VERSION
        records = content["records"]
        for item in records:
            index = records.index(item)
            item["clip_name"] = item.get("clip_id", "Clip")
            item["clip_id"] = f"clip_{index + 1}"
            item["level_label"] = item.get("level_label", "").upper()
            item["song_id"] = format_record_songid(item, item.get("song_id", None))
        return content
    else:
        raise ValueError("无法匹配存档版本，请检查存档文件")

def load_full_config_safe(config_file, username):
    # 尝试读取存档文件，如果不存在则返回None
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
    else:
        raise FileNotFoundError(f"存档文件不存在：{config_file}")
    # 检查版本号是否存在或过期
    if "version" not in content or content["version"] != DATA_CONFIG_VERSION:
        print(f"存档版本号不匹配，当前最新版本：{DATA_CONFIG_VERSION}，文件版本：{content.get('version', 'None') if type(content) == dict else 'None'}")
        # 尝试修复存档
        content = try_update_config_json(content, username)
        # 保存更新后的存档
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=4)
        return content
    else:
        return content


def update_music_metadata():
    for game_type in ['maimaidx']:
        metadata_dir = './music_metadata/maimaidx'
        if not os.path.exists(metadata_dir):
            os.makedirs(metadata_dir, exist_ok=True)
        json_path = os.path.join(metadata_dir, f"songs.json")
        latest =download_metadata(game_type)
        # 覆盖现有metadata信息
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(latest, f, ensure_ascii=False, indent=4)


def load_music_metadata(game_type="maimaidx"):
    metadata_dir = f'./music_metadata/{game_type}'
    json_path = os.path.join(metadata_dir, f"songs.json")
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Metadata file not found: {json_path}")


# r/w config/config_{platfrom}.json
def load_record_config(config_file, username=""):
    try:
        # 读取存档时，检查存档文件版本，若为旧版本尝试自动更新
        content = load_full_config_safe(config_file, username)
        return content.get("records", None)
    except FileNotFoundError:
        return None

def save_record_config(config_file, config_data):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
            content["records"] = config_data
    else:
        content = {"records": config_data}
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=4)

# r/w video_configs.json
def load_video_config(config_file):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_video_config(config_file, config_data):
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)


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


