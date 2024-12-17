import requests
import json
import os

# API 端点
url = "https://www.diving-fish.com/api/maimaidxprober/music_data"

# 文件路径
music_info_path = './music_datasets/all_music_infos.json'
etag_path = './music_datasets/etag.txt'

# 创建目录
os.makedirs(os.path.dirname(music_info_path), exist_ok=True)


# 读取缓存的 etag
def read_cached_etag():
    if os.path.exists(etag_path):
        with open(etag_path, 'r') as file:
            return file.read().strip()
    return None


# 缓存新的 etag
def cache_etag(etag):
    with open(etag_path, 'w') as file:
        file.write(etag)


# 请求乐曲信息并检查 etag
def fetch_music_data():
    headers = {}
    cached_etag = read_cached_etag()

    if cached_etag:
        headers['If-None-Match'] = cached_etag

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # 新数据可用，更新缓存
        music_data = response.json()
        with open(music_info_path, 'w', encoding='utf-8') as file:
            json.dump(music_data, file, ensure_ascii=False, indent=4)

        etag = response.headers.get('etag')
        if etag:
            cache_etag(etag)
        print("Music data updated.")

    elif response.status_code == 304:
        # 数据未更改，无需更新
        print("Music data is up-to-date.")

    else:
        print(f"Failed to fetch music data. Status code: {response.status_code}")

def get_single_song_info(song_id: str):
    with open(music_info_path, 'r', encoding='utf-8') as file:
        music_data = json.load(file)

    for song in music_data:
        if song['id'] == song_id:
            return song


if __name__ == "__main__":
    fetch_music_data()