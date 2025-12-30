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
