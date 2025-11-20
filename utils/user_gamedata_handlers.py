import glob
import json
from lxml import etree
import os
import re
import json
import requests

from utils.dxnet_extension import ChartManager
from utils.DataUtils import (
    FC_PROXY_ENDPOINT, 
    fish_to_new_record_format,
    query_songs_metadata,
    chart_type_str2value,
    level_label_to_index,
    chunithm_fc_status_to_label
)

LEVEL_LABEL = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]

# 辅助函数：格式化song_id
def format_record_songid(record, raw_song_id, game_type="maimai"):
    """格式化song_id，如果无效则返回原始值"""
    if raw_song_id and isinstance(raw_song_id, int) and raw_song_id > 0:
        return raw_song_id
    # 如果song_id无效，返回原始值或0
    return raw_song_id if raw_song_id else 0

################################################
# Query B50 data from diving-fish.com (maimai dx)
################################################
def get_data_from_fish(username, params=None):
    """从水鱼获取数据"""
    if params is None:
        params = {}
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    if type == "maimai":  # MAIMAI 的请求
        if query == "best":
            url = "https://www.diving-fish.com/api/maimaidxprober/query/player"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json"
            }
            payload = {
                "username": username,
                "b50": "1"
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400 or response.status_code == 403:
                msg = response.json().get("message", None)
                if not msg:
                    msg = response.json().get("msg", "水鱼端未知错误")
                return {"error": f"用户校验失败，返回消息：{msg}"}
            else:
                return {"error": f"请求水鱼数据失败，状态码: {response.status_code}，返回消息：{response.json()}"}
            
        elif query == "all":
            # get all data from thrid party function call
            response = requests.get(FC_PROXY_ENDPOINT, params={"username": username, "game": "maimai"}, timeout=60)
            response.raise_for_status()

            return json.loads(response.text)
        elif query == "test_all":
            url = "https://www.diving-fish.com/api/maimaidxprober/player/test_data"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            return response.json()
        else:
            raise ValueError("Invalid filter type for MAIMAI DX")
        
    elif type == "chunithm":  # CHUNITHM 的请求
        if query == "best":
            url = "https://www.diving-fish.com/api/chunithmprober/query/player"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json"
            }
            payload = {
                "username": username,
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400 or response.status_code == 403:
                msg = response.json().get("message", None)
                if not msg:
                    msg = response.json().get("msg", "水鱼端未知错误")
                return {"error": f"用户校验失败，返回消息：{msg}"}
            else:
                return {"error": f"请求水鱼数据失败，状态码: {response.status_code}，返回消息：{response.json()}"}
        elif query == "all":
            # TODO: update Function Call service.
            raise NotImplementedError("Function Call service for CHUNITHM is not implemented yet.")
            # response = requests.get(FC_PROXY_ENDPOINT, params={"username": username, "game": "chunithm"}, timeout=60)
            # response.raise_for_status()
            # return json.loads(response.text)
        else:
            raise ValueError("Invalid filter type for CHUNITHM")
    else:
        raise ValueError("Invalid game data type for diving-fish.com")

################################################
# Query B30 data from lxns.net (落雪查分器)
################################################
def get_data_from_lxns(friend_code, api_key, params=None):
    """
    从落雪查分器获取中二节奏数据
    
    Args:
        friend_code: 玩家好友码
        api_key: 开发者API密钥
        params: 查询参数
    """
    if params is None:
        params = {}
    type = params.get("type", "chunithm")
    query = params.get("query", "best")
    
    if type == "chunithm":
        if query == "best":
            # 获取B30和N20分表数据
            base_url = "https://maimai.lxns.net"
            bests_url = f"{base_url}/api/v0/chunithm/player/{friend_code}/bests"
            
            headers = {
                "Authorization": api_key
            }
            
            response = requests.get(bests_url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                error_data = response.json() if response.text else {}
                return {"error": f"认证失败，请检查API密钥是否正确。错误信息：{error_data}"}
            elif response.status_code == 403:
                error_data = response.json() if response.text else {}
                return {"error": f"权限不足，API密钥需要 allow_third_party_fetch_scores 权限。错误信息：{error_data}"}
            else:
                return {"error": f"请求落雪查分器数据失败，状态码: {response.status_code}，返回消息：{response.text[:200]}"}
        else:
            raise ValueError("Invalid filter type for CHUNITHM")
    else:
        raise ValueError("Invalid game data type for lxns.net")

################################################
# Convert lxns score data to internal format
################################################
def convert_lxns_score_to_internal(lxns_score, index, clip_prefix="Best"):
    """
    将落雪查分器的成绩数据转换为项目内部格式
    
    Args:
        lxns_score: 落雪查分器的成绩数据
        index: 索引（从1开始）
        clip_prefix: clip_name前缀（Best或New）
    
    Returns:
        转换后的成绩记录
    """
    # 难度标签映射
    LEVEL_LABEL_MAP = {
        0: "BASIC",
        1: "ADVANCED", 
        2: "EXPERT",
        3: "MASTER",
        4: "ULTIMA"
    }
    
    # 解析level字符串获取定数（中二节奏中，+号表示0.6的增量）
    level_str = lxns_score.get("level", "0")
    if "+" in level_str:
        base_level = float(level_str.replace("+", ""))
        ds = base_level + 0.6
    else:
        ds = float(level_str)
    
    # 计算达成率（chunithm满分是1010000）
    score = lxns_score.get("score", 0)
    achievements = (score / 1010000.0) * 100.0 if score > 0 else 0.0
    
    # 保持落雪查分器的原始格式（不缩写）
    fc_status = lxns_score.get("full_combo", "")
    fc = fc_status if fc_status else ""  # 保持原始值：fullcombo, alljustice 等
    
    # 保持落雪查分器的原始格式（不缩写）
    full_chain_status = lxns_score.get("full_chain", "")
    full_chain = full_chain_status if full_chain_status else ""  # 保持原始值：fullchain, alljustice 等
    
    # 获取难度索引和标签
    level_index = lxns_score.get("level_index", 0)
    level_label = LEVEL_LABEL_MAP.get(level_index, "EXPERT")
    
    # 构建记录
    record = {
        "title": lxns_score.get("song_name", ""),
        "artist": None,  # 落雪API不返回artist，需要从metadata中获取
        "level": level_str,
        "ds": ds,
        "level_index": level_index,
        "level_label": level_label,
        "achievements": achievements,
        "ra": lxns_score.get("rating", 0),
        "fc": fc,
        "fs": full_chain,
        "type": "STANDARD",
        "clip_name": f"{clip_prefix}_{index}",
        "clip_id": f"clip_{index}",
        "rank": lxns_score.get("rank", ""),
        "score": score,
        "over_power": lxns_score.get("over_power", 0),
        "clear": lxns_score.get("clear", ""),
    }
    
    # 格式化song_id
    raw_song_id = lxns_score.get("id")
    record["song_id"] = format_record_songid(record, raw_song_id, game_type="chunithm")
    # 保存原始song_id以便后续从元数据中查找定数
    record["raw_song_id"] = raw_song_id
    
    return record

################################################
# Convert internal format to new format (with chart_data)
################################################
def convert_internal_to_new_format(internal_record: dict, game_type: str = "chunithm") -> dict:
    """
    将内部格式的记录转换为包含chart_data的新格式
    
    Args:
        internal_record: 内部格式的记录（来自convert_lxns_score_to_internal）
        game_type: 游戏类型
    
    Returns:
        包含chart_data的新格式记录
    """
    import math
    from utils.DataUtils import query_songs_metadata, query_chunithm_ds_by_id
    
    # 获取歌曲信息
    song_name = internal_record.get("title", "")
    song_id = internal_record.get("song_id", "")
    artist = internal_record.get("artist", None)
    level_index = internal_record.get("level_index", 0)
    
    # 获取原始song_id（来自落雪API的id字段）
    raw_song_id = None
    if isinstance(song_id, str) and song_id.startswith("chunithm_"):
        # 从格式化的song_id中提取原始ID
        try:
            raw_song_id = int(song_id.replace("chunithm_", ""))
        except:
            pass
    elif isinstance(song_id, int):
        raw_song_id = song_id
    
    # 如果internal_record中有原始id，优先使用
    if 'raw_song_id' in internal_record:
        raw_song_id = internal_record['raw_song_id']
    
    # 查询歌曲元数据（如果失败，使用internal_record中的artist）
    resolved_artist = artist
    ds_from_metadata = None
    try:
        song = query_songs_metadata(game_type, song_name, artist)
        if song:
            resolved_artist = song.get('artist', artist)
            # 如果有原始song_id，尝试从元数据中获取定数
            if raw_song_id is not None:
                ds_from_metadata = query_chunithm_ds_by_id(raw_song_id, level_index)
    except Exception as e:
        print(f"警告: 查询歌曲元数据失败 ({song_name}): {e}")
    
    # 确定定数值：优先使用元数据中的internalLevelValue，否则使用internal_record中的ds
    if ds_from_metadata is not None:
        ds_value = ds_from_metadata
    else:
        ds_value = internal_record.get("ds", 0.0)
    
    # 截断ra到两位小数（不四舍五入）
    ra_value = internal_record.get("ra", 0.0)
    if isinstance(ra_value, (int, float)):
        ra_truncated = math.floor(ra_value * 100) / 100.0
    else:
        ra_truncated = ra_value
    
    # 构建chart_data
    chart_type = chart_type_str2value("normal", fish_record_style=False)  # Chunithm默认是normal (0)
    
    chart_data = {
        'game_type': game_type,
        'song_id': song_id if song_id else song_name,  # 如果没有song_id，使用song_name
        'chart_type': chart_type,
        'level_index': level_index,
        'difficulty': str(ds_value),  # 使用从元数据获取的定数
        'song_name': song_name,
        'artist': resolved_artist,
        'max_dx_score': 0,  # Chunithm不使用dx_score
        'video_path': None
    }
    
    # 构建新格式的记录（保持原始格式的fc和fs值）
    new_record = {
        'chart_data': chart_data,
        'order_in_archive': 0,  # 将在后续设置
        'achievement': internal_record.get("score", 0),  # Chunithm使用score作为achievement
        'fc_status': internal_record.get("fc", ""),  # 保持原始格式：fullcombo, alljustice等
        'fs_status': internal_record.get("fs", ""),  # 保持原始格式：fullchain, alljustice等
        'dx_score': None,
        'dx_rating': 0,
        'chuni_rating': ra_truncated,  # 使用截断后的ra值
        'play_count': 0,
        'clip_title_name': internal_record.get("clip_name", ""),
        # 存储原始数据（包含所有原始字段）
        'raw_data': json.dumps(internal_record, ensure_ascii=True)
    }
    
    return new_record

################################################
# Generate config file from lxns data
################################################
def generate_config_file_from_lxns(lxns_data, params, friend_code):
    """
    从落雪查分器数据生成存档初始化数据配置
    
    Args:
        lxns_data: 落雪查分器返回的数据
        params: 查询参数
        friend_code: 好友码
    
    Returns:
        用于创建新存档的数据字典
    """
    type = params.get("type", "chunithm")
    query = params.get("query", "best")
    
    if type == "chunithm":
        if query == "best":
            # 解析落雪查分器的B30和N20数据
            if not isinstance(lxns_data, dict) or 'data' not in lxns_data:
                raise ValueError("Error: 落雪查分器返回数据格式不正确")
            
            bests_data = lxns_data['data']
            b30_list = bests_data.get('bests', [])  # Best 30
            n20_list = bests_data.get('new_bests', [])  # New 20
            
            # 转换B30数据
            b30_records = []
            for i, score in enumerate(b30_list):
                # 先转换为内部格式（保持原始格式的fc和fs）
                internal_record = convert_lxns_score_to_internal(score, i + 1, "Best")
                # 再转换为包含chart_data的新格式
                new_format_record = convert_internal_to_new_format(internal_record, game_type="chunithm")
                b30_records.append(new_format_record)
            
            # 只使用B30数据
            all_records = b30_records
            
            # 使用好友码作为用户名
            username = friend_code
            
            # 计算总rating（B30的rating总和）
            total_rating = sum(record.get('chuni_rating', 0) for record in b30_records)
            
            # 设置order_in_archive（倒序，rating最高的在最前面）
            for i, record in enumerate(b30_records):
                record['order_in_archive'] = len(b30_records) - i
            
            new_archive_data = {
                "game_type": "chunithm",
                "sub_type": "best",
                "username": username,
                "rating_mai": 0,
                "rating_chu": total_rating,
                "game_version": "latest_CN",
                "initial_records": all_records
            }
            
            return new_archive_data
        else:
            raise ValueError("Error: 目前仅支持best查询类型。")
    else:
        raise ValueError("Invalid game data type for lxns.net")
    
################################################
# B50 data handlers from diving-fish.com
################################################
def fetch_user_gamedata(raw_file_path, username, params, source="fish") -> dict:
    """Entry point function for st_pages"""
    if source == "fish":
        try:
            fish_data = get_data_from_fish(username, params)
        except json.JSONDecodeError:
            print("Error: 读取 JSON 文件时发生错误，请检查数据格式。")
            return None
        
        # 缓存，写入b50_raw_file
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(fish_data, f, ensure_ascii=False, indent=4)

        if 'error' in fish_data:
            raise Exception(f"Error: 从水鱼获得B50数据失败。错误信息：{fish_data['error']}")
        if 'msg' in fish_data:
            raise Exception(f"Error: 从水鱼获得B50数据失败。错误信息：{fish_data['msg']}")
        
        # 解析查分器数据，并生成适用于写入数据库的配置字典
        return generate_archive_data_from_fish(fish_data, params)
    elif source == "lxns":
        # 从落雪查分器获取数据
        api_key = params.get("api_key", "")
        friend_code = params.get("friend_code", username)  # 如果没有提供friend_code，使用username
        
        if not api_key:
            raise Exception("Error: 使用落雪查分器需要提供API密钥")
        
        try:
            lxns_data = get_data_from_lxns(friend_code, api_key, params)
        except Exception as e:
            raise Exception(f"Error: 从落雪查分器获取数据失败: {e}")
        
        # 缓存，写入raw_file_path
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(lxns_data, f, ensure_ascii=False, indent=4)
        
        if 'error' in lxns_data:
            raise Exception(f"Error: 从落雪查分器获得数据失败。错误信息：{lxns_data['error']}")
        
        # 生成存档初始化数据配置
        return generate_config_file_from_lxns(lxns_data, params, friend_code)
    else:
        raise ValueError("Invalid source for fetching game data")


def generate_archive_data_from_fish(fish_data, params) -> dict:
    """根据从水鱼获取的原始数据，生成存档初始化数据配置
    Args:
        fish_data (dict): 从水鱼获取的原始数据
        data_file_path (str): 生成的数据文件路径
        params (dict): 处理参数:
            type (str): 游戏类型，"maimai"或"chuni"，默认为"maimai"
            query (str): 查询数据数量，"best"或"all"，默认为"best"
            filter (dict): 过滤条件，有效键值示例：{"tag": "ap", "top": 50}
        Returns: 
            new_archive (dict): 用于创建新存档的数据字典，包括存档信息和initial_records的列表
    """
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    filter = params.get("filter", None)

    sub_type_tag = ""
    to_modify_data = None

    if type == "maimai":
        if query == "best":
            # 解析fish b50数据
            charts_data = fish_data['charts']
            b35_data = charts_data['sd']
            b15_data = charts_data['dx']
            # 为初始化数据添加clip_title_name字段，
            for i in range(len(b35_data)):
                song = b35_data[i]
                song['clip_title_name'] = f"PastBest_{i + 1}"

            for i in range(len(b15_data)):
                song = b15_data[i]
                song['clip_title_name'] = f"NewBest_{i + 1}" 
            # 合并b35_data和b15_data到同一列表
            to_modify_data = b35_data + b15_data
            sub_type_tag = "best"
        else:
            if not filter:
                raise ValueError("Error: 查询类型为all时，必须提供filter参数。")
            else:
                tag = filter.get("tag", None)
                top_len = filter.get("top", 50)
                if tag == "ap":
                    data_list = filter_maimai_ap_data(fish_data, top_len)
                    if len(data_list) < top_len:
                        print(f"Warning: 仅找到{len(data_list)}条AP数据，生成实际数据长度小于top_len={top_len}的配置。")
                    to_modify_data = data_list
                    sub_type_tag = "ap"
                else:
                    raise ValueError("Error: 目前仅支持tag为ap的查询类型。")
    elif type == "chunithm":
        if query == "best":
            # 解析fish chunithm数据（仅保留b30）
            charts_data = fish_data['records']['b30']
            # 为初始化数据添加clip_title_name字段，
            for i in range(len(charts_data)):
                song = charts_data[i]
                song['clip_title_name'] = f"Best_{i + 1}"
            to_modify_data = charts_data
            sub_type_tag = "best"
        else:
            raise ValueError("Error: 暂未支持chunithm ap列表查询。")
    else:
        raise ValueError("Invalid game data type for diving-fish.com")
    
    # 统一转换为数据库记录格式
    new_record_data = [fish_to_new_record_format(song, type) for song in to_modify_data]

    # 构建默认排序（默认倒序） # TODO: 该项排序可以自定义，记得取消生成视频时的排序选项
    for i in range(len(new_record_data)):
        new_record_data[i]['order_in_archive'] = len(new_record_data) - i

    new_archive_data = {
        "game_type": type,
        "sub_type": sub_type_tag,
        "username": fish_data['username'],
        "rating_mai": fish_data['rating'] if type == "maimai" else 0,
        "rating_chu": fish_data['rating'] if type == "chunithm" else 0.0,
        "game_version": "latest_CN",
        "initial_records": new_record_data
    }
    return new_archive_data


def filter_maimai_ap_data(fish_data, top_len=50):
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
        song['clip_title_name'] = f"APBest_{index}"

    return ap_data

################################################
# Origin B50 data file finders
################################################

def find_origin_b50(username, file_type = "html", game_type = "maimai"):
    """查找原始B50数据文件
    
    Args:
        username: 用户名
        file_type: 文件类型，html 或 json
        game_type: 游戏类型，maimai 或 chunithm
    """
    data_dir = "chunithm_datas" if game_type == "chunithm" else "b50_datas"
    DATA_ROOT = f"./{data_dir}/{username}"
    # 1. Check for the {username}.html
    user_data_file = f"{DATA_ROOT}/{username}.{file_type}"
    if os.path.exists(user_data_file):
        with open(user_data_file, 'r', encoding="utf-8") as f:
            if file_type == "html":
                b50_origin = f.read()
            elif file_type == "json":
                b50_origin = json.load(f)
            print(f"Info: Found {file_type.upper()} file matching username: {user_data_file}")
            return b50_origin

    # 2. Check for the default HTML file name
    if file_type == "html":
        default_html_file = f"{DATA_ROOT}/maimai DX NET－Music for DX RATING－.html"
        if os.path.exists(default_html_file):
            with open(default_html_file, 'r', encoding="utf-8") as f:
                html_raw = f.read()
                print(f"Info: Default DX rating HTML file found: {default_html_file}")
                return html_raw

    # 3. Try to find any other `.html` or dxrating-export file
        html_files = glob.glob(f"{DATA_ROOT}/*.html")
        if html_files:
            with open(html_files[0], 'r', encoding="utf-8") as f:
                html_raw = f.read()
                print(f"Warning: No specific HTML file found, using the first available file: {html_files[0]}")
                return html_raw
    elif file_type == "json":
        json_files = glob.glob(f"{DATA_ROOT}/dxrating.export-*.json")
        if json_files:
            with open(json_files[-1], 'r', encoding="utf-8") as f:
                json_raw = f.read()
                print(f"Warning: No specific JSON file found, using the last available file: {json_files[-1]}")
                return json_raw

    # Raise an exception if no file is found
    raise Exception(f"Error: No {file_type.upper()} file found in the user's folder.")

################################################
# Read B50 from DX NET raw HTML
################################################

def read_b50_from_html(b50_raw_file, username):
    html_raw = find_origin_b50(username, "html")
    html_tree = etree.HTML(html_raw)
    # Locate B35 and B15
    b35_div_names = [
        "Songs for Rating(Others)",
        "RATING対象曲（ベスト）"
    ]
    b15_div_names = [
        "Songs for Rating(New)",
        "RATING対象曲（新曲）"
    ]
    b35_screw = locate_html_screw(html_tree, b35_div_names)
    b15_screw = locate_html_screw(html_tree, b15_div_names)

    # html_screws = html_tree.xpath('//div[@class="screw_block m_15 f_15 p_s"]')
    # if not html_screws:
    #     raise Exception("Error: B35/B15 screw not found. Please check HTML input!")
    # b35_screw = html_screws[1]
    # b15_screw = html_screws[0]

    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
        "rating": -1,
        "username": username
    }
    manager = ChartManager()
    song_id_placeholder = 0 # Avoid same file names for downloaded videos
    for song in iterate_songs(b35_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["sd"].append(song_json)
    for song in iterate_songs(b15_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["dx"].append(song_json)

    b50_json["rating"] = manager.total_rating

    # Write b50 JSON to raw file
    with open(b50_raw_file, 'w', encoding="utf-8") as f:
        json.dump(b50_json, f, ensure_ascii = False, indent = 4)
    return b50_json

def locate_html_screw(html_tree, div_names):
    for name in div_names:
        screw = html_tree.xpath(f'//div[text()="{name}"]')
        if screw:
            return screw[0]
    raise Exception(f"Error: HTML screw (type = \"{div_names[0]}\") not found.")

def iterate_songs(div_screw):
    current_div = div_screw
    while True:
        current_div = current_div.xpath('following-sibling::div[1]')[0]
        if len(current_div) == 0:
            break
        yield current_div

# Parse HTML div of a song to diving-fish raw data JSON
def parse_html_to_json(song_div, song_id_placeholder):
    LEVEL_DIV_LABEL = ["_basic", "_advanced", "_expert", "_master", "_remaster"]
    # Initialise chart JSON
    chart = {
        "achievements": 0,
        "ds": 0,
        "dxScore": 0,
        "fc": "",
        "fs": "",
        "level": "0",
        "level_index": -1,
        "level_label": "easy",
        "ra": 0,
        "rate": "",
        "song_id": song_id_placeholder,
        "title": "",
        "type": "",
    }

    # Get achievements
    score_div = song_div.xpath('.//div[contains(@class, "music_score_block")]')
    if score_div:
        score_text = score_div[0].text
        score_text = score_text.strip().replace('\xa0', '').replace('\n', '').replace('\t', '')
        score_text = score_text.rstrip('%')
        chart["achievements"] = float(score_text)

    # Get song level and internal level
    level_div = song_div.xpath('.//div[contains(@class, "music_lv_block")]')
    if level_div:
        level_text = level_div[0].text
        chart["level"] = level_text

    # Get song difficulty
    div_class = song_div.get("class", "")
    for idx, level in enumerate(LEVEL_DIV_LABEL):
        if level.lower() in div_class.lower():
            chart["level_index"] = idx
            chart["level_label"] = LEVEL_LABEL[idx]
            break

    # Get song title
    title_div = song_div.xpath('.//div[contains(@class, "music_name_block")]')
    if title_div:
        chart["title"] = title_div[0].text

    # Get chart type
    kind_icon_img = song_div.xpath('.//img[contains(@class, "music_kind_icon")]')
    if kind_icon_img:
        img_src = kind_icon_img[0].get("src", "")
        chart["type"] = "DX" if img_src.endswith("dx.png") else "SD"

    return chart

################################################
# Read B50 from dxrating.net export
################################################

def read_dxrating_json(b50_raw_file, username):
    dxrating_json = find_origin_b50(username, "json")
    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
        "rating": -1,
        "username": username
    }
    manager = ChartManager()
    song_id_placeholder = 0 # Avoid same file names for downloaded videos
    for song in dxrating_json:
        song_id_placeholder -= 1 # -1 ~ -35 = b35, -36 ~ -50 = b15, resume full b35
        song_json = parse_dxrating_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        if song_id_placeholder >= -35:
            b50_json["charts"]["sd"].append(song_json)
        else:
            b50_json["charts"]["dx"].append(song_json)

    b50_json["rating"] = manager.total_rating

    # Write b50 JSON to raw file
    with open(b50_raw_file, 'w', encoding="utf-8") as f:
        json.dump(b50_json, f, ensure_ascii = False, indent = 4)
    return b50_json

def parse_dxrating_json(song_json, song_id_placeholder):
    LEVEL_DIV_LABEL = ["basic", "advanced", "expert", "master", "remaster"]

    # Initialise chart JSON
    chart = {
        "achievements": 0,
        "ds": 0,
        "dxScore": 0,
        "fc": "",
        "fs": "",
        "level": "0",
        "level_index": -1,
        "level_label": "easy",
        "ra": 0,
        "rate": "",
        "song_id": song_id_placeholder,
        "title": "",
        "type": "",
    }

    chart["achievements"] = song_json["achievementRate"]

    sheet_id_parts = song_json["sheetId"].split("__dxrt__")
    if len(sheet_id_parts) != 3:
        print(f"Warning: can not resolve sheetId \"{song_json.get('sheetId')}\" at position {-song_id_placeholder}")
        return chart
    
    chart["title"] = sheet_id_parts[0]
    chart["type"] = "DX" if sheet_id_parts[1] == "dx" else "SD"
    for idx, level in enumerate(LEVEL_DIV_LABEL):
        if sheet_id_parts[2] == level.lower():
            chart["level_index"] = idx
            chart["level_label"] = LEVEL_LABEL[idx]
            break
    return chart

################################################
# Update local cache files
################################################

def update_b50_data_int(b50_raw_file, username, params, parser) -> dict:
    data_parser = read_b50_from_html # html parser is default
    if parser == "html":
        data_parser = read_b50_from_html
    elif parser == "json":
        data_parser = read_dxrating_json

    # building b50_raw
    parsed_data = data_parser(b50_raw_file, username)

    # building b50_config
    return generate_data_file_int(parsed_data, params)

def generate_data_file_int(parsed_data, params) -> dict:
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    filter = params.get("filter", None)
    if type == "maimai":
        if query == "best":
            # split b50 data
            charts_data = parsed_data["charts"]
            b35_data = charts_data["sd"]
            b15_data = charts_data["dx"]

            for i in range(len(b35_data)):
                song = b35_data[i]
                song['clip_title_name'] = f"PastBest_{i + 1}"

            for i in range(len(b15_data)):
                song = b15_data[i]
                song['clip_title_name'] = f"NewBest_{i + 1}"
            
            # 合并b35_data和b15_data到同一列表
            b50_data = b35_data + b15_data
            # 统一转换为数据库记录格式
            new_record_data = [fish_to_new_record_format(song, type) for song in b50_data]
            
            new_archive_data = {
                "type": type,
                "sub_type": "best",
                "username": parsed_data["username"],
                "rating": parsed_data["rating"],
                "game_version": "latest_INTL",
                "initial_records": new_record_data
            }

        return new_archive_data
    else:
        raise ValueError("Only MAIMAI DX is supported for now")   

################################################
# Deprecated: data merger
################################################

@DeprecationWarning
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