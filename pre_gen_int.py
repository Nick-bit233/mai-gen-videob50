import glob
import json
from lxml import etree
import os

from pre_gen import merge_b50_data
from utils.dxnet_extension import get_rate, ChartManager

################################################
# Origin B50 data file finders
################################################

def find_origin_b50(username, file_type = "html"):
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
    # b35_div_names = [
    #     "Songs for Rating(Others)",
    #     "rating対象曲（ベスト）"
    # ]
    # b15_div_names = [
    #     "Songs for Rating(New)",
    #     "rating対象曲（新曲）"
    # ]
    # b35_screw = locate_html_screw(html_tree, b35_div_names)
    # b15_screw = locate_html_screw(html_tree, b15_div_names)
    html_screws = html_tree.xpath('//div[@class="screw_block m_15 f_15 p_s"]')
    print(html_screws)
    if not html_screws:
        raise Exception("Error: B35/B15 screw not found. Please check HTML input!")
    b35_screw = html_screws[1]
    b15_screw = html_screws[0]

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
    for song in iterate_songs(html_tree, b35_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["sd"].append(song_json)
    for song in iterate_songs(html_tree, b15_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        song_json = manager.fill_json(song_json)
        b50_json["charts"]["dx"].append(song_json)

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


def iterate_songs(html_tree, div_screw):
    current_div = div_screw
    while True:
        current_div = current_div.xpath('following-sibling::div[1]')[0]
        if len(current_div) == 0:
            break
        yield current_div

# Parse HTML div of a song to diving-fish raw data JSON
def parse_html_to_json(song_div, song_id_placeholder):
    LEVEL_DIV_LABEL = ["_basic", "_advanced", "_expert", "_master", "_remaster"]
    LEVEL_LABEL = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]
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
        score_text = score_div[0].text.rstrip('%')
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

    # Write b50 JSON to raw file
    with open(b50_raw_file, 'w', encoding="utf-8") as f:
        json.dump(b50_json, f, ensure_ascii = False, indent = 4)
    return b50_json

def parse_dxrating_json(song_json, song_id_placeholder):
    LEVEL_DIV_LABEL = ["basic", "advanced", "expert", "master", "remaster"]
    LEVEL_LABEL = ["Basic", "Advanced", "Expert", "Master", "Re:MASTER"]

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

def update_b50_data_int(b50_raw_file, b50_data_file, username, data_parser):
    raw_data = data_parser(b50_raw_file, username)
    b35_data = raw_data['charts']['sd']
    b15_data = raw_data['charts']['dx']

    # No need for updating raw file again
    # 缓存，写入b50_raw_file
    # with open(b50_raw_file, "w", encoding="utf-8") as f:
    #     json.dump(fish_data, f, ensure_ascii=False, indent=4)

    # Keep remaining the same as original codes
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

def update_b50_data_int_html(b50_raw_file, b50_data_file, username):
    return update_b50_data_int(b50_raw_file, b50_data_file, username, read_b50_from_html)

def update_b50_data_int_json(b50_raw_file, b50_data_file, username):
    return update_b50_data_int(b50_raw_file, b50_data_file, username, read_dxrating_json)