"""Small, directly compared render recipes. No file or state hashing."""
from copy import deepcopy
import json
from pathlib import Path
from utils.style_config import constant_mode, resolve_bgm, write_json_atomic


def file_reference(path):
    if not path:
        return None
    p = Path(path)
    try:
        info = p.stat()
        return {"path": str(p.resolve()), "size": info.st_size, "mtime_ns": info.st_mtime_ns}
    except OSError:
        return {"path": str(p.resolve()), "missing": True}


def image_recipe(game, style):
    paths = style.get("asset_paths", {})
    keys = ["score_image_base", "ui_font", "score_image_assets_path"]
    if game == "chunithm":
        keys += ["constant_header_compare", "constant_header_single", "constant_logo_cn", "constant_logo_latest"]
    return {"layout_version": 2, "game": game,
            "mode": constant_mode(style) if game == "chunithm" else None,
            "assets": {key: file_reference(paths.get(key)) for key in keys}}


def metadata_path(path):
    return Path(str(path) + ".theme.json")


def read_recipe(path):
    try:
        return json.loads(metadata_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_image_recipe(path, game, style):
    write_json_atomic(metadata_path(path), image_recipe(game, style))


def validate_image_style(path, game, style, require_snapshot=False):
    if not path or not Path(path).is_file():
        if require_snapshot:
            raise ValueError("成绩图片尚未生成，请先到“生成成绩背景图片”完成图片生成。")
        return
    recipe = read_recipe(path)
    if recipe is None and not require_snapshot:
        return  # External images remain supported by the low-level renderer.
    if recipe != image_recipe(game, style):
        raise ValueError("成绩图片与当前主题或定数展示选项不一致，请先重新生成成绩背景图片。")


def clip_recipe(game, style, config, section, resolution, fps, bitrate, transition, backend):
    paths = style.get("asset_paths", {})
    if section == "content":
        keys = ["content_bg", "content_bg_video", "comment_font"]
        options = deepcopy(style.get("options", {}))
        text_style = style.get("content_text_style", {})
        audio = None
    else:
        keys = ["intro_text_bg", "intro_video_bg", "comment_font"]
        options = {}
        text_style = style.get("intro_text_style", {})
        audio = file_reference(resolve_bgm(style, section))
    return {"recipe_version": 2, "game": game, "section": section,
            "config": deepcopy(config), "resolution": list(resolution), "fps": fps,
            "bitrate": bitrate, "transition": transition, "backend": backend,
            "options": options, "text_style": deepcopy(text_style), "audio": audio,
            "assets": {key: file_reference(paths.get(key)) for key in keys},
            "media": {key: file_reference(config.get(key)) for key in ("video", "main_image", "bg_image")}}


def clip_is_current(path, recipe):
    return Path(path).is_file() and read_recipe(path) == recipe


def record_clip_recipe(path, recipe):
    write_json_atomic(metadata_path(path), recipe)


def record_clip_order(directory, filenames):
    write_json_atomic(Path(directory) / "clip_order.json", filenames)


def ordered_clip_files(directory):
    """Use only the last completed batch, never unrelated older numbered clips."""
    import re
    root = Path(directory)
    order_path = root / "clip_order.json"
    if order_path.is_file():
        names = json.loads(order_path.read_text(encoding="utf-8"))
        if not isinstance(names, list) or not names or len(set(names)) != len(names):
            raise ValueError("片段列表无效，请重新生成视频片段。")
        for name in names:
            if not isinstance(name, str) or Path(name).name != name or not re.match(r"^\d+_.+\.mp4$", name) or not (root / name).is_file():
                raise ValueError("片段列表包含缺失文件，请重新生成视频片段。")
        return names
    return sorted((path.name for path in root.glob("*.mp4") if re.match(r"^\d+_", path.name)),
                  key=lambda name: int(name.split("_", 1)[0]))
