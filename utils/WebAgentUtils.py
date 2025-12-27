import json
import os
import random
import time
import re

from copy import deepcopy
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader, YtDlpDownloader
from utils.DataUtils import chart_type_value2str, level_index_to_label
from utils.video_search_strategy import VideoSearchStrategy, SearchStrategy

def _clean_title_for_search(title: str) -> str:
    """
    清理歌曲名，移除可能影响搜索的特殊字符
    移除 '-'、'@'、'&' 等不常规符号，YouTube搜索可能无法正确识别
    """
    # 移除首尾空白
    cleaned = title.strip()
    
    # 移除或替换可能影响搜索的字符
    # 1. 移除常见的特殊符号（替换为空格）
    special_chars = ['-', '@', '&', '#', '%', '*', '+', '=', '|', '\\', '/', '<', '>', '^', '~', '`']
    for char in special_chars:
        cleaned = cleaned.replace(char, ' ')
    
    # 2. 将多个连续空格替换为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def get_keyword(downloader_type, game_type, title_name, difficulty_name, type):
    match difficulty_name:
        case "BASIC":
            dif_CN_name = "绿谱"
            dif_name = "Basic"
        case "ADVANCE":
            dif_CN_name = "黄谱"
            dif_name = "Advance"
        case "EXPERT":
            dif_CN_name = "红谱"
            dif_name = "Expert"
        case "MASTER":
            dif_CN_name = "紫谱"
            dif_name = "Master"
        case "RE:MASTER":
            dif_CN_name = "白谱"
            dif_name = "Re:MASTER"
        case "ULTIMA":
            dif_CN_name = "黑谱"
            dif_name = "ULTIMA"
        case _:
            dif_CN_name = ""
            dif_name = ""
            print(f"Warning: {title_name}具有未指定的谱面难度！")

    type_mapping = {0: ("标准", "SD"), 1: ("DX谱面", "DX")}
    type_CN_name, type_name = type_mapping.get(type, ("", "")) if game_type == "maimai" else ("", "")

    dif_game_name = "maimaiでらっく 外部出力" if game_type == "maimai" else "CHUNITHM チュウニズム 譜面確認"
    dif_game_CN_name = "maimai 舞萌DX 谱面确认" if game_type == "maimai" else "CHUNITHM 中二节奏 谱面确认"
    
    if downloader_type == "youtube" or downloader_type == "youtube-ytdlp":
        # 对于YouTube（包括yt-dlp），优化关键词格式：
        # 1. 初始搜索包含游戏标识，确保找到正确的游戏视频
        # 2. 如果失败，简化搜索会移除游戏标识，但会验证结果
        # 3. 关键词顺序：歌曲名 + 难度 + 游戏标识（更符合搜索习惯）
        if game_type == "chunithm":
            # 中二节奏：歌曲名 + 难度 + CHUNITHM
            # 注意：如果包含特殊字符可能触发400，但简化搜索会处理
            # 清理歌曲名，移除可能影响搜索的特殊字符（特别是'-'）
            clean_title = _clean_title_for_search(title_name)
            if dif_name:
                # 使用格式：歌曲名 + 难度 + CHUNITHM
                # 这样能确保找到中二节奏的视频，而不是其他游戏
                return f"{clean_title} {dif_name} CHUNITHM"
            else:
                return f"{clean_title} CHUNITHM"
        else:
            # 舞萌：歌曲名 + 类型 + 难度 + maimai
            clean_title = _clean_title_for_search(title_name)
            if type_name:
                return f"{clean_title} {type_name} {dif_name} maimai"
            else:
                return f"{clean_title} {dif_name} maimai"
    elif downloader_type == "bilibili":
        return f"{dif_game_CN_name} {title_name} {type_CN_name} {dif_CN_name}  "
    
    # 如果下载器类型不匹配，返回空字符串而不是 None
    return ""
    
def search_one_video(downloader, chart_data):
    """
    使用成熟的搜索策略搜索视频
    
    采用多策略搜索：
    1. 生成多个关键词变体（从精确到模糊）
    2. 按优先级尝试每个关键词
    3. 对结果进行评分和排序
    4. 选择最佳匹配
    """
    game_type = chart_data['game_type']
    title_name = chart_data['song_name']
    difficulty_name = level_index_to_label(game_type, chart_data['level_index'])
    chart_type = chart_data['chart_type']
    dl_type = "youtube" if isinstance(downloader, (PurePytubefixDownloader, YtDlpDownloader)) \
                else "bilibili" if isinstance(downloader, BilibiliDownloader) \
                else "None"
    
    ret_chart_data = deepcopy(chart_data)
    
    # 对于Bilibili，使用原有逻辑
    if dl_type == "bilibili":
        keyword = get_keyword(dl_type, game_type, title_name, difficulty_name, chart_type)
        print(f"搜索关键词: {keyword}")
        videos = downloader.search_video(keyword)
        
        if len(videos) == 0:
            output_info = f"Error: 没有找到{title_name}-{difficulty_name}-{chart_type}的视频"
            print(output_info)
            ret_chart_data['video_info_list'] = []
            ret_chart_data['video_info_match'] = {}
            return ret_chart_data, output_info
        
        match_index = 0
        output_info = f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}"
        print(f"首个搜索结果: {videos[match_index]['title']}, {videos[match_index]['url']}")
        
        ret_chart_data['video_info_list'] = videos
        ret_chart_data['video_info_match'] = videos[match_index]
        return ret_chart_data, output_info
    
    # 对于YouTube，使用新的多策略搜索
    if dl_type == "youtube":
        search_strategy = VideoSearchStrategy(game_type)
        
        # 生成多个关键词变体
        keyword_variants = search_strategy.generate_search_keywords(
            title_name, difficulty_name, chart_type
        )
        
        all_results = []
        last_error = None
        
        # 按优先级尝试每个关键词
        for keyword, strategy in keyword_variants:
            try:
                print(f"尝试搜索策略 [{strategy.value}]: {keyword}")
                videos = downloader.search_video(keyword)
                
                if videos and len(videos) > 0:
                    # 对结果进行评分和排序
                    scored_results = search_strategy.filter_and_rank_results(
                        videos, title_name, difficulty_name, strategy, min_score=20.0
                    )
                    
                    if scored_results:
                        # 选择最佳匹配
                        best_match = search_strategy.get_best_match(scored_results)
                        
                        if best_match:
                            # 转换为原有格式
                            max_results = getattr(downloader, 'search_max_results', 3)
                            formatted_videos = []
                            for result in scored_results[:max_results]:
                                formatted_videos.append({
                                    'id': result.url,
                                    'pure_id': result.video_id,
                                    'title': result.title,
                                    'url': result.url,
                                    'duration': result.duration,
                                    '_score': result.score,
                                    '_matched_game': result.matched_game,
                                    '_matched_difficulty': result.matched_difficulty
                                })
                            
                            # 选择最佳匹配作为默认结果
                            best_video = {
                                'id': best_match.url,
                                'pure_id': best_match.video_id,
                                'title': best_match.title,
                                'url': best_match.url,
                                'duration': best_match.duration
                            }
                            
                            # 输出匹配信息
                            match_info = []
                            if best_match.matched_game:
                                match_info.append("✓游戏类型匹配")
                            if best_match.matched_difficulty:
                                match_info.append("✓难度匹配")
                            if best_match.matched_title:
                                match_info.append("✓歌曲名匹配")
                            
                            match_status = " | ".join(match_info) if match_info else "⚠️部分匹配"
                            output_info = f"找到最佳匹配 (评分: {best_match.score:.1f}, {match_status}): {best_match.title}"
                            print(output_info)
                            
                            ret_chart_data['video_info_list'] = formatted_videos
                            ret_chart_data['video_info_match'] = best_video
                            return ret_chart_data, output_info
                    
                    # 如果当前策略有结果但评分不够，继续尝试下一个策略
                    all_results.extend(videos)
                
            except Exception as e:
                error_msg = str(e)
                last_error = e
                
                # 如果是400错误，继续尝试下一个策略
                if "400" in error_msg or "Bad Request" in error_msg:
                    print(f"搜索策略 [{strategy.value}] 失败: {error_msg}，尝试下一个策略...")
                    time.sleep(1)  # 短暂延迟
                    continue
                else:
                    # 其他错误，记录但继续尝试
                    print(f"搜索策略 [{strategy.value}] 出错: {error_msg}，尝试下一个策略...")
                    continue
        
        # 所有策略都失败
        if all_results:
            # 即使所有策略都失败，如果有任何结果，使用第一个
            max_results = getattr(downloader, 'search_max_results', 3)
            print(f"⚠️ 所有搜索策略都遇到问题，使用备用结果")
            ret_chart_data['video_info_list'] = all_results[:max_results]
            ret_chart_data['video_info_match'] = all_results[0]
            output_info = f"备用结果: {all_results[0]['title']}, {all_results[0]['url']}"
            return ret_chart_data, output_info
        else:
            error_msg = str(last_error) if last_error else "未知错误"
            output_info = f"Error: 所有搜索策略均失败，未找到{title_name}-{difficulty_name}-{chart_type}的视频。最后错误: {error_msg}"
            print(output_info)
            ret_chart_data['video_info_list'] = []
            ret_chart_data['video_info_match'] = {}
            return ret_chart_data, output_info
    
    # 未知下载器类型
    output_info = f"Error: 不支持的下载器类型"
    ret_chart_data['video_info_list'] = []
    ret_chart_data['video_info_match'] = {}
    return ret_chart_data, output_info

def download_one_video(downloader, db_handler, song, video_download_path, high_res=False):
    chart_id = song.get('chart_id', None)
    if not chart_id:
        return {"status": "error", "info": f"Error: 错误的谱面数据，未找到chart_id，Skipping………"}
    
    clip_tag = f"{song['game_type']}-{song['song_id']}-{song['level_index']}-{song['chart_type']}"
    # Do not use song_id in video file name, because song name may not consisted with windows file name rules
    clip_file_name = f"{song['game_type']}-{song['chart_id']}-{song['level_index']}-{song['chart_type']}"
    
    # Check if video already exists
    video_path = os.path.join(video_download_path, f"{clip_file_name}.mp4")
    # 转换为绝对路径
    abs_video_path = os.path.abspath(video_path)
    if os.path.exists(video_path):
        print(f"已找到谱面视频的缓存: {clip_tag}")
        # Write video path info to database
        db_handler.update_chart_video_path(chart_id=song['chart_id'], video_path=abs_video_path)
        return {"status": "skip", "info": f"已找到谱面视频的缓存: {clip_tag}"}
        
    if 'video_info_match' not in song or not song['video_info_match']:
        print(f"Error: 没有{clip_tag}的视频信息，Skipping………")
        return {"status": "error", "info": f"Error: 没有{clip_tag}的视频信息，Skipping………"}
    
    video_info = song['video_info_match']
    v_id = video_info['id']
    try:
        downloader.download_video(v_id, 
                                clip_file_name, 
                                video_download_path, 
                                high_res=high_res,
                                p_index=video_info.get('p_index', 0))
        # Write video path info to database
        db_handler.update_chart_video_path(chart_id=song['chart_id'], video_path=abs_video_path)
        return {"status": "success", "info": f"下载{clip_tag}完成"}
    except Exception as e:
        print(f"Error: 谱面视频下载失败: {clip_tag}，error: {e}")
        return {"status": "error", "info": f"Error: 谱面视频下载失败: {clip_tag}，Skipping………"}


def st_init_cache_pathes():
    cache_pathes = [
        f"./b50_datas",
        f"./chunithm_datas",
        f"./videos",
        f"./videos/downloads",
        f"./cred_datas"
    ]
    for path in cache_pathes:
        if not os.path.exists(path):
            os.makedirs(path)

# 弃用，自动初始化默认值，不再需要手动初始化
@DeprecationWarning
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