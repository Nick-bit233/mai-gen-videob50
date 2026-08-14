MAIMAI_METADATA_MODE = "metadata_bilibili"
MAIMAI_YOUTUBE_MODE = "youtube_search"
BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES = 3

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
    "metadata_bilibili_login_failures",
    "metadata_bilibili_high_res",
    "metadata_bilibili_high_res_fallback",
    "metadata_bilibili_authenticated_credential",
    "metadata_bilibili_authenticated_username",
    "metadata_bilibili_cached_credential_checked",
    "metadata_bilibili_cached_credential_error",
    "metadata_bilibili_show_qr",
    "bilibili_login_session",
    "bilibili_qr_image",
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


def build_authenticated_bilibili_downloader(
    factory,
    credential,
    username=None,
    **kwargs,
):
    """Build without another login check, then attach the verified session credential."""
    if credential is None:
        raise ValueError("高清下载需要有效的 Bilibili 登录凭证")
    downloader = factory(no_credential=True, skip_login=True, **kwargs)
    downloader.set_credential(credential)
    downloader.username = username
    return downloader


def classify_bilibili_login_result(success, credential, message: str) -> str:
    if success and credential is not None:
        return "success"
    if any(keyword in (message or "") for keyword in ("等待", "扫描", "确认", "正在登录")):
        return "pending"
    return "failure"


def register_bilibili_login_failure(
    current_failures: int,
    max_failures: int = BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES,
) -> tuple[int, bool]:
    failures = max(0, int(current_failures)) + 1
    return failures, failures >= max_failures
