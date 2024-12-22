import json
from lxml import etree
import os

from pre_gen import merge_b50_data

def read_b50_from_html(b50_raw_file):
    with open(f"./maimai DX NET－Music for DX RATING－.html", 'r', encoding="utf-8") as f:
        html_raw = f.read()
    html_tree = etree.HTML(html_raw)
    # Locate B35 and B15
    b35_screw = html_tree.xpath('//div[text()="Songs for Rating(Others)"]')
    b15_screw = html_tree.xpath('//div[text()="Songs for Rating(New)"]')
    if not b35_screw:
        print(f"Error: {B35_XPATH} not found. 请检查HTML文件是否正确保存！")
        return
    if not b15_screw:
        print(f"Error: {B15_XPATH} not found. 请检查HTML文件是否正确保存！")
        return
    # Iterate songs and save as JSON
    b50_json = {
        "charts": {
            "dx": [],
            "sd": []
        },
        "username": username
    }
    song_id_placeholder = 0 # Avoid same file names for downloaded videos
    for song in iterate_songs(html_tree, b35_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        b50_json["charts"]["sd"].append(song_json)
    for song in iterate_songs(html_tree, b15_screw):
        song_id_placeholder -= 1 # Remove after implemented dataset
        song_json = parse_html_to_json(song, song_id_placeholder)
        b50_json["charts"]["dx"].append(song_json)

    # Write b50 JSON to raw file
    with open(b50_raw_file, 'w', encoding="utf-8") as f:
        json.dump(b50_json, f, ensure_ascii = False, indent = 4)
    return b50_json

def iterate_songs(html_tree, div_screw):
    current_div = div_screw[0]
    while True:
        current_div = current_div.xpath('following-sibling::div[1]')[0]
        if not current_div:
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
        # Default internal level as .0 or .6(+). Need external dataset to specify.
        chart["ds"] = float(level_text.replace("+", ".6") if "+" in level_text else f"{level_text}.0")

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

# Parse achievement to rate name
def get_rate(achievement):
    if achievement >= 100.5:
        return "sssp"
    elif achievement >= 100:
        return "sss"
    elif achievement >= 99.5:
        return "ssp"
    elif achievement >= 99:
        return "ss"
    elif achievement >= 98:
        return "sp"
    elif achievement >= 97:
        return "s"
    elif achievement >= 94:
        return "aaa"
    elif achievement >= 90:
        return "aa"
    elif achievement >= 80:
        return "a"
    elif achievement >= 75:
        return "bbb"
    elif achievement >= 70:
        return "bb"
    elif achievement >= 60:
        return "b"
    elif achievement >= 50:
        return "c"
    else:
        return "d"

def update_b50_data_int(b50_raw_file, b50_data_file, username):
    raw_data = read_b50_from_html(b50_raw_file) # Use different B50 source
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
