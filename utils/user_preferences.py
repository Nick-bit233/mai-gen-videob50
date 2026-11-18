"""Small persisted user preferences shared across Streamlit reruns."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _preferences_path() -> Path:
    config_dir = Path.home() / ".mai-gen-videob50"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "user_preferences.json"


def load_user_preferences() -> dict:
    path = _preferences_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def update_user_preferences(**values) -> None:
    path = _preferences_path()
    data = load_user_preferences()
    data.update(values)
    handle, temporary = tempfile.mkstemp(
        prefix=".user_preferences.", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_username(username: str, safe_username: str = None) -> None:
    if not username:
        return
    update_user_preferences(
        last_username=username,
        last_safe_username=safe_username or username,
    )


def load_saved_user() -> tuple[str, str]:
    data = load_user_preferences()
    username = data.get("last_username") or ""
    safe_username = data.get("last_safe_username") or username
    return username, safe_username


def save_archive(username: str, game_type: str, archive_name: str) -> None:
    if not username or not archive_name:
        return
    data = load_user_preferences()
    archives = data.get("last_archives")
    if not isinstance(archives, dict):
        archives = {}
    user_archives = archives.get(username)
    if not isinstance(user_archives, dict):
        user_archives = {}
    if user_archives.get(game_type) == archive_name:
        return
    user_archives[game_type] = archive_name
    archives[username] = user_archives
    update_user_preferences(last_archives=archives)


def load_saved_archive(username: str, game_type: str) -> str:
    data = load_user_preferences()
    archives = data.get("last_archives")
    if not isinstance(archives, dict):
        return ""
    user_archives = archives.get(username)
    if not isinstance(user_archives, dict):
        return ""
    return user_archives.get(game_type) or ""


def save_data_source(username: str, game_type: str, source: str) -> None:
    if not username or not game_type or not source:
        return
    data = load_user_preferences()
    sources = data.get("last_data_sources")
    if not isinstance(sources, dict):
        sources = {}
    user_sources = sources.get(username)
    if not isinstance(user_sources, dict):
        user_sources = {}
    if user_sources.get(game_type) == source:
        return
    user_sources[game_type] = source
    sources[username] = user_sources
    update_user_preferences(last_data_sources=sources)


def load_saved_data_source(username: str, game_type: str) -> str:
    data = load_user_preferences()
    sources = data.get("last_data_sources")
    if not isinstance(sources, dict):
        return ""
    user_sources = sources.get(username)
    if not isinstance(user_sources, dict):
        return ""
    return user_sources.get(game_type) or ""
