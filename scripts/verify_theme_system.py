"""Real short renders, distinguishable BGM and bitmap QA in an isolated directory."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def command(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], capture_output=True, check=True, timeout=120, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "cuda", "vulkan"), default="cpu")
    parser.add_argument("--transition", type=float, default=0.5)
    parser.add_argument("--difficulty", type=int, choices=range(5), default=3,
                        help="CHUNITHM difficulty used by the nine preset images and full videos")
    parser.add_argument("--preset-assets", action="store_true", help="Also render supplied CHUNITHM preset music and compare decoded audio")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(ROOT)
    from utils.diagnostics import begin_report
    diagnostics = begin_report('主题实际渲染验收', output/'diagnostics')
    # Match the system FFmpeg used by the GPU renderer and by release builds.
    from utils.AccelRenderer import get_ffmpeg_binary
    ffmpeg, ffprobe = get_ffmpeg_binary(), get_ffmpeg_binary("ffprobe")
    os.environ["FFMPEG_BINARY"] = ffmpeg
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg
    import numpy as np
    from PIL import Image
    from utils.VideoUtils import render_all_video_clips, render_complete_full_video, get_video_preview_frame
    from utils.ImageUtils import generate_single_image
    from utils.style_config import preset_style
    from utils.bgm_upload import save_bgm_upload
    from utils.TaichiAccel import init_taichi, get_backend_name, is_available

    report = {"transition": args.transition, "backend": args.backend, "difficulty": args.difficulty,
              "audio": {}, "images": [], "full_videos": []}
    if args.backend != "cpu":
        init_taichi(args.backend)
        assert is_available() and args.backend in get_backend_name().lower(), get_backend_name()
    for section, frequency in (("intro", 440), ("ending", 880)):
        path = output / f"{section}.wav"
        command([ffmpeg, "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000",
                 "-t", "0.2", "-ac", "2", path])
    # Same original name, different bytes and independent destinations.
    uploaded = {section: save_bgm_upload("同名音乐.wav", (output / f"{section}.wav").read_bytes(),
                                         output / "uploads", "maimai", section)
                for section in ("intro", "ending")}

    def probe(path):
        return json.loads(command([ffprobe, "-v", "error", "-show_streams", "-of", "json", path], text=True).stdout)

    def frequency_at(path, start):
        audio = command([ffmpeg, "-v", "error", "-ss", start, "-i", path, "-t", "0.18",
                         "-vn", "-ac", "1", "-ar", "12000", "-f", "f32le", "-"]).stdout
        samples = np.frombuffer(audio, dtype=np.float32)
        assert len(samples) > 1000 and float(np.max(np.abs(samples))) > .001, (path, start, len(samples))
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
        return float(np.fft.rfftfreq(len(samples), 1 / 12000)[int(np.argmax(spectrum))])

    style = preset_style("maimai", "Magical")
    style["asset_paths"].update(intro_bgm=uploaded["intro"], ending_bgm=uploaded["ending"])
    clips = output / "audio-clips"
    clips.mkdir()
    config = {"duration": 1.2, "text": "", "clip_title_name": "Same title"}
    def render_audio_clips():
        render_all_video_clips("maimai", style, [], str(clips), intro_configs=[dict(config)], ending_configs=[dict(config)],
            video_res=(640, 360), video_fps=30, video_bitrate="1500k", auto_add_transition=False,
            use_gpu_accel=args.backend != "cpu", taichi_backend=args.backend)
    render_audio_clips()
    for section, name, expected in (("intro", "0_INTRO.mp4", 440), ("ending", "1_ENDING.mp4", 880)):
        path = clips / name
        data = probe(path)
        durations = {stream["codec_type"]: float(stream["duration"]) for stream in data["streams"]}
        assert abs(durations["video"] - 1.2) < .06 and abs(durations["audio"] - 1.2) < .06, durations
        frequency = frequency_at(path, .95)
        assert abs(frequency - expected) < 15, frequency
        report["audio"][section] = {"durations": durations, "tail_frequency": frequency}
    stamps = [(clips / name).stat().st_mtime_ns for name in ("0_INTRO.mp4", "1_ENDING.mp4")]
    render_audio_clips()
    assert stamps == [(clips / name).stat().st_mtime_ns for name in ("0_INTRO.mp4", "1_ENDING.mp4")]
    style["asset_paths"]["ending_bgm"] = uploaded["intro"]
    render_audio_clips()
    assert (clips / "0_INTRO.mp4").stat().st_mtime_ns == stamps[0]
    assert abs(frequency_at(clips / "1_ENDING.mp4", .95) - 440) < 15
    style["asset_paths"]["ending_bgm"] = uploaded["ending"]

    chuni_record = dict(title="新版主题测试", artist="测试", level_index=args.difficulty,
        ds_cur=14.4, ds_next=14.6, ds_cn=14.4, ds_latest=14.6, score=1009000,
        ra=16.55, combo_type="aj", chain_type="fc", play_count=5)
    for theme in ("Verse", "X-Verse", "MATE"):
        for mode in ("cn", "latest", "compare"):
            chuni = preset_style("chunithm", theme)
            chuni["options"]["chunithm_constant_display"] = mode
            path = output / f"{theme}-{mode}.png"
            generate_single_image("chunithm", chuni, chuni_record, str(path), "Best 1").close()
            report["images"].append(path.name)
    missing = dict(chuni_record, ds_cn=None, ds_latest=None)
    chuni = preset_style("chunithm", "Verse")
    chuni["options"]["chunithm_constant_display"] = "cn"
    generate_single_image("chunithm", chuni, missing, str(output / "missing-cn.png"), "Best 1").close()
    # Verify every supported difficulty frame with the new composition.
    report["missing_existing_frames"] = []
    for level in range(5):
        if not (ROOT / f"static/assets/images/Chunithm/Frames/{level}.png").is_file():
            raise FileNotFoundError(f"Missing CHUNITHM difficulty frame: {level}.png")
        generate_single_image("chunithm", chuni, dict(chuni_record, level_index=level),
                              str(output / f"difficulty-{level}.png"), "Best 1").close()
    video = output / "chart.mp4"
    command([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
             "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000", "-t", "1.5",
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", video])
    transparent = output / "transparent.png"
    Image.new("RGBA", (1920, 1080)).save(transparent)
    cases = [("maimai", "Magical", style, transparent)] + [
        ("chunithm", name, preset_style("chunithm", name), output/f"{name}-compare.png")
        for name in ("Verse", "X-Verse", "MATE")]
    for game, theme, game_style, main_image in cases:
        game_style["asset_paths"].update(intro_bgm=uploaded["intro"], ending_bgm=uploaded["ending"])
        destination = output / f"{game}-{theme}"
        destination.mkdir()
        main = dict(clip_title_name="Best 1", video=str(video), main_image=str(main_image),
                    bg_image=None, duration=1.2, start=0, end=1.2, text="主题测试", auto_center_align=False)
        result = render_complete_full_video("theme-test", game, game_style, [main], str(destination),
            intro_configs=[dict(config)], ending_configs=[dict(config)], video_res=(640, 360),
            video_fps=30, video_bitrate="1500k", video_trans_enable=True, video_trans_time=args.transition,
            use_gpu_accel=args.backend != "cpu", taichi_backend=args.backend)
        assert result["status"] == "success", result
        final = destination / "theme-test_FULL_VIDEO.mp4"
        durations = probe(final)
        command([ffmpeg, "-v", "error", "-i", final, "-f", "null", "-"])
        assert abs(frequency_at(final, .4) - 440) < 15
        video_duration = float(next(stream for stream in durations["streams"] if stream["codec_type"] == "video")["duration"])
        assert abs(frequency_at(final, video_duration - .4) - 880) < 15
        report["full_videos"].append({"game": game, "theme": theme, "output": str(final), "streams": [
            {key: stream.get(key) for key in ("codec_type", "codec_name", "duration", "width", "height")}
            for stream in durations["streams"]]})
        for part in ("intro", "ending"):
            get_video_preview_frame(game, config, game_style, (640, 360), part=part).save(output / f"{game}-{theme}-{part}.png")

    if args.preset_assets:
        def samples(path, start, duration):
            raw = command([ffmpeg, '-v', 'error', '-ss', start, '-i', path, '-t', duration,
                           '-vn', '-ac', '1', '-ar', '12000', '-f', 'f32le', '-']).stdout
            return np.frombuffer(raw, dtype=np.float32).astype(np.float64)

        def audio_similarity(rendered, source):
            reference = samples(source, .3, .8)
            actual = samples(rendered, .15, 1.7)
            if float(np.max(np.abs(reference))) < .0001:
                assert float(np.max(np.abs(actual))) < .001, 'Unexpected background audio in a silent BGM window'
                return None
            reference -= reference.mean()
            length = len(reference)
            sums = np.concatenate(([0.], np.cumsum(actual)))
            squares = np.concatenate(([0.], np.cumsum(actual*actual)))
            variance = squares[length:]-squares[:-length]-(sums[length:]-sums[:-length])**2/length
            denominator = np.sqrt(np.maximum(variance, 1e-20)*np.dot(reference,reference))
            value = float(np.max(np.abs(np.correlate(actual,reference,'valid')/denominator)))
            assert value > .85, (rendered, source, value)
            return value

        report['preset_music'] = []
        for theme in ('Verse','X-Verse','MATE'):
            real_style = preset_style('chunithm',theme)
            destination = output/f'preset-{theme}'
            destination.mkdir()
            real_config = {'duration':2.4,'text':'1.2.8 主题验收','clip_title_name':theme}
            render_all_video_clips('chunithm',real_style,[],str(destination),
                intro_configs=[dict(real_config)],ending_configs=[dict(real_config)],
                video_res=(640,360),video_fps=30,video_bitrate='1500k',auto_add_transition=False,
                use_gpu_accel=args.backend!='cpu',taichi_backend=args.backend)
            for section,name in (('intro','0_INTRO.mp4'),('ending','1_ENDING.mp4')):
                path = destination/name
                source = real_style['asset_paths']['intro_bgm' if section=='intro' else 'ending_bgm']
                recipe = json.loads(Path(str(path)+'.theme.json').read_text(encoding='utf-8'))
                assert recipe['recipe']['audio']['path'] == str(Path(source).resolve())
                command([ffmpeg,'-v','error','-i',path,'-f','null','-'])
                report['preset_music'].append({'theme':theme,'section':section,'source':source,
                                              'output':str(path),'audio_similarity':audio_similarity(path,source)})
    report['diagnostic_report'] = str(diagnostics.directory)
    report["actual_backend"] = get_backend_name()
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
