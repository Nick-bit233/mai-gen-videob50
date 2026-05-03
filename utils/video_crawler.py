from pytubefix import YouTube, Search
from bilibili_api import login_v2, user, search, video, Credential, sync, HEADERS
from utils.PageUtils import download_temp_image_to_static
from utils.AccelRenderer import get_ffmpeg_binary
from typing import Tuple, Optional
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
import re
import requests
import time
import tempfile
import shutil

MAX_LOGIN_RETRIES = 3
BILIBILI_URL_PREFIX = "https://www.bilibili.com/video/"


class POTokenGenerationError(RuntimeError):
    """PO Token 自动生成失败时抛出的明确异常。"""


def _run_ffmpeg_merge(input_files: list[str], output_file: str):
    cmd = [get_ffmpeg_binary('ffmpeg'), '-y']
    for input_file in input_files:
        cmd.extend(['-i', input_file])
    cmd.extend(['-vcodec', 'copy', '-acodec', 'copy', output_file])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _create_temp_media_file(output_path: str, suffix: str) -> str:
    fd, temp_path = tempfile.mkstemp(dir=output_path, suffix=suffix)
    os.close(fd)
    return temp_path

def custom_po_token_verifier() -> Tuple[str, str]:

    with open("global_config.yaml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    
    if config['CUSTOMER_PO_TOKEN']['visitor_data'] == "" or config['CUSTOMER_PO_TOKEN']['po_token'] == "":
        print("未配置CUSTOMER_PO_TOKEN，请检查global_config.yaml")

    # print(f"/Customer PO Token/\n"
    #       f"visitor_data: {config['CUSTOMER_PO_TOKEN']['visitor_data']}, \n"
    #       f"po_token: {config['CUSTOMER_PO_TOKEN']['po_token']}")

    return config["CUSTOMER_PO_TOKEN"]["visitor_data"], config["CUSTOMER_PO_TOKEN"]["po_token"]
        
def autogen_po_token_verifier() -> Tuple[str, str]:
    # 自动生成 PO Token
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "external_scripts", "po_token_generator.js")
    node_binary = shutil.which("node")
    if not node_binary:
        raise POTokenGenerationError("未找到 node，可在 macOS 上执行 `brew install node` 后重试自动生成 PO Token。")

    result = subprocess.run([node_binary, script_path], capture_output=True, text=True)
    
    try:
        cleaned_output = result.stdout.strip()  # 尝试清理输出中的空白字符
        output = json.loads(cleaned_output)
        # print(f"PO Token生成结果: {output}")
    except json.JSONDecodeError as e:
        error_details = [f"验证PO Token生成失败 (JSON解析错误): {str(e)}",
                         f"原始输出内容: {repr(result.stdout)}"]
        if result.stderr:
            error_details.append(f"外部脚本错误输出: {result.stderr}")
        raise POTokenGenerationError("\n".join(error_details)) from e
    
    # 检查输出中是否含有特定键
    if "visitorData" not in output or "poToken" not in output:
        raise POTokenGenerationError(
            "验证PO Token生成失败: 输出中不包含有效值\n"
            f"原始输出内容: {repr(result.stdout)}"
        )
    
    # print(f"/Auto Generated PO Token/\n"
    #       f"visitor_data: {output['visitor_data']}, \n"
    #       f"po_token: {output['po_token']}")
    
    return output["visitorData"], output["poToken"]

def remove_html_tags_and_invalid_chars(text: str) -> str:
    """去除字符串中的HTML标记和非法字符"""
    # 去除HTML标记
    clean = re.compile('<.*?>')
    text = re.sub(clean, ' ', text)
    
    # 去除非法字符
    invalid_chars = r'[<>:"/\\|?*【】]'  # 定义非法字符
    text = re.sub(invalid_chars, ' ', text)  # 替换为' '

    return text.strip()  # 去除首尾空白字符

def convert_duration_to_seconds(duration: str) -> int:
    try:
        minutes, seconds = map(int, duration.split(':'))
        return minutes * 60 + seconds
    except:
        return int(duration)

def load_credential(credential_path):
    if not os.path.isfile(credential_path):
        print("#####【未找到bilibili登录凭证，请先扫码登录】")
        return None, None
    else:
        # 读取凭证文件
        with open(credential_path, 'rb') as f:
            try:
                loaded_data = pickle.load(f)
            except Exception as e:
                # 凭证二进制文件损坏或格式错误，删除凭证并提示重新登录
                if os.path.isfile(credential_path):
                    os.remove(credential_path)
                print(f"#####【读取bilibili登录凭证失败: {str(e)}，请重新扫码登录】")
                return None, None
        
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
            print("#####【bilibili登录凭证无效，请重新扫码登录】")
            return None, None
        
        # 验证凭证的有效性
        is_valid = sync(credential.check_valid())
        if not is_valid:
            print("#####【bilibili登录凭证已失效，请重新扫码登录】")
            return None, None
        try:
            need_refresh = sync(credential.check_refresh())
            if need_refresh:
                print("#####【bilibili登录凭据需要刷新，正在尝试刷新中……】")
                sync(credential.refresh())
        except:
            traceback.print_exc()
            print("#####【刷新bilibili登录凭据失败，请重新扫码登录】")
            return None, None
        
        username = sync(user.get_self_info(credential))['name']
        print(f"#####【缓存登录bilibili成功，登录账号为：{username}】")
        return credential, username

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
                percentage = (process / int(length)) * 100 if length else 0
                print(f'      -- [正在从bilibili下载流: {info} {percentage:.2f}%]', end='\r')
                f.write(chunk)
        print("Done.\n")

async def bilibili_download(bvid, credential, output_name, output_path, high_res=False, p_index=0):
    v = video.Video(bvid=bvid, credential=credential)
    download_url_data = await v.get_download_url(p_index)
    detecter = video.VideoDownloadURLDataDetecter(data=download_url_data)

    # 获取最佳媒体流: 返回列表中0是视频流，1是音频流
    if high_res:
        streams = detecter.detect_best_streams()
    else:
        streams = detecter.detect_best_streams(video_max_quality=video.VideoQuality._480P,
                                               no_dolby_video=True, no_dolby_audio=True, no_hdr=True)

    output_file = os.path.join(output_path, f"{output_name}.mp4")
    
    # 新版 API 使用 check_flv_mp4_stream() 替代 check_flv_stream()
    if detecter.check_flv_mp4_stream():
        # FLV/MP4 流下载（音视频合并）
        temp_flv = _create_temp_media_file(output_path, ".flv")
        await download_url_from_bili(streams[0].url, temp_flv, "FLV/MP4 音视频")
        _run_ffmpeg_merge([temp_flv], output_file)
        # 删除临时文件
        os.remove(temp_flv)
        print(f"下载完成，存储为: {output_name}.mp4")
    else:
        # DASH 流下载（音视频分离）
        temp_video = _create_temp_media_file(output_path, ".m4s")
        temp_audio = _create_temp_media_file(output_path, ".m4s")
        await download_url_from_bili(streams[0].url, temp_video, "视频流")
        await download_url_from_bili(streams[1].url, temp_audio, "音频流")
        print(f"下载完成，正在合并视频和音频")
        _run_ffmpeg_merge([temp_video, temp_audio], output_file)
        # 删除临时文件
        os.remove(temp_video)
        os.remove(temp_audio)
        print(f"合并完成，存储为: {output_name}.mp4")

class Downloader(ABC):
    @abstractmethod
    def search_video(self, keyword):
        pass

    @abstractmethod
    def download_video(self, video_id, output_name, output_path, high_res=False, p_index=0):
        pass
    
    @abstractmethod
    def get_video_info(self, video_id):
        """通过视频ID直接获取视频信息"""
        pass
    
    @abstractmethod
    def get_video_pages(self, video_id):
        """获取视频的分P信息（如果有）"""
        pass

class PurePytubefixDownloader(Downloader):
    """
    使用pytubefix或YouTube Data API v3进行搜索和下载的youtube视频下载器
    """
    def __init__(self, proxy=None, use_oauth=False, use_potoken=False, auto_get_potoken=False, 
                 search_max_results=3, use_api=False, api_key=None):
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
        self.use_api = use_api  # 是否使用 YouTube Data API v3 进行搜索
        self.api_key = api_key  # YouTube Data API v3 的 API Key
        
        # 如果没有提供 API Key，尝试从配置文件读取
        if self.use_api and not self.api_key:
            try:
                with open("global_config.yaml", "r", encoding="utf-8") as f:
                    config = yaml.load(f, Loader=yaml.FullLoader)
                    self.api_key = config.get('YOUTUBE_API_KEY', '')
            except Exception as e:
                print(f"读取配置文件失败: {e}")
                self.api_key = ''

    def _build_search_with_auth(self, keyword, proxies):
        if self.use_potoken:
            try:
                return Search(
                    keyword,
                    proxies=proxies,
                    use_oauth=False,
                    use_po_token=True,
                    po_token_verifier=self.po_token_verifier
                )
            except POTokenGenerationError as e:
                print(f"{e}\n自动回退到不使用 PO Token 的搜索模式。")
                return Search(
                    keyword,
                    proxies=proxies,
                    use_oauth=False,
                    use_po_token=False
                )
        if self.use_oauth:
            return Search(
                keyword,
                proxies=proxies,
                use_oauth=True,
                use_po_token=False
            )
        return Search(
            keyword,
            proxies=proxies,
            use_oauth=False,
            use_po_token=False
        )

    def _build_youtube_with_auth(self, url, proxies):
        if self.use_potoken:
            try:
                return YouTube(
                    url,
                    proxies=proxies,
                    use_oauth=False,
                    use_po_token=True,
                    po_token_verifier=self.po_token_verifier
                )
            except POTokenGenerationError as e:
                print(f"{e}\n自动回退到不使用 PO Token 的模式。")
                return YouTube(
                    url,
                    proxies=proxies,
                    use_oauth=False,
                    use_po_token=False
                )
        if self.use_oauth:
            return YouTube(
                url,
                proxies=proxies,
                use_oauth=True,
                use_po_token=False
            )
        return YouTube(
            url,
            proxies=proxies,
            use_oauth=False,
            use_po_token=False
        )
    
    def search_video(self, keyword):
        # 如果配置了使用 API，优先使用 YouTube Data API v3
        if self.use_api and self.api_key:
            return self._search_video_with_api(keyword)
        else:
            return self._search_video_with_pytubefix(keyword)
    
    def _search_video_with_api(self, keyword):
        """
        使用 YouTube Data API v3 进行搜索
        参考: https://developers.google.com/youtube/v3/docs/search/list
        """
        keyword = keyword.strip()
        
        # YouTube Data API v3 搜索端点
        api_url = "https://www.googleapis.com/youtube/v3/search"
        
        params = {
            'part': 'snippet',
            'q': keyword,
            'type': 'video',
            'maxResults': self.search_max_results,
            'key': self.api_key,
            'order': 'relevance'  # 按相关性排序
        }
        
        # 配置代理
        proxies = None
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.get(api_url, params=params, proxies=proxies, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if 'items' not in data or len(data['items']) == 0:
                    print(f"API搜索未找到结果: {keyword}")
                    return []
                
                videos = []
                video_ids = [item['id']['videoId'] for item in data['items']]
                
                # 获取视频详细信息（包括时长）
                videos_info = self._get_videos_duration(video_ids)
                
                for item in data['items']:
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    # 获取视频时长
                    duration = videos_info.get(video_id, 0)
                    
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    videos.append({
                        'id': video_url,
                        'pure_id': video_id,
                        'title': remove_html_tags_and_invalid_chars(snippet['title']),
                        'url': video_url,
                        'duration': duration
                    })
                
                return videos
                
            except requests.exceptions.HTTPError as e:
                error_msg = str(e)
                if response.status_code == 403:
                    raise Exception(f"YouTube API 搜索失败 (403错误): API Key 可能无效或配额已用完。请检查 API Key 配置。")
                elif response.status_code == 400:
                    if attempt < max_retries - 1:
                        print(f"API搜索失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                        print(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        raise Exception(f"YouTube API 搜索失败 (400错误): {error_msg}。系统将自动尝试其他搜索策略。")
                else:
                    raise Exception(f"YouTube API 搜索失败: {error_msg}")
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    print(f"API搜索失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise Exception(f"YouTube API 搜索失败: {error_msg}")
        
        return []
    
    def _get_videos_duration(self, video_ids):
        """
        通过 YouTube Data API v3 获取视频时长
        参考: https://developers.google.com/youtube/v3/docs/videos/list
        """
        if not video_ids:
            return {}
        
        api_url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'contentDetails',
            'id': ','.join(video_ids),
            'key': self.api_key
        }
        
        proxies = None
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        
        try:
            response = requests.get(api_url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            durations = {}
            for item in data.get('items', []):
                video_id = item['id']
                duration_str = item['contentDetails']['duration']
                # 将 ISO 8601 格式的时长转换为秒数
                duration = self._parse_duration(duration_str)
                durations[video_id] = duration
            
            return durations
        except Exception as e:
            print(f"获取视频时长失败: {e}")
            return {video_id: 0 for video_id in video_ids}
    
    def _parse_duration(self, duration_str):
        """
        将 ISO 8601 格式的时长（如 PT1H2M10S）转换为秒数
        """
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _search_video_with_pytubefix(self, keyword):
        """
        使用 pytubefix 进行搜索（原有方法）
        """
        # 清理搜索关键词
        keyword = keyword.strip()
        # 注意：不要对关键词进行URL编码，pytubefix的Search类会自己处理
        
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        else:
            proxies = None

        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                results = self._build_search_with_auth(keyword, proxies)
                
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
                
            except Exception as e:
                error_msg = str(e)
                # 对于400错误和其他错误，都进行重试
                if attempt < max_retries - 1:
                    print(f"搜索失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                    print(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    continue
                else:
                    # 所有重试均失败，抛出异常让上层多策略系统尝试下一个关键词
                    if "400" in error_msg or "Bad Request" in error_msg:
                        raise Exception(f"YouTube搜索失败 (400错误): {error_msg}。系统将自动尝试其他搜索策略。")
                    else:
                        raise
    
    def get_video_info(self, video_id):
        """
        通过视频ID直接获取YouTube视频信息
        video_id: YouTube视频ID (例如: dQw4w9WgXcQ) 或完整URL
        """
        import time
        
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        else:
            proxies = None

        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # 如果输入的是完整URL，直接使用；否则构建URL
                if video_id.startswith('http'):
                    url = video_id
                else:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                
                yt = self._build_youtube_with_auth(url, proxies)
                
                # 返回符合存档格式的video_info信息
                video_info = {
                    'id': yt.watch_url,
                    'pure_id': yt.video_id,
                    'title': remove_html_tags_and_invalid_chars(yt.title),
                    'url': yt.watch_url,
                    'duration': yt.length,
                    'page_count': 1,  # YouTube视频没有分P
                    'p_index': 0  # 默认为0
                }
                return video_info
                
            except Exception as e:
                error_msg = str(e)
                if "400" in error_msg or "Bad Request" in error_msg or "HTTP Error" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"获取视频信息失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                        print(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        raise Exception(f"YouTube获取视频信息失败: {error_msg}。建议：1) 检查视频ID是否正确，2) 更新pytubefix库 (pip install --upgrade pytubefix)，3) 配置PO Token或OAuth认证，4) 检查网络连接。")
                else:
                    # 其他类型的错误直接抛出
                    raise
        
        # 如果所有重试都失败了
        raise Exception("获取YouTube视频信息失败，已超过最大重试次数。")
    
    def get_video_pages(self, video_id):
        """
        获取YouTube视频的分P信息
        YouTube视频没有分P的概念，返回一个只包含单个页面的列表
        """
        # YouTube 没有分P，返回简单的单页信息
        return [
            {
                "page": 1,
                "part": "完整视频",
                "duration": 0,  # 如果需要真实时长，需要重新调用API
                "first_frame": None,  # YouTube不提供首帧预览
                "static_frame": False
            }
        ]
    
    def download_video(self, video_id, output_name, output_path, high_res=False, p_index=0):
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

            yt = self._build_youtube_with_auth(video_id, proxies)
            
            print(f"正在下载: {yt.title}")
            if high_res:
                # 分别下载视频和音频
                video = yt.streams.filter(adaptive=True, file_extension='mp4').\
                    order_by('resolution').desc().first()
                audio = yt.streams.filter(only_audio=True).first()
                down_video = video.download(output_path, filename="video_temp")
                down_audio = audio.download(output_path, filename="audio_temp")
                print(f"下载完成，正在合并视频和音频")
                output_file = os.path.join(output_path, f"{output_name}.mp4")
                _run_ffmpeg_merge([down_video, down_audio], output_file)
                # 删除临时文件
                os.remove(f"{down_video}")
                os.remove(f"{down_audio}")
                print(f"合并完成，存储为: {output_name}.mp4")
            else:
                downloaded_file = yt.streams.filter(progressive=True, file_extension='mp4').\
                    order_by('resolution').desc().first().download(output_path)
                # 重命名下载到的视频文件
                new_filename = f"{output_name}.mp4"
                output_file = os.path.join(output_path, new_filename)
  
                # 检查文件是否存在，如果存在则删除
                if os.path.exists(output_file):
                    os.remove(output_file)  # 删除已存在的文件
                
                os.rename(downloaded_file, output_file)
                print(f"下载完成，存储为: {new_filename}")

            return output_file
            
        except Exception as e:
            print(f"下载视频时发生错误:")
            traceback.print_exc()
            return None

class BilibiliQrCodeLoginSession:
    """
    Bilibili 二维码登录会话，用于 Streamlit 等异步环境
    
    使用方式：
    1. 调用 generate_qrcode() 获取二维码图片
    2. 在 UI 中显示二维码
    3. 循环调用 check_state() 检查登录状态
    4. 登录成功后调用 get_credential() 获取凭证
    """
    def __init__(self):
        self._qr_login = None
        self._generated = False
    
    def generate_qrcode(self):
        """生成二维码，返回 PIL Image 对象"""
        import io
        from PIL import Image
        
        async def _generate():
            self._qr_login = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
            await self._qr_login.generate_qrcode()
            self._generated = True
            # Picture.content 是 PNG 字节数据
            pic = self._qr_login.get_qrcode_picture()
            return Image.open(io.BytesIO(pic.content))
        return sync(_generate())
    
    def check_state(self):
        """
        检查登录状态
        返回: (state, message)
            state: 'waiting' | 'scanned' | 'confirmed' | 'success' | 'timeout'
        """
        if not self._generated or not self._qr_login:
            return ('error', '请先生成二维码')
        
        # 检查是否已经完成
        if self._qr_login.has_done():
            return ('success', '登录成功！')
        
        state = sync(self._qr_login.check_state())
        
        if state == login_v2.QrCodeLoginEvents.DONE:
            return ('success', '登录成功！')
        elif state == login_v2.QrCodeLoginEvents.TIMEOUT:
            return ('timeout', '二维码已过期，请刷新重试')
        elif state == login_v2.QrCodeLoginEvents.SCAN:
            return ('scanned', '已扫描，请在手机上确认登录')
        elif state == login_v2.QrCodeLoginEvents.CONF:
            return ('confirmed', '已确认，正在登录...')
        else:
            return ('waiting', '等待扫码...')
    
    def get_credential(self):
        """获取登录凭证，仅在登录成功后有效"""
        if not self._qr_login or not self._qr_login.has_done():
            return None
        return self._qr_login.get_credential()


def streamlit_login_bilibili(credential_path="cred_datas/bilibili_cred.pkl"):
    """
    在 Streamlit 中进行 Bilibili 登录
    
    返回: (success: bool, credential: Credential|None, message: str)
    
    注意：此函数应该在 Streamlit 页面中调用，它会：
    1. 显示二维码
    2. 轮询检查登录状态
    3. 登录成功后保存凭证
    """
    import streamlit as st
    
    # 创建登录会话
    if 'bilibili_login_session' not in st.session_state:
        st.session_state.bilibili_login_session = BilibiliQrCodeLoginSession()
    
    session = st.session_state.bilibili_login_session
    
    # 显示二维码
    qr_placeholder = st.empty()
    status_placeholder = st.empty()
    
    # 生成二维码
    if 'bilibili_qr_image' not in st.session_state:
        try:
            qr_image = session.generate_qrcode()
            st.session_state.bilibili_qr_image = qr_image
        except Exception as e:
            return (False, None, f"生成二维码失败: {str(e)}", None)
    
    # 显示二维码图片
    qr_placeholder.image(st.session_state.bilibili_qr_image, caption="使用哔哩哔哩客户端扫描此二维码")
    
    # 检查登录状态
    state, message = session.check_state()
    status_placeholder.info(f"📱 {message}")
    
    if state == 'success':
        # 登录成功
        credential = session.get_credential()
        
        # 验证凭证
        try:
            credential.raise_for_no_bili_jct()
            credential.raise_for_no_sessdata()
        except Exception as e:
            # 清理会话
            del st.session_state.bilibili_login_session
            if 'bilibili_qr_image' in st.session_state:
                del st.session_state.bilibili_qr_image
            return (False, None, f"凭证验证失败: {str(e)}", None)
        
        # 获取用户名
        username = sync(user.get_self_info(credential))['name']
        
        # 保存凭证
        os.makedirs(os.path.dirname(credential_path), exist_ok=True)
        with open(credential_path, 'wb') as f:
            pickle.dump(credential, f)
        
        # 清理会话
        del st.session_state.bilibili_login_session
        if 'bilibili_qr_image' in st.session_state:
            del st.session_state.bilibili_qr_image
        
        return (True, credential, f"登录成功！", username)
    
    elif state == 'timeout':
        # 清理过期的二维码
        if 'bilibili_qr_image' in st.session_state:
            del st.session_state.bilibili_qr_image
        del st.session_state.bilibili_login_session
        return (False, None, "二维码已过期，请刷新页面重试", None)
    
    else:
        # 等待中，返回 None 表示需要继续轮询
        return (False, None, message, None)

class BilibiliDownloader(Downloader):
    def __init__(self, proxy=None, no_credential=False, credential_path="cred_datas/bilibili_cred.pkl", search_max_results=3, skip_login=False):
        self.proxy = proxy
        self.search_max_results = search_max_results
        self.credential_path = credential_path
        
        if no_credential:
            self.credential = None
            return
        
        self.credential, self.username = load_credential(credential_path)
        if self.credential:
            return
        
        # 如果跳过登录（用于 Streamlit 等异步环境），则不自动登录
        if skip_login:
            self.credential = None
            return
        
        # 原有的自动登录逻辑（使用终端打印二维码）
        for attempt in range(MAX_LOGIN_RETRIES):
            log_succ = self._login_terminal(credential_path)
            if log_succ:
                break  # 登录成功，退出循环
            print(f"正在尝试第 {attempt + 1} 次重新登录...")
    
    def get_credential_username(self):
        if not self.credential:
            return None
        return sync(user.get_self_info(self.credential))['name']

    def _login_terminal(self, credential_path):
        """
        使用终端打印二维码的方式登录（fallback 方案）
        """
        import qrcode_terminal
        
        async def _login():
            qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
            await qr.generate_qrcode()
            
            # 获取二维码链接并在终端打印
            qr_url = qr.get_qrcode_url()
            print("\n请使用哔哩哔哩客户端扫描以下二维码登录：")
            qrcode_terminal.qrcode(qr_url)
            print("\n或访问以下链接扫码：")
            print(qr_url)
            
            # 轮询检查登录状态
            while True:
                if qr.has_done():
                    return qr.get_credential()
                
                state = await qr.check_state()
                
                if state == login_v2.QrCodeLoginEvents.DONE:
                    return qr.get_credential()
                elif state == login_v2.QrCodeLoginEvents.TIMEOUT:
                    print("\n二维码已过期")
                    return None
                elif state == login_v2.QrCodeLoginEvents.SCAN:
                    print("\r已扫描，请在手机上确认登录...", end="", flush=True)
                elif state == login_v2.QrCodeLoginEvents.CONF:
                    print("\r已确认，正在登录...", end="", flush=True)
                
                await asyncio.sleep(1)
        
        credential = sync(_login())
        
        if credential is None:
            print("\n#####【登录失败，请重试】")
            return False
        
        try:
            credential.raise_for_no_bili_jct()
            credential.raise_for_no_sessdata()
        except:
            print("\n#####【登录失败，请重试】")
            return False
        
        print(f"\n#####【登录bilibili成功，登录账号为：{sync(user.get_self_info(credential))['name']}】")
        self.credential = credential
        with open(credential_path, 'wb') as f:
            pickle.dump(credential, f)
        return True
    
    def set_credential(self, credential):
        """设置凭证（用于 Streamlit 登录后手动设置）"""
        self.credential = credential
    
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
        if 'result' not in results:
            print(f"搜索结果异常，请检查如下输出：")
            print(results)
            return []
        res_list = results['result']

        for each in res_list:
            vid = each['bvid'] # 只取bvid，然后通过视频接口获取信息，这样可以得到分p信息
            match_info = self.get_video_info(vid)
            videos.append(match_info)
        return videos

    def download_video(self, video_id, output_name, output_path, high_res=False, p_index=0):
        if not self.credential:
            print(f"Warning: 未成功配置bilibili登录凭证，下载视频可能失败！")
        # 使用异步方法下载
        result = asyncio.run(
            bilibili_download(bvid=video_id, 
                              credential=self.credential, 
                              output_name=output_name, 
                              output_path=output_path,
                              high_res=high_res,
                              p_index=p_index)
        )

    def get_video_info(self, video_id):
        # 获取视频信息
        v = video.Video(bvid=video_id, credential=self.credential)
        info = sync(v.get_info())

        # 返回符合存档格式的match_info信息
        match_info = {
            "id": info.get("bvid", ""),
            "aid": info.get("aid", 0),
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "page_count": len(info.get("pages", [])),
            "p_index": info.get("p_index", 0),
            "url": BILIBILI_URL_PREFIX + info.get("bvid", ""),
        }
        return match_info

    def get_video_pages(self, video_id):
        # 获取视频分p信息
        v = video.Video(bvid=video_id, credential=self.credential)
        pages = sync(v.get_pages())
        
        page_info = []

        for each in pages:
            static_frame = len(pages) <= 5
            static_path = None
            if static_frame:
                # 尝试下载视频的首帧图像
                fframe_url = each.get("first_frame", "")
                static_path = download_temp_image_to_static(fframe_url)

            page_info.append({
                "cid": each.get("cid", 0),
                "page": each.get("page", 0),
                "part": remove_html_tags_and_invalid_chars(each.get("part", "")),
                "duration": each.get("duration", 0),
                "static_frame": static_frame,
                "first_frame": static_path
            })

        return page_info

# test
if __name__ == "__main__":
    downloader = BilibiliDownloader()
    downloader.search_video("【(maimai】【谱面确认】 DX谱面 Aegleseeker 紫谱 Master")
