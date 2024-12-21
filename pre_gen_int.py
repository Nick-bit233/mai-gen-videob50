import json
from lxml import etree
import os
import traceback
import yaml

from front_end.server import run_server
from gene_images import generate_b50_images
from pre_gen import load_global_config, search_b50_videos, download_b50_videos, gene_resource_config, start_editor_server
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader

# Global configuration variables
# Same definition and initialization as original codes
global_config = {}
username = ""
use_proxy = False
proxy = ""
downloader_type = ""
no_bilibili_credential = False
use_customer_potoken = False
use_auto_potoken = False
use_potoken = False
use_oauth = False
search_max_results = 0
search_wait_time = (0, 0)
use_all_cache = False
download_high_res = False
clip_play_time = 0
clip_start_interval = (0, 0)
full_last_clip = False
default_comment_placeholders = True

def load_config():
    global global_config, username, use_proxy, proxy, use_customer_potoken, use_auto_potoken
    global use_potoken, use_oauth, search_max_results, search_wait_time, use_all_cache
    global download_high_res, clip_play_time, clip_start_interval, full_last_clip
    global downloader_type, no_bilibili_credential

    # Read global_config.yaml file
    with open("./global_config.yaml", "r", encoding="utf-8") as f:
        global_config = yaml.load(f, Loader=yaml.FullLoader)

    username = global_config["USER_ID"]
    use_proxy = global_config["USE_PROXY"]
    proxy = global_config["HTTP_PROXY"]
    downloader_type = global_config["DOWNLOADER"]
    no_bilibili_credential = global_config["NO_BILIBILI_CREDENTIAL"]
    use_customer_potoken = global_config["USE_CUSTOM_PO_TOKEN"]
    use_auto_potoken = global_config["USE_AUTO_PO_TOKEN"]
    use_potoken = use_customer_potoken or use_auto_potoken
    use_oauth = global_config["USE_OAUTH"]
    search_max_results = global_config["SEARCH_MAX_RESULTS"]
    search_wait_time = tuple(global_config["SEARCH_WAIT_TIME"])
    use_all_cache = global_config["USE_ALL_CACHE"]
    download_high_res = global_config["DOWNLOAD_HIGH_RES"]
    clip_play_time = global_config["CLIP_PLAY_TIME"]
    clip_start_interval = tuple(global_config["CLIP_START_INTERVAL"])
    full_last_clip = global_config["FULL_LAST_CLIP"]
    default_comment_placeholders = global_config["DEFAULT_COMMENT_PLACEHOLDERS"]

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
            assert len(b50_data) == len(local_b50_data), f"本地b50_data与从水鱼获取的数据长度不一致，请考虑删除本地{b50_data_file}缓存文件后重新运行。"
            
            # 创建本地数据的复合键映射表
            local_song_map = {
                (song['song_id'], song['level_index'], song['type']): song 
                for song in local_b50_data
            }
            
            # 按新的b50_data顺序重组local_b50_data
            for new_song in b50_data:
                song_key = (new_song['song_id'], new_song['level_index'], new_song['type'])
                if song_key in local_song_map:
                    # 如果记录已存在，使用新数据但保留原有的视频信息
                    cached_song = local_song_map[song_key]
                    new_song['video_info_list'] = cached_song.get('video_info_list', [])
                    new_song['video_info_match'] = cached_song.get('video_info_match', {})
                    new_local_b50_data.append(new_song)
                else:
                    # 如果是新记录，直接使用新数据
                    new_local_b50_data.append(new_song)  
    else:
        new_local_b50_data = b50_data

    # 写入b50_data_file
    with open(b50_data_file, "w", encoding="utf-8") as f:
        json.dump(new_local_b50_data, f, ensure_ascii=False, indent=4)
    return new_local_b50_data



# Main function
def pre_gen_int():
    print("##### Mai-genB50 Video Creator #####")
    print("##### Step 1. Configuration and pre-processing #####")

    # Load global configuration
    load_config()
    # Load pre_gen config as pre_gen functions using global variables from it
    load_global_config()
    # Cache folders
    cache_pathes = [
        f"./b50_datas",
        f"./b50_images",
        f"./videos",
        f"./videos/downloads",
        f"./cred_datas"
    ]
    for path in cache_pathes:
        if not os.path.exists(path):
            os.makedirs(path)

    b50_raw_file = f"./b50_datas/b50_raw_{username}.json"
    b50_data_file = f"./b50_datas/b50_config_{username}.json"

    # init downloader
    if downloader_type == "youtube":
        downloader = PurePytubefixDownloader(
            proxy=proxy if use_proxy else None,
            use_potoken=use_potoken,
            use_oauth=use_oauth,
            auto_get_potoken=use_auto_potoken,
            search_max_results=search_max_results
        )
        print(f"##### 【当前配置信息】##### \n"
          f"  下载器: {downloader_type}\n" 
          f"  代理: {proxy if use_proxy else '未启用'}\n"
          f"  使用potoken: {use_potoken}\n"
          f"  使用oauth: {use_oauth}\n"
          f"  自动获取potoken: {use_auto_potoken}")
    elif downloader_type == "bilibili":
        downloader = BilibiliDownloader(
            proxy=proxy if use_proxy else None,
            no_credential=no_bilibili_credential,
            credential_path="./cred_datas/bilibili_cred.pkl",
            search_max_results=search_max_results
        )
        print(f"##### 【当前配置信息】##### \n"
          f"  下载器: {downloader_type}\n" 
          f"  代理: {proxy if use_proxy else '未启用'}\n"
          f"  禁用账号登录: {no_bilibili_credential}")
    else:
        print(f"Error: 未配置正确的下载器，请检查global_config.yaml配置文件！")
        return -1

    image_output_path = f"./b50_images/{username}"
    video_download_path = f"./videos/downloads"  # 不同用户的视频缓存均存放在downloads文件夹下
    config_output_file = f"./b50_datas/video_configs_{username}.json"

    # 检查用户是否已有完整的配置文件
    if os.path.exists(config_output_file):
        with open(config_output_file, "r", encoding="utf-8") as f:
            configs = json.load(f)
            if "enable_re_modify" in configs and configs["enable_re_modify"]:
                print(f"#####【已检测到用户{username}已生成完毕的配置文件，跳过数据更新】 #####")
                print(f"(注意：如果需要更新新的B50数据，请备份{config_output_file}中已填写的评论配置，然后删除该路径下的文件后重新运行程序）\n")
                print(f"#####【请在新打开的页面中修改配置和评论，退出前不要忘记点击页面底部的保存】 #####")
    
                if not start_editor_server(config_output_file, image_output_path, video_download_path, username):
                    return 1

    print("##### Step 2. Extracting B50 data from saved HTML #####")
    print(f"Current user: {username}")
    b50_data = update_b50_data_int(b50_raw_file, b50_data_file, username) # Use international B50 update function
    print("Best 50 information extracted!")

    if not use_all_cache:
        # 生成b50图片
        print("#####【1/3】生成b50背景图片 #####")
        # if not os.path.exists(image_output_path):
        #     os.makedirs(image_output_path)

        # b35_data = b50_data[:35]
        # b15_data = b50_data[35:]
        # try:
        #     generate_b50_images(username, b35_data, b15_data, image_output_path)
        # except Exception as e:
        #     print(f"Error: 生成图片时发生异常: {e}")
        #     traceback.print_exc()
        #     return 1
        print("Dataset API not found, skip.")

        print("#####【2/3】搜索b50视频信息 #####")
        try:
            b50_data = search_b50_videos(downloader, b50_data, b50_data_file, search_wait_time)
        except Exception as e:
            print(f"Error: 搜索视频信息时发生异常: {e}")
            traceback.print_exc()
            return -1
        
        # 下载谱面确认视频
        print("#####【3/3】下载谱面确认视频 #####")
        try:
            download_b50_videos(downloader, b50_data, video_download_path, search_wait_time)
        except Exception as e:
            print(f"Error: 下载视频时发生异常: {e}")
            traceback.print_exc()
            return -1       
        
    else:
        print(f"#####【已配置 USE_ALL_CACHE=true ，使用本地缓存数据生成配置文件】 #####")
        #print(f"##### 当前配置的水鱼用户名: {username} #####")
        print(f"##### 如要求更新数据，请配置 USE_ALL_CACHE=false #####")
    
    # 配置视频生成的配置文件
    try:
        gene_resource_config(b50_data, image_output_path, video_download_path, config_output_file)
    except Exception as e:
        print(f"Error: 生成视频配置时发生异常: {e}")
        traceback.print_exc()
        return 1

    print(f"#####【预处理完成, 请在新打开的页面中修改视频生成配置并填写评论，退出前不要忘记点击页面底部的保存】 #####")
    
    if not start_editor_server(config_output_file, image_output_path, video_download_path, username):
        return 1

    return 0



if __name__ == "__main__":
    pre_gen_int()
