import glob
import json
from lxml import etree
import os

from pre_gen import merge_b50_data
from utils.dxnet_extension import get_rate, ChartManager

def find_b50_html(username):
    # 1. Check for the {username}.html
    user_html_file = f"./{username}.html"
    if os.path.exists(user_html_file):
        with open(user_html_file, 'r', encoding="utf-8") as f:
            html_raw = f.read()
            print(f"Info: Found HTML file matching username: {user_html_file}")
            return html_raw

    # 2. Check for the default HTML file name
    default_html_file = "./view-source_https___maimaidx-eng.com_maimai-mobile_home_ratingTargetMusic_.html"
    if os.path.exists(default_html_file):
        with open(default_html_file, 'r', encoding="utf-8") as f:
            html_raw = f.read()
            print(f"Info: Default DX rating HTML file found: {default_html_file}")
            return html_raw

    # 3. Try to find any other `.html` file
    html_files = glob.glob("./*.html")
    if html_files:
        with open(html_files[0], 'r', encoding="utf-8") as f:
            html_raw = f.read()
            print(f"Warning: No specific HTML file found, using the first available file: {html_files[0]}")
            return html_raw

    # Raise an exception if no file is found
    raise Exception("Error: No HTML file found in the root folder.")

def read_b50_from_html(b50_raw_file, username):
    html_raw = find_b50_html(username)
    html_tree = etree.HTML(html_raw)
    # Locate B35 and B15
    b35_screw = html_tree.xpath('//div[text()="Songs for Rating(Others)"]')
    b15_screw = html_tree.xpath('//div[text()="Songs for Rating(New)"]')
    if not b35_screw:
        raise Exception(f"Error: {B35_XPATH} not found. 请检查HTML文件是否正确保存！")
    if not b15_screw:
        raise Exception(f"Error: {B15_XPATH} not found. 请检查HTML文件是否正确保存！")

    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
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

def iterate_songs(html_tree, div_screw):
    current_div = div_screw[0]
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
        "level": "",
        "level_index": -1,
        "level_label": "",
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

    # Parse rate
    chart["rate"] = get_rate(chart["achievements"])

    return chart

def update_b50_data_int(b50_raw_file, b50_data_file, username):
    raw_data = read_b50_from_html(b50_raw_file, username) # Use different B50 source
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
