import json
import os
import random

from utils.PageUtils import DATA_CONFIG_VERSION
from utils.DataUtils import get_data_from_fish
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader

# def merge_b50_data(new_b50_data, old_b50_data):
#     """
#     合并两份b50数据，使用新数据的基本信息但保留旧数据中的视频相关信息
    
#     Args:
#         new_b50_data (list): 新的b50数据（不含video_info_list和video_info_match）
#         old_b50_data (list): 旧的b50数据（youtube版或bilibili版）
    
#     Returns:
#         tuple: (合并后的b50数据列表, 更新计数)
#     """
#     # 检查数据长度是否一致
#     if len(new_b50_data) != len(old_b50_data):
#         print(f"Warning: 新旧b50数据长度不一致，将使用新数据替换旧数据。")
#         return new_b50_data, 0
    
#     # 创建旧数据的复合键映射表
#     old_song_map = {
#         (song['song_id'], song['level_index'], song['type']): song 
#         for song in old_b50_data
#     }
    
#     # 按新数据的顺序创建合并后的列表
#     merged_b50_data = []
#     keep_count = 0
#     for new_song in new_b50_data:
#         song_key = (new_song['song_id'], new_song['level_index'], new_song['type'])
#         if song_key in old_song_map:
#             # 如果记录已存在，使用新数据但保留原有的视频信息
#             cached_song = old_song_map[song_key]
#             new_song['video_info_list'] = cached_song.get('video_info_list', [])
#             new_song['video_info_match'] = cached_song.get('video_info_match', {})
#             if new_song == cached_song:
#                 keep_count += 1
#         else:
#             new_song['video_info_list'] = []
#             new_song['video_info_match'] = {}
#         merged_b50_data.append(new_song)

#     update_count = len(new_b50_data) - keep_count
#     return merged_b50_data, update_count

def fetch_user_gamedata(raw_file_path, data_file_path, username, params, source="fish"):
    # params = {
    #     "type": maimai / chuni / ...,
    #     "query": all / best /
    #     "filiter": {
    #         "tag": "ap",
    #         "top": 50,
    #     },
    #}
    if source == "fish":
        try:
            fish_data = get_data_from_fish(username, params)
        except json.JSONDecodeError:
            print("Error: 读取 JSON 文件时发生错误，请检查数据格式。")
            return None 
        if 'error' in fish_data:
            raise Exception(f"Error: 从水鱼获得B50数据失败。错误信息：{fish_data['error']}")
        
        # 缓存，写入b50_raw_file
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(fish_data, f, ensure_ascii=False, indent=4)
        
        # 生成数据文件
        generate_data_file_from_fish(fish_data, data_file_path, params)


def generate_data_file_from_fish(fish_data, data_file_path, params):
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    filiter = params.get("filiter", None)
    if type == "maimai":
        if query == "best":
            # 解析fish b50数据   
            charts_data = fish_data['charts']
            b35_data = charts_data['sd']
            b15_data = charts_data['dx']

            for i in range(len(b35_data)):
                song = b35_data[i]
                song['clip_name'] = f"PastBest_{i + 1}"

            for i in range(len(b15_data)):
                song = b15_data[i]
                song['clip_name'] = f"NewBest_{i + 1}"
            
            # 合并b35_data和b15_data到同一列表
            b50_data = b35_data + b15_data
            for i in range(len(b50_data)):
                song = b50_data[i]
                song["level_label"] = song.get("level_label", "").upper()
                song['clip_id'] = f"clip_{i + 1}"

            config_content = {
                "version": DATA_CONFIG_VERSION,
                "type": type,
                "sub_type": "best",
                "username": fish_data['username'],
                "rating": fish_data['rating'],
                "length_of_content": len(b50_data),
                "records": b50_data,
            }
        else:
            if not filiter:
                raise ValueError("Error: 查询类型为all时，必须提供filiter参数。")
            else:
                tag = filiter.get("tag", None)
                top_len = filiter.get("top", 50)
                if tag == "ap":
                    data_list = filit_maimai_ap_data(fish_data, top_len)
                    if len(data_list) < top_len:
                        print(f"Warning: 仅找到{len(data_list)}条AP数据，生成实际数据长度小于top_len={top_len}的配置。")
                    config_content = {
                        "version": DATA_CONFIG_VERSION,
                        "type": type,
                        "sub_type": tag,
                        "username": fish_data['username'],
                        "rating": fish_data['rating'],
                        "length_of_content": len(data_list),
                        "records": data_list,
                    }
                else:
                    raise ValueError("Error: 目前仅支持tag为ap的查询类型。")
                
        # 写入b50_data_file
        with open(data_file_path, "w", encoding="utf-8") as f:
            json.dump(config_content, f, ensure_ascii=False, indent=4)
        return config_content
    else:
        raise ValueError("Only MAIMAI DX is supported for now")

def filit_maimai_ap_data(fish_data, top_len=50):
    charts_data = fish_data['records']

    # 解析AP数据
    ap_data = []
    for song in charts_data:
        fc_flag = song.get('fc', '').lower()
        if 'ap' in fc_flag or 'app' in fc_flag:
            ap_data.append(song)

    # 按照ra值降序排序，如果ra值相同，按照ds定数降序排序
    ap_data.sort(key=lambda x: (x.get('ra', 0), x.get('ds', 0)), reverse=True)
    ap_data = ap_data[:top_len]

    for song in ap_data:
        index = ap_data.index(song) + 1
        # 将level_label转换为全大写
        song["level_label"] = song.get("level_label", "").upper()
        # 添加clip_id字段
        song['clip_name'] = f"APBest_{index}"
        song['clip_id'] = f"clip_{index}"

    return ap_data


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


def st_gene_resource_config(records, config_sub_type,
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

    for song in records:
        if not song['clip_id']:
            print(f"Error: 没有找到 {song['title']}-{song['level_label']}-{song['type']} 的clip_id，请检查数据格式，跳过该片段。")
            continue
        id = song['clip_id']
        clip_name = song.get('clip_name', id)
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
            "clip_name": clip_name,
            "achievement_title": song['title'],
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

    # 根据配置文件中的sub_type类型进行排序（b50/apb50等需要翻转排序，其余正序）
    match config_sub_type:
        case "best":
            main_clips.reverse()
        case "ap":
            main_clips.reverse()
        case "custom":
            pass
        case _:
            print(f"Error: 不支持的sub_type类型 {config_sub_type}，将使用默认正序。")
            pass

    video_config_data["main"] = main_clips

    with open(output_file, 'w', encoding="utf-8") as file:
        json.dump(video_config_data, file, ensure_ascii=False, indent=4)

    return video_config_data
