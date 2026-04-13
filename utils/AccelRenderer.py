"""
AccelRenderer.py - 加速渲染管线

使用 Taichi GPU 合成 + FFmpeg 硬件编码，替代 MoviePy 的逐帧 CPU 渲染。
提供与 VideoUtils.py 兼容的 API，可作为可选后端使用。
"""

import os
import subprocess
import traceback
import numpy as np
import cv2
from PIL import Image
from typing import Optional, Tuple, List

from utils.PageUtils import remove_invalid_chars


# ============================================================================
# FFmpeg 硬件编码器检测
# ============================================================================

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
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        for codec, name in encoders:
            if codec in output:
                _hw_encoder_cache = (codec, name)
                print(f"[AccelRenderer] ✓ 检测到硬件编码器: {name} ({codec})")
                return _hw_encoder_cache
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
                 audio_path: str = None, audio_start: float = 0, audio_duration: float = None):
        self.output_path = output_path
        self.width = width
        self.height = height

        if codec is None:
            codec, _ = detect_hw_encoder()

        encoder_args = get_ffmpeg_encoder_args(codec, bitrate)

        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning',
            # 视频输入 (raw frames from stdin)
            '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}', '-r', str(fps),
            '-i', 'pipe:0',
        ]

        # 音频输入
        if audio_path and os.path.exists(audio_path):
            cmd += ['-ss', str(audio_start)]
            if audio_duration:
                cmd += ['-t', str(audio_duration)]
            cmd += ['-i', audio_path]

        # 视频编码参数
        cmd += encoder_args
        cmd += ['-pix_fmt', 'yuv420p']

        # 音频编码
        if audio_path and os.path.exists(audio_path):
            cmd += ['-c:a', 'aac', '-b:a', '192k', '-map', '0:v', '-map', '1:a', '-shortest']

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
    img = cv2.imread(bg_path, cv2.IMREAD_COLOR)
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
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        if target_size:
            return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
        return np.zeros((1080, 1920, 3), dtype=np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if target_size:
        img = cv2.resize(img, target_size)
    return img


def compute_video_crop_and_size(game_type: str, video_reader: VideoFrameReader,
                                resolution: tuple) -> Tuple[tuple, tuple, tuple]:
    """
    计算视频的裁剪区域和目标尺寸（与 VideoUtils.edit_game_video_clip 逻辑一致）

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
            center_x = target_w / 2
            if target_w > target_h:
                x1 = center_x - target_h / 2
                x2 = center_x + target_h / 2
                if x1 < 0:
                    x1 = 0
                    x2 = target_h
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
    codec: str = None
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
            target_video_size, crop_rect, video_pos = compute_video_crop_and_size(
                game_type, video_reader, resolution
            )
        
        start_time = clip_config.get('start', 0)
        end_time = clip_config.get('end', start_time + duration)

        # === 提取音频路径 ===
        audio_path = clip_config.get('video', None)
        audio_start = start_time

        # === FFmpeg 写入器 ===
        writer = FFmpegWriter(
            output_path, resolution[0], resolution[1],
            fps=fps, codec=codec, bitrate=bitrate,
            audio_path=audio_path, audio_start=audio_start, audio_duration=duration
        )

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

            writer.write_frame(composed)

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
    codec: str = None
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

        writer = FFmpegWriter(
            output_path, resolution[0], resolution[1],
            fps=fps, codec=codec, bitrate=bitrate,
            audio_path=intro_bgm_path, audio_start=0, audio_duration=duration
        )

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

            writer.write_frame(composed[:, :, :3])

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
    fps: int = 30
):
    """
    使用 GPU 加速渲染所有视频片段 —— 替代 VideoUtils.render_all_video_clips()
    """
    codec, codec_name = detect_hw_encoder()
    print(f"[AccelRenderer] 使用编码器: {codec_name}")
    print(f"[AccelRenderer] 输出路径: {video_output_path}")

    vfile_prefix = 0

    def render_clip(config, prefix, clip_type="content", override_name=None):
        nonlocal vfile_prefix
        name = override_name or config.get('clip_title_name', 'clip')
        name = remove_invalid_chars(name)
        output_file = os.path.join(video_output_path, f"{prefix}_{name}.mp4")

        if os.path.exists(output_file) and not force_render:
            print(f"[AccelRenderer] 跳过已存在: {prefix}_{name}.mp4")
            return

        if clip_type == "content":
            result = render_segment_accel(
                game_type, config, style_config, video_res,
                output_file, fps=fps, bitrate=video_bitrate, codec=codec
            )
        else:
            result = render_info_segment_accel(
                config, style_config, video_res,
                output_file, fps=fps, bitrate=video_bitrate, codec=codec
            )

        if result['status'] == 'error':
            print(f"[AccelRenderer] Warning: {result['info']}")

    # 开场片段
    if intro_configs:
        for config in intro_configs:
            render_clip(config, vfile_prefix, "info", "INTRO")
            vfile_prefix += 1

    # 主要片段
    for config in main_configs:
        render_clip(config, vfile_prefix, "content")
        vfile_prefix += 1

    # 结尾片段
    if ending_configs:
        for config in ending_configs:
            render_clip(config, vfile_prefix, "info", "ENDING")
            vfile_prefix += 1

    print(f"[AccelRenderer] ✓ 所有片段渲染完成 (共 {vfile_prefix} 个)")
