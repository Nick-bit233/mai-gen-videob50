"""Sidecar cache for clip keyframe timestamps."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def cache_path(video_path: str) -> str:
    return f"{video_path}.keyframes.json"


def _signature(video_path: str) -> dict:
    stat = os.stat(video_path)
    return {"size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}


def write_keyframe_cache(video_path: str, keyframes) -> None:
    if not video_path or not os.path.exists(video_path):
        return
    values = sorted({round(float(value), 6) for value in keyframes
                     if float(value) >= 0})
    if not values:
        return
    path = Path(cache_path(video_path))
    payload = {"keyframes": values, **_signature(video_path)}
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_keyframe_cache(video_path: str):
    path = Path(cache_path(video_path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        signature = _signature(video_path)
        if (payload.get("size") != signature["size"]
                or payload.get("mtime_ns") != signature["mtime_ns"]):
            return None
        values = payload.get("keyframes")
        if isinstance(values, list) and values:
            return [float(value) for value in values]
    except (OSError, ValueError, TypeError):
        pass
    return None


def invalidate_keyframe_cache(video_path: str) -> None:
    try:
        os.remove(cache_path(video_path))
    except OSError:
        pass
