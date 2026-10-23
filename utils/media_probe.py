"""Media contracts for low-memory transitions, inspected without hashing."""
import json
import math
from pathlib import Path

from utils.diagnostics import current_report, execute


def probe_media(path):
    from utils.AccelRenderer import get_ffmpeg_binary
    key = str(Path(path).resolve())
    stat = Path(path).stat()
    report = current_report()
    cached = report.manifest['media'].get(key)
    reference = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
    if cached and cached.get('reference') == reference:
        return cached
    result = execute([get_ffmpeg_binary('ffprobe'), '-v', 'error', '-show_streams',
                      '-show_format', '-of', 'json', key], '检查媒体输入', timeout=30)
    raw = json.loads(result.stdout)
    video = next((s for s in raw.get('streams', []) if s.get('codec_type') == 'video'), None)
    audio = next((s for s in raw.get('streams', []) if s.get('codec_type') == 'audio'), None)
    if not video or not video.get('width') or not video.get('height'):
        raise ValueError(f'片段没有有效视频流：{path}')
    duration = float(video.get('duration') or raw.get('format', {}).get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f'片段没有有效时长：{path}')
    fields = ('codec_name', 'width', 'height', 'pix_fmt', 'avg_frame_rate', 'r_frame_rate',
              'time_base', 'sample_aspect_ratio', 'duration', 'nb_frames')
    info = {'reference': reference, 'duration': duration,
            'video': {k: video.get(k) for k in fields},
            'audio': {k: audio.get(k) for k in ('codec_name', 'sample_rate', 'channels', 'duration')} if audio else None}
    report.media(key, info)
    return info


def normalized_video(index, start, duration, fps, resolution, label):
    width, height = resolution
    return (f'[{index}:v]trim=start={start:.6f}:duration={duration:.6f},setpts=PTS-STARTPTS,'
            f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,'
            f'fps={fps},format=yuv420p,settb=AVTB[{label}]')


def normalized_audio(index, start, duration, has_audio, label):
    source = f'[{index}:a]atrim=start={start:.6f},asetpts=PTS-STARTPTS,' if has_audio else 'anullsrc=r=48000:cl=stereo,'
    return (source + f'aresample=48000:async=1:first_pts=0,aformat=sample_fmts=fltp:channel_layouts=stereo,'
            f'apad,atrim=duration={duration:.6f},asetpts=N/SR/TB[{label}]')
