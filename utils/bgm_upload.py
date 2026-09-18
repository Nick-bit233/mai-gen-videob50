"""Validate uploaded audio before publishing it under a unique local path."""
import json
import math
import os
from pathlib import Path
import subprocess
from uuid import uuid4


def validate_audio(path):
    from utils.AccelRenderer import get_ffmpeg_binary
    try:
        result = subprocess.run(
            [get_ffmpeg_binary("ffprobe"), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=15, check=True)
        data = json.loads(result.stdout)
        if not data.get("streams"):
            raise ValueError("没有音轨")
        duration = float(data["streams"][0].get("duration") or data.get("format", {}).get("duration", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("无效时长")
        subprocess.run(
            [get_ffmpeg_binary(), "-v", "error", "-xerror", "-i", str(path),
             "-map", "0:a:0", "-f", "null", "-"],
            capture_output=True, timeout=45, check=True)
        return duration
    except (ValueError, KeyError, subprocess.SubprocessError) as exc:
        raise ValueError("音乐无法完整解码或时长无效，请上传有效的 MP3/WAV 文件。") from exc


def save_bgm_upload(name, content, root, game_type, section):
    if game_type not in ("maimai", "chunithm") or section not in ("intro", "ending"):
        raise ValueError("无效的音乐用途")
    suffix = Path(name).suffix.lower()
    if suffix not in (".mp3", ".wav") or not content:
        raise ValueError("请上传非空的 MP3/WAV 文件。")
    directory = Path(root) / game_type / section
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{uuid4().hex}{suffix}"
    temporary = destination.with_suffix(f".upload{suffix}")
    try:
        temporary.write_bytes(content)
        validate_audio(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return str(destination)
