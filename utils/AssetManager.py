import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from utils.DataUtils import query_songs_metadata, get_jacket_image_from_url


class AssetManager:
    _executor = ThreadPoolExecutor(max_workers=4)
    _db = None  # 延迟初始化的数据库管理器

    @classmethod
    def _get_db(cls):
        """延迟获取数据库管理器，避免循环导入"""
        if cls._db is None:
            from db_utils.DatabaseDataHandler import get_database_handler
            cls._db = get_database_handler().db
        return cls._db

    @staticmethod
    def get_storage_path(game_type: str, image_code: str) -> str:
        """获取云端曲绘的本地存储路径"""
        # Create directory if it doesn't exist
        directory = os.path.join("static", "assets", "jackets", game_type)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Return absolute path with .png extension
        filename = f"{image_code}.png"
        return os.path.abspath(os.path.join(directory, filename))

    @staticmethod
    def download_jacket(game_type: str, title: str, artist: str):
        """从云端下载曲绘"""
        metadata = query_songs_metadata(game_type, title, artist)
        if not metadata:
            return

        image_code = metadata.get('image_code_otoge')
        if not image_code:
            return

        storage_path = AssetManager.get_storage_path(game_type, image_code)
        
        if os.path.exists(storage_path):
            return

        try:
            # Reuse DataUtils logic to fetch and resize image
            img = get_jacket_image_from_url(image_code, source='otoge', game_type=game_type)
            if img:
                img.save(storage_path, "PNG")
                print(f"[AssetManager] Downloaded jacket for {title}")
        except Exception as e:
            print(f"[AssetManager] Failed to download jacket for {title}: {e}")

    @staticmethod
    def start_background_download(chart_info_list: list):
        """
        后台下载曲绘
        Accepts a list of dicts: [{'game_type':..., 'title':..., 'artist':...}, ...]
        """
        for item in chart_info_list:
            AssetManager._executor.submit(
                AssetManager.download_jacket,
                item.get('game_type', 'maimai'),
                item.get('title'),
                item.get('artist')
            )

    @staticmethod
    def get_custom_jacket_path(archive_id: int, chart_id: int) -> str:
        """
        从 assets 表获取自定义曲绘路径
        
        Args:
            archive_id: 存档 ID
            chart_id: 谱面 ID
        
        Returns:
            str: 自定义曲绘路径，如果不存在则返回 None
        """
        try:
            db = AssetManager._get_db()
            assets = db.get_assets(archive_id=archive_id, asset_type='custom_jacket')
            
            # 遍历查找匹配 chart_id 的资源
            for asset in assets:
                metadata = asset.get('metadata', {})
                if metadata.get('chart_id') == chart_id:
                    file_path = asset.get('file_path')
                    if file_path and os.path.exists(file_path):
                        return file_path
            
            return None
        except Exception as e:
            print(f"[AssetManager] Error getting custom jacket: {e}")
            return None

    @staticmethod
    def get_jacket_image(game_type: str, title: str, artist: str, 
                         archive_id: int = None, chart_id: int = None) -> Image.Image:
        """
        获取曲绘图片
        
        优先级:
        1. 如果提供了 archive_id 和 chart_id，优先从 assets 表获取自定义曲绘
        2. 从本地存储获取已下载的云端曲绘
        3. 从云端下载
        
        Args:
            game_type: 游戏类型 ('maimai' 或 'chunithm')
            title: 曲名
            artist: 曲师
            archive_id: 存档 ID（可选，用于获取自定义曲绘）
            chart_id: 谱面 ID（可选，用于获取自定义曲绘）
        
        Returns:
            PIL.Image.Image: 曲绘图片
        """
        # 1. 优先检查自定义曲绘
        if archive_id is not None and chart_id is not None:
            custom_path = AssetManager.get_custom_jacket_path(archive_id, chart_id)
            if custom_path:
                try:
                    with Image.open(custom_path) as img:
                        return img.copy()
                except Exception as e:
                    print(f"[AssetManager] Failed to load custom jacket: {e}")
        
        # 2. 从本地存储或云端获取
        metadata = query_songs_metadata(game_type, title, artist)
        image_code = metadata.get('image_code_otoge') if metadata else None
        
        if image_code:
            path = AssetManager.get_storage_path(game_type, image_code)
            if os.path.exists(path):
                try:
                    with Image.open(path) as img:
                        return img.copy()
                except Exception:
                    return None
        
        # If image missing, trigger download and return placeholder
        # TODO: 阻塞式等待下载完成后再返回图片，或者实现一个回调机制通知图片已准备好
        if metadata:
            AssetManager.start_background_download([{'game_type': game_type, 'title': title, 'artist': artist}])
        
        # Return none for using placeholder
        return None
