import os
import re
import json
import yaml
import subprocess
import platform
from moviepy import VideoFileClip

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

# r/w config/config_{platfrom}.json
def load_record_config(config_file):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = json.load(f)
            return content.get("records", None)
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


