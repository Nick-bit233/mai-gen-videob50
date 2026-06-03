import csv
import glob
import json
import os
import re
import json
import requests

from utils.DataUtils import (
    FC_PROXY_ENDPOINT,
    fish_to_new_record_format,
    lxns_to_new_record_format,
    chart_type_str2value,
    compute_rating,
    filter_mgbl_b50,
    read_mtbl_tsv,
    filter_mtbl_b50,
    read_maimai_html,
    load_metadata,
    exact_match_chart
)

LXNS_API_BASE = "https://maimai.lxns.net"  # 落雪查分器API基础URL
LEVEL_LABEL = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]
# Labels for archive data's game_version field
GAME_VERSION_LABELS = {
    "latest_CN": "DX2025",
    "latest_INT": "CiRCLE",
    "latest_JP": "CiRCLE PLUS",
    "Not Specified": "Not Specified"
}

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
        "game_version": GAME_VERSION_LABELS["latest_CN"],
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
# Read B50 from dxrating.net export
################################################

@DeprecationWarning
def read_dxrating_json(b50_raw_file, username, params):
    dxrating_json = {}
    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
        "rating": -1,
        "username": username
    }
    manager = None
    song_id_placeholder = 0 # Avoid same file names for downloaded videos
    for song in dxrating_json:
        song_id_placeholder -= 1 # -1 ~ -35 = b35, -36 ~ -50 = b15, assume full b35
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

@DeprecationWarning
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
# Generate archive data from local data input
################################################

def generate_archive_data_from_mgbl(mgbl_data, username, params) -> dict:
    """
    Extract song data from Mai-gen booklet output and form archive data.

    Args:
        mgbl_data: Mai-gen booklet output JSON, example
            {
                "host": "maimaidx-eng.com",
                "rating": 11451,
                "scores": [
                    {
                        "songName": "Xaleid◆scopiX",
                        "difficulty": "Re:MASTER",
                        "level": "15",
                        "achievement": "99.7325%",
                        "dxscore": 4396,
                        "sync": "sync",
                        "combo": "fc",
                        "type": "DX",
                        "raw_difficulty_id": 4,
                        "isNew": true
                    },
                    {...}
                ]
            }
        username: user's name for recording
        params (dict): example params -> see unify_user_gamedata function for detail

    Returns:
        new_archive_data (dict): initialized profile data for database insertion, including initial_records list
    """
    game_type = params.get("type", "maimai")
    query = params.get("query", "all")
    filter = params.get("filter", {})
    tag = filter.get("tag", "")
    sub_type_tag = ""

    if game_type == "maimai":
        if query == "all":
            sub_type_tag = tag if tag else "best"
            try:
                record_data = filter_mgbl_b50(mgbl_data["scores"], filter)
            except:
                raise ValueError("Error: 解析MGBL数据时发生未知错误。")
        else:
            raise ValueError("Error: Only \"all\" query is supported for Mai-gen booklet data.")
    else:
        raise ValueError("Error: Only MAIMAI DX is supported for Mai-gen booklet data")
    
    # Keep the same database ordering as generate_archive_data
    for i in range(len(record_data)):
        record_data[i]['order_in_archive'] = len(record_data) - i

    game_version = GAME_VERSION_LABELS["Not Specified"]
    if filter and filter.get("b15_versions", -1) >= 0:
        if mgbl_data["host"] == "maimaidx-eng.com":
            game_version = GAME_VERSION_LABELS["latest_INT"]
        else:
            game_version = GAME_VERSION_LABELS["latest_JP"]

    local_rating = sum(record['dx_rating'] for record in record_data)
    if local_rating != mgbl_data["rating"]:
        print(f"""
            ==============================================================================
            Warning: 计算得到的rating {local_rating} 与从官网读取并录入存档的rating {mgbl_data['rating']} 不一致。请检查以下情况，必要时在"编辑数据"页面手动调整相关谱面。
            0. 如果正在使用带有特殊筛选条件或全版本B50筛选, 属正常现象, 但还请检查...
            1. 数据来自国际服且现与日服的大版本不一致, B50可能包含了定数有变动的谱面;
            2. B50中存在同名的曲目, 如"Trust"、"Link"等;
            3. B50中存在被改动过名称的曲目, 如"Help me, ERINNNNNN!!"等;
            4. 潜在B50中存在近期被删除或国际服独占曲目, 如"全世界共通リズム感テスト"，这些曲目无法被检索;
            5. 近期您的数据源服务器有大版本更新, 我们的数据库可能尚未及时更新相关数据。
            ==============================================================================
        """)

    new_archive_data = {
        "game_type": game_type,
        "sub_type": sub_type_tag,
        "username": username,
        "rating_mai": local_rating,
        "rating_chu": 0.0,
        "game_version": game_version,
        "initial_records": record_data
    }
    return new_archive_data

def generate_archive_data_from_mtbl(mtbl_data, username, params) -> dict:
    """
    Generate initialised profile for dataset from MTBL data.

    Args:
        mtbl_data: list of dicts converted from MTBL TSV data
        username: user's name for recording
        params (dict): example params -> see unify_user_gamedata function for details

    Returns:
        new_archive_data (dict): initialized profile data for database insertion, including initial_records list
    """
    game_type = params.get("type", "maimai")
    query = params.get("query", "best")
    filter = params.get("filter", {})
    tag = filter.get("tag", "")
    sub_type_tag = ""

    if game_type == "maimai":
        if query == "all":
            sub_type_tag = tag if tag else "best"
            try:
                record_data = filter_mtbl_b50(mtbl_data, filter)
            except KeyError:
                raise ValueError("Error: MTBL数据格式不正确，缺少必要字段。请检查选择的数据源类型或MTBL导出数据的设置。")
        else:
            raise ValueError("Error: Only \"all\" query is supported for MTBL data for now")
    else:
        raise ValueError("Error: Only MAIMAI DX is supported for MTBL data")
    
    # Keep the same database ordering as generate_archive_data
    for i in range(len(record_data)):
        record_data[i]['order_in_archive'] = len(record_data) - i

    b15_versions = filter.get("b15_versions", -1) if filter else -1
    if b15_versions == 0:
        game_version = GAME_VERSION_LABELS["latest_INT"]
    elif b15_versions == 1:
        game_version = GAME_VERSION_LABELS["latest_JP"]
    else:
        game_version = GAME_VERSION_LABELS["Not Specified"]

    new_archive_data = {
        "game_type": game_type,
        "sub_type": sub_type_tag,
        "username": username,
        "rating_mai": sum(record['dx_rating'] for record in record_data),
        "rating_chu": 0.0,
        "game_version": game_version,
        "initial_records": record_data
    }
    return new_archive_data

def generate_archive_data_from_html(html_data, username, params = None) -> dict:
    """
    Generate initialised profile for dataset from raw HTML data.

    Args:
        html_raw: raw HTML string from DXrating page
        username: user's name for recording
        params (dict): no parameters will be used
    """
    game_type = params.get("type", "maimai")
    sub_type_tag = "best"

    raw_html_records = html_data["raw_records"]
    game_version = GAME_VERSION_LABELS["latest_INT"] if html_data["html_language"] == 0 else GAME_VERSION_LABELS["latest_JP"]

    if game_type == "maimai":
        # Build database records from raw html records. Fill artist, chart constant, rating for each record by exact matching
        songs_metadata = load_metadata(game_type)
        record_data = []
        for raw_record in raw_html_records:
            # For the data structure of raw_record, see the return value of parse_maimai_html
            query = raw_record["query"]
            chart_data = exact_match_chart(query, songs_metadata)
            if not chart_data:
                print(f"Warning: 无法匹配谱面{query}, 已自动跳过。如果缺失的数据是\"全世界共通リズム感テスト\"属正常现象。")
                continue
            dx_rating = compute_rating(chart_data["difficulty"], float(raw_record["achievement"]))
            record = {
                'chart_data': chart_data,
                'order_in_archive': 0, # Do not modify order here, will be set when inserting to DB
                'achievement': raw_record["achievement"],
                'fc_status': "none", # not provided in HTML
                'fs_status': "none", # not provided in HTML
                'dx_score': 0, # not provided in HTML
                'dx_rating': dx_rating,
                'chuni_rating': 0,
                'play_count': 0,
                'clip_title_name': raw_record["clip_title_name"],
                # Store the original HTML div as raw data for potential future use
                'raw_data': raw_record["raw_data"]
            }
            record_data.append(record)
    else:
        raise ValueError("Error: Only MAIMAI DX is supported for HTML data")
    
    # Keep the same database ordering as generate_archive_data
    for i in range(len(record_data)):
        record_data[i]['order_in_archive'] = len(record_data) - i

    new_archive_data = {
        "game_type": game_type,
        "sub_type": sub_type_tag,
        "username": username,
        "rating_mai": sum(record['dx_rating'] for record in record_data),
        "rating_chu": 0.0,
        "game_version": game_version,
        "initial_records": record_data
    }
    return new_archive_data

################################################
# Unify user imported texts to internal format
################################################

def unify_user_gamedata(raw_file_path, username, params, source="mgbl") -> dict:
    """
    Unify user imported data. First, process with read_x methods to get JSON-like dict data. Then, generate archive data with generate_x methods for database insertion.

    Args:
        raw_file_path (str): The path to save raw data for future reference. Raw data needs to be processed.
        username (str): user's name for recording
        params (dict): Example
            type (str): game type, only "maimai" is supported
            query (str): query type, only "best" supported... currently?
            filter (dict): filter conditions, example: {"tag": "ap", "b15_versions": 0}
        source (str): the source of the input data
    
    Returns:
        Generated archive data.
    """
    data_input = params.get("data_input", None)
    if not data_input:
        print("Error: 读取用户输入的文本数据时发生错误，文本框可能为空？")
    
    if source == "mgbl":
        mgbl_data = json.loads(data_input)
        # 保存原始JSON
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(mgbl_data, f, ensure_ascii=False, indent=4)
        
        return generate_archive_data_from_mgbl(mgbl_data, username, params)
    elif source == "mtbl":
        mtbl_data = read_mtbl_tsv(data_input, params)
        # 将初步转译为dict的数据保存
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(mtbl_data, f, ensure_ascii=False, indent=4)
        
        return generate_archive_data_from_mtbl(mtbl_data, username, params)
    
    elif source == "html":
        html_data = read_maimai_html(data_input, params)
        # 将半成品的dict数据保存
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(html_data["raw_records"], f, ensure_ascii=False, indent=4)

        return generate_archive_data_from_html(html_data, username, params)
    
    else:
        raise ValueError(f"Invalid source {source} for unifying user game data input")
