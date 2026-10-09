"""Versioned video styles. Reading old settings never rewrites user files."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from utils.themes import DEFAULT_STYLES

STYLE_CONFIG_PATH = "./static/video_style_config.json"
INITIAL_STYLES = {"maimai": "Buddies", "chunithm": "Verse"}
RESET_STYLES = {"maimai": "Circle", "chunithm": "X-Verse"}
CONSTANT_MODES = {"cn": "国服", "latest": "最新", "compare": "定数对比"}


def preset_style(game_type, name=None):
    name = name or INITIAL_STYLES[game_type]
    for style in DEFAULT_STYLES[game_type]:
        if style["style_name"] == name:
            return deepcopy(style)
    raise ValueError(f"未知视频主题：{game_type} / {name}")


def constant_mode(style):
    mode = style.get("options", {}).get("chunithm_constant_display", "compare")
    if mode not in CONSTANT_MODES:
        raise ValueError(f"无效的定数展示选项：{mode}")
    return mode


def normalize_style(style, game_type):
    if not style:
        return preset_style(game_type)
    style = deepcopy(style)
    name = style.get("base_style_name") or style.get("style_name")
    known = {item["style_name"] for item in DEFAULT_STYLES[game_type]}
    defaults = preset_style(game_type, name if name in known else None)
    result = deepcopy(defaults)
    for key, value in style.items():
        if key in ("asset_paths", "options", "intro_text_style", "content_text_style"):
            result[key].update(value)
        else:
            result[key] = value
    old_paths = style.get("asset_paths", {})
    if "ending_bgm" not in old_paths:
        result["asset_paths"]["ending_bgm"] = result["asset_paths"]["intro_bgm"]
    result["base_style_name"] = name if name in known else None
    result["style_schema_version"] = 2
    result["type"] = game_type
    if game_type == "chunithm":
        constant_mode(result)
        legacy_audio = Path("static/assets/audios/intro_chunithm_verse.mp3").resolve()
        for audio_key in ("intro_bgm", "ending_bgm"):
            audio_path = Path(result["asset_paths"].get(audio_key) or "")
            if audio_path.resolve() == legacy_audio and not audio_path.is_file():
                result["asset_paths"][audio_key] = defaults["asset_paths"][audio_key]
        old_base = Path(old_paths.get("score_image_base") or "").resolve()
        if old_base == Path("static/assets/images/Chunithm/content_base_chunithm_verse.png").resolve():
            result["asset_paths"]["score_image_base"] = defaults["asset_paths"]["score_image_base"]
    return result


def read_style(game_type, config_file=STYLE_CONFIG_PATH):
    path = Path(config_file)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return normalize_style(data.get(game_type), game_type)


def write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_style(game_type, style, config_file=STYLE_CONFIG_PATH):
    path = Path(config_file)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data[game_type] = normalize_style(style, game_type)
    write_json_atomic(path, data)


def resolve_bgm(style, section="intro"):
    if section not in ("intro", "ending"):
        raise ValueError(f"未知片段类型：{section}")
    paths = style.get("asset_paths", {})
    path = paths.get("ending_bgm", paths.get("intro_bgm")) if section == "ending" else paths.get("intro_bgm")
    if not path or not Path(path).is_file():
        label = "片头" if section == "intro" else "片尾"
        raise FileNotFoundError(f"{label}背景音乐不存在，请重新选择：{path}")
    return str(path)
