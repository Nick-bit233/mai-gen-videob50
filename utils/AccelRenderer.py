"""
AccelRenderer.py - 加速渲染管线

使用 Taichi GPU 合成 + FFmpeg 硬件编码，替代 MoviePy 的逐帧 CPU 渲染。
提供与 VideoUtils.py 兼容的 API，可作为可选后端使用。
"""

import os
import shutil
import subprocess
import traceback
import time
import numpy as np
import cv2
from PIL import Image
from typing import Optional, Tuple, List

from utils.PageUtils import remove_invalid_chars


# ============================================================================
# FFmpeg 版本检测与硬件编码器检测
# ============================================================================

_FFMPEG_MIN_VERSION = (5, 0)  # 最低要求 FFmpeg 5.0（NVENC 新版 preset API）
_ffmpeg_version_checked = False


def get_ffmpeg_binary(tool_name: str = 'ffmpeg') -> str:
    """解析 FFmpeg 工具路径，优先使用运行目录中的打包二进制。"""
    executable = f"{tool_name}.exe" if os.name == 'nt' else tool_name
    local_path = os.path.join(os.getcwd(), executable)
    if os.path.exists(local_path):
        return local_path

    resolved = shutil.which(tool_name)
    if resolved:
        return resolved

    raise FileNotFoundError(f"未找到 {executable}")

def check_ffmpeg_version():
    """检测 FFmpeg 版本，低于最低要求时抛出 RuntimeError。

    可多次调用，仅首次实际执行检测，后续直接返回。
    """
    global _ffmpeg_version_checked
    if _ffmpeg_version_checked:
        return

    import re
    try:
        ffmpeg_path = get_ffmpeg_binary('ffmpeg')
        ffprobe_path = get_ffmpeg_binary('ffprobe')
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True, text=True, timeout=10
        )
        # 匹配多种版本号格式:
        #   "ffmpeg version 7.1-full_build-..."
        #   "ffmpeg version n4.3.2-160-gfbb9368226 ..."
        #   "ffmpeg version N-112107-..."
        match = re.search(r'ffmpeg version [nN]?(\d+)\.(\d+)', result.stdout)
        if not match:
            raise RuntimeError(
                f"无法解析 FFmpeg 版本号。请确认 FFmpeg 已正确安装。\n"
                f"FFmpeg 输出: {result.stdout.splitlines()[0] if result.stdout else '(空)'}"
            )
        major, minor = int(match.group(1)), int(match.group(2))
        if (major, minor) < _FFMPEG_MIN_VERSION:
            raise RuntimeError(
                f"FFmpeg 版本过低: 检测到 {major}.{minor}，"
                f"最低要求 {_FFMPEG_MIN_VERSION[0]}.{_FFMPEG_MIN_VERSION[1]}。"
                f"请更新 FFmpeg 或使用最新的 runtime 运行环境包。"
            )
        # xfade 拼接与时长探测依赖 ffprobe，前置确认可以避免在长时间渲染后才报 WinError 2。
        subprocess.run(
            [ffprobe_path, '-version'],
            capture_output=True, text=True, timeout=10, check=True
        )
        _ffmpeg_version_checked = True
        print(f"[AccelRenderer] ✓ FFmpeg 版本: {major}.{minor}")
    except FileNotFoundError:
        raise RuntimeError(
            "未找到 FFmpeg 或 FFprobe，请确认使用最新 runtime 包，或已将它们添加到系统 PATH 中。"
        )

_hw_encoder_cache = None

def detect_hw_encoder() -> Tuple[str, str]:
    """
    检测可用的 FFmpeg 硬件编码器。
    
    Returns:
        (codec_name, display_name) 元组
    """
    global _hw_encoder_cache
    if _hw_encoder_cache is not None:
        return _hw_encoder_cache

    encoders = [
        ('h264_videotoolbox', 'macOS VideoToolbox'),
        ('h264_nvenc', 'NVIDIA NVENC'),
        ('h264_amf', 'AMD AMF'),
        ('h264_qsv', 'Intel QuickSync'),
    ]

    try:
        result = subprocess.run(
            [get_ffmpeg_binary('ffmpeg'), '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        for codec, name in encoders:
            if codec in output:
                # 实际探测编码器是否能工作（驱动版本可能不满足要求）
                probe = subprocess.run(
                    [get_ffmpeg_binary('ffmpeg'), '-y', '-hide_banner', '-loglevel', 'error',
                     '-f', 'lavfi', '-i', 'nullsrc=s=256x256:d=0.1:r=30',
                     '-c:v', codec, '-f', 'null', '-'],
                    capture_output=True, text=True, timeout=10
                )
                if probe.returncode == 0:
                    _hw_encoder_cache = (codec, name)
                    print(f"[AccelRenderer] ✓ 检测到硬件编码器: {name} ({codec})")
                    return _hw_encoder_cache
                else:
                    reason = probe.stderr.strip().split('\n')[-1] if probe.stderr.strip() else '未知原因'
                    print(f"[AccelRenderer] ✗ {name} ({codec}) 不可用: {reason}")
    except Exception as e:
        print(f"[AccelRenderer] Warning: 检测硬件编码器失败: {e}")

    _hw_encoder_cache = ('libx264', 'CPU Software (libx264)')
    print(f"[AccelRenderer] 未检测到硬件编码器，使用 CPU 软件编码")
    return _hw_encoder_cache


def get_ffmpeg_encoder_args(codec: str, bitrate: str = "5000k") -> list:
    """根据编码器返回对应的 FFmpeg 参数"""
    if codec == 'h264_videotoolbox':
        return ['-c:v', codec, '-b:v', bitrate, '-allow_sw', '1']
    elif codec == 'h264_nvenc':
        return ['-c:v', codec, '-b:v', bitrate, '-preset', 'p4', '-tune', 'hq']
    elif codec == 'h264_amf':
        return ['-c:v', codec, '-b:v', bitrate, '-quality', 'balanced']
    elif codec == 'h264_qsv':
        return ['-c:v', codec, '-b:v', bitrate, '-preset', 'medium']
    else:
        return ['-c:v', 'libx264', '-b:v', bitrate, '-preset', 'medium']


# ============================================================================
# 音频响度测量
# ============================================================================

import re as _re

def _measure_audio_rms(audio_path: str, start: float = 0, duration: float = None) -> float:
    """使用 FFmpeg volumedetect 测量音频片段的 RMS 电平 (dB)
    
    Returns:
        float: mean_volume in dB, or -20.0 if measurement fails
    """
    cmd = [get_ffmpeg_binary('ffmpeg'), '-hide_banner', '-loglevel', 'info']
    if start > 0:
        cmd += ['-ss', str(start)]
    if duration:
        cmd += ['-t', str(duration)]
    cmd += ['-i', audio_path, '-af', 'volumedetect', '-f', 'null', '-']
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        match = _re.search(r'mean_volume:\s*([-\d.]+)\s*dB', result.stderr)
        if match:
            return float(match.group(1))
    except Exception as e:
        print(f"[AccelRenderer] Warning: 音频RMS测量失败: {e}")
    return -20.0  # fallback: 假设已在目标电平


# ============================================================================
# 视频帧读取工具
# ============================================================================

class VideoFrameReader:
    """使用 OpenCV 读取视频帧，支持顺序读取模式避免随机 seek 开销"""

    def __init__(self, video_path: str):
        self.path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"无法打开视频: {video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.frame_count / self.fps if self.fps > 0 else 0
        self._current_pos = 0

    def seek_to(self, time_sec: float):
        """定位到指定时间点，用于开始顺序读取前的初始定位"""
        frame_idx = int(time_sec * self.fps)
        frame_idx = max(0, min(frame_idx, self.frame_count - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        self._current_pos = frame_idx

    def read_next(self) -> Optional[np.ndarray]:
        """顺序读取下一帧 (RGB uint8)，避免随机 seek 开销"""
        ret, frame = self.cap.read()
        if ret:
            self._current_pos += 1
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    def get_frame(self, time_sec: float) -> Optional[np.ndarray]:
        """获取指定时间点的帧 (RGB uint8)，需要随机访问时使用"""
        frame_idx = int(time_sec * self.fps)
        frame_idx = max(0, min(frame_idx, self.frame_count - 1))
        if frame_idx != self._current_pos:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            self._current_pos = frame_idx
        ret, frame = self.cap.read()
        if ret:
            self._current_pos += 1
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    def close(self):
        if self.cap:
            self.cap.release()

    def __del__(self):
        self.close()


# ============================================================================
# FFmpeg 写入管线
# ============================================================================

class FFmpegWriter:
    """通过 stdin pipe 向 FFmpeg 写入原始帧数据"""

    def __init__(self, output_path: str, width: int, height: int,
                 fps: int = 30, codec: str = None, bitrate: str = "5000k",
                 audio_path: str = None, audio_start: float = 0, audio_duration: float = None,
                 audio_fade_in: float = 0, audio_fade_out: float = 0,
                 volume_adjust_db: float = 0):
        self.output_path = output_path
        self.width = width
        self.height = height

        if codec is None:
            codec, _ = detect_hw_encoder()

        encoder_args = get_ffmpeg_encoder_args(codec, bitrate)

        cmd = [
            get_ffmpeg_binary('ffmpeg'), '-y', '-hide_banner', '-loglevel', 'warning',
            # 视频输入 (raw frames from stdin)
            '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}', '-r', str(fps),
            '-i', 'pipe:0',
        ]

        # 音频输入
        has_audio = audio_path and os.path.exists(audio_path)
        if has_audio:
            cmd += ['-ss', str(audio_start)]
            if audio_duration:
                cmd += ['-t', str(audio_duration)]
            cmd += ['-i', audio_path]
        else:
            # 无音频源时生成静音音轨，确保输出始终包含音频流（xfade 拼接需要）
            cmd += ['-f', 'lavfi', '-i',
                    f'anullsrc=channel_layout=stereo:sample_rate=44100']

        # 视频编码参数
        cmd += encoder_args
        cmd += ['-pix_fmt', 'yuv420p']

        # 音频编码 + 可选淡入淡出滤镜
        if has_audio:
            af_filters = []
            # 裁剪后的音频必须从 0 PTS 开始，否则后续 xfade/acrossfade 可能继承源文件时间戳，
            # 表现为完整视频中音频相对画面整体滞后。
            af_filters.append("asetpts=PTS-STARTPTS")
            if abs(volume_adjust_db) > 0.5:
                af_filters.append(f"volume={volume_adjust_db:.1f}dB")
            if audio_fade_in > 0:
                af_filters.append(f"afade=t=in:d={audio_fade_in}")
            if audio_fade_out > 0 and audio_duration:
                fade_out_start = max(0, audio_duration - audio_fade_out)
                af_filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={audio_fade_out}")
            af_filters.append("aresample=48000:first_pts=0")
            af_filters.append("asetpts=N/SR/TB")
            if af_filters:
                cmd += ['-af', ','.join(af_filters)]
            cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-map', '0:v', '-map', '1:a', '-shortest']
        else:
            # 静音音轨：仅需编码，用 -shortest 使其匹配视频长度
            cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-map', '0:v', '-map', '1:a', '-shortest']

        cmd += [output_path]
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def write_frame(self, frame: np.ndarray):
        """写入一帧 RGB uint8 数据"""
        if self.process.stdin:
            # 确保帧尺寸正确
            if frame.shape[0] != self.height or frame.shape[1] != self.width:
                frame = cv2.resize(frame, (self.width, self.height))
            if frame.shape[2] == 4:
                frame = frame[:, :, :3]
            self.process.stdin.write(frame.astype(np.uint8).tobytes())

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        self.process.wait()
        if self.process.returncode != 0:
            stderr = self.process.stderr.read().decode() if self.process.stderr else ""
            print(f"[FFmpegWriter] Warning: FFmpeg 返回码 {self.process.returncode}")
            if stderr:
                print(f"[FFmpegWriter] stderr: {stderr[:500]}")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ============================================================================
# 加速渲染 API
# ============================================================================

def _prepare_bg_frame(bg_path: str, resolution: tuple, is_video: bool = False,
                      reader: 'VideoFrameReader' = None, time_sec: float = 0) -> np.ndarray:
    """准备背景帧"""
    if is_video and reader is not None:
        frame = reader.get_frame(time_sec)
        if frame is not None:
            return cv2.resize(frame, resolution)
    
    # 静态图片背景
    try:
        with open(bg_path, 'rb') as f:
            img_array = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is None:
        return np.zeros((resolution[1], resolution[0], 3), dtype=np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return cv2.resize(img, resolution)


def _prepare_video_frame(reader: VideoFrameReader, time_sec: float,
                         target_size: tuple, crop_rect: tuple = None) -> np.ndarray:
    """准备谱面视频帧"""
    frame = reader.get_frame(time_sec)
    if frame is None:
        return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
    
    if crop_rect:
        x1, y1, x2, y2 = [int(v) for v in crop_rect]
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        frame = frame[y1:y2, x1:x2]
    
    return cv2.resize(frame, target_size)


def _load_image_rgba(path: str) -> np.ndarray:
    """加载图片为 RGBA numpy 数组"""
    img = Image.open(path).convert('RGBA')
    return np.array(img)


def _load_image_rgb(path: str, target_size: tuple = None) -> np.ndarray:
    """加载图片为 RGB numpy 数组"""
    try:
        with open(path, 'rb') as f:
            img_array = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is None:
        if target_size:
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
        return np.zeros((1080, 1920, 3), dtype=np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if target_size:
        img = cv2.resize(img, target_size)
    return img


def compute_video_crop_and_size(game_type: str, video_reader: VideoFrameReader,
                                resolution: tuple,
                                visual_center: tuple = None) -> Tuple[tuple, tuple, tuple]:
    """
    计算视频的裁剪区域和目标尺寸（与 VideoUtils.edit_game_video_clip 逻辑一致）

    Args:
        visual_center: (x, y) 在缩放后帧空间中的视觉中心（来自圆检测），None 使用几何中心

    Returns:
        (target_size, crop_rect_on_resized, video_pos)
        target_size: (w, h) 缩放后尺寸
        crop_rect_on_resized: (x1, y1, x2, y2) 在缩放后帧上的裁剪区域，None 表示不裁剪
        video_pos: (x, y) 在画布上的位置
    """
    h_resize_ratio = 0.5 if game_type == "maimai" else 0.667
    target_h = int(h_resize_ratio * resolution[1])
    scale = target_h / video_reader.height
    target_w = int(video_reader.width * scale)

    crop_rect = None
    if game_type == "maimai":
        # 裁剪为正方形
        if abs(target_h - target_w) > 2:
            center_x = visual_center[0] if visual_center else target_w / 2
            if target_w > target_h:
                x1 = center_x - target_h / 2
                x2 = center_x + target_h / 2
                if x1 < 0:
                    x1 = 0
                    x2 = target_h
                elif x2 > target_w:
                    x2 = target_w
                    x1 = target_w - target_h
                crop_rect = (int(x1), 0, int(x2), target_h)
            else:
                center_y = target_h / 2
                y1 = center_y - target_w / 2
                y2 = center_y + target_w / 2
                if y1 < 0:
                    y1 = 0
                    y2 = target_w
                crop_rect = (0, int(y1), target_w, int(y2))
    elif game_type == "chunithm":
        target_ar = 16.0 / 9.0
        current_ar = target_w / target_h if target_h > 0 else target_ar
        if abs(current_ar - target_ar) / target_ar > 0.03:
            if current_ar > target_ar:
                crop_w = int(round(target_h * target_ar))
                cx1 = int(round((target_w - crop_w) / 2))
                crop_rect = (cx1, 0, cx1 + crop_w, target_h)
            else:
                crop_h = int(round(target_w / target_ar))
                cy1 = int(round((target_h - crop_h) / 2))
                crop_rect = (0, cy1, target_w, cy1 + crop_h)

    rel_v_pos_map = {
        "maimai": (0.092, 0.328),
        "chunithm": (0.0422, 0.0583)
    }
    mul_x, mul_y = rel_v_pos_map.get(game_type, (0.092, 0.328))
    video_pos = (int(mul_x * resolution[0]), int(mul_y * resolution[1]))

    return (target_w, target_h), crop_rect, video_pos


def render_segment_accel(
    game_type: str,
    clip_config: dict,
    style_config: dict,
    resolution: tuple,
    output_path: str,
    fps: int = 30,
    bitrate: str = "5000k",
    codec: str = None,
    progress_callback=None,
    fade_in: float = 0,
    fade_out: float = 0
) -> dict:
    """
    使用 Taichi GPU + FFmpeg 硬件编码渲染单个视频片段。
    替代 VideoUtils.create_video_segment() + write_videofile() 的组合。
    
    Returns:
        {"status": "success"|"error", "info": str}
    """
    from utils.TaichiAccel import (
        is_available as ti_available,
        composite_five_layers,
        FrameCompositor
    )

    clip_name = clip_config.get('clip_title_name', 'clip')
    print(f"[AccelRenderer] 正在渲染: {clip_name} (GPU加速)")

    if not ti_available():
        return {"status": "error", "info": "Taichi GPU 加速不可用"}

    try:
        duration = clip_config.get('duration', 10)
        total_frames = int(duration * fps)

        # === 准备静态资源 ===
        # 背景
        default_bg_path = style_config['asset_paths']['content_bg']
        override_bg = style_config['options'].get('override_content_default_bg', False)
        using_video_bg = style_config['options'].get('content_use_video_bg', False)

        if override_bg:
            bg_path = default_bg_path
        elif 'bg_image' in clip_config and clip_config['bg_image'] and os.path.exists(clip_config.get('bg_image', '')):
            bg_path = clip_config['bg_image']
        else:
            bg_path = default_bg_path

        bg_frame = _load_image_rgb(bg_path, resolution)

        # 背景视频（如果启用）
        bg_video_reader = None
        if using_video_bg:
            bg_video_path = style_config['asset_paths'].get('content_bg_video', None)
            if bg_video_path and os.path.exists(bg_video_path):
                bg_video_reader = VideoFrameReader(bg_video_path)

        # 成绩图 (RGBA)
        if 'main_image' in clip_config and clip_config['main_image'] and os.path.exists(clip_config.get('main_image', '')):
            score_img = _load_image_rgba(clip_config['main_image'])
            # 缩放到画布宽度
            score_scale = resolution[0] / score_img.shape[1]
            new_h = int(score_img.shape[0] * score_scale)
            score_img_resized = cv2.resize(score_img, (resolution[0], new_h), interpolation=cv2.INTER_AREA)
        else:
            score_img_resized = np.zeros((resolution[1], resolution[0], 4), dtype=np.uint8)

        # 文字图 (RGBA) - 使用 TextRenderer 预渲染
        from utils.TextRenderer import TextRenderer, TextStyle, LayoutConfig
        font_path = style_config['asset_paths']['comment_font']
        text_size = style_config['content_text_style']['font_size']
        inline_max = style_config['content_text_style']['inline_max_chara']
        text_area_width = max(400, inline_max * text_size)
        interline = style_config['content_text_style']['interline']
        h_align = style_config['content_text_style']['horizontal_align']
        text_color = style_config['content_text_style']['font_color']
        enable_stroke = style_config['content_text_style']['enable_stroke']
        stroke_color = style_config['content_text_style'].get('stroke_color') if enable_stroke else None
        stroke_width = style_config['content_text_style'].get('stroke_width', 0) if enable_stroke else 0

        text_style = TextStyle(
            font_path=font_path, font_size=text_size, color=text_color,
            stroke_color=stroke_color, stroke_width=stroke_width
        )
        text_layout = LayoutConfig(
            width=text_area_width, auto_height=True,
            padding=(10, 10, 10, 10), line_spacing=interline * 1.2,
            horizontal_align=h_align, vertical_align="top"
        )
        renderer = TextRenderer(text_style, text_layout)
        text_pil = renderer.render(clip_config.get('text', ''))
        text_img = np.array(text_pil)

        # 文字位置
        rel_t_pos_map = {"maimai": (0.54, 0.54), "chunithm": (0.76, 0.227)}
        tmx, tmy = rel_t_pos_map.get(game_type, (0.54, 0.54))
        text_pos = (int(tmx * resolution[0]), int(tmy * resolution[1]))

        # === 准备视频源 ===
        video_reader = None
        video_pos = (0, 0)
        target_video_size = (540, 540)
        crop_rect = None

        if 'video' in clip_config and clip_config['video'] and os.path.exists(clip_config.get('video', '')):
            video_reader = VideoFrameReader(clip_config['video'])

            # 自动居中对齐：检测视觉中心（maimai 圆形检测）
            visual_center = None
            auto_center = clip_config.get('auto_center_align', True)
            if auto_center and game_type == "maimai":
                try:
                    from utils.VisionUtils import find_circle_center
                    start_time_tmp = clip_config.get('start', 0)
                    end_time_tmp = clip_config.get('end', start_time_tmp + duration)
                    mid_time = (start_time_tmp + end_time_tmp) / 2
                    analysis_frame = video_reader.get_frame(mid_time)
                    if analysis_frame is not None:
                        raw_center = find_circle_center(
                            analysis_frame, debug=False,
                            name=clip_config.get('clip_title_name', 'clip'))
                        if raw_center is not None:
                            # 将原始帧坐标转换到缩放后帧空间
                            h_resize_ratio = 0.5
                            scale = int(h_resize_ratio * resolution[1]) / video_reader.height
                            visual_center = (raw_center[0] * scale, raw_center[1] * scale)
                except Exception as e:
                    print(f"[AccelRenderer] Warning: 自动居中检测失败: {e}")

            target_video_size, crop_rect, video_pos = compute_video_crop_and_size(
                game_type, video_reader, resolution, visual_center=visual_center
            )
        
        start_time = clip_config.get('start', 0)
        end_time = clip_config.get('end', start_time + duration)

        # === 提取音频路径 ===
        audio_path = clip_config.get('video', None)
        audio_start = start_time

        # === 逐片段音频响度均衡（匹配 CPU 路径的 per-clip RMS 归一化）===
        volume_adjust_db = 0
        if audio_path and os.path.exists(audio_path):
            measured_rms = _measure_audio_rms(audio_path, audio_start, duration)
            target_rms_db = -20.0
            volume_adjust_db = target_rms_db - measured_rms
            # 限制增益范围：对应 CPU 路径 gain clamp [0.1, 3.0] → [-20dB, +9.5dB]
            volume_adjust_db = max(-20.0, min(9.5, volume_adjust_db))
            if abs(volume_adjust_db) > 0.5:
                print(f"[AccelRenderer] 音频均衡: {clip_name} RMS={measured_rms:.1f}dB, 调整={volume_adjust_db:+.1f}dB")

        # === FFmpeg 写入器 ===
        writer = FFmpegWriter(
            output_path, resolution[0], resolution[1],
            fps=fps, codec=codec, bitrate=bitrate,
            audio_path=audio_path, audio_start=audio_start, audio_duration=duration,
            audio_fade_in=fade_in, audio_fade_out=fade_out,
            volume_adjust_db=volume_adjust_db
        )

        # === 预计算淡入淡出帧数 ===
        fade_in_frames = int(fade_in * fps) if fade_in > 0 else 0
        fade_out_frames = int(fade_out * fps) if fade_out > 0 else 0

        # === 逐帧渲染（使用 FrameCompositor 预计算静态层）===
        compositor = FrameCompositor(
            bg=bg_frame,
            score_image=score_img_resized,
            text_image=text_img,
            video_pos=video_pos,
            text_pos=text_pos,
            bg_brightness=0.8,
            output_size=resolution,
        )

        for frame_idx in range(total_frames):
            t = start_time + frame_idx / fps

            # 准备当前视频帧
            if video_reader:
                raw_frame = video_reader.get_frame(t)
                if raw_frame is None:
                    raw_frame = np.zeros((target_video_size[1], target_video_size[0], 3), dtype=np.uint8)
                else:
                    raw_frame = cv2.resize(raw_frame, (target_video_size[0], target_video_size[1]))
                    if crop_rect:
                        x1, y1, x2, y2 = crop_rect
                        x1, y1 = max(0, x1), max(0, y1)
                        x2 = min(raw_frame.shape[1], x2)
                        y2 = min(raw_frame.shape[0], y2)
                        raw_frame = raw_frame[y1:y2, x1:x2]
                video_frame = raw_frame
            else:
                video_frame = np.zeros((target_video_size[1], target_video_size[0], 3), dtype=np.uint8)

            # 动态背景
            if bg_video_reader:
                bg_t = t % bg_video_reader.duration if bg_video_reader.duration > 0 else 0
                current_bg = _prepare_bg_frame(bg_path, resolution, is_video=True,
                                               reader=bg_video_reader, time_sec=bg_t)
                compositor.update_bg(current_bg)

            # GPU 快速合成（零拷贝路径）
            composed = compositor.composite(video_frame)

            # 视频淡入淡出（GPU 亮度渐变）
            if fade_in_frames > 0 and frame_idx < fade_in_frames:
                brightness = frame_idx / fade_in_frames
                composed = (composed.astype(np.float32) * brightness).clip(0, 255).astype(np.uint8)
            elif fade_out_frames > 0 and frame_idx >= total_frames - fade_out_frames:
                brightness = (total_frames - 1 - frame_idx) / fade_out_frames
                composed = (composed.astype(np.float32) * brightness).clip(0, 255).astype(np.uint8)

            writer.write_frame(composed)

            # 节流的进度回调（每 30 帧或最后一帧）
            if progress_callback and (frame_idx % 30 == 0 or frame_idx == total_frames - 1):
                progress_callback(frame_idx + 1, total_frames, clip_name)
        writer.close()
        if video_reader:
            video_reader.close()
        if bg_video_reader:
            bg_video_reader.close()

        print(f"[AccelRenderer] ✓ 渲染完成: {clip_name}")
        return {"status": "success", "info": f"GPU加速渲染 {clip_name} 完成"}

    except Exception as e:
        print(f"[AccelRenderer] Error: {traceback.format_exc()}")
        return {"status": "error", "info": f"GPU渲染失败: {str(e)}"}


def render_info_segment_accel(
    clip_config: dict,
    style_config: dict,
    resolution: tuple,
    output_path: str,
    fps: int = 30,
    bitrate: str = "5000k",
    codec: str = None,
    progress_callback=None,
    fade_in: float = 0,
    fade_out: float = 0
) -> dict:
    """
    使用 FFmpeg 硬件编码渲染开场/结尾信息片段。
    """
    from utils.TaichiAccel import is_available as ti_available, multiply_brightness, alpha_composite

    clip_name = clip_config.get('clip_title_name', '片段')
    print(f"[AccelRenderer] 正在渲染信息片段: {clip_name}")

    try:
        duration = clip_config.get('duration', 5)
        total_frames = int(duration * fps)

        # 加载资源
        intro_text_bg_path = style_config['asset_paths']['intro_text_bg']
        intro_video_bg_path = style_config['asset_paths']['intro_video_bg']
        intro_bgm_path = style_config['asset_paths']['intro_bgm']

        text_bg = _load_image_rgba(intro_text_bg_path)
        text_bg_resized = cv2.resize(text_bg, resolution, interpolation=cv2.INTER_AREA)

        # 背景视频
        bg_reader = VideoFrameReader(intro_video_bg_path)

        # 渲染文字
        from utils.TextRenderer import TextRenderer, TextStyle, LayoutConfig
        font_path = style_config['asset_paths']['comment_font']
        ts = style_config['intro_text_style']

        text_style = TextStyle(
            font_path=font_path, font_size=ts['font_size'], color=ts['font_color'],
            stroke_color=ts.get('stroke_color') if ts['enable_stroke'] else None,
            stroke_width=ts.get('stroke_width', 0) if ts['enable_stroke'] else 0
        )
        text_layout = LayoutConfig(
            width=max(400, ts['inline_max_chara'] * ts['font_size']),
            auto_height=True, padding=(10, 10, 10, 10),
            line_spacing=ts['interline'] * 1.2,
            horizontal_align=ts['horizontal_align'], vertical_align="top"
        )
        renderer = TextRenderer(text_style, text_layout)
        text_pil = renderer.render(clip_config.get('text', ''))
        text_img = np.array(text_pil)
        text_pos = (int(0.16 * resolution[0]), int(0.18 * resolution[1]))

        # 预拆分静态 RGBA 层（循环外一次性完成）
        text_bg_rgb = text_bg_resized[:, :, :3].astype(np.float32)
        text_bg_mask = text_bg_resized[:, :, 3].astype(np.float32) / 255.0 if text_bg_resized.shape[2] == 4 else None
        text_img_rgb = text_img[:, :, :3].astype(np.float32)
        text_img_mask = text_img[:, :, 3].astype(np.float32) / 255.0 if text_img.shape[2] == 4 else None
        tx, ty = text_pos

        # === 逐片段音频响度均衡 ===
        volume_adjust_db = 0
        if intro_bgm_path and os.path.exists(intro_bgm_path):
            measured_rms = _measure_audio_rms(intro_bgm_path, 0, duration)
            target_rms_db = -20.0
            volume_adjust_db = target_rms_db - measured_rms
            volume_adjust_db = max(-20.0, min(9.5, volume_adjust_db))
            if abs(volume_adjust_db) > 0.5:
                print(f"[AccelRenderer] 音频均衡: {clip_name} RMS={measured_rms:.1f}dB, 调整={volume_adjust_db:+.1f}dB")

        writer = FFmpegWriter(
            output_path, resolution[0], resolution[1],
            fps=fps, codec=codec, bitrate=bitrate,
            audio_path=intro_bgm_path, audio_start=0, audio_duration=duration,
            audio_fade_in=fade_in, audio_fade_out=fade_out,
            volume_adjust_db=volume_adjust_db
        )

        # 预计算淡入淡出帧数
        fade_in_frames = int(fade_in * fps) if fade_in > 0 else 0
        fade_out_frames = int(fade_out * fps) if fade_out > 0 else 0

        # 使用顺序读取模式
        bg_reader.seek_to(0)

        for frame_idx in range(total_frames):
            t = frame_idx / fps
            bg_t = t % bg_reader.duration if bg_reader.duration > 0 else 0
            # 循环播放背景视频时需要 seek 回起始点
            if frame_idx > 0 and bg_t < (frame_idx - 1) / fps % bg_reader.duration:
                bg_reader.seek_to(bg_t)
            bg_frame = bg_reader.read_next()
            if bg_frame is None:
                bg_reader.seek_to(bg_t)
                bg_frame = bg_reader.read_next()
            if bg_frame is None:
                bg_frame = np.zeros((resolution[1], resolution[0], 3), dtype=np.uint8)
            else:
                bg_frame = cv2.resize(bg_frame, resolution)

            if ti_available():
                bg_frame = multiply_brightness(bg_frame, 0.75)
                composed = alpha_composite(bg_frame if bg_frame.shape[2] == 4 else
                    np.dstack([bg_frame, np.full(bg_frame.shape[:2], 255, dtype=np.uint8)]),
                    text_bg_resized, (0, 0))
                composed = alpha_composite(
                    np.dstack([composed[:, :, :3], np.full(composed.shape[:2], 255, dtype=np.uint8)]),
                    text_img, text_pos)
            else:
                # CPU fallback: 完整合成（暗化背景 + text_bg + text）
                composed = (bg_frame.astype(np.float32) * 0.75).clip(0, 255)
                # 叠加 text_bg
                if text_bg_mask is not None:
                    h, w = text_bg_rgb.shape[:2]
                    mask3 = text_bg_mask[:, :, np.newaxis]
                    composed[:h, :w] = composed[:h, :w] * (1 - mask3) + text_bg_rgb * mask3
                # 叠加 text
                if text_img_mask is not None:
                    th, tw = text_img_rgb.shape[:2]
                    y1, y2 = ty, min(ty + th, composed.shape[0])
                    x1, x2 = tx, min(tx + tw, composed.shape[1])
                    sh, sw = y2 - y1, x2 - x1
                    if sh > 0 and sw > 0:
                        mask3 = text_img_mask[:sh, :sw, np.newaxis]
                        composed[y1:y2, x1:x2] = composed[y1:y2, x1:x2] * (1 - mask3) + text_img_rgb[:sh, :sw] * mask3
                composed = composed.clip(0, 255).astype(np.uint8)

            # 视频淡入淡出（亮度渐变）
            out_frame = composed[:, :, :3]
            if fade_in_frames > 0 and frame_idx < fade_in_frames:
                brightness = frame_idx / fade_in_frames
                out_frame = (out_frame.astype(np.float32) * brightness).clip(0, 255).astype(np.uint8)
            elif fade_out_frames > 0 and frame_idx >= total_frames - fade_out_frames:
                brightness = (total_frames - 1 - frame_idx) / fade_out_frames
                out_frame = (out_frame.astype(np.float32) * brightness).clip(0, 255).astype(np.uint8)

            writer.write_frame(out_frame)

            if progress_callback and (frame_idx % 30 == 0 or frame_idx == total_frames - 1):
                progress_callback(frame_idx + 1, total_frames, clip_name)
        writer.close()
        bg_reader.close()
        print(f"[AccelRenderer] ✓ 信息片段渲染完成: {clip_name}")
        return {"status": "success", "info": f"渲染 {clip_name} 完成"}

    except Exception as e:
        print(f"[AccelRenderer] Error: {traceback.format_exc()}")
        return {"status": "error", "info": f"渲染失败: {str(e)}"}


def render_all_clips_accel(
    game_type: str,
    style_config: dict,
    main_configs: list,
    video_output_path: str,
    video_res: tuple,
    video_bitrate: str,
    intro_configs: list = None,
    ending_configs: list = None,
    auto_add_transition: bool = True,
    trans_time: float = 1,
    force_render: bool = False,
    fps: int = 30,
    progress_callback=None
):
    """
    使用 GPU 加速渲染所有视频片段 —— 替代 VideoUtils.render_all_video_clips()
    progress_callback: (clip_index, total_clips, frame, total_frames, clip_name) -> None
    """
    codec, codec_name = detect_hw_encoder()
    print(f"[AccelRenderer] 使用编码器: {codec_name}")
    print(f"[AccelRenderer] 输出路径: {video_output_path}")

    t_all_start = time.perf_counter()
    total_clips = len(main_configs) + len(intro_configs or []) + len(ending_configs or [])
    clip_index = [0]  # 使用列表以便在闭包中修改
    vfile_prefix = 0

    def _make_frame_callback():
        """为当前片段创建帧级回调"""
        idx = clip_index[0]
        if progress_callback is None:
            return None
        def cb(frame, total_frames, clip_name):
            progress_callback(idx, total_clips, frame, total_frames, clip_name)
        return cb

    def render_clip(config, prefix, clip_type="content", override_name=None):
        nonlocal vfile_prefix
        name = override_name or config.get('clip_title_name', 'clip')
        name = remove_invalid_chars(name)
        output_file = os.path.join(video_output_path, f"{prefix}_{name}.mp4")

        if os.path.exists(output_file) and not force_render:
            print(f"[AccelRenderer] 跳过已存在: {prefix}_{name}.mp4")
            clip_index[0] += 1
            return

        # 确定淡入淡出时长
        fade_in_time = trans_time if auto_add_transition else 0
        fade_out_time = trans_time if auto_add_transition else 0

        t_clip_start = time.perf_counter()
        frame_cb = _make_frame_callback()
        if clip_type == "content":
            result = render_segment_accel(
                game_type, config, style_config, video_res,
                output_file, fps=fps, bitrate=video_bitrate, codec=codec,
                progress_callback=frame_cb,
                fade_in=fade_in_time, fade_out=fade_out_time
            )
        else:
            result = render_info_segment_accel(
                config, style_config, video_res,
                output_file, fps=fps, bitrate=video_bitrate, codec=codec,
                progress_callback=frame_cb,
                fade_in=fade_in_time, fade_out=fade_out_time
            )
        t_clip_elapsed = time.perf_counter() - t_clip_start
        print(f"[Timer] 片段 {prefix}_{name} 渲染耗时: {t_clip_elapsed:.2f}s")

        if result['status'] == 'error':
            raise RuntimeError(f"[AccelRenderer] 片段 {prefix}_{name} 渲染失败: {result['info']}")
        clip_index[0] += 1

    # 开场片段
    t_phase = time.perf_counter()
    if intro_configs:
        for config in intro_configs:
            render_clip(config, vfile_prefix, "info", "INTRO")
            vfile_prefix += 1
    if intro_configs:
        print(f"[Timer] === 开场片段阶段耗时: {time.perf_counter() - t_phase:.2f}s ===")

    # 主要片段
    t_phase = time.perf_counter()
    for config in main_configs:
        render_clip(config, vfile_prefix, "content")
        vfile_prefix += 1
    print(f"[Timer] === 主要片段阶段耗时: {time.perf_counter() - t_phase:.2f}s ({len(main_configs)} 个) ===")

    # 结尾片段
    t_phase = time.perf_counter()
    if ending_configs:
        for config in ending_configs:
            render_clip(config, vfile_prefix, "info", "ENDING")
            vfile_prefix += 1
    if ending_configs:
        print(f"[Timer] === 结尾片段阶段耗时: {time.perf_counter() - t_phase:.2f}s ===")

    t_all_elapsed = time.perf_counter() - t_all_start
    print(f"[Timer] ====== 全部片段渲染总耗时: {t_all_elapsed:.2f}s (共 {vfile_prefix} 个) ======")
