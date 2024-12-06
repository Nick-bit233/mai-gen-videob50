from pytubefix import YouTube, Search
from bilibili_api import login, user, search, video, Credential, sync, HEADERS
from typing import Tuple
from abc import ABC, abstractmethod
import os
import yaml
import json
import asyncio
import pickle
import httpx
import traceback
import subprocess
import platform
import re  # 确保导入re模块

# 根据操作系统选择FFMPEG的输出重定向方式
# TODO：添加日志输出
if platform.system() == "Windows":
    REDIRECT = "> NUL 2>&1"
else:
    REDIRECT = "> /dev/null 2>&1"

MAX_LOGIN_RETRIES = 3

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

def convert_duration_to_seconds(duration: str) -> int:
    minutes, seconds = map(int, duration.split(':'))
    return minutes * 60 + seconds

def load_credential(credential_path):
    if not os.path.isfile(credential_path):
        print("#####【未找到bilibili登录凭证，请在弹出的窗口中扫码登录】")
        return None
    else:
        # 读取凭证文件
        with open(credential_path, 'rb') as f:
            loaded_data = pickle.load(f)
        
        try:
            # 创建 Credential 实例
            credential = Credential(
                sessdata=loaded_data.sessdata,
                bili_jct=loaded_data.bili_jct,
                buvid3=loaded_data.buvid3,
                dedeuserid=loaded_data.dedeuserid,
                ac_time_value=loaded_data.ac_time_value
            )
        except:
            traceback.print_exc()
            print("#####【bilibili登录凭证无效，请在弹出的窗口中重新扫码登录】")
            return False
        
        # 验证凭证的有效性
        is_valid = sync(credential.check_valid())
        if not is_valid:
            print("#####【bilibili登录凭证无效，请在弹出的窗口中重新扫码登录】")
            return None
        
        need_refresh = sync(credential.check_refresh())
        print(need_refresh)
        if need_refresh:
            print("#####【bilibili登录凭据需要刷新，正在尝试刷新中……】")
            sync(credential.refresh())
        
        print(f"#####【缓存登录bilibili成功，登录账号为：{sync(user.get_self_info(credential))['name']}】")
        return credential

async def download_url_from_bili(url: str, out: str, info: str):
    async with httpx.AsyncClient(headers=HEADERS) as sess:
        resp = await sess.get(url)
        length = resp.headers.get('content-length')
        with open(out, 'wb') as f:
            process = 0
            for chunk in resp.iter_bytes(1024):
                if not chunk:
                    break

                process += len(chunk)
                print(f'      -- [正在从bilibili下载流: {info} {process} / {length}]', end='\r')
                f.write(chunk)
        print("Done.\n")

async def bilibili_download(bvid, credential, output_name, output_path, high_res=False):
    FFMPEG_PATH = 'ffmpeg'
    v = video.Video(bvid=bvid, credential=credential)
    download_url_data = await v.get_download_url(0)
    detecter = video.VideoDownloadURLDataDetecter(data=download_url_data)

    # 获取最佳媒体流: 返回列表中0是视频流，1是音频流
    if high_res:
        streams = detecter.detect_best_streams()
    else:
        streams = detecter.detect_best_streams(video_max_quality=video.VideoQuality._480P,
                                               no_dolby_video=True, no_dolby_audio=True, no_hdr=True)

    output_file = os.path.join(output_path, f"{output_name}.mp4")
    if detecter.check_flv_stream() == True:
        # FLV 流下载
        await download_url_from_bili(streams[0].url, "flv_temp.flv", "FLV 音视频")
        os.system(f'{FFMPEG_PATH} -y -i flv_temp.flv {output_file} {REDIRECT}')
        # 删除临时文件
        os.remove("flv_temp.flv")
        print(f"下载完成，存储为: {output_name}.mp4")
    else:
        # MP4 流下载
        await download_url_from_bili(streams[0].url, "video_temp.m4s", "视频流")
        await download_url_from_bili(streams[1].url, "audio_temp.m4s", "音频流")
        print(f"下载完成，正在合并视频和音频")
        os.system(f'{FFMPEG_PATH} -y -i video_temp.m4s -i audio_temp.m4s -vcodec copy -acodec copy {output_file} {REDIRECT}')
        # 删除临时文件
        os.remove("video_temp.m4s")
        os.remove("audio_temp.m4s")
        print(f"合并完成，存储为: {output_name}.mp4")

class Downloader(ABC):
    @abstractmethod
    def search_video(self, keyword):
        pass

    @abstractmethod
    def download_video(self, video_id, output_name, output_path, high_res=False):
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
                'id': result.watch_url,  # 使用Pytubefix时，video_id是url字符串
                'pure_id': result.video_id,
                'title': remove_html_tags_and_invalid_chars(result.title),
                'url': result.watch_url,
                'duration': result.length
            })
        if self.search_max_results < len(videos):
            videos = videos[:self.search_max_results]
        return videos
    
    def download_video(self, video_id, output_name, output_path, high_res=False):
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

            yt = YouTube(video_id, 
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
                subprocess.run(['ffmpeg', '-y -i', down_video, '-i', down_audio, '-c:v', 'copy', '-c:a', 'aac', output_file, REDIRECT])
                print(f"合并完成，存储为: {output_name}.mp4")
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
    def __init__(self, proxy=None, no_credential=False, credential_path="cred_datas/bilibili_cred.pkl", search_max_results=3):
        self.proxy = proxy
        self.search_max_results = search_max_results
        
        if no_credential:
            self.credential = None
            return
        
        self.credential = load_credential(credential_path)
        if self.credential:
            return
        
        for attempt in range(MAX_LOGIN_RETRIES):
            log_succ = self.log_in(credential_path)
            if log_succ:
                break  # 登录成功，退出循环
            print(f"正在尝试第 {attempt + 1} 次重新登录...")

    def log_in(self, credential_path):
        # credential = login.login_with_qrcode_term() # 在终端打印二维码登录
        credential = login.login_with_qrcode() # 使用tkinter GUI显示二维码登录
        try:
            credential.raise_for_no_bili_jct() # 判断是否成功
            credential.raise_for_no_sessdata() # 判断是否成功
        except:
            print("#####【登录失败，请重试】")
            return False
        print(f"#####【登录bilibili成功，登录账号为：{sync(user.get_self_info(credential))['name']}】")
        self.credential = credential
        # 缓存凭证
        with open(credential_path, 'wb') as f:
            pickle.dump(credential, f)
        return True
    
    def search_video(self, keyword): 
        # 并发搜索50个视频可能被风控，使用同步方法逐个搜索
        results = sync(
            search.search_by_type(keyword=keyword, 
                                  search_type=search.SearchObjectType.VIDEO,
                                  order_type=search.OrderVideo.TOTALRANK,
                                  order_sort=0,  # 由高到低
                                  page=1,
                                  page_size=self.search_max_results)
        )
        videos = []
        # print(results)  # Debugging line to check the structure of results
        res_list = results['result']
        for each in res_list:
            videos.append({
                'id': each['bvid'],  # 使用bilibili-api时，video_id是bvid字符串或aid
                'aid': each['aid'],
                'cid': each['cid'] if 'cid' in each else 0,
                'title': remove_html_tags_and_invalid_chars(each['title']),  # 去除特殊字符
                'url': each['arcurl'],
                'duration': convert_duration_to_seconds(each['duration']),  # 转换为总秒数
            })
        return videos

    def download_video(self, video_id, output_name, output_path, high_res=False):
        if not self.credential:
            print(f"Warning: 未成功配置bilibili登录凭证，下载视频可能失败！")
        # 使用异步方法下载
        result = asyncio.run(
            bilibili_download(bvid=video_id, 
                              credential=self.credential, 
                              output_name=output_name, 
                              output_path=output_path,
                              high_res=high_res)
        )