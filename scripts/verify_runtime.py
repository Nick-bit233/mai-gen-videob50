"""Offline acceptance using real assets, AV1 decoding, Taichi and FFmpeg.

Run each GPU backend in a fresh process. All generated files stay in --output.
"""
import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(command):
    return subprocess.run([str(arg) for arg in command], capture_output=True,
                          text=True, check=True, timeout=120)


def verify_images(output):
    from PIL import Image, ImageChops
    from utils.ImageUtils import MaiImageGenerater, ChuniImageGenerater
    from utils.themes import DEFAULT_STYLES
    records = [
        ('maimai', MaiImageGenerater(DEFAULT_STYLES['maimai'][1]),
         dict(title='Runtime test', level_index=3, type=1, ds=13.7,
              dxScore=2700, max_dx_score=3000, achievements='100.5000', fc='ap', fs='fs', ra=300)),
        ('chunithm', ChuniImageGenerater(DEFAULT_STYLES['chunithm'][0]),
         dict(title='Runtime test', artist='Test artist', level_index=3,
              ds_cur=14.5, ds_next=14.6, score=1009000, ra=16.5, combo_type='aj', chain_type='fc')),
    ]
    results = {}
    for game, generator, record in records:
        record['jacket'] = Image.new('RGBA', (400, 400), (100, 150, 200, 255))
        empty = generator.GenerateOneAchievement(dict(record, play_count=0))
        counted = generator.GenerateOneAchievement(dict(record, play_count=5))
        assert empty is not None and counted is not None, f'{game}: failed to generate image'
        # Compare RGB; transparent alpha alone must not hide changed RGB pixels.
        assert ImageChops.difference(empty.convert('RGB'), counted.convert('RGB')).getbbox(), f'{game}: play count missing'
        counted.save(output / f'{game}-play-count.png')
        results[game] = list(counted.size)
        empty.close()
        counted.close()
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--media', type=Path, help='Optional directory containing av1.mp4 and h264.mp4')
    ap.add_argument('--backend', choices=['auto', 'cuda', 'vulkan', 'cpu'], default='auto')
    ap.add_argument('--ffmpeg', type=Path)
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--force-hw-failure', action='store_true', help='On a host without NVENC, verify the original software fallback')
    args = ap.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    if args.ffmpeg:
        ffmpeg = args.ffmpeg.resolve()
        os.environ['PATH'] = str(ffmpeg.parent) + os.pathsep + os.environ.get('PATH', '')
        os.environ['FFMPEG_BINARY'] = str(ffmpeg)
        os.environ['IMAGEIO_FFMPEG_EXE'] = str(ffmpeg)
    else:
        ffmpeg = 'ffmpeg'
    import numpy as np
    from PIL import Image
    from utils.AccelRenderer import get_ffmpeg_binary, VideoFrameReader, render_info_segment_accel
    from utils.VideoUtils import render_complete_full_video, combine_full_video_xfade_islands
    from utils.themes import DEFAULT_STYLES
    from utils.TaichiAccel import get_backend_name
    ffprobe = get_ffmpeg_binary('ffprobe')
    report = {'packages': {name: importlib.metadata.version(name) for name in
                          ['taichi', 'opencv-python', 'numpy', 'moviepy', 'streamlit']}}
    report['images'] = verify_images(output)
    media = args.media.resolve() if args.media else output / 'media'
    media.mkdir(exist_ok=True)
    if not args.media:
        for name, codec, extra in [('h264', 'libx264', ['-preset', 'ultrafast']),
                                  ('av1', 'libaom-av1', ['-cpu-used', '8', '-crf', '35'])]:
            run([ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '5',
                 '-threads', '2', '-c:v', codec, *extra, '-pix_fmt', 'yuv420p', '-c:a', 'aac', media / f'{name}.mp4'])
    report['decode'] = {}
    for codec in ['h264', 'av1']:
        reader = VideoFrameReader(str(media / f'{codec}.mp4'))
        try:
            for t in [0, 0, 0.5, 0.5, 2.0, 0.25]:
                assert np.mean(reader.get_frame(t)) > 10
            report['decode'][codec] = {'fps': reader.fps, 'frames': reader.frame_count}
        finally:
            reader.close()
    transparent = output / 'transparent.png'
    Image.new('RGBA', (1920, 1080), (0, 0, 0, 0)).save(transparent)
    style = copy.deepcopy(DEFAULT_STYLES['maimai'][1])
    style['asset_paths'].update(intro_video_bg=str(media / 'av1.mp4'),
                                intro_bgm=str(media / 'h264.mp4'),
                                intro_text_bg=str(transparent), content_bg_video=str(media / 'av1.mp4'))
    style['options']['content_use_video_bg'] = True
    clips = [dict(clip_title_name=codec, video=str(media / f'{codec}.mp4'), main_image=str(transparent),
                  duration=2, start=0.5, end=2.5, text=f'v1.2.6 {codec}', auto_center_align=False)
             for codec in ['h264', 'av1']]
    video_dir = output / 'clips'
    video_dir.mkdir(exist_ok=True)
    started = time.perf_counter()
    result = render_complete_full_video(
        'runtime126', 'maimai', style, clips, str(video_dir),
        intro_configs=[{'duration': 1, 'text': 'Opening'}],
        ending_configs=[{'duration': 1, 'text': 'Ending'}],
        video_res=(args.width, args.height), video_fps=60,
        video_trans_time=0.25, use_gpu_accel=args.backend != 'cpu',
        taichi_backend=args.backend, force_render=True,
    )
    assert result['status'] == 'success', result
    report['render_seconds'] = time.perf_counter() - started
    report['requested_backend'] = args.backend
    report['actual_backend'] = get_backend_name()
    if args.backend != 'cpu':
        assert report['actual_backend'] in ('cuda', 'vulkan', 'metal'), report
    final = video_dir / 'runtime126_FULL_VIDEO.mp4'
    streams = json.loads(run([ffprobe, '-v', 'error', '-count_frames', '-show_entries',
                              'stream=codec_name,codec_type,width,height,start_time,duration,nb_read_frames',
                              '-of', 'json', final]).stdout)['streams']
    report['streams'] = streams
    video = next(s for s in streams if s['codec_type'] == 'video')
    audio = next(s for s in streams if s['codec_type'] == 'audio')
    assert (video['width'], video['height']) == (args.width, args.height)
    assert int(video['nb_read_frames']) == 315, streams
    tail = float(audio['duration']) - float(video['duration'])
    report['audio_tail_seconds'] = tail
    if args.backend != 'cpu':
        # Confirmed against main's original concat + loudnorm on the same fixture.
        # Preserve its existing AAC tail; do not silently change the concat policy.
        assert abs(tail - 0.232) < 0.03, streams
        assert abs(float(video['start_time']) - float(audio['start_time'])) < 0.03, streams
    else:
        assert abs(tail) < 0.06, streams
    run([ffmpeg, '-v', 'error', '-i', final, '-f', 'null', '-'])
    run([ffmpeg, '-y', '-v', 'error', '-ss', '2', '-i', final, '-frames:v', '1', output / 'preview.png'])
    if args.force_hw_failure:
        joined = combine_full_video_xfade_islands(str(video_dir), trans_time=0.25, codec='h264_nvenc', video_fps=60)
        run([ffmpeg, '-v', 'error', '-i', joined, '-f', 'null', '-'])
        report['explicit_nvenc_then_fallback'] = True
    # Real corrupt input must fail without clobbering a previous good output.
    bad_source = output / 'broken.mp4'
    bad_source.write_bytes(b'not a video')
    bad_style = copy.deepcopy(style)
    bad_style['asset_paths']['intro_video_bg'] = str(bad_source)
    previous = output / 'preserved.mp4'
    previous.write_bytes(b'keep existing output')
    failure = render_info_segment_accel({'duration': 1}, bad_style, (64, 64), str(previous))
    assert failure['status'] == 'error', failure
    assert previous.read_bytes() == b'keep existing output'
    assert not list(output.glob('.render-*'))
    report['failure_preserves_output'] = True
    failure = render_info_segment_accel({'duration': 0.1, 'text': ''}, style, (64, 64),
                                       str(previous), bitrate='invalid-bitrate')
    assert failure['status'] == 'error', failure
    assert previous.read_bytes() == b'keep existing output'
    assert not list(output.glob('.render-*'))
    report['encoder_failure_preserves_output'] = True
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        from utils.TaichiAccel import shutdown_taichi
        shutdown_taichi()
