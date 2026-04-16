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

def get_user_media_dir(username, game_type="maimai", archive_id=None):
    """Get media directory for user data. When archive_id is provided, images are stored in an archive-specific subdirectory."""
    base_dir = get_user_base_dir(username)
    if archive_id is not None:
        image_dir = os.path.join(base_dir, "images", str(archive_id))
    else:
        image_dir = os.path.join(base_dir, "images")
    return {
        'image_dir': image_dir,
        'output_video_dir': os.path.join(base_dir, "videos"),
    }
