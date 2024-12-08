import os
from PIL import Image
import yaml
import requests
import traceback
from gene_images import generate_single_image
from gene_video import create_info_segment, create_video_segment, add_clip_with_transition
from moviepy import CompositeVideoClip
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader


def test_network_proxy(use_proxy, http_proxy):
    print("\n## [1/4]测试网络代理配置...")
    try:
        if use_proxy:
            print(f"当前代理设置: {http_proxy}")
        else:
            print("当前未使用代理，进行直连网络测试")

        # 测试访问 youtube
        youtube_url = "https://www.youtube.com"
        if use_proxy:
            response = requests.get(youtube_url, proxies={"http": http_proxy, "https": http_proxy})
        else:
            response = requests.get(youtube_url)

        if response.status_code == 200:
            print("## [1/4]网络测试成功")
        else:
            print(f"## [1/4]网络测试失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"测试网络代理时发生错误:")
        traceback.print_exc()

def test_image_generation(test_image_config):
    print("\n## [2/4]测试图片生成功能...")
    try:
        # 测试生成单张图片
        generate_single_image(
            background_path="./images/B50ViedoBase.png",
            record_detail=test_image_config,
            user_id="test",
            prefix="NewBest",
            index=0
        )

        # 检查图片是否可以正常打开和读取
        img = Image.open(f"b50_images/test/NewBest_1.png")
        img.verify()
        print("## [2/4]图片生成测试成功")
        return True
    except Exception as e:
        print(f"测试图片生成时发生错误: ")
        traceback.print_exc()

        return False

def test_video_generation(test_video_config):
    print("\n## [4/4]测试视频生成功能...")
    try:
        clips = []
        intro_segment = create_info_segment(
            clip_config=test_video_config["intro"][0],
            resolution=(1920, 1080),
            font_path="./font/SOURCEHANSANSSC-BOLD.OTF"
        )
        
        video_segment = create_video_segment(
            clip_config=test_video_config["main"][0],
            resolution=(1920, 1080),
            font_path="./font/SOURCEHANSANSSC-BOLD.OTF"
        )

        ending_segment = create_info_segment(
            clip_config=test_video_config["ending"][0],
            resolution=(1920, 1080),
            font_path="./font/SOURCEHANSANSSC-BOLD.OTF"
        )
        
        for clip in [intro_segment, video_segment, ending_segment]:
            add_clip_with_transition(clips, clip, set_start=True, trans_time=1)
        
        final_video = CompositeVideoClip(clips)
        final_video.write_videofile("videos/test/test_video.mp4", fps=30, threads=4, preset='ultrafast', codec="libx264")
        
        final_video.close()
        for clip in clips:
            clip.close()
            
        print("## [4/4]视频生成测试成功")
        return True
    except Exception as e:
        print(f"测试视频生成时发生错误:")
        traceback.print_exc()
        return False

def test_system():
    print("##### 开始系统功能测试...")
    
    # 测试文件夹创建
    if not os.path.exists("videos"):
        os.makedirs("videos")
    if not os.path.exists("b50_images"):
        os.makedirs("b50_images")

    # 读取全局配置
    with open("global_config.yaml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    use_proxy = config["USE_PROXY"]
    http_proxy = config["HTTP_PROXY"]

    downloader_type = config["DOWNLOADER"]

    use_customer_potoken = config["USE_CUSTOM_PO_TOKEN"]
    use_auto_potoken = config["USE_AUTO_PO_TOKEN"]
    use_potoken = use_customer_potoken or use_auto_potoken
    use_oauth = config["USE_OAUTH"]
    
    search_max_results = config["SEARCH_MAX_RESULTS"]
    download_high_res = config["DOWNLOAD_HIGH_RES"]

    test_network_proxy(use_proxy, http_proxy)

    image_config = {
        "achievements": "101.0000",
        "ds": 15.0,
        "dxScore": 4200,
        "fc": "app",
        "fs": "fdsp",
        "level": "15",
        "level_index": 4,
        "level_label": "Re:MASTER",
        "ra": 337,
        "rate": "sssp",
        "song_id": 11663,
        "title": "系ぎて",
        "type": "DX",
    }

    if not os.path.exists("b50_images/test"):
        os.makedirs("b50_images/test")

    test_image_generation(test_image_config=image_config)

    print("\n## [3/4]测试视频搜索和下载功能...")
    test_video_config = {
        "intro": [
        {
            "id": "intro_1",
            "duration": 7,
            "text": " 要开始了呦~ "
        }
        ],
        "ending": [
            {
                "id": "ending_1",
                "duration": 5,
                "text": "期待下次与你相见~"
            }
        ],
        "main": [
            {
                "id": "NewBest_1",
                "achievement_title": "系ぎて-re:Master-DX",
                "song_id": 11663,
                "level_index": 4,
                "type": "DX",
                "main_image": "b50_images\\test\\NewBest_1.png",
                "video": "videos\\test\\11663-4-DX.mp4",
                "duration": 10,
                "start": 126,
                "end": 136,
                "text": " 音ゲー史上一番神聖なボス曲ってくらい綺麗 "
            },
        ]
    }

    if not os.path.exists("videos/test"):
        os.makedirs("videos/test")
    
    if os.path.exists("videos/test/11663-4-DX.mp4"):
        os.remove("videos/test/11663-4-DX.mp4")

    if downloader_type == "youtube":
        downloader = PurePytubefixDownloader(
            proxy=http_proxy if use_proxy else None,
            use_potoken=use_potoken,
            use_oauth=use_oauth,
            auto_get_potoken=use_auto_potoken,
            search_max_results=search_max_results
        )

    elif downloader_type == "bilibili":
        downloader = BilibiliDownloader(
            proxy=http_proxy if use_proxy else None,
            no_credential=True,
            search_max_results=search_max_results
        )
    else:
        print(f"Error: 未配置正确的下载器，请检查global_config.yaml配置文件！")
        return -1
    
    # test search
    results = downloader.search_video("系ぎて Re:MASTER AP【maimaiでらっくす外部出力】")
    for result in results:
        print(f"测试搜索结果: {result}")

    # test download
    test_video_id = results[0]['id']
    downloader.download_video(test_video_id, "11663-4-DX", "videos/test", high_res=download_high_res)
    print("## [3/4]测试完毕")

    test_video_generation(test_video_config=test_video_config)

    print("##### 全部系统功能测试完成！")

if __name__ == "__main__":
    test_system()