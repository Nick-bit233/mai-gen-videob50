import os
import numpy as np
import subprocess
import traceback
import gc
import time
from PIL import Image, ImageFilter
from moviepy import VideoFileClip, ImageClip, TextClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
from moviepy import vfx, afx
from utils.VisionUtils import find_circle_center, draw_center_marker
from utils.PageUtils import remove_invalid_chars
from utils.Variables import HARD_RENDER_METHOD
from typing import Union, Tuple
try:
    from moviepy.video.io.ffmpeg_reader import FFMPEG_VideoReader
    if not getattr(FFMPEG_VideoReader, "_safe_del_patched", False):
        def _safe_ffmpeg_reader_del(self):
            try:
                self.close()
            except OSError:
                pass
            except Exception:
                pass
        FFMPEG_VideoReader.__del__ = _safe_ffmpeg_reader_del
        FFMPEG_VideoReader._safe_del_patched = True
except Exception:
    pass


def get_splited_text(text, text_max_bytes=60):
    """
    将说明文本按照最大字节数限制切割成多行 #TODO：使用更智能的分词算法
    
    Args:
        text (str): 输入文本
        text_max_bytes (int): 每行最大字节数限制（utf-8编码）
        
    Returns:
        str: 按规则切割并用换行符连接的文本
    """
    lines = []
    current_line = ""
    
    # 按现有换行符先分割
    for line in text.split('\n'):
        current_length = 0
        current_line = ""
        
        for char in line:
            # 计算字符长度：中日文为2，其他为1
            if '\u4e00' <= char <= '\u9fff' or '\u3040' <= char <= '\u30ff':
                char_length = 2
            else:
                char_length = 1
            
            # 如果添加这个字符会超出限制，保存当前行并重新开始
            if current_length + char_length > text_max_bytes:
                lines.append(current_line)
                current_line = char
                current_length = char_length
            else:
                current_line += char
                current_length += char_length
        
        # 处理剩余的字符
        if current_line:
            lines.append(current_line)
    
    return lines


def blur_image(pil_image, blur_radius=5):
    """
    对图片进行高斯模糊处理
    
    Args:
        pil_image (obj): PIL.Image对象
        blur_radius (int): 模糊半径，默认为10
        
    Returns:
        numpy.ndarray: 模糊处理后的图片数组
    """
    try:
        blurred_image = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        # 将模糊后的图片转换为 numpy 数组
        return np.array(blurred_image)
    except Exception as e:
        print(f"Warning: 图片模糊处理失败 - {str(e)}")
        return pil_image


def create_blank_image(width, height, color=(0, 0, 0, 0)):
    """
    创建一个透明的图片
    """
    # 创建一个RGBA模式的空白图片
    image = Image.new('RGBA', (width, height), color)
    # 转换为numpy数组，moviepy需要这种格式
    return np.array(image)


def save_jacket_background_image(img_data: Image.Image, save_path: str):
    try:
        # 高斯模糊处理图片
        jacket_array = blur_image(img_data, blur_radius=5)

        # Ensure we have a PIL Image
        if isinstance(jacket_array, np.ndarray):
            jacket_image = Image.fromarray(jacket_array)
        elif isinstance(jacket_array, Image.Image):
            jacket_image = jacket_array
        else:
            # Fallback: try to coerce to array then to image
            jacket_image = Image.fromarray(np.array(jacket_array))

        # 直接从原图中裁出最大的 16:9 区域（居中），然后等比缩放到 1920x1080（不拉伸）
        target_w, target_h = 1920, 1080
        target_ar = target_w / target_h

        orig_w, orig_h = jacket_image.size
        if orig_w == 0 or orig_h == 0:
            raise ValueError("Invalid jacket image size")

        orig_ar = orig_w / orig_h

        if abs(orig_ar - target_ar) < 1e-6:
            # 已经是 16:9，直接缩放到目标分辨率
            crop_box = (0, 0, orig_w, orig_h)
        elif orig_ar > target_ar:
            # 图片比 16:9 更宽：保留高度，裁剪宽度
            crop_h = orig_h
            crop_w = int(round(crop_h * target_ar))
            left = int(round((orig_w - crop_w) / 2))
            top = 0
            crop_box = (left, top, left + crop_w, top + crop_h)
        else:
            # 图片比 16:9 更高（更窄）：保留宽度，裁剪高度
            crop_w = orig_w
            crop_h = int(round(crop_w / target_ar))
            left = 0
            top = int(round((orig_h - crop_h) / 2))
            crop_box = (left, top, left + crop_w, top + crop_h)

        jacket_image = jacket_image.crop(crop_box)  # 执行裁剪
        jacket_image = jacket_image.resize((target_w, target_h), resample=Image.LANCZOS)  # 等比缩放到目标 1920x1080（使用高质量重采样）
        jacket_image.save(save_path)  # 保存图片
    except Exception as e:
        print(f"Warning: 保存曲绘背景图片{save_path}失败 - {str(e)}")



def validate_cache_video_file(file_path, expected_fps=None):
    """
    验证缓存视频文件是否有效
    
    Args:
        file_path: 视频文件路径
        expected_fps: 期望的帧率（可选，用于验证）
    
    Returns:
        tuple: (is_valid, error_message)
        - is_valid: bool, 文件是否有效
        - error_message: str, 如果无效，返回错误信息
    """
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    try:
        clip = VideoFileClip(file_path, audio=False)  # 使用 audio=False 加快验证速度
        
        # 检查时长
        if clip.duration is None or clip.duration <= 0:
            clip.close()
            return False, f"视频时长无效: {clip.duration}"
        
        # 检查帧率（如果提供了期望值）
        if expected_fps is not None:
            actual_fps = clip.fps
            if abs(actual_fps - expected_fps) > 1.0:  # 允许1fps的误差
                clip.close()
                return False, f"帧率不匹配: 期望 {expected_fps}fps, 实际 {actual_fps}fps"
        
        # 尝试读取第一帧和最后一帧（验证文件完整性）
        try:
            _ = clip.get_frame(0)
            # 尝试读取接近末尾的帧（但不超出范围）
            last_frame_time = min(clip.duration - 0.1, clip.duration * 0.9)
            last_frame_time = max(0, last_frame_time)
            _ = clip.get_frame(last_frame_time)
        except Exception as e:
            clip.close()
            return False, f"无法读取视频帧: {str(e)}"
        
        clip.close()
        return True, None
        
    except Exception as e:
        return False, f"验证视频文件时发生错误: {str(e)}"


def normalize_audio_volume(clip, target_dbfs=-20):
    """均衡化音频响度到指定的分贝值"""
    if clip.audio is None:
        return clip
    
    try:
        # 获取音频数据
        audio = clip.audio
        
        # 采样音频的多个点来计算平均音量
        sample_times = np.linspace(0, clip.duration, num=100)
        samples = []
        
        for t in sample_times:
            frame = audio.get_frame(t)
            if isinstance(frame, (list, tuple, np.ndarray)):
                samples.append(np.array(frame))
        
        if not samples:
            return clip
            
        # 将样本堆叠成数组
        audio_array = np.stack(samples)
        
        # 计算当前音频的均方根值
        current_rms = np.sqrt(np.mean(audio_array**2))
        
        # 计算需要的增益
        target_rms = 10**(target_dbfs/20)
        gain = target_rms / (current_rms + 1e-8)  # 添加小值避免除零
        
        # 限制增益范围，避免过度放大或减弱
        gain = np.clip(gain, 0.1, 3.0)
        
        # print(f"Applying volume gain: {gain:.2f}")
        
        # 应用音量调整
        return clip.with_volume_scaled(gain)
    except Exception as e:
        print(f"Warning: Audio normalization failed - {str(e)}")
        return clip


def create_info_segment(clip_config, style_config, resolution):
    """ 合成一个信息介绍的Moviepy Clip，用于开场或结尾 """

    clip_name = clip_config.get('clip_title_name', '开场/结尾片段')
    print(f"正在合成视频片段: {clip_name}")
    
    # 检查必需的字段并提供默认值
    if 'duration' not in clip_config:
        raise ValueError(f"片段 {clip_name} 缺少 'duration' 字段")
    if 'text' not in clip_config:
        print(f"Warning: 片段 {clip_name} 缺少 'text' 字段，使用默认文本")
        clip_config['text'] = "欢迎观看"

    font_path = style_config['asset_paths']['comment_font']
    intro_video_bg_path = style_config['asset_paths']['intro_video_bg']
    intro_text_bg_path = style_config['asset_paths']['intro_text_bg']
    intro_bgm_path = style_config['asset_paths']['intro_bgm']

    text_size = style_config['intro_text_style']['font_size']
    inline_max_len = style_config['intro_text_style']['inline_max_chara'] * 2
    interline_size = style_config['intro_text_style']['interline']
    horizontal_align = style_config['intro_text_style']['horizontal_align']
    text_color = style_config['intro_text_style']['font_color']
    enable_stroke = style_config['intro_text_style']['enable_stroke']
    if enable_stroke:
        stroke_color = style_config['intro_text_style']['stroke_color']
        stroke_width = style_config['intro_text_style']['stroke_width']

    bg_image = ImageClip(intro_text_bg_path).with_duration(clip_config['duration'])
    bg_image = bg_image.with_effects([vfx.Resize(width=resolution[0])])

    bg_video = VideoFileClip(intro_video_bg_path)
    # 移除音频以避免循环时的索引错误
    bg_video = bg_video.without_audio()
    bg_video = bg_video.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                      vfx.MultiplyColor(0.75),
                                      vfx.Resize(width=resolution[0])])

    # 创建文字
    text_list = get_splited_text(clip_config['text'], text_max_bytes=inline_max_len)
    txt_clip = TextClip(font=font_path, text="\n".join(text_list),
                        method = "label",
                        font_size=text_size,
                        margin=(20, 20),
                        interline=interline_size,
                        text_align=horizontal_align,
                        vertical_align="top",
                        color=text_color,
                        stroke_color = None if not enable_stroke else stroke_color,
                        stroke_width = 0 if not enable_stroke else stroke_width,
                        duration=clip_config['duration'])
    
    # 水印已移除
    # addtional_text = "【本视频由mai-genVb50视频生成器生成】"
    # addtional_txt_clip = TextClip(font=font_path, text=addtional_text,
    #                     method = "label",
    #                     font_size=18,
    #                     vertical_align="bottom",
    #                     color="white",
    #                     duration=clip_config['duration']
    # )
    
    text_pos = (int(0.16 * resolution[0]), int(0.18 * resolution[1]))
    # addtional_text_pos = (int(0.2 * resolution[0]), int(0.88 * resolution[1]))
    composite_clip = CompositeVideoClip([
            bg_video.with_position((0, 0)),
            bg_image.with_position((0, 0)),
            txt_clip.with_position((text_pos[0], text_pos[1])),
            # addtional_txt_clip.with_position((addtional_text_pos[0], addtional_text_pos[1]))  # 水印已移除
        ],
        size=resolution,
        use_bgclip=True
    )

    # 为整个composite_clip添加bgm
    bg_audio = AudioFileClip(intro_bgm_path)
    bg_audio = bg_audio.with_effects([afx.AudioLoop(duration=clip_config['duration'])])
    composite_clip = composite_clip.with_audio(bg_audio)

    return composite_clip.with_duration(clip_config['duration'])


def edit_game_video_clip(game_type, clip_config, resolution, auto_center_align=False) -> Union[VideoFileClip, tuple]:
    if 'video' in clip_config and clip_config['video'] is not None and os.path.exists(clip_config['video']):
        video_path = clip_config['video']
        
        # 尝试读取视频，添加错误处理和重试机制
        video_clip = None
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # 尝试使用不同的参数读取视频
                if attempt == 0:
                    # 第一次尝试：正常读取
                    video_clip = VideoFileClip(video_path)
                else:
                    # 第二次尝试：使用 audio=False 和更宽松的参数
                    video_clip = VideoFileClip(video_path, audio=False)
                
                # 验证视频是否可以正常访问
                test_duration = video_clip.duration
                if test_duration is None or test_duration <= 0:
                    raise ValueError(f"视频时长无效: {test_duration}")
                
                # 尝试获取第一帧（验证视频可以正常读取）
                try:
                    _ = video_clip.get_frame(0)
                except Exception as frame_error:
                    if attempt < max_retries - 1:
                        print(f"警告: 无法读取视频第一帧，尝试重新读取 (尝试 {attempt + 1}/{max_retries}): {frame_error}")
                        if video_clip:
                            try:
                                video_clip.close()
                            except:
                                pass
                        continue
                    else:
                        # 最后一次尝试也失败，但继续使用（某些情况下可能仍然可以工作）
                        print(f"警告: 无法读取视频第一帧，但继续处理: {frame_error}")
                
                # 成功读取，退出重试循环
                break
                
            except (OSError, IOError, ValueError) as e:
                error_msg = str(e)
                is_memory_error = '1455' in error_msg or '页面文件太小' in error_msg or 'page file' in error_msg.lower()
                
                if attempt < max_retries - 1:
                    if video_clip:
                        try:
                            video_clip.close()
                        except:
                            pass
                    
                    # 清理资源
                    gc.collect()
                    
                    if is_memory_error:
                        # 内存不足，等待更长时间并清理内存
                        print(f"警告: 系统内存不足，等待 {2 * (attempt + 1)} 秒后重试 (尝试 {attempt + 1}/{max_retries})...")
                        time.sleep(2 * (attempt + 1))  # 递增等待时间
                        gc.collect()  # 再次清理
                    else:
                        print(f"警告: 读取视频失败，尝试重新读取 (尝试 {attempt + 1}/{max_retries}): {e}")
                        time.sleep(1)  # 短暂等待
                    
                    continue
                else:
                    # 所有尝试都失败
                    if is_memory_error:
                        # 内存不足，创建占位符而不是抛出异常
                        print(f"错误: 系统内存不足，无法读取视频文件 {video_path}")
                        print(f"提示: 将使用黑色占位符替代该视频片段")
                        print(f"建议: 1) 关闭其他占用内存的程序 2) 增加虚拟内存大小 3) 减少同时处理的视频数量")
                        
                        # 创建占位符
                        duration = clip_config.get('duration', 10.0)
                        target_height = int(0.667 * resolution[1]) if game_type == "chunithm" else int(0.5 * resolution[1])
                        target_width = int(target_height * 16 / 9) if game_type == "chunithm" else target_height
                        
                        placeholder_clip = ImageClip(create_blank_image(target_width, target_height, color=(0, 0, 0, 255))).with_duration(duration)
                        placeholder_clip = placeholder_clip.with_effects([vfx.Resize(width=target_width)])
                        
                        x_offset = (resolution[0] - target_width) // 2
                        y_offset = (resolution[1] - target_height) // 2
                        
                        return placeholder_clip, (x_offset, y_offset)
                    else:
                        raise Exception(f"无法读取视频文件 {video_path}，已重试 {max_retries} 次: {e}")
        
        if video_clip is None:
            raise Exception(f"无法读取视频文件 {video_path}")
        
        # 添加调试信息
        print(f"Start time: {clip_config['start']}, Clip duration: {video_clip.duration}, End time: {clip_config['end']}")
        
        # 计算目标尺寸（考虑视频显示区域）
        if game_type == "maimai":
            # maimai: 目标区域约为 540x540 (正方形)
            target_height = int(0.5 * resolution[1])  # 540/1080
            target_width = target_height  # 正方形
        else:  # chunithm
            # chunithm: 目标区域约为 1280x720 (16:9)
            target_height = int(0.667 * resolution[1])  # 720/1080
            target_width = int(target_height * 16 / 9)  # 16:9 宽高比
        
        # 获取原始视频尺寸
        orig_width = video_clip.w
        orig_height = video_clip.h
        orig_ar = orig_width / orig_height if orig_height > 0 else 1.0
        target_ar = target_width / target_height if target_height > 0 else 1.0
        
        # 智能缩放：确保视频能够完整显示在目标区域内（使用填充而不是裁剪）
        # 计算缩放比例：选择较小的缩放比例，确保视频完全适配目标区域
        scale_by_height = target_height / orig_height
        scale_by_width = target_width / orig_width
        scale_ratio = min(scale_by_height, scale_by_width)  # 使用较小的比例，确保不超出
        
        # 等比例缩放
        new_width = int(orig_width * scale_ratio)
        new_height = int(orig_height * scale_ratio)
        
        print(f"原始视频尺寸: {orig_width}x{orig_height}, 目标区域: {target_width}x{target_height}")
        print(f"缩放比例: {scale_ratio:.3f}, 缩放后尺寸: {new_width}x{new_height}")
        
        # 使用 MoviePy 的 resized 方法
        # MoviePy 2.1.1+ 的 resized 方法接受 newsize 作为位置参数或关键字参数
        try:
            # 尝试使用位置参数 (newsize 作为第一个参数)
            video_clip = video_clip.resized((new_width, new_height))
        except (TypeError, AttributeError):
            try:
                # 尝试使用关键字参数
                video_clip = video_clip.resized(newsize=(new_width, new_height))
            except (TypeError, AttributeError):
                try:
                    # 尝试使用 width 和 height 参数
                    video_clip = video_clip.resized(width=new_width, height=new_height)
                except (TypeError, AttributeError):
                    # 如果都不支持，使用 Resize 效果（但 Resize 只支持 width，会保持宽高比）
                    # 我们需要手动处理高度
                    video_clip = video_clip.with_effects([vfx.Resize(width=new_width)])
                    # 如果高度不匹配，需要裁剪或填充
                    if abs(video_clip.h - new_height) > 1:  # 允许1像素误差
                        if video_clip.h > new_height:
                            # 高度超出，居中裁剪
                            y_center = video_clip.h / 2
                            video_clip = video_clip.cropped(y1=y_center - new_height/2, y2=y_center + new_height/2)
                        else:
                            # 高度不足，需要填充（创建黑色背景并居中放置视频）
                            # 这种情况应该很少，因为我们的缩放逻辑确保视频能完全容纳
                            print(f"警告: 视频高度 {video_clip.h} 小于目标高度 {new_height}，可能需要填充")

        # height and width after init resize
        video_height = video_clip.h
        video_width = video_clip.w

        # 检查并自动调整 start_time 和 end_time，确保不超出视频长度
        video_duration = video_clip.duration
        
        # 调整开始时间
        if clip_config['start'] < 0:
            print(f"警告: 片段开始时间 {clip_config['start']} 为负数，自动调整为 0")
            clip_config['start'] = 0
        elif clip_config['start'] >= video_duration:
            print(f"警告: 片段开始时间 {clip_config['start']} 超出视频长度 {video_duration:.2f}，自动调整为视频开始")
            clip_config['start'] = 0
        
        # 调整结束时间
        if clip_config['end'] <= clip_config['start']:
            print(f"警告: 片段结束时间 {clip_config['end']} 小于等于开始时间 {clip_config['start']}，自动调整为开始时间 + 1秒")
            clip_config['end'] = min(clip_config['start'] + 1, video_duration)
        elif clip_config['end'] > video_duration:
            print(f"警告: 片段结束时间 {clip_config['end']} 超出视频长度 {video_duration:.2f}，自动调整为视频实际长度")
            clip_config['end'] = video_duration
        
        # 确保结束时间不超过视频长度（双重检查）
        clip_config['end'] = min(clip_config['end'], video_duration)
        
        # 裁剪目标视频片段
        video_clip = video_clip.subclipped(start_time=clip_config['start'],
                                            end_time=clip_config['end'])

        # 更新缩放后的尺寸（subclipped不会改变尺寸）
        video_height = video_clip.h
        video_width = video_clip.w

        # 使用填充而不是裁剪，确保视频完整显示
        # 如果缩放后的视频尺寸小于目标区域，创建带黑边的视频
        if game_type == "maimai":
            # maimai: 目标区域是正方形
            if video_width != target_width or video_height != target_height:
                # 创建黑色背景
                black_bg = create_blank_image(target_width, target_height)
                bg_clip = ImageClip(black_bg).with_duration(video_clip.duration)
                
                # 计算居中位置
                x_offset = (target_width - video_width) // 2
                y_offset = (target_height - video_height) // 2
                
                # 将视频叠加到黑色背景上（居中显示）
                video_clip = CompositeVideoClip([
                    bg_clip.with_position((0, 0)),
                    video_clip.with_position((x_offset, y_offset))
                ], size=(target_width, target_height))
                
                print(f"maimai: 视频已填充到目标尺寸 {target_width}x{target_height}，居中偏移 ({x_offset}, {y_offset})")
        elif game_type == "chunithm":
            # chunithm: 目标区域是16:9
            if video_width != target_width or video_height != target_height:
                # 创建黑色背景
                black_bg = create_blank_image(target_width, target_height)
                bg_clip = ImageClip(black_bg).with_duration(video_clip.duration)
                
                # 计算居中位置
                x_offset = (target_width - video_width) // 2
                y_offset = (target_height - video_height) // 2
                
                # 将视频叠加到黑色背景上（居中显示）
                video_clip = CompositeVideoClip([
                    bg_clip.with_position((0, 0)),
                    video_clip.with_position((x_offset, y_offset))
                ], size=(target_width, target_height))
                
                print(f"chunithm: 视频已填充到目标尺寸 {target_width}x{target_height}，居中偏移 ({x_offset}, {y_offset})")
        
        # 更新最终尺寸
        video_width = video_clip.w
        video_height = video_clip.h

    else:
        print(f"Video Generator Warning:{clip_config['clip_title_name']} 没有对应的视频, 请检查本地资源")
        default_size_map = {
            "maimai": (540/1080, 540/1080),
            "chunithm": (1280/1920, 720/1920)
        }
        size_mul_x, size_mul_y = default_size_map.get(game_type, (540/1080, 540/1080))
        # 创建一个透明的视频片段
        blank_frame = create_blank_image(
            int(size_mul_x * resolution[0]),
            int(size_mul_y * resolution[1])
        )
        video_clip = ImageClip(blank_frame).with_duration(clip_config['duration'])

    # if 'video_position' in clip_config:
    #     pos = clip_config['video_position']
    #     if isinstance(pos, (list, tuple)) and len(pos) == 2:
    #         # 若为相对值（0<val<=1），按分辨率计算；否则视为像素值
    #         if 0 < pos[0] <= 1 and 0 < pos[1] <= 1:
    #             video_pos = (int(pos[0] * resolution[0]), int(pos[1] * resolution[1]))
    #         else:
    #             video_pos = (int(pos[0]), int(pos[1]))

    rel_v_pos_map = {
        "maimai": (0.092, 0.328),
        "chunithm": (0.0422, 0.0583)
    }
    mul_x, mul_y = rel_v_pos_map.get(game_type, rel_v_pos_map["maimai"])
    video_pos = (int(mul_x * resolution[0]), int(mul_y * resolution[1]))

    return video_clip, video_pos


def edit_game_text_clip(game_type, clip_config, resolution, style_config) -> Union[TextClip, tuple]:
    """
    抽象出的文字处理函数，返回 (TextClip, position)
    """
    # 读取样式配置
    font_path = style_config['asset_paths']['comment_font']
    text_size = style_config['content_text_style']['font_size']
    inline_max_len = style_config['content_text_style']['inline_max_chara'] * 2
    interline_size = style_config['content_text_style']['interline']
    horizontal_align = style_config['content_text_style']['horizontal_align']
    text_color = style_config['content_text_style']['font_color']
    enable_stroke = style_config['content_text_style']['enable_stroke']
    stroke_color = style_config['content_text_style'].get('stroke_color', None) if enable_stroke else None
    stroke_width = style_config['content_text_style'].get('stroke_width', 0) if enable_stroke else 0

    # 创建文字
    text_list = get_splited_text(clip_config.get('text', ''), text_max_bytes=inline_max_len)
    txt_clip = TextClip(font=font_path, text="\n".join(text_list),
                        method="label",
                        font_size=text_size,
                        margin=(20, 20),
                        interline=interline_size,
                        text_align=horizontal_align,
                        vertical_align="top",
                        color=text_color,
                        stroke_color=None if not enable_stroke else stroke_color,
                        stroke_width=0 if not enable_stroke else stroke_width,
                        duration=clip_config.get('duration', 5))
    
    rel_t_pos_map = {
        "maimai": (0.54, 0.54),
        "chunithm": (0.76, 0.227)
    }
    mul_x, mul_y = rel_t_pos_map.get(game_type, rel_t_pos_map["maimai"])
    text_pos = (int(mul_x * resolution[0]), int(mul_y * resolution[1]))

    return txt_clip, text_pos


def create_video_segment(
        game_type: str,
        clip_config: dict, 
        style_config: dict, 
        resolution: tuple
    ):
    print(f"正在合成视频片段: {clip_config['clip_title_name']}")
    
    # 配置底部背景选项
    default_bg_path = style_config['asset_paths']['content_bg']
    override_content_bg = style_config['options'].get('override_content_default_bg', False)
    using_video_content_bg = style_config['options'].get('content_use_video_bg', False)

    # black_video仅作为纯黑色背景，避免透明素材的遮挡问题
    black_clip = VideoFileClip("./static/assets/bg_clips/black_bg.mp4")
    # 移除音频以避免循环时的索引错误
    black_clip = black_clip.without_audio()
    black_clip = black_clip.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                      vfx.Resize(width=resolution[0])])
    
    # 检查图片资源是否存在
    # 'main_image' == achievement_image
    if 'main_image' in clip_config and clip_config['main_image'] is not None and os.path.exists(clip_config['main_image']):
        main_image_clip = ImageClip(clip_config['main_image']).with_duration(clip_config['duration'])
        main_image_clip = main_image_clip.with_effects([vfx.Resize(width=resolution[0])])
    else:
        print(f"Video Generator Warning: {clip_config['clip_title_name']} 没有对应的成绩图, 请检查成绩图资源是否已生成")
        main_image_clip = ImageClip(create_blank_image(resolution[0], resolution[1])).with_duration(clip_config['duration'])

    if override_content_bg:
        bg_image_path = default_bg_path
    elif 'bg_image' in clip_config and clip_config['bg_image'] is not None and os.path.exists(clip_config['bg_image']):
        bg_image_path = clip_config['bg_image']
    else:
        print(f"Video Generator Warning: {clip_config['clip_title_name']} 没有对应的背景图, 请检查背景图资源是否成功获取，将使用默认背景替代")
        bg_image_path = default_bg_path

    bg_image_clip = ImageClip(bg_image_path).with_duration(clip_config['duration'])
    bg_image_clip = bg_image_clip.with_effects([vfx.Resize(width=resolution[0]), vfx.MultiplyColor(0.8)])  # apply 80% brightness on bg image

    if using_video_content_bg:
        bg_video_path = style_config['asset_paths'].get('content_bg_video', None)
        if bg_video_path and os.path.exists(bg_video_path):
            bg_clip = VideoFileClip(bg_video_path)
            # 移除音频以避免循环时的索引错误
            bg_clip = bg_clip.without_audio()
            bg_clip = bg_clip.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                              vfx.Resize(width=resolution[0]),
                                              vfx.MultiplyColor(0.8)])  # apply 80% brightness on bg video
        else:
            print(f"Video Generator Warning: 无法加载背景视频，将使用背景图片代替")
            bg_clip = bg_image_clip
    else:
        bg_clip = bg_image_clip

    # 是否自动对齐
    if 'auto_center_align' in clip_config:
        auto_align = clip_config['auto_center_align']
    else:
        auto_align = True
    # 拆分clip处理逻辑到单独的函数
    video_clip, video_pos = edit_game_video_clip(game_type, clip_config, resolution, auto_center_align=auto_align)
    text_clip, text_pos = edit_game_text_clip(game_type, clip_config, resolution, style_config)

    # 叠放剪辑，以生成完整片段
    # 图层顺序（从下到上）：
    # 1. black_clip - 黑色背景（避免透明素材的通道bug）
    # 2. bg_clip - 背景图片或视频
    # 3. main_image_clip - 成绩图片（包含紫色边框和完整UI框架，应该在游戏视频之前）
    # 4. video_clip - 游戏视频（叠加在成绩图片之上）
    # 5. text_clip - 评论文字（最上层）
    composite_clip = CompositeVideoClip([
            black_clip.with_position((0, 0)),  # 使用一个pure black的视频作为背景（此背景用于避免透明素材的通道的bug问题）
            bg_clip.with_position((0, 0)),  # 背景图片或视频
            main_image_clip.with_position((0, 0)),  # 成绩图片（包含完整UI框架，应该在游戏视频之前）
            video_clip.with_position((video_pos[0], video_pos[1])),  # 谱面确认视频（叠加在成绩图片之上）
            text_clip.with_position((text_pos[0], text_pos[1]))  # 评论文字
        ],
        size=resolution,
        use_bgclip=True  # 必须设置为true，否则其上透明素材的通道会失效（疑似为moviepy2.0的bug）
    )

    return composite_clip.with_duration(clip_config['duration'])


def get_video_preview_frame(game_type, clip_config, style_config, resolution, part="intro") -> Image.Image:
    """ 获取视频片段的预览帧，返回PIL.Image对象 """
    if part == "intro":
        preview_clip = create_info_segment(clip_config, style_config, resolution)
    elif part == "content":
        preview_clip = create_video_segment(game_type, clip_config, style_config, resolution)
    
    try:
        frame = preview_clip.get_frame(t=1)
        pil_img = Image.fromarray(frame.astype("uint8"))
        return pil_img
    finally:
        if hasattr(preview_clip, "close"):
            preview_clip.close()



def add_transitions_to_clips(clips, trans_time=1, resolution=None):
    """
    为视频片段列表添加过渡效果（交叉淡入淡出），使用 CompositeVideoClip 实现
    
    Args:
        clips: 视频片段列表
        trans_time: 过渡时长
        resolution: 视频分辨率（用于 CompositeVideoClip）
    
    Returns:
        添加了过渡效果的合成视频片段
    """
    if not clips or len(clips) == 0:
        return None

    min_duration = min((clip.duration for clip in clips if clip is not None), default=0)
    if min_duration and trans_time > min_duration:
        safe_trans_time = max(0.0, min_duration / 2)
        print(f"Warning: trans_time {trans_time}s exceeds clip duration; clamping to {safe_trans_time}s")
        trans_time = safe_trans_time
    
    if len(clips) == 1:
        # 只有一个片段，只添加淡入淡出
        clip = clips[0]
        clip = clip.with_effects([
            vfx.FadeIn(duration=trans_time),
            vfx.FadeOut(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])
        return clip
    
    # 多个片段，使用 CompositeVideoClip 实现交叉淡入淡出
    transitioned_clips = []
    current_time = 0
    
    for i, clip in enumerate(clips):
        # 确保所有片段的位置都是 (0, 0)，避免画面被裁剪
        clip = clip.with_position((0, 0))
        
        # 第一个片段：只有淡入，从时间 0 开始
        if i == 0:
            # 第一个片段不需要 CrossFadeIn，只需要在最后添加淡出（如果有下一个片段）
            if len(clips) > 1:
                # 如果有下一个片段，添加淡出效果
                clip = clip.with_effects([
                    vfx.FadeOut(duration=trans_time),
                    afx.AudioFadeOut(duration=trans_time)
                ])
            clip = clip.with_start(current_time)
            transitioned_clips.append(clip)
            current_time = clip.duration - trans_time  # 减去重叠部分
        # 最后一个片段：只有淡出，与前一个片段有重叠
        elif i == len(clips) - 1:
            # 最后一个片段添加淡入效果（与前一个片段交叉）
            clip = clip.with_effects([
                vfx.FadeIn(duration=trans_time),
                afx.AudioFadeIn(duration=trans_time),
                vfx.FadeOut(duration=trans_time),
                afx.AudioFadeOut(duration=trans_time)
            ])
            # 与前一个片段重叠 trans_time 秒
            clip = clip.with_start(current_time)
            transitioned_clips.append(clip)
        # 中间片段：交叉淡入淡出，与前一个片段有重叠
        else:
            # 中间片段添加淡入和淡出效果
            clip = clip.with_effects([
                vfx.FadeIn(duration=trans_time),
                afx.AudioFadeIn(duration=trans_time),
                vfx.FadeOut(duration=trans_time),
                afx.AudioFadeOut(duration=trans_time)
            ])
            # 与前一个片段重叠 trans_time 秒
            clip = clip.with_start(current_time)
            transitioned_clips.append(clip)
            # 更新当前时间：当前片段结束时间减去下一个片段的过渡重叠时间
            current_time = current_time + clip.duration - trans_time
    
    # 计算最终时长
    if transitioned_clips:
        max_end_time = max(clip.end if hasattr(clip, 'end') else (getattr(clip, 'start', 0) + clip.duration) 
                          for clip in transitioned_clips)
        
        # 使用 CompositeVideoClip 合成，确保所有片段位置正确
        if resolution:
            final_clip = CompositeVideoClip(transitioned_clips, size=resolution, use_bgclip=False)
        else:
            final_clip = CompositeVideoClip(transitioned_clips, use_bgclip=False)
        
        # 确保时长正确
        if hasattr(final_clip, 'duration') and final_clip.duration < max_end_time:
            final_clip = final_clip.with_duration(max_end_time)
        
        return final_clip
    
    return None


def add_clip_with_transition(clips, new_clip, set_start=False, trans_time=1):
    """
    添加新片段到片段列表中，并处理转场效果
    
    Args:
        clips (list): 现有片段列表
        new_clip: 要添加的新片段
        trans_time (float): 转场时长
        set_start (bool): 是否设置开始时间（用于主要视频片段）
    """
    if len(clips) == 0:
        clips.append(new_clip)
        return
    
    # 对主要视频片段设置开始时间
    if set_start:
        new_clip = new_clip.with_start(clips[-1].end - trans_time)

    # 为前一个片段添加渐出效果
    clips[-1] = clips[-1].with_effects([
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])

    # 为新片段添加渐入效果
    new_clip = new_clip.with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time)
        ])
    
    clips.append(new_clip)


def create_full_video(game_type: str, style_config: dict, resolution: tuple,
                      main_configs: list, 
                      intro_configs: list = None, ending_configs: list = None,
                      auto_add_transition=True, trans_time=1, full_last_clip=False,
                      batch_size: int = None, temp_output_dir: str = None,
                      batch_inner_trans_enable: bool = False,
                      progress_callback=None, fps: int = 60, skip_cache_files: dict = None):
    """ 创建完整视频的 Moviepy Clip，包含开场、主要视频片段和结尾片段 
    
    Args:
        batch_size: 每批处理的视频数量，None 表示不分批（一次性处理所有）
        temp_output_dir: 临时文件输出目录，如果提供且使用分批处理，将生成临时视频文件
    Returns:
        如果使用分批处理且提供了 temp_output_dir，返回临时文件路径列表
        否则返回 VideoClip 对象
    """
    clips = []
    ending_clips = []
    temp_video_files = []  # 存储临时视频文件路径

    # 处理开场片段
    if intro_configs:
        # 检查是否使用缓存的开场文件
        if skip_cache_files and 'intro' in skip_cache_files and os.path.exists(skip_cache_files['intro']):
            # 验证缓存文件是否有效
            is_valid, error_msg = validate_cache_video_file(skip_cache_files['intro'], expected_fps=fps)
            if is_valid:
                print(f"使用缓存的开场文件: {skip_cache_files['intro']}")
                if temp_output_dir:
                    temp_video_files.insert(0, skip_cache_files['intro'])
            else:
                print(f"警告: 缓存的开场文件无效，将重新生成")
                print(f"错误信息: {error_msg}")
                # 继续生成开场片段
                print(f"处理开场片段，共 {len(intro_configs)} 个")
                for idx, clip_config in enumerate(intro_configs):
                    print(f"开场片段 {idx + 1}: 配置键 = {list(clip_config.keys())}")
                    clip = create_info_segment(clip_config, style_config, resolution)
                    clip = normalize_audio_volume(clip)
                    add_clip_with_transition(clips, clip, 
                                            set_start=True, 
                                            trans_time=trans_time)
        else:
            print(f"处理开场片段，共 {len(intro_configs)} 个")
            for idx, clip_config in enumerate(intro_configs):
                print(f"开场片段 {idx + 1}: 配置键 = {list(clip_config.keys())}")
                clip = create_info_segment(clip_config, style_config, resolution)
                clip = normalize_audio_volume(clip)
                add_clip_with_transition(clips, clip, 
                                        set_start=True, 
                                        trans_time=trans_time)

    combined_start_time = 0

    # 处理主要视频片段（分批处理）
    total_main_configs = len(main_configs)
    if batch_size and batch_size > 0 and total_main_configs > batch_size and temp_output_dir:
        # 分批处理并生成临时文件
        num_batches = (total_main_configs + batch_size - 1) // batch_size
        print(f"主要视频片段总数: {total_main_configs}，将分 {num_batches} 批处理，每批 {batch_size} 个")
        print(f"每批将生成临时视频文件保存到: {temp_output_dir}")
        
        os.makedirs(temp_output_dir, exist_ok=True)
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_main_configs)
            batch_configs = main_configs[start_idx:end_idx]
            
            # 首先检查是否使用缓存的批次文件（在开始处理片段之前）
            cache_key = f'batch_{batch_idx}'
            if skip_cache_files and cache_key in skip_cache_files and os.path.exists(skip_cache_files[cache_key]):
                # 验证缓存文件是否有效
                is_valid, error_msg = validate_cache_video_file(skip_cache_files[cache_key], expected_fps=fps)
                if is_valid:
                    print(f"\n{'='*60}")
                    print(f"跳过第 {batch_idx + 1}/{num_batches} 批，使用缓存文件")
                    print(f"缓存文件: {skip_cache_files[cache_key]}")
                    print(f"{'='*60}")
                    temp_video_files.append(skip_cache_files[cache_key])
                    # 更新进度：跳过批次
                    if progress_callback:
                        progress_callback({
                            'stage': 'batch_processing',
                            'current_batch': batch_idx + 1,
                            'total_batches': num_batches,
                            'progress': ((batch_idx + 1) / num_batches) * 0.7
                        })
                    continue  # 跳过整个批次的处理
                else:
                    print(f"\n{'='*60}")
                    print(f"警告: 缓存文件无效，将重新生成第 {batch_idx + 1} 批")
                    print(f"错误信息: {error_msg}")
                    print(f"{'='*60}")
            
            print(f"\n{'='*60}")
            print(f"处理第 {batch_idx + 1}/{num_batches} 批 (片段 {start_idx + 1}-{end_idx})")
            print(f"{'='*60}")
            
            # 更新进度：批次处理开始
            if progress_callback:
                progress_callback({
                    'stage': 'batch_processing',
                    'current_batch': batch_idx + 1,
                    'total_batches': num_batches,
                    'progress': (batch_idx / num_batches) * 0.7  # 批次处理占70%进度
                })
            
            batch_clips = []  # 当前批次的片段
            
            for local_idx, clip_config in enumerate(batch_configs):
                global_idx = start_idx + local_idx
                is_last_in_all = (global_idx == total_main_configs - 1)
                
                # 更新进度：单个片段处理
                if progress_callback:
                    batch_progress = (local_idx + 1) / len(batch_configs)
                    overall_progress = (batch_idx / num_batches) * 0.7 + (batch_progress / num_batches) * 0.7
                    progress_callback({
                        'stage': 'clip_processing',
                        'current_batch': batch_idx + 1,
                        'total_batches': num_batches,
                        'current_clip': global_idx + 1,
                        'total_clips': total_main_configs,
                        'progress': overall_progress
                    })
                
                # 判断是否是最后一个片段
                if is_last_in_all and full_last_clip:
                    start_time = clip_config['start']
                    # 获取原始视频的长度（不是配置文件中配置的duration）
                    full_clip = VideoFileClip(clip_config['video'])
                    try:
                        full_clip_duration = full_clip.duration - 5
                    finally:
                        full_clip.close()
                    # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
                    clip_config['duration'] = full_clip_duration - start_time
                    clip_config['end'] = full_clip_duration

                clip = create_video_segment(game_type, clip_config, style_config, resolution)  
                clip = normalize_audio_volume(clip)
                batch_clips.append(clip)
            
            # 合成当前批次的视频并保存为临时文件
            # 注意：批次内的片段不添加过渡效果，过渡效果只在合并批次时添加
            # 这样可以避免双重过渡（批次内过渡 + 批次间过渡）
            if batch_clips:
                print(f"合成第 {batch_idx + 1} 批视频片段，共 {len(batch_clips)} 个片段...")
                # 更新进度：批次合成
                if progress_callback:
                    progress_callback({
                        'stage': 'batch_compositing',
                        'current_batch': batch_idx + 1,
                        'total_batches': num_batches,
                        'progress': ((batch_idx + 0.8) / num_batches) * 0.7
                    })
                
                # 批次内的片段直接拼接，不添加过渡效果
                # 过渡效果将在合并批次时统一添加，避免双重过渡
                print(f"  直接拼接批次内片段（过渡效果将在合并批次时添加）...")
                if auto_add_transition and batch_inner_trans_enable and trans_time > 0:
                    inner_trans_time = trans_time
                    min_duration = min((clip.duration for clip in batch_clips if clip is not None), default=0)
                    if min_duration and inner_trans_time > min_duration:
                        inner_trans_time = max(0.0, min_duration / 2)
                    print(f"  为批次内片段添加过渡效果（{inner_trans_time}秒）...")
                    transitioned_batch_clips = []
                    for clip in batch_clips:
                        if not transitioned_batch_clips:
                            transitioned_batch_clips.append(clip)
                        else:
                            add_clip_with_transition(
                                transitioned_batch_clips,
                                clip,
                                set_start=True,
                                trans_time=inner_trans_time
                            )
                    batch_video = CompositeVideoClip(
                        transitioned_batch_clips,
                        size=resolution,
                        use_bgclip=False
                    )
                else:
                    batch_video = concatenate_videoclips(batch_clips, method="compose")
                print(f"  批次视频时长: {batch_video.duration:.2f}秒")
                
                temp_file = os.path.join(temp_output_dir, f"batch_{batch_idx:04d}.mp4")
                print(f"保存第 {batch_idx + 1} 批临时视频到: {temp_file}")
                batch_video.write_videofile(
                    temp_file,
                    fps=fps,  # 使用用户设置的帧率
                    codec='libx264',
                    preset='medium',
                    audio_codec='aac',
                    audio_bitrate='192k',
                    logger=None  # 减少输出
                )
                batch_video.close()
                temp_video_files.append(temp_file)
                
                # 关闭所有片段，释放内存
                for clip in batch_clips:
                    if hasattr(clip, 'close'):
                        clip.close()
                batch_clips = []
                batch_ending_clips = []
                
                print(f"第 {batch_idx + 1} 批处理完成，已保存临时文件")
                gc.collect()
                time.sleep(2)  # 等待系统释放资源
            else:
                print(f"警告：第 {batch_idx + 1} 批没有生成任何片段")
        
        # 如果有开场片段，也需要保存为临时文件（如果还没有使用缓存）
        if clips and not (skip_cache_files and 'intro' in skip_cache_files):
            print("合成开场片段...")
            if auto_add_transition:
                intro_video = CompositeVideoClip(clips)
            else:
                intro_video = concatenate_videoclips(clips)
            
            intro_temp_file = os.path.join(temp_output_dir, "intro.mp4")
            intro_video.write_videofile(
                intro_temp_file,
                fps=fps,  # 使用用户设置的帧率
                codec='libx264',
                preset='medium',
                audio_codec='aac',
                audio_bitrate='192k',
                logger=None
            )
            intro_video.close()
            temp_video_files.insert(0, intro_temp_file)  # 插入到开头
            
            for clip in clips:
                if hasattr(clip, 'close'):
                    clip.close()
            clips = []
            gc.collect()
        
        # 返回临时文件列表
        return temp_video_files
    elif batch_size and batch_size > 0 and total_main_configs > batch_size:
        # 分批处理但不生成临时文件（原有逻辑）
        num_batches = (total_main_configs + batch_size - 1) // batch_size
        print(f"主要视频片段总数: {total_main_configs}，将分 {num_batches} 批处理，每批 {batch_size} 个")
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_main_configs)
            batch_configs = main_configs[start_idx:end_idx]
            
            print(f"\n{'='*60}")
            print(f"处理第 {batch_idx + 1}/{num_batches} 批 (片段 {start_idx + 1}-{end_idx})")
            print(f"{'='*60}")
            
            for local_idx, clip_config in enumerate(batch_configs):
                global_idx = start_idx + local_idx
                is_last_in_all = (global_idx == total_main_configs - 1)
                
                # 判断是否是最后一个片段
                if is_last_in_all and full_last_clip:
                    start_time = clip_config['start']
                    # 获取原始视频的长度（不是配置文件中配置的duration）
                    full_clip = VideoFileClip(clip_config['video'])
                    try:
                        full_clip_duration = full_clip.duration - 5
                    finally:
                        full_clip.close()
                    # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
                    clip_config['duration'] = full_clip_duration - start_time
                    clip_config['end'] = full_clip_duration

                    clip = create_video_segment(game_type, clip_config, style_config, resolution)  
                    clip = normalize_audio_volume(clip)

                    combined_start_time = clips[-1].end - trans_time if clips else 0
                    ending_clips.append(clip)     
                else:
                    clip = create_video_segment(game_type, clip_config, style_config, resolution)  
                    clip = normalize_audio_volume(clip)

                    add_clip_with_transition(clips, clip, 
                                            set_start=True, 
                                            trans_time=trans_time)
            
            # 每批处理完后清理内存
            if batch_idx < num_batches - 1:  # 不是最后一批
                print(f"第 {batch_idx + 1} 批处理完成，清理内存...")
                gc.collect()
                time.sleep(1)  # 短暂等待，让系统释放资源
    else:
        # 不分批，一次性处理所有
        print(f"处理主要视频片段，共 {total_main_configs} 个（不分批）")
        for clip_config in main_configs:
            # 判断是否是最后一个片段
            if main_configs.index(clip_config) == len(main_configs) - 1 and full_last_clip:
                start_time = clip_config['start']
                # 获取原始视频的长度（不是配置文件中配置的duration）
                full_clip = VideoFileClip(clip_config['video'])
                try:
                    full_clip_duration = full_clip.duration - 5
                finally:
                    full_clip.close()
                # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
                clip_config['duration'] = full_clip_duration - start_time
                clip_config['end'] = full_clip_duration

                clip = create_video_segment(game_type, clip_config, style_config, resolution)  
                clip = normalize_audio_volume(clip)

                combined_start_time = clips[-1].end - trans_time if clips else 0
                ending_clips.append(clip)     
            else:
                clip = create_video_segment(game_type, clip_config, style_config, resolution)  
                clip = normalize_audio_volume(clip)

                add_clip_with_transition(clips, clip, 
                                        set_start=True, 
                                        trans_time=trans_time)

    # 处理结尾片段
    if ending_configs:
        for clip_config in ending_configs:
            clip = create_info_segment(clip_config, style_config, resolution)
            clip = normalize_audio_volume(clip)
            if full_last_clip:
                ending_clips.append(clip)
            else:
                add_clip_with_transition(clips, clip, 
                                        set_start=True, 
                                        trans_time=trans_time)

    if full_last_clip and len(ending_clips) > 0:
        clips.append(get_combined_ending_clip(ending_clips, combined_start_time, trans_time))

    print(f"视频片段总数: {len(clips)}")
    for idx, clip in enumerate(clips):
        start_time = getattr(clip, 'start', 0)
        print(f"  片段 {idx + 1}: 时长 {clip.duration:.2f}秒, 开始时间 {start_time:.2f}秒")

    if auto_add_transition:
        # 使用 CompositeVideoClip 处理带转场效果的片段
        # 注意：所有片段必须正确设置 start 时间
        final_clip = CompositeVideoClip(clips)
        print(f"最终视频时长: {final_clip.duration:.2f}秒")
        return final_clip
    else:
        return concatenate_videoclips(clips)  # 该方法不会添加转场效果，即使设置了trans_time


def sort_video_files(files):
    """
    对视频文件按照文件名开头的数字索引进行排序
    例如: "0_xxx.mp4", "1_xxx.mp4", "2_xxx.mp4" 等
    """
    def get_sort_key(filename):
        try:
            # 获取文件名（不含扩展名）中第一个下划线前的数字
            number = int(os.path.splitext(filename)[0].split('_')[0])
            return number
        except (ValueError, IndexError):
            print(f"Error: 无法从文件名解析索引: {filename}")
            return float('inf')  # 将无效文件排到最后
    
    # 直接按照数字索引排序
    return sorted(files, key=get_sort_key)


def combine_full_video_from_existing_clips(video_clips: list, resolution, trans_time=1):
    """ 从已有的视频片段中合成完整视频，需要按照列表顺序传入每个视频片段的路径，添加moviepy转场效果  """
    clips = []

    for video_clip in video_clips:
        clip = VideoFileClip(video_clip)
        clip = normalize_audio_volume(clip)
        if len(clips) == 0:
            clips.append(clip)
        else:
            # 为前一个片段添加音频渐出效果
            clips[-1] = clips[-1].with_audio_fadeout(trans_time)
            # 为当前片段添加音频渐入效果和视频渐入效果
            current_clip = clip.with_audio_fadein(trans_time).with_crossfadein(trans_time)
            # 设置片段开始时间
            clips.append(current_clip.with_start(clips[-1].end - trans_time))

    final_video = CompositeVideoClip(clips, size=resolution)
    return final_video


def gene_pure_black_video(output_path, duration, resolution):
    """
    生成一个纯黑色的视频，输出保存到output_path
    """
    black_frame = create_blank_image(resolution[0], resolution[1], color=(0, 0, 0, 1))
    clip = ImageClip(black_frame).with_duration(duration)
    clip.write_videofile(output_path, fps=30)


def get_combined_ending_clip(ending_clips, combined_start_time, trans_time):
    """合并最后一个主要视频的片段与结尾，使用统一音频（实验性功能）"""

    if len(ending_clips) < 2:
        print("Warning: 没有足够的结尾片段，将只保留最终片段")
        return ending_clips[0].with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])
    
    # 获得最终片段
    b1_clip = ending_clips[0]
    # 获得结尾片段组
    ending_comment_clips = ending_clips[1:]

    # 取出最终片段的音频
    combined_clip_audio = b1_clip.audio
    b1_clip = b1_clip.without_audio()

    # 计算需要从最终片段结尾截取的时间
    ending_full_duration = sum([clip.duration for clip in ending_comment_clips])

    if ending_full_duration > b1_clip.duration:
        print(f"Warning: 最终片段的长度不足，FULL_LAST_CLIP选项将无效化！")
        return CompositeVideoClip(ending_clips).with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])

    # 将ending_clip的时间提前到b1片段的结尾，并裁剪最终片段
    b1_clip = b1_clip.subclipped(start_time=b1_clip.start, end_time=b1_clip.end - ending_full_duration)
    # 裁剪ending_comment_clips
    for i in range(len(ending_comment_clips)):
        if i == 0:
            ending_comment_clips[i] = ending_comment_clips[i].with_start(b1_clip.end)
        else:
            ending_comment_clips[i] = ending_comment_clips[i].with_start(ending_comment_clips[i-1].end)

    full_list = [b1_clip] + ending_comment_clips
    # for clip in full_list:
    #     print(f"Combined Ending Clip: clip的开始时间：{clip.start}, 结束时间：{clip.end}")

    # 将最终片段与ending_clip合并
    combined_clip = CompositeVideoClip(full_list)
    print(f"Video Generator: b1_clip_audio_len: {combined_clip_audio.duration}, combined_clip_len: {combined_clip.duration}")
    # 设置combined_clip的音频为原最终片段的音频（二者长度应该相同）
    combined_clip = combined_clip.with_audio(combined_clip_audio)
    # 设置combined_clip的开始时间
    combined_clip = combined_clip.with_start(combined_start_time)
    # 设置结尾淡出到黑屏
    combined_clip = combined_clip.with_effects([
        vfx.CrossFadeIn(duration=trans_time),
        afx.AudioFadeIn(duration=trans_time),
        vfx.CrossFadeOut(duration=trans_time),
        afx.AudioFadeOut(duration=trans_time)
    ])
    
    return combined_clip


def render_all_video_clips(game_type: str, style_config: dict, main_configs: list,
                           video_output_path: str, video_res: tuple, video_bitrate: str,
                           intro_configs: list = None, ending_configs: list = None,
                           auto_add_transition=True, trans_time=1, force_render=False,
                           use_hardware_acceleration=False, acceleration_method=None):
    """ 渲染所有视频片段，并按照clip_title_name输出到指定路径文件 """
    vfile_prefix = 0

    def modify_and_rend_clip(clip, config, prefix, auto_add_transition, trans_time):
        clip_title_name = remove_invalid_chars(config['clip_title_name'])  # clip_title_name作为输出文件名的一部分，需要进行清洗，去除不合法字符
        output_file = os.path.join(video_output_path, f"{prefix}_{clip_title_name}.mp4")

        # 检查文件是否已经存在
        if os.path.exists(output_file) and not force_render:
            print(f"视频文件{output_file}已存在，跳过渲染。如果需要强制覆盖已存在的文件，请设置勾选force_render")
            clip.close()
            del clip
            return
        
        clip = normalize_audio_volume(clip)
        # 如果启用了自动添加转场效果，则在头尾加入淡入淡出
        if auto_add_transition:
            clip = clip.with_effects([
                vfx.FadeIn(duration=trans_time),
                vfx.FadeOut(duration=trans_time),
                afx.AudioFadeIn(duration=trans_time),
                afx.AudioFadeOut(duration=trans_time)
            ])
        # 直接渲染clip为视频文件
        print(f"正在合成视频片段: {prefix}_{clip_title_name}.mp4")
        
        # 根据硬件加速设置选择编码器
        if use_hardware_acceleration and acceleration_method and acceleration_method in HARD_RENDER_METHOD:
            encoder_prefix = "h264"
            hardware_suffix = HARD_RENDER_METHOD[acceleration_method]["codec"]
            final_codec = f"{encoder_prefix}_{hardware_suffix}"
            print(f"使用硬件加速编码: {final_codec}")
        else:
            final_codec = "libx264"
            print(f"使用软件编码: {final_codec}")
        
        clip.write_videofile(output_file, fps=30, threads=4, preset='ultrafast', 
                            codec=final_codec, bitrate=video_bitrate)
        clip.close()
        # 强制垃圾回收
        del clip


    if intro_configs:
        for clip_config in intro_configs:
            clip = create_info_segment(clip_config, style_config, video_res)
            clip = modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time)
            vfile_prefix += 1

    for clip_config in main_configs:
        clip = create_video_segment(game_type, clip_config, style_config, video_res)
        clip = modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time)

        vfile_prefix += 1

    if ending_configs:
        for clip_config in ending_configs:
            clip = create_info_segment(clip_config, style_config, video_res)
            clip = modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time)
            vfile_prefix += 1


def render_one_video_clip(
        game_type: str,
        config: dict, 
        style_config: dict, 
        video_output_path: str, video_res: tuple, video_bitrate: str,
        video_file_name: str=None
    ):
    """ 根据一条配置合成单个视频片段，并保存到指定路径的文件 """
    if not video_file_name:
        video_file_name = f"{remove_invalid_chars(config['clip_title_name'])}.mp4"
    print(f"正在合成视频片段: {video_file_name}")
    try:
        clip = create_video_segment(game_type, config, style_config, video_res)
        clip.write_videofile(os.path.join(video_output_path, video_file_name), 
                             fps=30, threads=4, preset='ultrafast', bitrate=video_bitrate)
        clip.close()
        return {"status": "success", "info": f"合成视频片段{video_file_name}成功"}
    except Exception as e:
        print(f"Error: 合成视频片段{video_file_name}时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成视频片段{video_file_name}时发生异常: {traceback.print_exc()}"}
   
    
def render_complete_full_video(
        username: str,
        game_type: str,
        style_config: dict, 
        main_configs: list, 
        video_output_path: str, 
        intro_configs: list=None, ending_configs: list=None,
        video_res: tuple = (1920, 1080), video_bitrate: str = "4000k",
        video_trans_enable: bool = True, video_trans_time: float = 1.0, full_last_clip: bool = False,
        use_hardware_acceleration: bool = False, acceleration_method: str = None,
        batch_size: int = None, progress_callback=None, video_fps: int = 60, skip_cache_files: dict = None,
        batch_inner_trans_enable: bool = False):
    """ 根据完整配置合成完整视频，并保存到指定路径的文件 
    
    Args:
        batch_size: 每批处理的视频数量，None 表示不分批（一次性处理所有）
    """

    print(f"正在合成完整视频...")
    try:
        # 根据硬件加速设置选择编码器
        output_file = os.path.join(video_output_path, f"{username}_FULL_VIDEO.mp4")
        
        if use_hardware_acceleration and acceleration_method and acceleration_method in HARD_RENDER_METHOD:
            encoder_prefix = "h264"
            hardware_suffix = HARD_RENDER_METHOD[acceleration_method]["codec"]
            final_codec = f"{encoder_prefix}_{hardware_suffix}"
            render_mode = f"{acceleration_method} 硬件加速"
            print("=" * 60)
            print(f"使用 {render_mode} 渲染模式")
            print("=" * 60)
        else:
            final_codec = 'libx264'
            render_mode = "CPU 软件编码"
            print("=" * 60)
            print(f"使用 {render_mode} 渲染模式 (balanced 质量)")
            print("=" * 60)
        
        print(f"输出文件: {output_file}")
        print(f"视频比特率: {video_bitrate}")
        print(f"编码器: {final_codec}")
        print("提示：如需更快速度，可以考虑：")
        print("  1. 降低视频分辨率（1280x720 比 1920x1080 快4倍）")
        print("  2. 减少片段数量")
        print("  3. 关闭转场效果")
        if not use_hardware_acceleration:
            print("  4. 启用 GPU 硬件加速（如果支持）")
        print("=" * 60)
        
        # 如果使用分批处理，创建临时目录并生成临时文件
        temp_dir = None
        if batch_size and batch_size > 0 and len(main_configs) > batch_size:
            temp_dir = os.path.join(video_output_path, "temp_batches")
            os.makedirs(temp_dir, exist_ok=True)
            print(f"使用分批处理模式，临时文件将保存到: {temp_dir}")
        
        result = create_full_video(
            game_type=game_type,
            style_config=style_config,
            main_configs=main_configs,
            intro_configs=intro_configs,
            ending_configs=ending_configs,
            resolution=video_res,
            auto_add_transition=video_trans_enable,
            trans_time=video_trans_time,
            full_last_clip=full_last_clip,
            batch_size=batch_size,
            temp_output_dir=temp_dir,
            batch_inner_trans_enable=batch_inner_trans_enable,
            progress_callback=progress_callback,
            fps=video_fps,
            skip_cache_files=skip_cache_files
        )
        
        # 如果返回的是临时文件列表，需要合并这些文件
        if isinstance(result, list) and temp_dir:
            print(f"\n{'='*60}")
            print(f"开始合并 {len(result)} 个批次视频文件...")
            print(f"{'='*60}")
            
            # 处理结尾片段（如果有）
            ending_temp_file = None
            if ending_configs:
                # 检查是否使用缓存的结尾文件
                if skip_cache_files and 'ending' in skip_cache_files and os.path.exists(skip_cache_files['ending']):
                    # 验证缓存文件是否有效
                    is_valid, error_msg = validate_cache_video_file(skip_cache_files['ending'], expected_fps=video_fps)
                    if is_valid:
                        print(f"使用缓存的结尾文件: {skip_cache_files['ending']}")
                        result.append(skip_cache_files['ending'])
                    else:
                        print(f"警告: 缓存的结尾文件无效，将重新生成")
                        print(f"错误信息: {error_msg}")
                        # 继续生成结尾片段
                        print("处理结尾片段...")
                        ending_clips = []
                        for clip_config in ending_configs:
                            clip = create_info_segment(clip_config, style_config, video_res)
                            clip = normalize_audio_volume(clip)
                            ending_clips.append(clip)
                        
                        if ending_clips:
                            # 在分批处理时，结尾片段单独处理，不需要与最后一个主要片段合并
                            if video_trans_enable:
                                ending_video = CompositeVideoClip(ending_clips)
                            else:
                                ending_video = concatenate_videoclips(ending_clips)
                            
                            ending_temp_file = os.path.join(temp_dir, "ending.mp4")
                            ending_video.write_videofile(
                                ending_temp_file,
                                fps=video_fps,  # 使用用户设置的帧率
                                codec='libx264',
                                preset='medium',
                                audio_codec='aac',
                                audio_bitrate='192k',
                                logger=None
                            )
                            ending_video.close()
                            for clip in ending_clips:
                                if hasattr(clip, 'close'):
                                    clip.close()
                            ending_clips = []
                            gc.collect()
                            result.append(ending_temp_file)
                else:
                    print("处理结尾片段...")
                    ending_clips = []
                    for clip_config in ending_configs:
                        clip = create_info_segment(clip_config, style_config, video_res)
                        clip = normalize_audio_volume(clip)
                        ending_clips.append(clip)
                    
                    if ending_clips:
                        # 在分批处理时，结尾片段单独处理，不需要与最后一个主要片段合并
                        if video_trans_enable:
                            ending_video = CompositeVideoClip(ending_clips)
                        else:
                            ending_video = concatenate_videoclips(ending_clips)
                        
                        ending_temp_file = os.path.join(temp_dir, "ending.mp4")
                        ending_video.write_videofile(
                            ending_temp_file,
                            fps=video_fps,  # 使用用户设置的帧率
                            codec='libx264',
                            preset='medium',
                            audio_codec='aac',
                            audio_bitrate='192k',
                            logger=None
                        )
                        ending_video.close()
                        for clip in ending_clips:
                            if hasattr(clip, 'close'):
                                clip.close()
                        ending_clips = []
                        gc.collect()
                        result.append(ending_temp_file)
            
            # 加载所有临时视频文件并合并
            print("加载临时视频文件...")
            if progress_callback:
                progress_callback({
                    'stage': 'loading_temp_files',
                    'progress': 0.75
                })
            
            temp_clips = []
            for idx, temp_file in enumerate(result):
                if os.path.exists(temp_file):
                    clip = VideoFileClip(temp_file)
                    temp_clips.append(clip)
                    print(f"  已加载: {os.path.basename(temp_file)} ({clip.duration:.2f}秒)")
                    if progress_callback:
                        progress_callback({
                            'stage': 'loading_temp_files',
                            'current_file': idx + 1,
                            'total_files': len(result),
                            'progress': 0.75 + (idx + 1) / len(result) * 0.05
                        })
            
            if not temp_clips:
                return {"status": "error", "info": "没有找到有效的临时视频文件"}
            
            print(f"\n合并 {len(temp_clips)} 个视频文件...")
            if progress_callback:
                progress_callback({
                    'stage': 'merging_videos',
                    'progress': 0.80
                })
            
            # 为批次视频之间添加过渡效果
            if video_trans_enable and video_trans_time > 0:
                print(f"为批次视频之间添加过渡效果（{video_trans_time}秒）...")
                final_video = add_transitions_to_clips(temp_clips, video_trans_time, video_res)
                if final_video is None:
                    # 如果过渡效果失败，回退到直接拼接
                    final_video = concatenate_videoclips(temp_clips, method="compose")
            else:
                # 不使用过渡效果，直接拼接
                final_video = concatenate_videoclips(temp_clips, method="compose")
            
            print(f"最终视频时长: {final_video.duration:.2f}秒")
            print("开始渲染最终视频...")
            
            if progress_callback:
                progress_callback({
                    'stage': 'rendering_final',
                    'progress': 0.85
                })
            
            # 构建 write_videofile 参数
            write_params = {
                'fps': video_fps,  # 使用用户设置的帧率
                'threads': 12 if not use_hardware_acceleration else 4,
                'codec': final_codec,
                'bitrate': video_bitrate,
                'audio_codec': 'aac',
                'audio_bitrate': '192k',
                'logger': 'bar'
            }
            # 只有在非硬件加速时才添加 preset 参数
            if not use_hardware_acceleration:
                write_params['preset'] = 'medium'
            
            final_video.write_videofile(output_file, **write_params)
            
            if progress_callback:
                progress_callback({
                    'stage': 'completed',
                    'progress': 1.0
                })
            
            # 关闭所有临时视频
            final_video.close()
            for clip in temp_clips:
                clip.close()
            temp_clips = []
            gc.collect()
            
            # 清理临时文件
            print("清理临时文件...")
            try:
                for temp_file in result:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                print("临时文件已清理")
            except Exception as e:
                print(f"警告：清理临时文件时出错: {e}")
        else:
            # 原有逻辑：直接渲染 VideoClip 对象
            final_video = result
            # 构建 write_videofile 参数
            write_params = {
                'fps': video_fps,  # 使用用户设置的帧率
                'threads': 12 if not use_hardware_acceleration else 4,  # GPU模式使用较少线程
                'codec': final_codec,
                'bitrate': video_bitrate,
                'audio_codec': 'aac',
                'audio_bitrate': '192k',
                'logger': 'bar'
            }
            # 只有在非硬件加速时才添加 preset 参数
            if not use_hardware_acceleration:
                write_params['preset'] = 'medium'
            
            final_video.write_videofile(output_file, **write_params)
            print(f"✓ {render_mode} 渲染完成")
            final_video.close()
        
        return {"status": "success", "info": f"合成完整视频成功"}
    except Exception as e:
        print(f"Error: 合成完整视频时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成完整视频时发生异常: {traceback.print_exc()}"}


def combine_from_cached_batches(temp_batches_dir, output_file, 
                                 use_hardware_acceleration=False, 
                                 acceleration_method=None,
                                 video_bitrate="4000k",
                                 progress_callback=None,
                                 fps=60,
                                 trans_enable=True,
                                 trans_time=1.0):
    """
    从缓存的批次文件直接合成最终视频
    
    Args:
        temp_batches_dir: 临时批次文件目录路径
        output_file: 输出文件路径
        use_hardware_acceleration: 是否使用硬件加速
        acceleration_method: 硬件加速方法
        video_bitrate: 视频比特率
        progress_callback: 进度回调函数
    """
    print(f"从缓存文件合成最终视频...")
    print(f"缓存目录: {temp_batches_dir}")
    print(f"输出文件: {output_file}")
    
    if not os.path.exists(temp_batches_dir):
        return {"status": "error", "info": f"缓存目录不存在: {temp_batches_dir}"}
    
    # 查找所有批次文件
    batch_files = []
    intro_file = None
    ending_file = None
    
    for file in os.listdir(temp_batches_dir):
        if file.startswith("batch_") and file.endswith(".mp4"):
            batch_files.append(file)
        elif file == "intro.mp4":
            intro_file = file
        elif file == "ending.mp4":
            ending_file = file
    
    # 按文件名排序批次文件
    batch_files.sort()
    
    if not batch_files:
        return {"status": "error", "info": "没有找到批次文件"}
    
    print(f"找到 {len(batch_files)} 个批次文件")
    if intro_file:
        print(f"找到开场文件: {intro_file}")
    if ending_file:
        print(f"找到结尾文件: {ending_file}")
    
    # 构建文件列表（按顺序：intro -> batches -> ending）
    video_files = []
    if intro_file:
        video_files.append(os.path.join(temp_batches_dir, intro_file))
    for batch_file in batch_files:
        video_files.append(os.path.join(temp_batches_dir, batch_file))
    if ending_file:
        video_files.append(os.path.join(temp_batches_dir, ending_file))
    
    # 加载所有视频文件
    print("加载视频文件...")
    if progress_callback:
        progress_callback({
            'stage': 'loading_cached_files',
            'progress': 0.1
        })
    
    temp_clips = []
    for idx, video_file in enumerate(video_files):
        if os.path.exists(video_file):
            clip = VideoFileClip(video_file)
            temp_clips.append(clip)
            print(f"  已加载: {os.path.basename(video_file)} ({clip.duration:.2f}秒)")
            if progress_callback:
                progress_callback({
                    'stage': 'loading_cached_files',
                    'current_file': idx + 1,
                    'total_files': len(video_files),
                    'progress': 0.1 + (idx + 1) / len(video_files) * 0.3
                })
    
    if not temp_clips:
        return {"status": "error", "info": "没有找到有效的视频文件"}
    
    # 合并视频
    print(f"\n合并 {len(temp_clips)} 个视频文件...")
    if progress_callback:
        progress_callback({
            'stage': 'merging_videos',
            'progress': 0.5
        })
    
    # 为批次视频之间添加过渡效果
    # 需要从第一个视频片段获取分辨率
    resolution = None
    if temp_clips:
        resolution = (temp_clips[0].w, temp_clips[0].h)
    
    if trans_enable and trans_time > 0:
        print(f"为批次视频之间添加过渡效果（{trans_time}秒）...")
        final_video = add_transitions_to_clips(temp_clips, trans_time, resolution)
        if final_video is None:
            # 如果过渡效果失败，回退到直接拼接
            final_video = concatenate_videoclips(temp_clips, method="compose")
    else:
        # 不使用过渡效果，直接拼接
        final_video = concatenate_videoclips(temp_clips, method="compose")
    
    print(f"最终视频时长: {final_video.duration:.2f}秒")
    print("开始渲染最终视频...")
    
    # 根据硬件加速设置选择编码器
    if use_hardware_acceleration and acceleration_method and acceleration_method in HARD_RENDER_METHOD:
        encoder_prefix = "h264"
        hardware_suffix = HARD_RENDER_METHOD[acceleration_method]["codec"]
        final_codec = f"{encoder_prefix}_{hardware_suffix}"
        render_mode = f"{acceleration_method} 硬件加速"
    else:
        final_codec = 'libx264'
        render_mode = "CPU 软件编码"
    
    print(f"使用 {render_mode} 渲染模式")
    
    if progress_callback:
        progress_callback({
            'stage': 'rendering_final',
            'progress': 0.6
        })
    
    # 构建 write_videofile 参数
    write_params = {
        'fps': fps,  # 使用用户设置的帧率
        'threads': 12 if not use_hardware_acceleration else 4,
        'codec': final_codec,
        'bitrate': video_bitrate,
        'audio_codec': 'aac',
        'audio_bitrate': '192k',
        'logger': 'bar'
    }
    # 只有在非硬件加速时才添加 preset 参数（硬件加速编码器不支持 preset）
    if not use_hardware_acceleration:
        write_params['preset'] = 'medium'
    # 注意：硬件加速编码器（如 h264_amf, h264_nvenc 等）不支持 preset 参数
    
    try:
        final_video.write_videofile(output_file, **write_params)
    except Exception as e:
        # 如果硬件加速失败，尝试使用软件编码
        if use_hardware_acceleration:
            print(f"硬件加速编码失败，尝试使用软件编码: {e}")
            write_params['codec'] = 'libx264'
            write_params['preset'] = 'medium'
            final_video.write_videofile(output_file, **write_params)
        else:
            raise
    
    # 关闭所有视频
    final_video.close()
    for clip in temp_clips:
        clip.close()
    temp_clips = []
    gc.collect()
    
    if progress_callback:
        progress_callback({
            'stage': 'completed',
            'progress': 1.0
        })
    
    print(f"✓ {render_mode} 渲染完成")
    return {"status": "success", "info": f"从缓存文件合成完整视频成功"}


def combine_full_video_direct(video_clip_path):
    """ 
        拼接指定文件夹下的所有视频片段，生成最终视频文件
        片段需要具有正确的命名格式(0_xxx, 1_xxx, ...)以确保正确排序 
    """
    print("[Info] --------------------开始拼接视频-------------------")
    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！")

    # 创建临时目录存放 ts 文件
    temp_dir = os.path.join(video_clip_path, "temp_ts")
    os.makedirs(temp_dir, exist_ok=True)
    
    current_dir = os.getcwd()
    try:
        # 1. 创建MP4文件列表
        mp4_list_file = os.path.join(video_clip_path, "mp4_files.txt")
        with open(mp4_list_file, 'w', encoding='utf-8') as f:
            for file in sorted_files:
                # 使用正斜杠替换反斜杠，并使用相对路径
                full_path = os.path.join(video_clip_path, file).replace('\\', '/')
                f.write(f"file '{full_path}'\n")

        # 2. 创建TS文件列表并转换视频
        ts_list_file = os.path.join(video_clip_path, "ts_files.txt")
        with open(ts_list_file, 'w', encoding='utf-8') as f:
            for i, file in enumerate(sorted_files):
                ts_name = f"{i:04d}.ts"
                ts_path = os.path.join(temp_dir, ts_name)
                
                # 转换MP4为TS
                cmd = [
                    'ffmpeg', '-y',
                    '-i', os.path.join(video_clip_path, file),
                    '-c', 'copy',
                    '-bsf:v', 'h264_mp4toannexb',
                    '-f', 'mpegts',
                    ts_path
                ]
                subprocess.run(cmd, check=True)
                
                # 写入TS文件相对路径，使用正斜杠
                relative_ts_path = os.path.join('temp_ts', ts_name).replace('\\', '/')
                f.write(f"file '{relative_ts_path}'\n")

        # 3. 拼接TS文件并输出为MP4
        output_path = os.path.join(video_clip_path, "final_output.mp4")
        
        # 切换到视频目录执行拼接命令
        os.chdir(video_clip_path)
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', 'ts_files.txt',  # 使用相对路径
            '-c', 'copy',
            'final_output.mp4'  # 使用相对路径
        ]
        
        subprocess.run(cmd, check=True)
        print("视频拼接完成")
        
    finally:
        try:
            os.chdir(current_dir)  # 恢复原始工作目录
        except Exception:
            pass
        # 清理临时文件
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    return output_path


def combine_full_video_ffmpeg_concat_gl(video_clip_path, trans_name="fade", trans_time=1):
    """ 
        使用ffmpeg的concat_gl脚本，以指定的转场效果拼接指定文件夹下的所有视频片段，生成最终视频文件
        片段需要具有正确的命名格式(0_xxx, 1_xxx, ...)以确保正确排序
    """
    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！")
    
    output_path = os.path.join(video_clip_path, "final_output.mp4")
    
    # 创建MP4文件列表
    mp4_list_file = os.path.join(video_clip_path, "mp4_files.txt")
    with open(mp4_list_file, 'w', encoding='utf-8') as f:
        for file in sorted_files:
            # 使用正斜杠替换反斜杠，并使用相对路径
            full_path = os.path.join(video_clip_path, file).replace('\\', '/')
            f.write(f"file '{full_path}'\n")


    # 使用nodejs脚本拼接视频
    node_script_path = os.path.join(os.path.dirname(__file__), "external_scripts", "concat_videos_ffmpeg.js")

    cmd = f'node {node_script_path} -o {output_path} -v {mp4_list_file} -t {trans_name} -d {int(trans_time * 1000)}'
    print(f"执行命令: {cmd}")

    os.system(cmd)

    return output_path

