MAIMAI_METADATA_MODE = "metadata_bilibili"
MAIMAI_YOUTUBE_MODE = "youtube_search"

MAIMAI_SOURCE_RESET_KEYS = (
    "downloader",
    "downloader_type",
    "video_source_results",
    "video_session_overrides",
    "search_results",
    "search_completed",
    "download_completed",
    "video_download_summary",
    "current_index",
    "record_selector",
    "config_saved_step2",
    "pending_video_source_mode",
)


def expected_maimai_platform(mode: str | None) -> str | None:
    return {
        MAIMAI_METADATA_MODE: "bilibili",
        MAIMAI_YOUTUBE_MODE: "youtube",
    }.get(mode)


def is_valid_maimai_source_state(mode: str | None, downloader_type: str | None) -> bool:
    expected = expected_maimai_platform(mode)
    return expected is not None and downloader_type == expected


def build_metadata_bilibili_downloader(factory, **kwargs):
    """Reuse cached credentials when readable, otherwise construct anonymously."""
    try:
        return factory(no_credential=False, skip_login=True, **kwargs), None
    except Exception as credential_error:
        return (
            factory(no_credential=True, skip_login=True, **kwargs),
            credential_error,
        )
