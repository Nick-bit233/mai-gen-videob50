from pytubefix import YouTube, Search
from bilibili_api import search, sync
from typing import Tuple
from abc import ABC, abstractmethod
import os
import yaml
import json
import time
import random
import traceback
import subprocess
import re  # 确保导入re模块

def custom_po_token_verifier() -> Tuple[str, str]:

    with open("global_config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if config['CUSTOMER_PO_TOKEN']['visitor_data'] == "" or config['CUSTOMER_PO_TOKEN']['po_token'] == "":
        print("未配置CUSTOMER_PO_TOKEN，请检查global_config.yaml")

    # print(f"/Customer PO Token/\n"
    #       f"visitor_data: {config['CUSTOMER_PO_TOKEN']['visitor_data']}, \n"
    #       f"po_token: {config['CUSTOMER_PO_TOKEN']['po_token']}")

    return config["CUSTOMER_PO_TOKEN"]["visitor_data"], config["CUSTOMER_PO_TOKEN"]["po_token"]
        
def autogen_po_token_verifier() -> Tuple[str, str]:
    # 自动生成 PO Token
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "external_scripts", "po_token_generator.js")
    result = subprocess.run(["node", script_path], capture_output=True, text=True)
    
    try:
        cleaned_output = result.stdout.strip()  # 尝试清理输出中的空白字符
        output = json.loads(cleaned_output)
        # print(f"PO Token生成结果: {output}")
    except json.JSONDecodeError as e:
        print(f"验证PO Token生成失败 (JSON解析错误): {str(e)}")
        print(f"原始输出内容: {repr(result.stdout)}")  # 使用repr()显示所有特殊字符
        
        if result.stderr:
            print(f"外部脚本错误输出: {result.stderr}")
        return None, None
    
    # 检查输出中是否含有特定键
    if "visitorData" not in output or "poToken" not in output:
        print("验证PO Token生成失败: 输出中不包含有效值")
        print(f"原始输出内容: {repr(result.stdout)}")
        return None, None
    
    # print(f"/Auto Generated PO Token/\n"
    #       f"visitor_data: {output['visitor_data']}, \n"
    #       f"po_token: {output['po_token']}")
    
    return output["visitorData"], output["poToken"]

def remove_html_tags_and_invalid_chars(text: str) -> str:
    """去除字符串中的HTML标记和非法字符"""
    # 去除HTML标记
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    
    # 去除非法字符
    invalid_chars = r'[<>:"/\\|?*【】]'  # 定义非法字符
    text = re.sub(invalid_chars, '', text)  # 替换为''

    return text.strip()  # 去除首尾空白字符

class Downloader(ABC):
    @abstractmethod
    def search_video(self, keyword):
        pass

    @abstractmethod
    def download_video(self, video_url, output_name, output_path, high_res=False):
        pass

class PurePytubefixDownloader(Downloader):
    """
    只使用pytubefix进行搜索和下载的youtube视频下载器
    """
    def __init__(self, proxy=None, use_oauth=False, use_potoken=False, auto_get_potoken=False, 
                 search_max_results=3):
        self.proxy = proxy
        # use_oauth 和 use_potoken 互斥，优先使用use_potoken
        self.use_potoken = use_potoken
        if use_potoken:
            self.use_oauth = False
        else:
            self.use_oauth = use_oauth
        if auto_get_potoken:
            self.po_token_verifier = autogen_po_token_verifier
        else:
            self.po_token_verifier = custom_po_token_verifier

        self.search_max_results = search_max_results
    
    def search_video(self, keyword):
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        else:
            proxies = None

        results = Search(keyword, 
                         proxies=proxies, 
                         use_oauth=self.use_oauth, 
                         use_po_token=self.use_potoken,
                         po_token_verifier=self.po_token_verifier)
        videos = []
        for result in results.videos:
            videos.append({
                'id': result.video_id,
                'title': remove_html_tags_and_invalid_chars(result.title),
                'url': result.watch_url,
                'duration': result.length
            })
        if self.search_max_results < len(videos):
            videos = videos[:self.search_max_results]
        return videos
    
    def download_video(self, video_url, output_name, output_path, high_res=False):
        try:
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            if self.proxy:
                proxies = {
                    'http': self.proxy,
                    'https': self.proxy
                }
            else:
                proxies = None

            yt = YouTube(video_url, 
                         proxies=proxies, 
                         use_oauth=self.use_oauth, 
                         use_po_token=self.use_potoken,
                         po_token_verifier=self.po_token_verifier)
            
            print(f"正在下载: {yt.title}")
            if high_res:
                # 分别下载视频和音频
                video = yt.streams.filter(adaptive=True, file_extension='mp4').\
                    order_by('resolution').desc().first()
                audio = yt.streams.filter(only_audio=True).first()
                down_video = video.download(output_path)
                down_audio = audio.download(output_path)
                print(f"下载完成，正在合并视频和音频")
                # 使用 ffmpeg 合并视频和音频
                output_file = os.path.join(output_path, f"{output_name}.mp4")
                subprocess.run(['ffmpeg', '-i', down_video, '-i', down_audio, '-c:v', 'copy', '-c:a', 'aac', output_file])
            else:
                downloaded_file = yt.streams.filter(progressive=True, file_extension='mp4').\
                    order_by('resolution').desc().first().download(output_path)
                # 重命名下载到的视频文件
                new_filename = f"{output_name}.mp4"
                output_file = os.path.join(output_path, new_filename)
                os.rename(downloaded_file, output_file)
                print(f"下载完成，存储为: {new_filename}")

            return output_file
            
        except Exception as e:
            print(f"下载视频时发生错误:")
            traceback.print_exc()
            return None

class BilibiliDownloader(Downloader):
    def __init__(self, proxy=None, credential=None, search_max_results=3):
        self.proxy = proxy
        self.search_max_results = search_max_results
    
    def search_video(self, keyword):
        results = sync(
            search.search_by_type(keyword=keyword, 
                                  search_type=search.SearchObjectType.VIDEO,
                                  page=1,
                                  page_size=self.search_max_results)
        )
        videos = []
        # print(results)  # Debugging line to check the structure of results
        res_list = results['result']
        for each in res_list:
            videos.append({
                'id': each['bvid'],
                'aid': each['aid'],
                'cid': each['cid'] if 'cid' in each else 0,
                'title': remove_html_tags_and_invalid_chars(each['title']),  # 去除特殊字符
                'url': each['arcurl'],
                'duration': each['duration']  # 注意这里是 分钟:秒 的形式
            })
        print(videos[0])
        return videos

    def download_video(self, video_url, output_name, output_path, high_res=False):
        pass

# test
if __name__ == "__main__":
    dl = BilibiliDownloader()
    dl.search_video("【maimai】【谱面确认】 系ぎて")