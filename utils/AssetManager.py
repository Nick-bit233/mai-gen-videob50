import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from utils.DataUtils import query_songs_metadata, get_jacket_image_from_url

class AssetManager:
    _executor = ThreadPoolExecutor(max_workers=4)

    @staticmethod
    def get_storage_path(game_type: str, image_code: str) -> str:
        # Create directory if it doesn't exist
        directory = os.path.join("static", "assets", "jackets", game_type)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Return absolute path with .png extension
        # Note: image_code from otoge usually includes extension (e.g. 123.png)
        # resulting in 123.png.png, which is safe and consistent.
        # But let's check if image_code already has extension.
        # Usually query_songs_metadata returns image_code_otoge which is often just the filename or code.
        # Let's just append .png to be safe as local storage format.
        filename = f"{image_code}.png"
        return os.path.abspath(os.path.join(directory, filename))

    @staticmethod
    def download_jacket(game_type: str, title: str, artist: str):
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
            # source='otoge' is what was used in the original code
            img = get_jacket_image_from_url(image_code, source='otoge', game_type=game_type)
            if img:
                img.save(storage_path, "PNG")
                print(f"[AssetManager] Downloaded jacket for {title}")
        except Exception as e:
            print(f"[AssetManager] Failed to download jacket for {title}: {e}")

    @staticmethod
    def start_background_download(chart_info_list: list):
        """
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
    def get_jacket_image(game_type: str, title: str, artist: str) -> Image.Image:
        metadata = query_songs_metadata(game_type, title, artist)
        image_code = metadata.get('image_code_otoge') if metadata else None
        
        if image_code:
            path = AssetManager.get_storage_path(game_type, image_code)
            if os.path.exists(path):
                try:
                    return Image.open(path)
                except Exception:
                    pass
        
        # If image missing, trigger download and return placeholder
        if metadata:
            AssetManager.start_background_download([{'game_type': game_type, 'title': title, 'artist': artist}])
        
        # Return 400x400 black placeholder
        return Image.new('RGB', (400, 400), (0, 0, 0))
