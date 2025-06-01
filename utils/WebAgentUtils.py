import json
import os
import random

from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader

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

    search_result = {
        "song_id": song_data['song_id'],
        "level_index": song_data['level_index']
    }

    if len(videos) == 0:
        output_info = f"Error: 没有找到{title_name}-{difficulty_name}({level_index})-{type}的视频"
        print(output_info)
        search_result['video_info_list'] = []
        search_result['video_info_match'] = {}
        return search_result, output_info

    match_index = 0
    output_info = f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}"
    print(f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}")

    search_result['video_info_list'] = videos
    search_result['video_info_match'] = videos[match_index]
    return search_result, output_info


def download_one_video(downloader, song, video_info, video_download_path, high_res=False):
    clip_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
    
    # Check if video already exists
    video_path = os.path.join(video_download_path, f"{clip_name}.mp4")
    if os.path.exists(video_path):
        print(f"已找到谱面视频的缓存: {clip_name}")
        return {"status": "skip", "info": f"已找到谱面视频的缓存: {clip_name}"}
    
    v_id = video_info['id']
    downloader.download_video(v_id, 
                              clip_name, 
                              video_download_path, 
                              high_res=high_res,
                              p_index=video_info.get('p_index', 0))
    return {"status": "success", "info": f"下载{clip_name}完成"}


def st_init_cache_pathes():
    cache_pathes = [
        f"./b50_datas",
        f"./videos",
        f"./videos/downloads",
        f"./cred_datas"
    ]
    for path in cache_pathes:
        if not os.path.exists(path):
            os.makedirs(path)
