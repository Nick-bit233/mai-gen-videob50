"""Real FFmpeg acceptance for 1.2.8 transitions, fallback and finished-file protection."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.diagnostics import begin_report, capture_exception
from utils.VideoUtils import combine_full_video_xfade_islands
from utils.AccelRenderer import detect_hw_encoder, get_ffmpeg_encoder_args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    if not root.is_relative_to(ROOT / 'test_output'):
        parser.error('Acceptance output must be within test_output')
    root.mkdir(parents=True, exist_ok=False)
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    results = []
    for name, codec in [('software', 'libx264'), ('hardware', detect_hw_encoder()[0]), ('forced-fallback', 'h264_nvenc')]:
        folder = root / name
        folder.mkdir()
        report = begin_report(name, root / 'diagnostics')
        for index, (width, height, fps, audio) in enumerate(((160, 90, 15, True), (240, 160, 30, False), (160, 90, 30, True))):
            command = [ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={"red" if index == 0 else "blue"}:s={width}x{height}:r={fps}:d=1.2']
            if audio:
                command += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1.2']
            command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(folder / f'{index:04d}_clip.mp4')]
            subprocess.run(command, check=True, capture_output=True)
        def encoder(selected, bitrate, force_software=False):
            if selected == 'h264_nvenc' and not force_software:
                return ['-c:v', selected, '-b:v', 'invalid-bitrate']
            return get_ffmpeg_encoder_args(selected or 'libx264', bitrate)
        if name == 'forced-fallback':
            with patch('utils.VideoUtils._get_encoder_args_with_fallback', side_effect=encoder):
                output = combine_full_video_xfade_islands(str(folder), .2, codec=codec, video_fps=30, video_res=(160, 90))
        else:
            output = combine_full_video_xfade_islands(str(folder), .2, codec=codec, video_fps=30, video_res=(160, 90))
        subprocess.run([ffmpeg, '-v', 'error', '-i', output, '-f', 'null', '-'], check=True, capture_output=True)
        probe = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', output]))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        assert (video['width'], video['height']) == (160, 90), video
        assert abs(float(video['duration']) - 3.2) < .06, video
        assert abs(float(video['duration']) - float(audio['duration'])) < .07, probe
        attempts = report.manifest['attempts']
        if name == 'forced-fallback':
            assert any(a['status'] == 'failed' and 'h264_nvenc' in a['stage'] for a in attempts)
            assert any(a['status'] == 'success' and 'libx264' in a['stage'] for a in attempts)
        previous = Path(output).read_bytes()
        (folder / '0001_clip.mp4').write_bytes(b'broken media')
        try:
            combine_full_video_xfade_islands(str(folder), .2, codec=codec, video_fps=30)
        except Exception as exc:
            capture_exception(exc, 'corrupt-input-check')
        else:
            raise AssertionError('Corrupt input was accepted')
        assert Path(output).read_bytes() == previous
        results.append({'case': name, 'requested_codec': codec, 'video': video,
                        'audio': audio, 'decode_passed': True, 'old_output_preserved': True,
                        'diagnostic_directory': str(report.directory)})
    (root / 'verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{'case': r['case'], 'codec': r['requested_codec'], 'passed': True} for r in results]))


if __name__ == '__main__':
    main()
