import os
from datetime import datetime

def get_user_base_dir(username):
    """Get base directory for user data"""
    return os.path.join("b50_datas", username)

def get_user_version_dir(username, timestamp=None):
    """Get versioned directory for user data"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(get_user_base_dir(username), timestamp)

def get_data_paths(username, timestamp=None):
    """Get all data file paths for a specific version"""
    version_dir = get_user_version_dir(username, timestamp)
    return {
        'raw_file': os.path.join(version_dir, "b50_raw.json"),
        'data_file': os.path.join(version_dir, "b50_config.json"),
        'config_file': os.path.join(version_dir, "video_configs.json")
    }

def get_user_versions(username):
    """Get all available versions for a user"""
    base_dir = get_user_base_dir(username)
    if not os.path.exists(base_dir):
        return []
    versions = [d for d in os.listdir(base_dir) 
               if os.path.isdir(os.path.join(base_dir, d))]
    return sorted(versions, reverse=True)
