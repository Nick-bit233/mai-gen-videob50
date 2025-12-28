import os
import numpy as np
import subprocess
import traceback
from PIL import Image, ImageFilter
from moviepy import VideoFileClip, ImageClip, TextClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
from moviepy import vfx, afx
from utils.VisionUtils import find_circle_center, draw_center_marker
from utils.PageUtils import remove_invalid_chars
from typing import Union, Tuple


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
        video_clip = VideoFileClip(clip_config['video'])
        # 添加调试信息
        print(f"Start time: {clip_config['start']}, Clip duration: {video_clip.duration}, End time: {clip_config['end']}")
        # 等比例缩放
        h_resize_ratio = 0.5 if game_type == "maimai" else 0.667  # 540/1080 for maimai, 720/1080 for chunithm
        video_clip = video_clip.with_effects([vfx.Resize(height=h_resize_ratio * resolution[1])])

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

        if game_type == "maimai":
            visual_center = None
            if auto_center_align:
                # 从未剪裁的视频中提取中间一帧用于分析
                analysis_frame = video_clip.get_frame(t=(video_clip.duration / 2))
                # 检测传入谱面确认视频的视觉中心，此操作的目的是为了识别原始视频存在中心偏移的情况
                visual_center = find_circle_center(analysis_frame, debug=False, name=clip_config['clip_title_name'])
    
            # 改进的裁剪逻辑：避免过度裁剪
            # 如果视频不是正方形，优先保留更多内容
            if abs(video_height - video_width) > 2:  # 允许2像素的误差，避免浮点数精度问题
                # 确定裁剪中心（优先使用视觉中心，未识别到时使用几何中心）
                center_x = visual_center[0] if visual_center else video_width / 2
                
                # 根据宽高比决定裁剪策略
                if video_width > video_height:
                    # 视频更宽：裁剪左右两侧，保留中间部分
                    # 计算方形宽度范围（以高度为基准）
                    x1 = center_x - (video_height / 2)
                    x2 = center_x + (video_height / 2)
                    
                    # 处理边界：如果裁剪框超出边界，调整到边界
                    if x1 < 0:
                        x1 = 0
                        x2 = video_height
                    elif x2 > video_width:
                        x2 = video_width
                        x1 = video_width - video_height
                    
                    # 裁剪成正方形（保留完整高度）
                    video_clip = video_clip.cropped(x1=x1, y1=0, x2=x2, y2=video_height)
                else:
                    # 视频更高：裁剪上下两侧，保留中间部分
                    # 计算方形高度范围（以宽度为基准）
                    center_y = video_height / 2
                    y1 = center_y - (video_width / 2)
                    y2 = center_y + (video_width / 2)
                    
                    # 处理边界
                    if y1 < 0:
                        y1 = 0
                        y2 = video_width
                    elif y2 > video_height:
                        y2 = video_height
                        y1 = video_height - video_width
                    
                    # 裁剪成正方形（保留完整宽度）
                    video_clip = video_clip.cropped(x1=0, y1=y1, x2=video_width, y2=y2)
        elif game_type == "chunithm":
            # 检查视频宽高比，若非近似16:9则使用填充或裁剪，避免拉伸变形
            target_ar = 16.0 / 9.0
            # 使用当前裁剪/缩放后的尺寸判断
            current_ar = video_width / video_height if video_height > 0 else target_ar
            tolerance = 0.03  # 允许约3%的误差视为近似16:9
            if abs(current_ar - target_ar) / target_ar > tolerance:
                print(f"Video Generator Info: chunithm 视频宽高比 {current_ar:.3f} 与 16:9 差异超出容差，执行适配处理")
                
                # 改进策略：使用填充或裁剪，而不是拉伸变形
                if current_ar > target_ar:
                    # 视频更宽：裁剪左右两侧，保留中间部分
                    target_w = int(round(video_height * target_ar))
                    crop_x1 = int(round((video_width - target_w) / 2))
                    crop_x2 = crop_x1 + target_w
                    video_clip = video_clip.cropped(x1=crop_x1, y1=0, x2=crop_x2, y2=video_height)
                    print(f"  裁剪左右两侧，从宽度 {video_width} 裁剪到 {target_w}")
                else:
                    # 视频更高：裁剪上下两侧，保留中间部分
                    target_h = int(round(video_width / target_ar))
                    crop_y1 = int(round((video_height - target_h) / 2))
                    crop_y2 = crop_y1 + target_h
                    video_clip = video_clip.cropped(x1=0, y1=crop_y1, x2=video_width, y2=crop_y2)
                    print(f"  裁剪上下两侧，从高度 {video_height} 裁剪到 {target_h}")
                
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
    composite_clip = CompositeVideoClip([
            black_clip.with_position((0, 0)),  # 使用一个pure black的视频作为背景（此背景用于避免透明素材的通道的bug问题）
            bg_clip.with_position((0, 0)),  # 背景图片或视频
            video_clip.with_position((video_pos[0], video_pos[1])),  # 谱面确认视频
            main_image_clip.with_position((0, 0)),  # 成绩图片
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
    
    frame = preview_clip.get_frame(t=1)
    pil_img = Image.fromarray(frame.astype("uint8"))
    return pil_img



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
                      auto_add_transition=True, trans_time=1, full_last_clip=False):
    """ 创建完整视频的 Moviepy Clip，包含开场、主要视频片段和结尾片段 """
    clips = []
    ending_clips = []

    # 处理开场片段
    if intro_configs:
        print(f"处理开场片段，共 {len(intro_configs)} 个")
        for idx, clip_config in enumerate(intro_configs):
            print(f"开场片段 {idx + 1}: 配置键 = {list(clip_config.keys())}")
            clip = create_info_segment(clip_config, style_config, resolution)
            clip = normalize_audio_volume(clip)
            add_clip_with_transition(clips, clip, 
                                    set_start=True, 
                                    trans_time=trans_time)

    combined_start_time = 0

    # 处理主要视频片段
    for clip_config in main_configs:
        # 判断是否是最后一个片段
        if main_configs.index(clip_config) == len(main_configs) - 1 and full_last_clip:
            start_time = clip_config['start']
            # 获取原始视频的长度（不是配置文件中配置的duration）
            full_clip_duration = VideoFileClip(clip_config['video']).duration - 5
            # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
            clip_config['duration'] = full_clip_duration - start_time
            clip_config['end'] = full_clip_duration

            clip = create_video_segment(game_type, clip_config, style_config, resolution)  
            clip = normalize_audio_volume(clip)

            combined_start_time = clips[-1].end - trans_time
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
                           auto_add_transition=True, trans_time=1, force_render=False):
    """ 渲染所有视频片段，并按照clip_title_name输出到指定路径文件 """
    vfile_prefix = 0

    def modify_and_rend_clip(clip, config, prefix, auto_add_transition, trans_time, override_clip_name=None):
        if override_clip_name:
            clip_title_name = override_clip_name
        else:
            clip_title_name = config.get('clip_title_name', "clip")
        clip_title_name = remove_invalid_chars(clip_title_name)  # clip_title_name作为输出文件名的一部分，需要进行清洗，去除不合法字符
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
        clip.write_videofile(output_file, fps=30, threads=4, preset='ultrafast', bitrate=video_bitrate)
        clip.close()
        # 强制垃圾回收
        del clip


    if intro_configs:
        for clip_config in intro_configs:
            clip = create_info_segment(clip_config, style_config, video_res)
            modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time, override_clip_name="INTRO")
            vfile_prefix += 1

    for clip_config in main_configs:
        clip = create_video_segment(game_type, clip_config, style_config, video_res)
        modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time)

        vfile_prefix += 1

    if ending_configs:
        for clip_config in ending_configs:
            clip = create_info_segment(clip_config, style_config, video_res)
            modify_and_rend_clip(clip, clip_config, vfile_prefix, auto_add_transition, trans_time, override_clip_name="ENDING")
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
        video_trans_enable: bool = True, video_trans_time: float = 1.0, full_last_clip: bool = False):
    """ 根据完整配置合成完整视频，并保存到指定路径的文件 """

    print(f"正在合成完整视频...")
    try:
        final_video = create_full_video(
            game_type=game_type,
            style_config=style_config,
            main_configs=main_configs,
            intro_configs=intro_configs,
            ending_configs=ending_configs,
            resolution=video_res,
            auto_add_transition=video_trans_enable,
            trans_time=video_trans_time,
            full_last_clip=full_last_clip
        )
        # 使用 CPU 渲染，质量设为 balanced (medium preset)
        output_file = os.path.join(video_output_path, f"{username}_FULL_VIDEO.mp4")
        
        print("=" * 60)
        print("使用 CPU 渲染模式 (balanced 质量)")
        print("=" * 60)
        print(f"输出文件: {output_file}")
        print(f"视频比特率: {video_bitrate}")
        print("提示：如需更快速度，可以考虑：")
        print("  1. 降低视频分辨率（1280x720 比 1920x1080 快4倍）")
        print("  2. 减少片段数量")
        print("  3. 关闭转场效果")
        print("=" * 60)
        
        final_video.write_videofile(
            output_file, 
            fps=30,
            threads=12,  # CPU模式使用多线程
            codec='libx264',
            preset='medium',  # balanced 质量：medium preset
            bitrate=video_bitrate,
            audio_codec='aac',
            audio_bitrate='192k',
            logger='bar'
        )
        print("✓ CPU 渲染完成")
        final_video.close()
        return {"status": "success", "info": f"合成完整视频成功"}
    except Exception as e:
        print(f"Error: 合成完整视频时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成完整视频时发生异常: {traceback.print_exc()}"}


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
        current_dir = os.getcwd()
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
        os.chdir(current_dir)  # 恢复原始工作目录
        print("视频拼接完成")
        
    finally:
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

