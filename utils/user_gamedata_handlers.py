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
    fish_to_new_record_format, lxns_to_new_record_format,
)

LXNS_API_BASE = "https://maimai.lxns.net"  # 落雪查分器API基础URL
LEVEL_LABEL = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]

################################################
# Query Achievement data from diving-fish.com (maimai dx)
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
            response = requests.get(FC_PROXY_ENDPOINT, 
                                    params={
                                        "source": "fish",
                                        "username": username, 
                                        "game": "maimai",
                                        "query": "all"
                                    }, timeout=60)
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
            response = requests.get(FC_PROXY_ENDPOINT, 
                                    params={
                                        "source": "fish",
                                        "username": username, 
                                        "game": "chunithm",
                                        "query": "all"
                                    }, timeout=60)
            response.raise_for_status()

            return json.loads(response.text)
        else:
            raise ValueError("Invalid filter type for CHUNITHM")
    else:
        raise ValueError("Invalid game data type for diving-fish.com")

################################################
# Query Achievement data from lxns.net (落雪查分器)
################################################
def get_data_from_lxns(friend_code, params=None):
    """
    从落雪查分器获取数据（使用开发者API函数调用）
    """
    type = params.get("type", "maimai")
    query = params.get("query", "best")

    response = requests.get(
        FC_PROXY_ENDPOINT, 
        params={
            "source": "lxns",
            "friend_code": friend_code, 
            "game": type,
            "query": query
        }, 
        timeout=60
    )
    response.raise_for_status() 
    return json.loads(response.text)

def get_data_from_lxns_user(friend_code, api_key, params=None):
    """
    从落雪查分器**使用个人api**获取数据
    
    Args:
        friend_code: 玩家好友码 (事实上使用个人api并不需要)
        api_key: 个人API密钥
        params: 查询参数
    """
    if params is None:
        params = {}
    type = params.get("type", "maimai")
    query = params.get("query", "best")

    headers = {
        "X-User-Token": api_key
    }

    if type == "maimai":
        if query == "best":
            # 获取B35和B15分表数据
            bests_url = f"{LXNS_API_BASE}/api/v0/user/maimai/player/bests"
        elif query == "best_ap":
            # AP B50数据接口**不支持个人api**
            raise ValueError("落雪查分器个人API不支持获取maimai AP B50数据")
        elif query == "all":
            # 获取完整B50数据（仅支持落雪查分器个人api）
            bests_url = f"{LXNS_API_BASE}/api/v0/user/maimai/player/scores"
        else:
            # 注意：落雪查分器不支持返回完整all类型的查询
            raise ValueError("Invalid filter type for MAIMAI")
    elif type == "chunithm":
        if query == "best":
            # 获取B30和N20分表数据
            bests_url = f"{LXNS_API_BASE}/api/v0/user/chunithm/player/bests" 
        else:
            raise ValueError("Invalid filter type for CHUNITHM")
    else:
        raise ValueError("Invalid game data type for lxns.net")
    
    print(f"Fetching data from lxns.net: {bests_url}")
    
    response = requests.get(bests_url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        error_data = response.json() if response.text else {}
        raise ValueError(f"认证失败，请检查API密钥是否正确。错误信息：{error_data}")
    elif response.status_code == 403:
        error_data = response.json() if response.text else {}
        raise ValueError(f"权限不足，API密钥需要 allow_third_party_fetch_scores 权限。错误信息：{error_data}")
    else:
        raise ValueError(f"请求落雪查分器数据失败，状态码: {response.status_code}，返回消息：{response.text[:200]}")

################################################
# B50 data handlers (entry point)
################################################
def fetch_user_gamedata(raw_file_path, username, params, source="fish") -> dict:
    """Entry point function for st_pages"""
    response_data = None

    if source == "fish":
        try:
            fish_data = get_data_from_fish(username, params)
        except json.JSONDecodeError:
            print("Error: 读取 JSON 文件时发生错误，请检查数据格式。")
            return None
        
        # 函数计算返回体的错误处理
        if fish_data.get('error'): 
            if "user not exists" in fish_data['error']:
                raise Exception(f"Error: 从水鱼获得B50数据失败，此用户名不存在。请检查用户名称是否有对应的水鱼账号。")
            if 'msg' in fish_data:
                raise Exception(f"Error: 从水鱼获得B50数据失败，请将以下错误信息报告给开发者。错误信息：{fish_data['msg']}")
        
        # 缓存，写入b50_raw_file
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(fish_data, f, ensure_ascii=False, indent=4)

        response_data = fish_data
        
    elif source == "lxns":
        # 从落雪查分器获取数据
        local_user_api = params.get("local_user_api", False)  # 是否使用个人api_key
        local_api_key = params.get("api_key", None)  # 允许通过参数传入个人api_key
        friend_code = params.get("friend_code", None)
        
        if local_user_api: # 使用个人api_key
            if not local_api_key:
                raise ValueError("Error: 使用个人api时，必须提供落雪查分器的API密钥（api_key）。")    
            try:
                lxns_data = get_data_from_lxns_user(friend_code, local_api_key, params)
            except Exception as e:
                raise Exception(f"Error: 从落雪查分器获取数据失败: {e}")
        else:  # 使用开发者函数调用
            try:
                lxns_data = get_data_from_lxns(friend_code, params)
            except Exception as e:
                raise Exception(f"Error: 从落雪查分器获取数据失败: {e}")
        
        # 函数计算返回体的错误处理
        if lxns_data.get('error') and 'msg' in lxns_data:
            if "404 Client Error" in lxns_data['msg']:
                raise Exception(f"Error: 落雪查分器用户不存在，请检查好友码是否正确。错误信息：{lxns_data['msg']}")
            else:
                raise Exception(f"Error: 从落雪查分器获得数据失败，请将以下错误信息报告给开发者。错误信息：{lxns_data['msg']}")
        
        # 缓存，写入raw_file_path
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(lxns_data, f, ensure_ascii=False, indent=4)
        
        response_data = lxns_data

    else:
        raise ValueError("Invalid source for fetching game data")
    
    # print(response_data)
    
    return generate_archive_data(
        username = username,
        response_data=response_data,
        source=source,
        params=params
    )


################################################
# Data transformation from third-party to archive data
################################################
def generate_archive_data(username, response_data, source, params) -> dict:
    """
    提取原始数据，经过筛选和变换，构成数据库初始化配置
    Args:
        username (str): 用户名
        response_data (dict): 来自第三方的数据响应
        source (str): 数据来源，"fish"或"lxns"
        params (dict): 处理参数:
            type (str): 游戏类型，"maimai"或"chunithm"，默认为"maimai"
            query (str): 查询数据数量，"best"/"all"/"best_ap"，默认为"best"
            filter (dict): 过滤条件，有效键值示例：{"tag": "ap", "top": 50}
        Returns: 
            new_archive (dict): 用于创建新存档的数据字典，包括存档信息和initial_records的列表
    """
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    filter = params.get("filter", None)
    if filter:
        tag = filter.get("tag", None)
        top_len = filter.get("top", 50)

    sub_type_tag = ""
    to_modify_data = None

    if type == "maimai":
        charts_key = 'charts' if source == "fish" else 'data'
        b35_key = 'sd' if source == "fish" else 'standard'
        n20_key = 'dx' # both fish and lxns use 'dx' for B15 data
        if query == "best" or query == "best_ap":  # TODO: 需要测试best_ap接口
            # 解析b50数据
            charts_data = response_data[charts_key]
            b35_data = charts_data[b35_key]
            b15_data = charts_data[n20_key]
            # 为初始化数据添加clip_title_name字段，
            for i in range(len(b35_data)):
                song = b35_data[i]
                song['clip_title_name'] = f"PastBest_{i + 1}" if query == "best" else f"PastAP_{i + 1}"

            for i in range(len(b15_data)):
                song = b15_data[i]
                song['clip_title_name'] = f"NewBest_{i + 1}"  if query == "best" else f"NewAP_{i + 1}"
            # 合并b35_data和b15_data到同一列表
            to_modify_data = b35_data + b15_data
            sub_type_tag = "best" if query == "best" else "ap"
        elif query == "all":
            if not filter:
                raise ValueError("Error: 查询类型为all时，必须提供filter参数。")
            else:
                if tag == "ap":
                    data_list = filter_maimai_ap_data(response_data, source, match_version=False, top_len=top_len)
                    if len(data_list) < top_len:
                        print(f"Warning: 仅找到{len(data_list)}条AP数据，生成实际数据长度小于top_len={top_len}的配置。")
                    to_modify_data = data_list
                    sub_type_tag = "ap"
                else:
                    raise ValueError("Error: 目前仅支持tag为ap的查询类型。")
        else:
            raise ValueError("Invalid filter type for MAIMAI DX")
    elif type == "chunithm":
        charts_key = 'records' if source == "fish" else 'data'
        b30_key = 'b30' if source == "fish" else 'bests'
        n20_key = 'n20' if source == "fish" else 'new_bests'
        if query == "best":
            # 解析fish chunithm数据（TODO：支持N20）
            charts_data = response_data[charts_key]
            b30_data = charts_data[b30_key]
            n20_data = charts_data[n20_key]
            # 为初始化数据添加clip_title_name字段，
            for i in range(len(b30_data)):
                song = b30_data[i]
                song['clip_title_name'] = f"PastBest_{i + 1}"

            for i in range(len(n20_data)):
                song = n20_data[i]
                song['clip_title_name'] = f"NewBest_{i + 1}"
            to_modify_data = b30_data + n20_data
            sub_type_tag = "best"
        else:
            # TODO：添加筛除N20，仅B30的filter
            raise ValueError("Error: 暂未支持chunithm ap列表查询。")
    else:
        raise ValueError("Invalid game data type for diving-fish.com")
    
    # 统一转换为数据库记录格式
    if source == "fish":
        new_record_data = [fish_to_new_record_format(song, type) for song in to_modify_data]
    elif source == "lxns":
        new_record_data = [lxns_to_new_record_format(song, type) for song in to_modify_data]

    # 构建默认排序（默认倒序） 
    for i in range(len(new_record_data)):
        new_record_data[i]['order_in_archive'] = len(new_record_data) - i

    # 获取元数据
    archive_username = response_data.get('username', username)
    if source == "lxns":
        rating = counting_total_rating_lxns(response_data, game_type=type)
    else:
        rating = response_data.get('rating', 0)

    new_archive_data = {
        "game_type": type,
        "sub_type": sub_type_tag,
        "username": archive_username,
        "rating_mai": rating if type == "maimai" else 0,
        "rating_chu": rating if type == "chunithm" else 0.0,
        "game_version": "latest_CN",  # TODO：规范化这个版本命名
        "initial_records": new_record_data
    }
    return new_archive_data

def counting_total_rating_lxns(response_data, game_type="maimai"):
    """
    计算落雪查分器返回数据的总rating
    """
    if game_type == "maimai":
        total_rating = 0
        data = response_data.get('data', {})
        if 'standard_total' in data and 'dx_total' in data:
            total_rating = data.get('standard_total', 0) + data.get('dx_total', 0)
        else:
            total_rating = 0  # TODO：对于从全部成绩中抽取的分表（如ap b50），完善计算逻辑
    elif game_type == "chunithm":
        total_rating = 0.0
        data = response_data.get('data', {})
        charts = data.get('bests', []) + data.get('new_bests', [])
        for record in charts:
            rating = record.get("rating", 0.0)
            total_rating += rating
        # TODO： 分表长度依照查询选项（B50/B30/记录长度）调整
        total_rating = total_rating / len(charts) if charts else 0.0
    return total_rating

def filter_maimai_ap_data(data, source, match_version=False, top_len=50):
    """
    筛选maimai AP数据: TODO: 实现match_version，即与普通分表一样区分新旧版本
    """
    charts_data = data['records'] if source == "fish" else data['data']

    # 解析AP数据
    ap_data = []
    for song in charts_data:
        fc_flag = song.get('fc', '')
        if fc_flag is None:
            continue
        if 'ap' in fc_flag or 'app' in fc_flag:
            ap_data.append(song)

    # 按照ra值降序排序，如果ra值相同，按照ds定数降序排序
    if source == "fish":
        ap_data.sort(key=lambda x: (x.get('ra', 0), x.get('ds', 0)), reverse=True)
    else:  # lxns data，词条中没有ds字段，仅使用dx_rating排序
        ap_data.sort(key=lambda x: (x.get('dx_rating', 0)), reverse=True)
    ap_data = ap_data[:top_len]

    for song in ap_data:
        index = ap_data.index(song) + 1
        if source == "fish":
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
    DATA_ROOT = f"./b50_datas/{username}"
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