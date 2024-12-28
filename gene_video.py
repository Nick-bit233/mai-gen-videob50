import os
import numpy as np
import subprocess
from PIL import Image, ImageFilter
from moviepy import VideoFileClip, ImageClip, TextClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
from moviepy import vfx, afx

def get_splited_text(text, text_max_bytes=60):
    """
    将说明文本按照最大字节数限制切割成多行
    
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


def blur_image(image_path, blur_radius=5):
    """
    对图片进行高斯模糊处理
    
    Args:
        image_path (str): 图片路径
        blur_radius (int): 模糊半径，默认为10
        
    Returns:
        numpy.ndarray: 模糊处理后的图片数组
    """
    try:
        pil_image = Image.open(image_path)
        blurred_image = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        # 将模糊后的图片转换为 numpy 数组
        return np.array(blurred_image)
    except Exception as e:
        print(f"Warning: 图片模糊处理失败 - {str(e)}")
        return np.array(Image.open(image_path))


def create_blank_image(width, height, color=(0, 0, 0, 0)):
    """
    创建一个透明的图片
    """
    # 创建一个RGBA模式的空白图片
    image = Image.new('RGBA', (width, height), color)
    # 转换为numpy数组，moviepy需要这种格式
    return np.array(image)


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


def create_info_segment(clip_config, resolution, font_path, text_size=44, inline_max_len=52):
    print(f"正在合成视频片段: {clip_config['id']}")
    bg_image = ImageClip("./images/IntroBase.png").with_duration(clip_config['duration'])
    bg_image = bg_image.with_effects([vfx.Resize(width=resolution[0])])

    bg_video = VideoFileClip("./images/BgClips/bg.mp4")
    bg_video = bg_video.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                      vfx.MultiplyColor(0.5),
                                      vfx.Resize(width=resolution[0])])

    # 创建文字
    text_list = get_splited_text(clip_config['text'], text_max_bytes=inline_max_len)
    txt_clip = TextClip(font=font_path, text="\n".join(text_list),
                        method = "label",
                        font_size=text_size,
                        margin=(20, 20),
                        interline=6.5,
                        vertical_align="top",
                        color="white",
                        duration=clip_config['duration'])
    
    addtional_text = "【本视频由mai-genVb50视频生成器生成】"
    addtional_txt_clip = TextClip(font=font_path, text=addtional_text,
                        method = "label",
                        font_size=18,
                        vertical_align="bottom",
                        color="white",
                        duration=clip_config['duration']
    )
    
    text_pos = (int(0.16 * resolution[0]), int(0.18 * resolution[1]))
    addtional_text_pos = (int(0.2 * resolution[0]), int(0.88 * resolution[1]))
    composite_clip = CompositeVideoClip([
            bg_video.with_position((0, 0)),
            bg_image.with_position((0, 0)),
            txt_clip.with_position((text_pos[0], text_pos[1])),
            addtional_txt_clip.with_position((addtional_text_pos[0], addtional_text_pos[1]))
        ],
        size=resolution,
        use_bgclip=True
    )

    # 为整个composite_clip添加bgm
    bg_audio = AudioFileClip("./images/Audioes/intro_bgm.mp3")
    bg_audio = bg_audio.with_effects([afx.AudioLoop(duration=clip_config['duration'])])
    composite_clip = composite_clip.with_audio(bg_audio)

    return composite_clip.with_duration(clip_config['duration'])


def create_video_segment(clip_config, resolution, font_path, text_size=28, inline_max_len=48):
    print(f"正在合成视频片段: {clip_config['id']}")
    
    # 默认的底部背景
    default_bg_path = "./images/VideoUnderBase.png"

    bg_video = VideoFileClip("./images/BgClips/black_bg.mp4")
    bg_video = bg_video.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                      vfx.Resize(width=resolution[0])])
    
    # 检查背景图片是否存在
    if 'main_image' in clip_config and os.path.exists(clip_config['main_image']):
        main_image = ImageClip(clip_config['main_image']).with_duration(clip_config['duration'])
        main_image = main_image.with_effects([vfx.Resize(width=resolution[0])])
    else:
        print(f"Video Generator Warning: {clip_config['id']} 没有对应的成绩图, 请检查成绩图资源是否已生成")
        main_image = ImageClip(create_blank_image(resolution[0], resolution[1])).with_duration(clip_config['duration'])

    # 读取song_id，并获取预览图jacket
    __musicid = str(clip_config['song_id'])[-4:].zfill(4)
    __jacket_path = f"./images/Jackets/UI_Jacket_00{__musicid}.png"
    if os.path.exists(__jacket_path):
        # 高斯模糊处理图片
        jacket_array = blur_image(__jacket_path, blur_radius=5)
        # 创建 ImageClip
        jacket_image = ImageClip(jacket_array).with_duration(clip_config['duration'])
        # 将jacket图片按视频分辨率宽度等比例缩放，以填充整个背景
        jacket_image = jacket_image.with_effects([vfx.Resize(width=resolution[0])])
    else:
        print(f"Video Generator Warning: {clip_config['id']} 没有找到对应的封面图, 将使用默认背景")
        jacket_image = ImageClip(default_bg_path).with_duration(clip_config['duration'])

    jacket_image = jacket_image.with_effects([vfx.MultiplyColor(0.65)])

    # 检查视频是否存在
    if 'video' in clip_config and os.path.exists(clip_config['video']):
        video_clip = VideoFileClip(clip_config['video'])
        
        # 添加调试信息
        print(f"Start time: {clip_config['start']}, Clip duration: {video_clip.duration}, End time: {clip_config['end']}")
        
        # 检查 start_time 和 end_time 是否超出 clip 的持续时间
        if clip_config['start'] < 0 or clip_config['start'] >= video_clip.duration:
            raise ValueError(f"片段开始时间 {clip_config['start']} 超出视频{clip_config['video']}的长度. 请检查该片段的时间配置.")
        
        if clip_config['end'] <= clip_config['start'] or clip_config['end'] > video_clip.duration:
            raise ValueError(f"片段结束时间 {clip_config['end']} 超出视频{clip_config['video']}的长度. 请检查该片段的时间配置.")
        
        video_clip = video_clip.subclipped(start_time=clip_config['start'],
                                            end_time=clip_config['end'])
        # 等比例缩放，在高为1080像素的情况下，谱面确认的高度应该是540像素，因此比例为0.5
        video_clip = video_clip.with_effects([vfx.Resize(height=0.5 * resolution[1])])
        
        # 裁剪成正方形
        video_height = video_clip.h
        video_width = video_clip.w
        x_center = video_width / 2
        crop_size = video_height
        x1 = x_center - (crop_size / 2)
        x2 = x_center + (crop_size / 2)
        video_clip = video_clip.cropped(x1=x1, y1=0, x2=x2, y2=video_height)
    else:
        print(f"Video Generator Warning:{clip_config['id']} 没有对应的视频, 请检查本地资源")
        # 创建一个透明的视频片段
        blank_frame = create_blank_image(
            int(540/1080 * resolution[1]),  # 使用相同的尺寸计算
            int(540/1080 * resolution[1])   
        )
        video_clip = ImageClip(blank_frame).with_duration(clip_config['duration'])

    # 计算位置
    video_pos = (int(0.092 * resolution[0]), int(0.328 * resolution[1]))
    text_pos = (int(0.54 * resolution[0]), int(0.54 * resolution[1]))

    # 创建文字
    text_list = get_splited_text(clip_config['text'], text_max_bytes=inline_max_len)
    txt_clip = TextClip(font=font_path, text="\n".join(text_list),
                        method = "label",
                        # size=(text_max_width, text_max_height), 
                        font_size=text_size,
                        margin=(20, 20),
                        interline=6.5,
                        vertical_align="top",
                        color="white",
                        duration=clip_config['duration'])

    # 视频叠放顺序，从下往上：背景底图，谱面预览，图片（带有透明通道），文字
    composite_clip = CompositeVideoClip([
            bg_video.with_position((0, 0)),  # 使用一个pure black的视频作为背景（此背景用于避免透明素材的通道的bug问题）
            jacket_image.with_position((0, -0.5), relative=True),
            video_clip.with_position((video_pos[0], video_pos[1])),
            main_image.with_position((0, 0)),
            txt_clip.with_position((text_pos[0], text_pos[1]))
        ],
        size=resolution,
        use_bgclip=True  # 必须设置为true，否则其上透明素材的通道会失效（疑似为moviepy2.0的bug）
    )

    return composite_clip.with_duration(clip_config['duration'])


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


def create_full_video(resources, resolution, font_path, auto_add_transition=True, trans_time=1, full_last_clip=False):
    clips = []
    ending_clips = []

    # 处理开场片段
    if 'intro' in resources:
        for clip_config in resources['intro']:
            clip = create_info_segment(clip_config, resolution, font_path)
            clip = normalize_audio_volume(clip)
            add_clip_with_transition(clips, clip, 
                                    set_start=True, 
                                    trans_time=trans_time)

    combined_start_time = 0
    if not 'main' in resources:
        print("Error: 没有找到主视频片段的合成！请检查配置文件！")
        return
    
    # 处理主要视频片段
    for clip_config in resources['main']:
        # 判断是否是最后一个片段
        if clip_config['id'] == resources['main'][-1]['id'] and full_last_clip:
            start_time = clip_config['start']
            # 获取原始视频的长度（不是配置文件中配置的duration）
            full_clip_duration = VideoFileClip(clip_config['video']).duration - 5
            # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
            clip_config['duration'] = full_clip_duration - start_time
            clip_config['end'] = full_clip_duration

            clip = create_video_segment(clip_config, resolution, font_path)  
            clip = normalize_audio_volume(clip)

            combined_start_time = clips[-1].end - trans_time
            ending_clips.append(clip)     
        else:
            clip = create_video_segment(clip_config, resolution, font_path)  
            clip = normalize_audio_volume(clip)

            add_clip_with_transition(clips, clip, 
                                    set_start=True, 
                                    trans_time=trans_time)

    # 处理结尾片段
    if 'ending' in resources:
        for clip_config in resources['ending']:
            clip = create_info_segment(clip_config, resolution, font_path)
            clip = normalize_audio_volume(clip)
            if full_last_clip:
                ending_clips.append(clip)
            else:
                add_clip_with_transition(clips, clip, 
                                        set_start=True, 
                                        trans_time=trans_time)

    if full_last_clip and len(ending_clips) > 0:
        clips.append(get_combined_ending_clip(ending_clips, combined_start_time, trans_time))

    if auto_add_transition:
        return CompositeVideoClip(clips)
    else:
        return concatenate_videoclips(clips)  # 该方法不会添加转场效果，即使设置了trans_time


def sort_video_files(files):
    """
    对视频文件名进行排序，
    排序规则：NewBest_15到NewBest_1，然后是PastBest_35到PastBest_1
    """
    def get_sort_key(filename):
        # 移除文件扩展名
        name = os.path.splitext(filename)[0]
        try:
            if name.startswith('NewBest_'):
                number = int(name.replace('NewBest_', ''))
                if 1 <= number <= 15:  # 只处理1-15的编号
                    return (1, number)
            elif name.startswith('PastBest_'):
                number = int(name.replace('PastBest_', ''))
                if 1 <= number <= 35:  # 只处理1-35的编号
                    return (0, number)
        except ValueError:
            print(f"Error: 无法解析视频文件名: {filename}")
            return None
        return None  
    
    # 过滤并排序文件
    valid_files = []
    for file in files:
        sort_key = get_sort_key(file)
        if sort_key is not None:  # 只保留有效的文件
            valid_files.append((file, sort_key))
    
    # 根据排序键排序并返回文件名列表
    sorted_files = sorted(valid_files, key=lambda x: x[1], reverse=True)
    return [f[0] for f in sorted_files]  # 只返回文件名列表


def combine_full_video_from_existing_clips(video_clip_path, resolution, trans_time=1):
    clips = []

    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    print(f"Sorted files: {sorted_files}")

    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！(NewBest_1-15 or PastBest_1-35)")

    for file in sorted_files:
        clip = VideoFileClip(os.path.join(video_clip_path, file))
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


def gene_pure_black_video(duration, resolution):
    """
    生成一个纯黑色的视频
    """
    black_frame = create_blank_image(resolution[0], resolution[1], color=(0, 0, 0, 1))
    clip = ImageClip(black_frame).with_duration(duration)
    clip.write_videofile("./videos/black_bg.mp4", fps=30)


def get_combined_ending_clip(ending_clips, combined_start_time, trans_time):
    """合并B1片段与结尾，使用统一音频"""

    if len(ending_clips) < 2:
        print("Warning: 没有足够的结尾片段，将只保留B1片段")
        return ending_clips[0].with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])
    
    # 获得b1片段
    b1_clip = ending_clips[0]
    # 获得结尾片段组
    ending_comment_clips = ending_clips[1:]

    # 取出b1片段的音频
    combined_clip_audio = b1_clip.audio
    b1_clip = b1_clip.without_audio()

    # 计算需要从b1片段结尾截取的时间
    ending_full_duration = sum([clip.duration for clip in ending_comment_clips])

    if ending_full_duration > b1_clip.duration:
        print(f"Warning: B1片段的长度不足，FULL_LAST_CLIP选项将无效化！")
        return CompositeVideoClip(ending_clips).with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])

    # 将ending_clip的时间提前到b1片段的结尾，并裁剪b1片段
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

    # 将b1片段与ending_clip合并
    combined_clip = CompositeVideoClip(full_list)
    print(f"Video Generator: b1_clip_audio_len: {combined_clip_audio.duration}, combined_clip_len: {combined_clip.duration}")
    # 设置combined_clip的音频为原b1片段的音频（二者长度应该相同）
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


def combine_full_video_pure_ffmpeg(video_clip_path, resolution, trans_time=1):
    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    # TODO:处理intro和ending片段
    
    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！")

    # 准备ffmpeg复杂过滤器命令
    filter_complex = []
    inputs = []
    
    # 为每个视频文件添加输入
    for i, file in enumerate(sorted_files):
        inputs.extend(['-i', os.path.join(video_clip_path, file)])
    
    # 构建过滤器复杂命令
    for i in range(len(sorted_files) - 1):
        if i == 0:
            # 第一个转场
            filter_complex.append(f'[{i}:v][{i+1}:v]xfade=transition=fade:duration={trans_time}:offset={trans_time}[v{i}];')
            filter_complex.append(f'[{i}:a][{i+1}:a]acrossfade=d={trans_time}[a{i}];')
        else:
            # 后续转场
            filter_complex.append(f'[v{i-1}][{i+1}:v]xfade=transition=fade:duration={trans_time}:offset={trans_time}[v{i}];')
            filter_complex.append(f'[a{i-1}][{i+1}:a]acrossfade=d={trans_time}[a{i}];')

    # 构建完整的ffmpeg命令
    output_path = os.path.join(video_clip_path, "final_output.mp4")
    ffmpeg_cmd = ['ffmpeg', '-y']
    ffmpeg_cmd.extend(inputs)
    ffmpeg_cmd.extend([
        '-filter_complex',
        ''.join(filter_complex) + f'[v{len(sorted_files)-2}][a{len(sorted_files)-2}]',
        '-map', f'[v{len(sorted_files)-2}]',
        '-map', f'[a{len(sorted_files)-2}]',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        output_path
    ])
    
    # 执行ffmpeg命令
    try:
        subprocess.run(ffmpeg_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg命令执行失败: {e}")
        print(f"完整命令: {' '.join(ffmpeg_cmd)}")
        raise

    return output_path