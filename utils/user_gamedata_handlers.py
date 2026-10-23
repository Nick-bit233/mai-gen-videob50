import json

from utils.DataUtils import (
    compute_rating,
    read_mtbl_tsv,
    read_maimai_html,
    load_metadata,
    exact_match_chart,
    mgbl_to_unified,
    mtbl_to_unified,
    dxjs_to_unified,
    mujs_to_unified,
    filter_unified_b50
)

# Labels for archive data's game_version field
GAME_VERSION_LABELS = {
    "latest_CN": "DX2025",
    "latest_INT": "CiRCLE",
    "latest_JP": "CiRCLE PLUS",
    "Not Specified": "Not Specified"
}

def fetch_user_gamedata(raw_file_path, username, params, source="fish") -> dict:
    """Create a local archive from an already authorized, complete score snapshot."""
    from utils.score_oauth import OAuthError, ScoreSnapshot
    from utils.score_selection import build_oauth_archive

    snapshot = (params or {}).get("oauth_snapshot")
    if not isinstance(snapshot, ScoreSnapshot) or snapshot.provider != source:
        raise OAuthError("请先通过 OAuth 授权并获取全部成绩。")
    if snapshot.game_type != params.get("type", "maimai"):
        raise OAuthError("授权成绩的游戏类型不匹配，请重新授权。")
    archive = build_oauth_archive(snapshot, username, params.get("selection", "b50"))
    # Only score data is cached; OAuth codes, state, and tokens are never persisted.
    with open(raw_file_path, "w", encoding="utf-8") as f:
        json.dump(snapshot.payload, f, ensure_ascii=False, indent=4)
    return archive


################################################
# Generate archive data from local data input
################################################

@DeprecationWarning
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
                record_data = None #filter_mgbl_b50(mgbl_data["scores"], filter)
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
            2. B50中存在未解锁的门曲, 如"有明/Ariake"、"宙天"等, 这些曲目的成绩无法被直接读取;
            3. B50中存在同名的曲目, 如"Trust"、"Link"等, 请检查是否读取了错误的谱面;
            4. B50中存在被改动过名称的曲目, 如"Help me, ERINNNNNN!!"等, 请检查谱面信息;
            5. 潜在B50中存在近期被删除或国际服独占曲目, 如"全世界共通リズム感テスト"，这些曲目无法被检索;
            6. 近期您的数据源服务器有大版本更新, 我们的数据库可能尚未及时更新相关数据。
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

@DeprecationWarning
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
                record_data = None #filter_mtbl_b50(mtbl_data, filter)
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

def generate_archive_data_from_unified(unified_data: list, username, params) -> dict:
    game_type = params.get("type", "maimai")
    query = params.get("query", "all")
    filter = params.get("filter", {})
    tag = filter.get("tag", "")

    if game_type != "maimai":
        raise ValueError("Error: Only MAIMAI DX is supported for unified data.")
    if query == "all" and not filter:
        print("Warning: query is set to \"all\" but no filter provided.")

    sub_type_tag = tag if tag else "best"

    try:
        record_data = filter_unified_b50(unified_data, filter)
    except KeyError:
        raise ValueError("Error: 数据格式不正确，缺少必要字段。请检查选择的数据源类型或导出数据的设置。")

    for i in range(len(record_data)):
        record_data[i]['order_in_archive'] = len(record_data) - i

    # game_version
    source_rating = params.get("mgbl_rating", None)
    source_host = params.get("mgbl_host", None)
    b15_versions = filter.get("b15_versions", -1) if filter else -1 # 不区分B15时为-1
    if b15_versions >= 0:
        if source_host == "maimaidx-eng.com":
            game_version = GAME_VERSION_LABELS["latest_INT"]
        elif source_host:
            game_version = GAME_VERSION_LABELS["latest_JP"]
        elif b15_versions == 0:
            game_version = GAME_VERSION_LABELS["latest_INT"]
        elif b15_versions >= 1:
            game_version = GAME_VERSION_LABELS["latest_JP"]
    else:
        game_version = GAME_VERSION_LABELS["Not Specified"]

    local_rating = sum(record['dx_rating'] for record in record_data)

    # rating 校验 (仅 mgbl 提供 source_rating)
    if source_rating is not None and local_rating != source_rating:
        print(f"""
            ==============================================================================
            Warning: 计算得到的rating {local_rating} 与从官网读取并录入存档的rating {source_rating} 不一致。请检查以下情况，必要时在"编辑数据"页面手动调整相关谱面。
            0. 如果正在使用带有特殊筛选条件或全版本B50筛选, 属正常现象, 但还请检查...
            1. 数据来自国际服且现与日服的大版本不一致, B50可能包含了定数有变动的谱面;
            2. B50中存在同名的曲目, 如"Trust"、"Link"等;
            3. B50中存在被改动过名称的曲目, 如"Help me, ERINNNNNN!!"等;
            4. 潜在B50中存在近期被删除或国际服独占曲目, 如"全世界共通リズム感テスト"，这些曲目无法被检索;
            5. 近期您的数据源服务器有大版本更新, 我们的数据库可能尚未及时更新相关数据。
            ==============================================================================
        """)

    return {
        "game_type": game_type,
        "sub_type": sub_type_tag,
        "username": username,
        "rating_mai": local_rating,
        "rating_chu": 0.0,
        "game_version": game_version,
        "initial_records": record_data
    }

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
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(mgbl_data, f, ensure_ascii=False, indent=4)
        unified_data = mgbl_to_unified(mgbl_data["scores"], params)
        params["mgbl_rating"] = mgbl_data.get("rating")
        params["mgbl_host"] = mgbl_data.get("host")
        return generate_archive_data_from_unified(unified_data, username, params)
    
    elif source == "dxjs":
        dxjs_data = json.loads(data_input)
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(dxjs_data, f, ensure_ascii=False, indent=4)
        unified_data = dxjs_to_unified(dxjs_data, params)
        return generate_archive_data_from_unified(unified_data, username, params)

    elif source == "mujs":
        mujs_data = json.loads(data_input)
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(mujs_data, f, ensure_ascii=False, indent=4)
        unified_data = mujs_to_unified(mujs_data, params)
        return generate_archive_data_from_unified(unified_data, username, params)

    elif source == "mtbl":
        mtbl_data = read_mtbl_tsv(data_input, params)
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(mtbl_data, f, ensure_ascii=False, indent=4)
        unified_data = mtbl_to_unified(mtbl_data, params)
        return generate_archive_data_from_unified(unified_data, username, params)
    
    elif source == "html":
        # HTML数据源直接提供可信B50，单独处理
        html_data = read_maimai_html(data_input, params)
        # 将半成品的dict数据保存
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(html_data["raw_records"], f, ensure_ascii=False, indent=4)

        return generate_archive_data_from_html(html_data, username, params)
    
    else:
        raise ValueError(f"Invalid source {source} for unifying user game data input")
