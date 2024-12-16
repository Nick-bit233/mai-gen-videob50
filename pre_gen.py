import json
import os
import random
import time
import yaml
import traceback
import threading
import webbrowser
from update_music_data import fetch_music_data
from gene_images import generate_b50_images
from utils.Utils import get_b50_data_from_fish
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader

def merge_b50_data(new_b50_data, old_b50_data):
    """
    合并两份b50数据，使用新数据的基本信息但保留旧数据中的视频相关信息
    
    Args:
        new_b50_data (list): 新的b50数据（不含video_info_list和video_info_match）
        old_b50_data (list): 旧的b50数据（youtube版或bilibili版）
    
    Returns:
        tuple: (合并后的b50数据列表, 更新计数)
    """
    # 检查数据长度是否一致
    if len(new_b50_data) != len(old_b50_data):
        print(f"Warning: 新旧b50数据长度不一致，将使用新数据替换旧数据。")
        return new_b50_data, 0
    
    # 创建旧数据的复合键映射表
    old_song_map = {
        (song['song_id'], song['level_index'], song['type']): song 
        for song in old_b50_data
    }
    
    # 按新数据的顺序创建合并后的列表
    merged_b50_data = []
    keep_count = 0
    for new_song in new_b50_data:
        song_key = (new_song['song_id'], new_song['level_index'], new_song['type'])
        if song_key in old_song_map:
            # 如果记录已存在，使用新数据但保留原有的视频信息
            cached_song = old_song_map[song_key]
            new_song['video_info_list'] = cached_song.get('video_info_list', [])
            new_song['video_info_match'] = cached_song.get('video_info_match', {})
            if new_song == cached_song:
                keep_count += 1
        else:
            new_song['video_info_list'] = []
            new_song['video_info_match'] = {}
        merged_b50_data.append(new_song)

    update_count = len(new_b50_data) - keep_count
    return merged_b50_data, update_count


def update_b50_data(b50_raw_file, b50_data_file, username):
    try:
        fish_data = get_b50_data_from_fish(username)
    except json.JSONDecodeError:
        print("Error: 读取 JSON 文件时发生错误，请检查数据格式。")
        return None 
    if 'error' in fish_data:
        raise Exception(f"Error: 从水鱼获得B50数据失败。错误信息：{fish_data['error']}")
    
    charts_data = fish_data['charts']
    # user_rating = fish_data['rating']
    # user_dan = fish_data['additional_rating']
    b35_data = charts_data['sd']
    b15_data = charts_data['dx']

    # 缓存，写入b50_raw_file
    with open(b50_raw_file, "w", encoding="utf-8") as f:
        json.dump(fish_data, f, ensure_ascii=False, indent=4)

    for i in range(len(b35_data)):
        song = b35_data[i]
        song['clip_id'] = f"PastBest_{i + 1}"

    for i in range(len(b15_data)):
        song = b15_data[i]
        song['clip_id'] = f"NewBest_{i + 1}"
    
    # 合并b35_data和b15_data到同一列表
    b50_data = b35_data + b15_data
    new_local_b50_data = []
    # 检查是否已有b50_data_file
    if os.path.exists(b50_data_file):
        with open(b50_data_file, "r", encoding="utf-8") as f:
            local_b50_data = json.load(f)
            new_local_b50_data, _ = merge_b50_data(b50_data, local_b50_data)
    else:
        new_local_b50_data = b50_data

    # 写入b50_data_file
    with open(b50_data_file, "w", encoding="utf-8") as f:
        json.dump(new_local_b50_data, f, ensure_ascii=False, indent=4)
    return new_local_b50_data


def get_keyword(downloader_type, title_name, level_index, type):
    match level_index:
        case 0:
            dif_CN_name = "绿谱"
            dif_name = "Basic"
        case 1:
            dif_CN_name = "黄谱"
            dif_name = "Advance"
        case 2:
            dif_CN_name = "红谱"
            dif_name = "Expert"
        case 3:
            dif_CN_name = "紫谱"
            dif_name = "Master"
        case 4:
            dif_CN_name = "白谱"
            dif_name = "Re:MASTER"
        case _:
            dif_CN_name = ""
            dif_name = ""
            print(f"Warning: {title_name}具有未指定的谱面难度！")
    if downloader_type == "youtube":
        suffix = "AP【maimaiでらっくす外部出力】"
        return f"{title_name} {'DX譜面' if type != 'SD' else ''} {dif_name} {suffix}"
    elif downloader_type == "bilibili":
        prefix = "【maimai】【谱面确认】"
        return f"{prefix} {'DX谱面' if type != 'SD' else '标准谱面'} {title_name} {dif_CN_name} {dif_name} "
    

def search_one_video(downloader, song_data):
    title_name = song_data['title']
    difficulty_name = song_data['level_label']
    level_index = song_data['level_index']
    type = song_data['type']
    dl_type = "youtube" if isinstance(downloader, PurePytubefixDownloader) \
                else "bilibili" if isinstance(downloader, BilibiliDownloader) \
                else "None"
    keyword = get_keyword(dl_type, title_name, level_index, type)

    print(f"搜索关键词: {keyword}")
    videos = downloader.search_video(keyword)

    if len(videos) == 0:
        output_info = f"Error: 没有找到{title_name}-{difficulty_name}({level_index})-{type}的视频"
        print(output_info)
        song_data['video_info_list'] = []
        song_data['video_info_match'] = {}
        return song_data, output_info

    match_index = 0
    output_info = f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}"
    print(f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}")

    song_data['video_info_list'] = videos
    song_data['video_info_match'] = videos[match_index]
    return song_data, output_info


def search_b50_videos(downloader, b50_data, b50_data_file, search_wait_time=(0,0)):
    global search_max_results, downloader_type

    i = 0
    for song in b50_data:
        i += 1
        # Skip if video info already exists and is not empty
        if 'video_info_match' in song and song['video_info_match']:
            print(f"跳过({i}/50): {song['title']} ，已储存有相关视频信息")
            continue
        
        print(f"正在搜索视频({i}/50): {song['title']}")
        song_data = search_one_video(downloader, song)

        # 每次搜索后都写入b50_data_file
        with open(b50_data_file, "w", encoding="utf-8") as f:
            json.dump(b50_data, f, ensure_ascii=False, indent=4)
        
        # 等待几秒，以减少被检测为bot的风险
        if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0]:
            time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))
    
    return b50_data


def download_one_video(downloader, song, video_download_path, high_res=False):
    clip_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
    
    # Check if video already exists
    video_path = os.path.join(video_download_path, f"{clip_name}.mp4")
    if os.path.exists(video_path):
        print(f"已找到谱面视频的缓存: {clip_name}")
        return {"status": "skip", "info": f"已找到谱面视频的缓存: {clip_name}"}
        
    if 'video_info_match' not in song or not song['video_info_match']:
        print(f"Error: 没有{song['title']}-{song['level_label']}-{song['type']}的视频信息，Skipping………")
        return {"status": "error", "info": f"Error: 没有{song['title']}-{song['level_label']}-{song['type']}的视频信息，Skipping………"}
    
    video_info = song['video_info_match']
    v_id = video_info['id'] 
    downloader.download_video(v_id, 
                              clip_name, 
                              video_download_path, 
                              high_res=high_res)
    return {"status": "success", "info": f"下载{clip_name}完成"}

    
def download_b50_videos(downloader, b50_data, video_download_path, download_wait_time=(0,0)):
    global download_high_res

    i = 0
    for song in b50_data:
        i += 1
        # 视频命名为song['song_id']-song['level_index']-song['type']，以便查找复用
        clip_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
        
        # Check if video already exists
        video_path = os.path.join(video_download_path, f"{clip_name}.mp4")
        if os.path.exists(video_path):
            print(f"已找到谱面视频的缓存({i}/50): {clip_name}")
            continue
            
        print(f"正在下载视频({i}/50): {clip_name}……")
        if 'video_info_match' not in song or not song['video_info_match']:
            print(f"Error: 没有{song['title']}-{song['level_label']}-{song['type']}的视频信息，Skipping………")
            continue
        video_info = song['video_info_match']
        v_id = video_info['id'] 
        downloader.download_video(v_id, 
                                  clip_name, 
                                  video_download_path, 
                                  high_res=download_high_res)
        
        # 等待几秒，以减少被检测为bot的风险
        if download_wait_time[0] > 0 and download_wait_time[1] > download_wait_time[0]:
            time.sleep(random.randint(download_wait_time[0], download_wait_time[1]))
        print("\n")


def gene_resource_config(b50_data, images_path, videoes_path, ouput_file):
    global clip_start_interval, clip_play_time, default_comment_placeholders

    intro_clip_data = {
        "id": "intro_1",
        "duration": 10,
        "text": "【请填写前言部分】" if default_comment_placeholders else ""
    }

    ending_clip_data = {
        "id": "ending_1",
        "duration": 10,
        "text": "【请填写后记部分】" if default_comment_placeholders else ""
    }

    video_config_data = {
        "enable_re_modify": False,
        "intro": [intro_clip_data],
        "ending": [ending_clip_data],
        "main": [],
    }

    main_clips = []
    
    if clip_start_interval[0] > clip_start_interval[1]:
        print(f"Error: 视频开始时间区间设置错误，请检查global_config.yaml文件中的CLIP_START_INTERVAL配置。")
        clip_start_interval = (clip_start_interval[1], clip_start_interval[1])

    for song in b50_data:
        if not song['clip_id']:
            print(f"Error: 没有找到 {song['title']}-{song['level_label']}-{song['type']} 的clip_id，请检查数据格式，跳过该片段。")
            continue
        id = song['clip_id']
        video_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
        __image_path = os.path.join(images_path, id + ".png")
        __image_path = os.path.normpath(__image_path)
        if not os.path.exists(__image_path):
            print(f"Error: 没有找到 {id}.png 图片，请检查本地缓存数据。")
            __image_path = ""

        __video_path = os.path.join(videoes_path, video_name + ".mp4")
        __video_path = os.path.normpath(__video_path)
        if not os.path.exists(__video_path):
            print(f"Error: 没有找到 {video_name}.mp4 视频，请检查本地缓存数据。")
            __video_path = ""
        
        duration = clip_play_time
        start = random.randint(clip_start_interval[0], clip_start_interval[1])
        end = start + duration

        main_clip_data = {
            "id": id,
            "achievement_title": f"{song['title']}-{song['level_label']}-{song['type']}",
            "song_id": song['song_id'],
            "level_index": song['level_index'],
            "type": song['type'],
            "main_image": __image_path,
            "video": __video_path,
            "duration": duration,
            "start": start,
            "end": end,
            "text": "【请填写b50评价】" if default_comment_placeholders else "",
        }
        main_clips.append(main_clip_data)

    # 倒序排列（b15在前，b35在后）
    main_clips.reverse()

    video_config_data["main"] = main_clips

    with open(ouput_file, 'w', encoding="utf-8") as file:
        json.dump(video_config_data, file, ensure_ascii=False, indent=4)

    return video_config_data


def st_init_cache_pathes():
    cache_pathes = [
        f"./b50_datas",
        f"./b50_images",
        f"./videos",
        f"./videos/downloads",
        f"./cred_datas"
    ]
    for path in cache_pathes:
        if not os.path.exists(path):
            os.makedirs(path)


def st_gene_resource_config(b50_data, 
                            images_path, videoes_path, output_file,
                            clip_start_interval, clip_play_time, default_comment_placeholders):
    intro_clip_data = {
        "id": "intro_1",
        "duration": 10,
        "text": "【请填写前言部分】" if default_comment_placeholders else ""
    }

    ending_clip_data = {
        "id": "ending_1",
        "duration": 10,
        "text": "【请填写后记部分】" if default_comment_placeholders else ""
    }

    video_config_data = {
        "enable_re_modify": False,
        "intro": [intro_clip_data],
        "ending": [ending_clip_data],
        "main": [],
    }

    main_clips = []
    
    if clip_start_interval[0] > clip_start_interval[1]:
        print(f"Error: 视频开始时间区间设置错误，请检查global_config.yaml文件中的CLIP_START_INTERVAL配置。")
        clip_start_interval = (clip_start_interval[1], clip_start_interval[1])

    for song in b50_data:
        if not song['clip_id']:
            print(f"Error: 没有找到 {song['title']}-{song['level_label']}-{song['type']} 的clip_id，请检查数据格式，跳过该片段。")
            continue
        id = song['clip_id']
        video_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
        __image_path = os.path.join(images_path, id + ".png")
        __image_path = os.path.normpath(__image_path)
        if not os.path.exists(__image_path):
            print(f"Error: 没有找到 {id}.png 图片，请检查本地缓存数据。")
            __image_path = ""

        __video_path = os.path.join(videoes_path, video_name + ".mp4")
        __video_path = os.path.normpath(__video_path)
        if not os.path.exists(__video_path):
            print(f"Error: 没有找到 {video_name}.mp4 视频，请检查本地缓存数据。")
            __video_path = ""
        
        duration = clip_play_time
        start = random.randint(clip_start_interval[0], clip_start_interval[1])
        end = start + duration

        main_clip_data = {
            "id": id,
            "achievement_title": f"{song['title']}-{song['level_label']}-{song['type']}",
            "song_id": song['song_id'],
            "level_index": song['level_index'],
            "type": song['type'],
            "main_image": __image_path,
            "video": __video_path,
            "duration": duration,
            "start": start,
            "end": end,
            "text": "【请填写b50评价】" if default_comment_placeholders else "",
        }
        main_clips.append(main_clip_data)

    # 倒序排列（b15在前，b35在后）
    main_clips.reverse()

    video_config_data["main"] = main_clips

    with open(output_file, 'w', encoding="utf-8") as file:
        json.dump(video_config_data, file, ensure_ascii=False, indent=4)

    return video_config_data
