from __future__ import annotations

import os
import time
from typing import Any, Mapping


def download_one_video(
    downloader,
    db_handler,
    song: Mapping[str, Any],
    video_download_path: str,
    high_res: bool = False,
    force_redownload: bool = False,
) -> dict[str, str]:
    chart_id = song.get("chart_id")
    if not chart_id:
        return {
            "status": "error",
            "info": "Error: 错误的谱面数据，未找到chart_id，Skipping………",
        }

    clip_file_name = (
        f"{song['game_type']}-{song['chart_id']}-"
        f"{song['level_index']}-{song['chart_type']}"
    )
    clip_tag = (
        f"{song['song_name']}[{song['game_type']}-{song['chart_id']}-"
        f"{song['level_index']}-{song['chart_type']}]"
    )
    video_path = os.path.join(video_download_path, f"{clip_file_name}.mp4")
    abs_video_path = os.path.abspath(video_path)
    if os.path.exists(video_path) and not force_redownload:
        print(f"已找到谱面视频的缓存: {clip_tag}, Skipping………")
        db_handler.update_chart_video_path(chart_id=chart_id, video_path=abs_video_path)
        return {
            "status": "skip",
            "info": f"已找到谱面视频的缓存: {clip_tag}，跳过下载",
        }

    video_info = song.get("video_info_match")
    if not video_info:
        print(f"Error: 没有{clip_tag}的视频信息，Skipping………")
        return {
            "status": "error",
            "info": f"Error: 没有{clip_tag}的视频信息，跳过下载",
        }

    pending_path = None
    try:
        output_name = clip_file_name
        if force_redownload and os.path.exists(video_path):
            output_name = (
                f".{clip_file_name}.pending-{os.getpid()}-{time.time_ns()}"
            )
            pending_path = os.path.join(video_download_path, f"{output_name}.mp4")

        downloader.download_video(
            video_info["id"],
            output_name,
            video_download_path,
            high_res=high_res,
            p_index=video_info.get("p_index", 0),
        )
        if pending_path is not None:
            if not os.path.exists(pending_path):
                raise FileNotFoundError("下载器未生成预期的临时视频文件")
            os.replace(pending_path, video_path)
        elif not os.path.exists(video_path):
            raise FileNotFoundError("下载器未生成预期的视频文件")

        db_handler.update_chart_video_path(chart_id=chart_id, video_path=abs_video_path)
        return {"status": "success", "info": f"下载{clip_tag}完成"}
    except Exception as exc:
        print(
            f"Error: 谱面视频下载失败: {clip_tag}，"
            f"文件名: {clip_file_name}.mp4，error: {exc}"
        )
        return {
            "status": "error",
            "info": f"Error: 谱面视频下载失败: {clip_tag}，{exc}",
        }
    finally:
        if pending_path is not None and os.path.exists(pending_path):
            os.remove(pending_path)
