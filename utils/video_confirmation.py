from __future__ import annotations

from typing import Any, Mapping, Sequence

from utils.video_metadata import video_info_platform


def is_chart_video_matched(chart: Mapping[str, Any], platform: str) -> bool:
    video_info = chart.get("video_info_match")
    if not isinstance(video_info, Mapping) or not video_info:
        return False
    if video_info_platform(video_info) != platform:
        return False
    video_id = str(video_info.get("id") or video_info.get("pure_id") or "").strip()
    video_url = str(video_info.get("url") or "").strip()
    return bool(video_id and video_url)


def prioritize_unmatched_charts(
    charts: Sequence[Mapping[str, Any]], platform: str
) -> list[dict[str, Any]]:
    """Keep stable order inside unmatched and matched groups."""
    return [
        dict(chart)
        for _, chart in sorted(
            enumerate(charts),
            key=lambda item: (
                is_chart_video_matched(item[1], platform),
                item[0],
            ),
        )
    ]


def summarize_chart_video_matches(
    charts: Sequence[Mapping[str, Any]], platform: str
) -> dict[str, Any]:
    matched = []
    unmatched = []
    metadata_count = 0
    for chart in charts:
        if is_chart_video_matched(chart, platform):
            matched.append(chart)
            if chart["video_info_match"].get("_origin") == "metadata":
                metadata_count += 1
        else:
            unmatched.append(chart)
    return {
        "total": len(charts),
        "matched": len(matched),
        "unmatched": len(unmatched),
        "metadata": metadata_count,
        "history_or_manual": len(matched) - metadata_count,
        "unmatched_chart_ids": [chart.get("chart_id") for chart in unmatched],
    }
