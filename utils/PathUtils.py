import os
from datetime import datetime
from utils.PageUtils import process_username


def get_user_base_dir(username):
    """
    Get base directory for user data, use same base dir for all game_type
    Use safe username to avoid windows issues with special characters
    """
    raw_username, safe_username = process_username(username)
    return os.path.join("b50_datas", safe_username)

def get_user_media_dir(username, game_type="maimai"):
    """Get media directory for user data"""
    base_dir = get_user_base_dir(username)
    return {
        'image_dir': os.path.join(base_dir, "images"),
        'output_video_dir': os.path.join(base_dir, "videos"),
    }
