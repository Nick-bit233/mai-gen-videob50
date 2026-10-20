"""Select charts only after a complete authorized score snapshot is available."""
from __future__ import annotations

import math

from utils.score_oauth import OAuthError, request_json, score_list


def _number(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise OAuthError(f"成绩缺少有效的{name}，已停止筛选。") from None
    if isinstance(value, bool) or not math.isfinite(result) or result < 0:
        raise OAuthError(f"成绩包含无效的{name}，已停止筛选。")
    return result


def _identity(row, provider, game):
    difficulty = row.get("level_index")
    if isinstance(difficulty, bool) or not isinstance(difficulty, int):
        raise OAuthError("成绩难度字段无效，已停止筛选。")
    chart_type = str(row.get("type", "normal" if game == "chunithm" else "")).strip().lower()
    if not 0 <= difficulty <= 4 or str(row.get("level_label", "")).lower() == "utage":
        return None
    if game == "maimai":
        if chart_type == "utage":
            return None
        if chart_type not in ("sd", "standard", "dx"):
            raise OAuthError("成绩谱面类型缺失或无法识别，已停止筛选。")
        chart_type = "standard" if chart_type == "sd" else chart_type
    elif chart_type in ("we", "worldsend"):
        return None
    else:
        chart_type = "normal"
    raw_id = row.get("song_id" if game == "maimai" else "mid") if provider == "fish" else row.get("id")
    music_id = _number(raw_id, "曲目 ID")
    if music_id != int(music_id):
        raise OAuthError("曲目 ID 必须是整数。")
    if game == "maimai" and music_id >= 100000:
        return None
    return int(music_id), chart_type, difficulty


def _catalog_index(catalog, game):
    if not isinstance(catalog, dict) or not isinstance(catalog.get("songs"), list):
        raise OAuthError("落雪曲库无效，无法确定谱面版本。")
    versions = catalog.get("versions")
    if not isinstance(versions, list) or not versions:
        raise OAuthError("落雪曲库缺少当前版本。")
    version_numbers = [_number(item.get("version"), "曲库版本") for item in versions]
    index = {}
    for song in catalog["songs"]:
        music_id = int(_number(song.get("id"), "曲目 ID"))
        difficulties = song.get("difficulties", {})
        groups = difficulties if game == "maimai" else {"normal": difficulties}
        for chart_type in (("standard", "dx") if game == "maimai" else ("normal",)):
            for chart in groups.get(chart_type, []):
                difficulty = chart.get("difficulty")
                if difficulty not in range(5):
                    continue
                index[music_id, chart_type, difficulty] = {
                    "version": chart.get("version"), "ds": chart.get("level_value"),
                    "title": song.get("title"),
                    "disabled": song.get("disabled") is True or chart.get("disabled") is True,
                }
    return index, max(version_numbers)


def _lxns_context(snapshot, identities):
    catalog = snapshot.context["catalog"]
    index, current = _catalog_index(catalog, snapshot.game_type)
    missing = identities - index.keys()
    # Match SaaS: inspect a bounded number of historical catalogs only to prove
    # retirement. Never turn a missing current chart into an old-chart guess.
    versions = sorted({int(item["version"]) for item in catalog["versions"]
                       if 23000 <= int(item["version"]) < current}, reverse=True)[:3]
    history = snapshot.context.setdefault("history", {})
    for version in versions:
        if not missing:
            break
        if version not in history:
            history[version] = request_json("GET", f"https://maimai.lxns.net/api/v0/{snapshot.game_type}/song/list",
                                            params={"version": version}, stage="确认已移除谱面")
        old_index, _ = _catalog_index(history[version], snapshot.game_type)
        for key in list(missing):
            if key in old_index and old_index[key]["disabled"]:
                index[key] = old_index[key]
                missing.remove(key)
    if missing:
        raise OAuthError(f"落雪当前曲库无法识别 {len(missing)} 个谱面，不能可靠筛选；请更新成绩或稍后重试。")
    return index, current


def select_scores(snapshot, mode="b50"):
    try:
        return _select_scores(snapshot, mode)
    except OAuthError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        raise OAuthError("成绩或曲库数据格式无效，无法可靠筛选，请重新获取。") from None


def _select_scores(snapshot, mode):
    if mode not in ("b50", "apb50") or (snapshot.game_type != "maimai" and mode != "b50"):
        raise OAuthError("不支持的分表筛选方式。")
    provider, game = snapshot.provider, snapshot.game_type
    candidates = [(key, dict(row)) for row in snapshot.payload["records"]
                  if (key := _identity(row, provider, game)) is not None]
    if provider == "fish" and game == "maimai":
        extra = snapshot.context["new_scores"]
        echo = extra.get("filters", {}).get("is_new")
        values = echo if isinstance(echo, list) else [echo]
        if not values or any(str(value).strip().lower() not in ("true", "1") for value in values):
            raise OAuthError("水鱼未确认新版本筛选条件，无法可靠区分 B35/B15。")
        new_rows = [(key, dict(row)) for row in score_list(extra, provider, game)
                    if (key := _identity(row, provider, game)) is not None]
        new_keys = {key for key, _ in new_rows}
        # Preserve the first full snapshot when the supplementary request changes a score.
        merged = {}
        for key, row in candidates + new_rows:
            merged.setdefault(key, row)
        candidates = list(merged.items())
        catalog_index = None
    elif provider == "fish":
        catalog = snapshot.context["catalog"]
        latest = snapshot.context["latest"].get("version")
        if not isinstance(catalog, list) or not isinstance(latest, list) or not latest:
            raise OAuthError("中二曲库或新曲版本信息无效。")
        versions = {int(song["id"]): song.get("basic_info", {}).get("from") for song in catalog}
        if any(key[0] not in versions or not versions[key[0]] for key, _ in candidates):
            raise OAuthError("中二成绩无法匹配曲库版本。")
        new_keys = {key for key, _ in candidates if versions[key[0]] in latest}
        catalog_index = None
    else:
        catalog_index, current = _lxns_context(snapshot, {key for key, _ in candidates})
        new_keys = {key for key, _ in candidates if not catalog_index[key]["disabled"]
                    and _number(catalog_index[key]["version"], "谱面版本") >= current}

    deduplicated = {}
    for key, row in candidates:
        if catalog_index is not None:
            chart = catalog_index[key]
            if chart["disabled"]:
                continue
            row["ds"] = chart["ds"]
            row["song_name"] = row.get("song_name") or chart["title"]
        row["ds"] = _number(row.get("ds"), "谱面定数")
        rating_field = "ra" if provider == "fish" else ("dx_rating" if game == "maimai" else "rating")
        score_field = "achievements" if game == "maimai" else "score"
        row[rating_field] = _number(row.get(rating_field), "单曲 Rating")
        if game == "maimai":
            row[rating_field] = math.floor(row[rating_field])
            fc = str(row.get("fc") or "").strip().lower()
            row["fc"] = "app" if fc == "ap+" else fc
            row["type"] = ("SD" if key[1] == "standard" else "DX") if provider == "fish" else key[1]
        row[score_field] = _number(row.get(score_field), "成绩")
        rank = (row[rating_field], row["ds"], row[score_field])
        if key not in deduplicated or rank > deduplicated[key][0]:
            deduplicated[key] = (rank, row)
    ranked = sorted(deduplicated.items(), key=lambda pair: pair[1][0], reverse=True)
    groups = []
    if mode == "apb50":
        groups.append(("APBest", [row for _, (_, row) in ranked if row["fc"] in ("ap", "app")][:50]))
    else:
        past_count, new_count = (35, 15) if game == "maimai" else (30, 20)
        groups.append(("PastBest", [row for key, (_, row) in ranked if key not in new_keys][:past_count]))
        groups.append(("NewBest", [row for key, (_, row) in ranked if key in new_keys][:new_count]))
    selected = []
    for prefix, rows in groups:
        selected.extend({**row, "clip_title_name": f"{prefix}_{i}"} for i, row in enumerate(rows, 1))
    if not selected:
        raise OAuthError("没有符合条件的 AP/AP+ 成绩。" if mode == "apb50" else "没有可用于分表的普通谱面成绩。")
    return selected


def build_oauth_archive(snapshot, username, mode="b50"):
    from utils.DataUtils import fish_to_new_record_format, lxns_to_new_record_format
    from utils.user_gamedata_handlers import GAME_VERSION_LABELS

    selected = select_scores(snapshot, mode)
    converter = fish_to_new_record_format if snapshot.provider == "fish" else lxns_to_new_record_format
    try:
        records = [converter(row, snapshot.game_type) for row in selected]
    except LookupError:
        raise OAuthError("选中成绩尚未匹配本地曲库，请先在首页更新元数据后重试保存。") from None
    for i, record in enumerate(records):
        record["order_in_archive"] = len(records) - i
    rating = sum(record["dx_rating"] if snapshot.game_type == "maimai" else record["chuni_rating"] for record in records)
    return {
        "game_type": snapshot.game_type, "sub_type": "ap" if mode == "apb50" else "best",
        "username": username, "rating_mai": rating if snapshot.game_type == "maimai" else 0,
        "rating_chu": rating / 50 if snapshot.game_type == "chunithm" else 0,
        "game_version": GAME_VERSION_LABELS["latest_CN"], "initial_records": records,
    }
