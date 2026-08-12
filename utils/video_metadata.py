from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_METADATA_PATH = PROJECT_ROOT / "video_metadata" / "asset-manifest.json"
VIDEO_METADATA_URL = (
    "https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/"
    "metadata_json/asset-manifest.json"
)
VIDEO_METADATA_STATE_PATH = Path.home() / ".mai-gen-videob50" / "metadata_update.json"
VIDEO_METADATA_UPDATE_INTERVAL = timedelta(hours=24)

_BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}(?![0-9A-Za-z])")
_CHART_TYPE_NAMES = {0: "standard", 1: "dx", 2: "utage"}
_REQUIRED_ASSET_FIELDS = (
    "chart_key",
    "asset_id",
    "song_title",
    "artist",
    "chart_type",
    "difficulty",
    "source_type",
    "source_id",
    "source_pid",
    "source_url",
    "review_status",
)
_PUBLIC_ASSET_FIELDS = (
    *_REQUIRED_ASSET_FIELDS,
    "source_title",
    "source_page_title",
    "duration_sec",
)


class VideoMetadataError(ValueError):
    """Raised when a desktop video manifest cannot be safely consumed."""


@dataclass(frozen=True)
class VideoMetadataUpdateResult:
    updated: bool
    metadata_store_version: str | None
    generated_at: str | None
    usable_asset_count: int
    message: str


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoMetadataError(f"{field_name} must be a non-empty string")
    return value.strip()


def _asset_identity(asset: Mapping[str, Any]) -> tuple[str, str, str, int]:
    title = _required_text(asset.get("song_title"), "song_title")
    artist = _required_text(asset.get("artist"), "artist")
    chart_type = _required_text(asset.get("chart_type"), "chart_type")
    difficulty = asset.get("difficulty")
    if not isinstance(difficulty, int) or isinstance(difficulty, bool):
        raise VideoMetadataError("difficulty must be an integer")
    if chart_type not in _CHART_TYPE_NAMES.values():
        raise VideoMetadataError(f"unsupported maimai chart_type: {chart_type}")
    if difficulty < 0 or difficulty > 4:
        raise VideoMetadataError("difficulty must be between 0 and 4")
    return title, artist, chart_type, difficulty


def _is_valid_bilibili_source(source_id: Any, source_url: Any, source_pid: Any) -> bool:
    if (
        not isinstance(source_id, str)
        or _BVID_PATTERN.fullmatch(source_id) is None
        or not isinstance(source_url, str)
        or not isinstance(source_pid, int)
        or isinstance(source_pid, bool)
        or source_pid < 1
    ):
        return False
    parsed = urlparse(source_url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        hostname == "bilibili.com" or hostname.endswith(".bilibili.com")
    ):
        return False
    if f"/video/{source_id}" not in parsed.path:
        return False
    raw_pid = parse_qs(parsed.query).get("p", [None])[0]
    if raw_pid is None:
        return True
    try:
        return int(raw_pid) == source_pid
    except (TypeError, ValueError):
        return False


def _validate_public_asset(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise VideoMetadataError("manifest assets must contain objects")

    missing_fields = [field for field in _REQUIRED_ASSET_FIELDS if field not in raw]
    if missing_fields:
        raise VideoMetadataError(
            f"manifest asset is missing fields: {', '.join(missing_fields)}"
        )

    asset = {field: raw.get(field) for field in _PUBLIC_ASSET_FIELDS}
    asset["chart_key"] = _required_text(asset["chart_key"], "chart_key")
    asset["asset_id"] = _required_text(asset["asset_id"], "asset_id")
    asset["song_title"], asset["artist"], asset["chart_type"], asset["difficulty"] = (
        _asset_identity(asset)
    )
    asset["source_type"] = _required_text(asset["source_type"], "source_type")
    asset["source_id"] = _required_text(asset["source_id"], "source_id")
    asset["source_url"] = _required_text(asset["source_url"], "source_url")
    asset["review_status"] = _required_text(
        asset["review_status"], "review_status"
    )

    if asset["review_status"] != "reviewed":
        raise VideoMetadataError("desktop manifest assets must be reviewed")
    source_pid = asset["source_pid"]
    if not _is_valid_bilibili_source(
        asset["source_id"], asset["source_url"], source_pid
    ):
        raise VideoMetadataError("invalid or inconsistent Bilibili source fields")

    duration = asset.get("duration_sec")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0
    ):
        raise VideoMetadataError("duration_sec must be a non-negative number or null")
    return asset


def validate_desktop_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise VideoMetadataError("video metadata must be a top-level object")
    if payload.get("game_type") != "maimai":
        raise VideoMetadataError("video metadata game_type must be maimai")

    generated_at = _required_text(payload.get("generated_at"), "generated_at")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VideoMetadataError("generated_at must be an ISO-8601 timestamp") from exc
    metadata_store_version = _required_text(
        payload.get("metadata_store_version"), "metadata_store_version"
    )
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise VideoMetadataError("video metadata assets must be a non-empty array")

    assets: list[dict[str, Any]] = []
    seen_chart_keys: set[str] = set()
    seen_identities: set[tuple[str, str, str, int]] = set()
    for raw in raw_assets:
        asset = _validate_public_asset(raw)
        chart_key = asset["chart_key"]
        identity = _asset_identity(asset)
        if chart_key in seen_chart_keys:
            raise VideoMetadataError(f"duplicate chart_key: {chart_key}")
        if identity in seen_identities:
            raise VideoMetadataError(
                "duplicate desktop chart identity: " + repr(identity)
            )
        seen_chart_keys.add(chart_key)
        seen_identities.add(identity)
        assets.append(asset)

    assets.sort(key=lambda item: item["chart_key"])
    return {
        "generated_at": generated_at,
        "game_type": "maimai",
        "metadata_store_version": metadata_store_version,
        "assets": assets,
    }


def build_desktop_manifest(source_payload: Any) -> dict[str, Any]:
    if not isinstance(source_payload, dict):
        raise VideoMetadataError("source manifest must be a top-level object")
    if source_payload.get("game_type") != "maimai":
        raise VideoMetadataError("source manifest game_type must be maimai")

    projected_assets: list[dict[str, Any]] = []
    raw_assets = source_payload.get("assets")
    if not isinstance(raw_assets, list):
        raise VideoMetadataError("source manifest assets must be an array")

    for raw in raw_assets:
        if not isinstance(raw, dict):
            continue
        if raw.get("review_status") != "reviewed" or raw.get("is_placeholder"):
            continue
        if not _is_valid_bilibili_source(
            raw.get("source_id"), raw.get("source_url"), raw.get("source_pid")
        ):
            continue
        if not str(raw.get("song_title") or "").strip() or not str(
            raw.get("artist") or ""
        ).strip():
            # A desktop client without a persisted chart_key cannot safely resolve
            # entries whose legacy title/artist identity is incomplete.
            continue
        projected_assets.append(
            {field: raw.get(field) for field in _PUBLIC_ASSET_FIELDS}
        )

    return validate_desktop_manifest(
        {
            "generated_at": source_payload.get("generated_at"),
            "game_type": "maimai",
            "metadata_store_version": source_payload.get("metadata_store_version"),
            "assets": projected_assets,
        }
    )


@lru_cache(maxsize=1)
def load_video_manifest(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path is not None else VIDEO_METADATA_PATH
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise VideoMetadataError(f"video metadata file not found: {manifest_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise VideoMetadataError(f"video metadata file is unreadable: {manifest_path}") from exc
    return validate_desktop_manifest(payload)


@lru_cache(maxsize=1)
def _default_manifest_index() -> dict[tuple[str, str, str, int], dict[str, Any]]:
    manifest = load_video_manifest()
    return {_asset_identity(asset): asset for asset in manifest["assets"]}


def clear_video_manifest_cache() -> None:
    load_video_manifest.cache_clear()
    _default_manifest_index.cache_clear()


def chart_identity(chart: Mapping[str, Any]) -> tuple[str, str, str, int] | None:
    if chart.get("game_type") != "maimai":
        return None
    title = chart.get("song_name")
    artist = chart.get("artist")
    chart_type = _CHART_TYPE_NAMES.get(chart.get("chart_type"))
    difficulty = chart.get("level_index")
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(artist, str)
        or not artist.strip()
        or chart_type is None
        or not isinstance(difficulty, int)
        or isinstance(difficulty, bool)
    ):
        return None
    return title.strip(), artist.strip(), chart_type, difficulty


def asset_to_video_info(
    asset: Mapping[str, Any], metadata_store_version: str
) -> dict[str, Any]:
    source_pid = int(asset["source_pid"])
    title = (
        asset.get("source_title")
        or asset.get("source_page_title")
        or asset.get("song_title")
        or asset["source_id"]
    )
    return {
        "id": asset["source_id"],
        "pure_id": asset["source_id"],
        "title": title,
        "duration": asset.get("duration_sec") or 0,
        "page_count": max(1, source_pid),
        "p_index": source_pid - 1,
        "url": asset["source_url"],
        "_origin": "metadata",
        "_platform": "bilibili",
        "_chart_key": asset["chart_key"],
        "_asset_id": asset["asset_id"],
        "_metadata_store_version": metadata_store_version,
        "_page_count_known": False,
    }


def resolve_maimai_video(
    chart: Mapping[str, Any], manifest: Mapping[str, Any] | None = None
) -> dict[str, Any] | None:
    identity = chart_identity(chart)
    if identity is None:
        return None
    if manifest is None:
        index = _default_manifest_index()
        metadata_store_version = load_video_manifest()["metadata_store_version"]
    else:
        validated = validate_desktop_manifest(dict(manifest))
        index = {_asset_identity(asset): asset for asset in validated["assets"]}
        metadata_store_version = validated["metadata_store_version"]
    asset = index.get(identity)
    if asset is None:
        return None
    return asset_to_video_info(asset, metadata_store_version)


def resolve_maimai_video_sources(
    charts: list[Mapping[str, Any]],
    manifest: Mapping[str, Any] | None = None,
) -> tuple[dict[Any, dict[str, Any]], dict[str, int]]:
    """Resolve the default maimai source set without searching either platform."""
    results: dict[Any, dict[str, Any]] = {}
    counts = {"history": 0, "metadata": 0, "missing": 0, "incompatible": 0}
    manifest_unavailable = False
    for chart in charts:
        chart_id = chart.get("chart_id")
        selected = None
        source_kind = None
        existing = chart.get("video_metadata")
        if existing:
            platform = video_info_platform(existing)
            if platform != "bilibili":
                counts["incompatible"] += 1
            elif platform == "bilibili" and existing.get("_origin") != "metadata":
                selected = dict(existing)
                selected.setdefault("_platform", "bilibili")
                selected.setdefault("_origin", "legacy")
                source_kind = "history"

        if selected is None and not manifest_unavailable:
            try:
                selected = resolve_maimai_video(chart, manifest)
            except VideoMetadataError:
                manifest_unavailable = True
                selected = None
            if selected is not None:
                source_kind = "metadata"

        if selected is None or chart_id is None:
            counts["missing"] += 1
            continue
        counts[source_kind] += 1
        results[chart_id] = {
            "video_info_list": [selected],
            "video_info_match": selected,
            "source_kind": source_kind,
        }
    return results, counts


def video_info_platform(video_info: Mapping[str, Any] | None) -> str | None:
    if not video_info:
        return None
    explicit = video_info.get("_platform")
    if explicit in {"bilibili", "youtube"}:
        return explicit
    url = str(video_info.get("url") or "")
    video_id = str(video_info.get("id") or "")
    pure_id = str(video_info.get("pure_id") or "")
    if (
        "bilibili.com/video/" in url
        or _BVID_PATTERN.search(url)
        or _BVID_PATTERN.fullmatch(video_id)
        or _BVID_PATTERN.fullmatch(pure_id)
    ):
        return "bilibili"
    if "youtube.com/" in url or "youtu.be/" in url:
        return "youtube"
    if any(
        len(candidate) == 11
        and candidate.replace('-', '').replace('_', '').isalnum()
        for candidate in (video_id, pure_id)
    ):
        return "youtube"
    return None


def parse_bilibili_reference(
    value: str,
    *,
    title: str,
    requested_pid: int | None = None,
) -> dict[str, Any]:
    text = (value or "").strip()
    match = _BVID_PATTERN.search(text)
    if match is None:
        raise VideoMetadataError("请输入有效的 Bilibili BV 号或视频链接")
    bvid = match.group(0)

    pid = requested_pid
    if pid is None and text.startswith(("http://", "https://")):
        raw_pid = parse_qs(urlparse(text).query).get("p", [None])[0]
        if raw_pid is not None:
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                raise VideoMetadataError("Bilibili 分 P 必须是正整数")
    pid = 1 if pid is None else pid
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        raise VideoMetadataError("Bilibili 分 P 必须是正整数")

    return {
        "id": bvid,
        "pure_id": bvid,
        "title": title or bvid,
        "duration": 0,
        "page_count": max(1, pid),
        "p_index": pid - 1,
        "url": f"https://www.bilibili.com/video/{bvid}?p={pid}",
        "_origin": "manual",
        "_platform": "bilibili",
        "_page_count_known": False,
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _read_update_state(path: Path = VIDEO_METADATA_STATE_PATH) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def should_update_video_manifest(
    *,
    now: datetime | None = None,
    state_path: Path = VIDEO_METADATA_STATE_PATH,
) -> bool:
    state = _read_update_state(state_path)
    raw_last_update = state.get("video_metadata_last_update")
    if not isinstance(raw_last_update, str):
        return True
    try:
        last_update = datetime.fromisoformat(raw_last_update)
    except ValueError:
        return True
    current_time = now or datetime.now()
    try:
        return current_time - last_update >= VIDEO_METADATA_UPDATE_INTERVAL
    except TypeError:
        # A state written with incompatible timezone-awareness is treated as stale.
        return True


def update_video_manifest(
    *,
    url: str = VIDEO_METADATA_URL,
    destination: Path = VIDEO_METADATA_PATH,
    state_path: Path = VIDEO_METADATA_STATE_PATH,
    request_get=requests.get,
    now: datetime | None = None,
) -> VideoMetadataUpdateResult:
    try:
        response = request_get(url, timeout=30)
        response.raise_for_status()
        payload = validate_desktop_manifest(response.json())
        _atomic_write_json(destination, payload)

        installed_at = now or datetime.now()
        state = _read_update_state(state_path)
        state["video_metadata_last_update"] = installed_at.isoformat()
        state["video_metadata_store_version"] = payload["metadata_store_version"]
        _atomic_write_json(state_path, state)
        clear_video_manifest_cache()
        return VideoMetadataUpdateResult(
            updated=True,
            metadata_store_version=payload["metadata_store_version"],
            generated_at=payload["generated_at"],
            usable_asset_count=len(payload["assets"]),
            message="视频 metadata 已更新",
        )
    except Exception as exc:
        try:
            cached = load_video_manifest(destination)
        except VideoMetadataError:
            cached = None
        return VideoMetadataUpdateResult(
            updated=False,
            metadata_store_version=(
                cached.get("metadata_store_version") if cached else None
            ),
            generated_at=cached.get("generated_at") if cached else None,
            usable_asset_count=len(cached.get("assets", [])) if cached else 0,
            message=f"视频 metadata 更新失败，继续使用本地版本：{exc}",
        )


def get_video_manifest_status() -> dict[str, Any]:
    manifest = load_video_manifest()
    return {
        "metadata_store_version": manifest["metadata_store_version"],
        "generated_at": manifest["generated_at"],
        "usable_asset_count": len(manifest["assets"]),
    }
