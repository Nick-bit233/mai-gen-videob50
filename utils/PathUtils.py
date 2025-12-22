import os
from datetime import datetime


def get_user_base_dir(username):
    """
    Get base directory for user data, use same base dir for all game_type
    """
    return os.path.join("b50_datas", username)

def get_user_media_dir(username, game_type="maimai"):
    """Get media directory for user data"""
    # TODO: convert_to safe username
    base_dir = get_user_base_dir(username)
    return {
        'image_dir': os.path.join(base_dir, "images"),
        'output_video_dir': os.path.join(base_dir, "videos"),
    }

# TODO: 重构，下方函数不再使用，替换为仅缓存媒体资源的上方函数

@DeprecationWarning
def get_user_version_dir(username, timestamp=None, game_type="maimai"):
    """Get versioned directory for user data"""
    # 如果没有指定时间戳，则使用当前时间，返回新的时间戳组成的文件夹路径
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(get_user_base_dir(username), timestamp)
@DeprecationWarning
def get_data_paths(username, timestamp=None, game_type="maimai"):
    """Get all data file paths for a specific version"""
    version_dir = get_user_version_dir(username, timestamp, game_type)
    raw_file_name = "chunithm_b30_raw.json" if game_type == "chunithm" else "b50_raw.json"
    config_file_name = "chunithm_b30_config.json" if game_type == "chunithm" else "b50_config.json"
    return {
        'raw_file': os.path.join(version_dir, raw_file_name),
        'data_file': os.path.join(version_dir, config_file_name),
        'config_yt': os.path.join(version_dir, "b50_config_youtube.json"),
        'config_bi': os.path.join(version_dir, "b50_config_bilibili.json"),
        'video_config': os.path.join(version_dir, "video_configs.json"),
        'image_dir': os.path.join(version_dir, "images"),
        'output_video_dir': os.path.join(version_dir, "videos"),
    }
@DeprecationWarning
def get_user_versions(username, game_type="maimai"):
    """Get all available versions for a user"""
    base_dir = get_user_base_dir(username)
    if not os.path.exists(base_dir):
        return []
    versions = [d for d in os.listdir(base_dir) 
               if os.path.isdir(os.path.join(base_dir, d))]
    return sorted(versions, reverse=True)
