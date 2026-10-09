import json
from datetime import datetime, timedelta

import pytest

from utils.video_metadata import (
    VIDEO_METADATA_UPDATE_INTERVAL,
    VideoMetadataError,
    build_desktop_manifest,
    chart_identity,
    load_video_manifest,
    parse_bilibili_reference,
    resolve_maimai_video,
    resolve_maimai_video_sources,
    should_update_video_manifest,
    update_video_manifest,
    video_info_platform,
)
from utils.video_source_mode import (
    BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES,
    MAIMAI_METADATA_MODE,
    MAIMAI_SOURCE_RESET_KEYS,
    MAIMAI_YOUTUBE_MODE,
    build_authenticated_bilibili_downloader,
    build_metadata_bilibili_downloader,
    classify_bilibili_login_result,
    is_valid_maimai_source_state,
    register_bilibili_login_failure,
)
from utils.video_confirmation import (
    is_chart_video_matched,
    prioritize_unmatched_charts,
    summarize_chart_video_matches,
)


def source_asset(
    chart_key="song_example__standard__0",
    *,
    asset_id="asset-1",
    title="Example Song",
    artist="Example Artist",
    chart_type="standard",
    difficulty=0,
    source_id="BV1ab411c7DE",
    source_pid=2,
):
    return {
        "chart_key": chart_key,
        "asset_id": asset_id,
        "song_title": title,
        "artist": artist,
        "chart_type": chart_type,
        "difficulty": difficulty,
        "source_type": "bilibili",
        "source_id": source_id,
        "source_pid": source_pid,
        "source_url": f"https://www.bilibili.com/video/{source_id}?p={source_pid}",
        "source_title": "谱面确认",
        "source_page_title": "P2",
        "duration_sec": 123,
        "review_status": "reviewed",
        "is_placeholder": False,
        "oss_object_key": "must/not/be/public.mp4",
    }


def source_manifest(assets=None):
    return {
        "generated_at": "2026-06-29T12:00:00+08:00",
        "game_type": "maimai",
        "metadata_store_version": "test-v1",
        "assets": assets if assets is not None else [source_asset()],
    }


def test_projection_filters_and_sorts_without_internal_object_keys():
    later = source_asset(chart_key="song_z__dx__3", asset_id="asset-z")
    earlier = source_asset(
        chart_key="song_a__standard__0",
        asset_id="asset-a",
        title="Another Song",
        source_id="BV1cd411c7FG",
    )
    pending = source_asset(chart_key="song_pending__standard__0", asset_id="pending")
    pending["review_status"] = "pending"
    placeholder = source_asset(chart_key="song_placeholder__standard__0", asset_id="placeholder")
    placeholder["is_placeholder"] = True
    invalid_source = source_asset(chart_key="song_invalid__standard__0", asset_id="invalid")
    invalid_source["source_id"] = "not-a-bv"

    projected = build_desktop_manifest(
        source_manifest([later, pending, placeholder, invalid_source, earlier])
    )

    assert [item["chart_key"] for item in projected["assets"]] == [
        "song_a__standard__0",
        "song_z__dx__3",
    ]
    assert all("oss_object_key" not in item for item in projected["assets"])


@pytest.mark.parametrize(
    "assets, expected_message",
    [
        (
            [source_asset(), source_asset(asset_id="asset-2")],
            "duplicate chart_key",
        ),
        (
            [
                source_asset(),
                source_asset(
                    chart_key="different-key",
                    asset_id="asset-2",
                    source_id="BV1cd411c7FG",
                ),
            ],
            "duplicate desktop chart identity",
        ),
    ],
)
def test_projection_rejects_duplicate_keys_and_legacy_identities(assets, expected_message):
    with pytest.raises(VideoMetadataError, match=expected_message):
        build_desktop_manifest(source_manifest(assets))


@pytest.mark.parametrize(
    "chart_type, chart_type_name",
    [(0, "standard"), (1, "dx"), (2, "utage")],
)
def test_exact_matching_supports_all_maimai_chart_types(chart_type, chart_type_name):
    asset = source_asset(
        chart_key=f"song_example__{chart_type_name}__3",
        chart_type=chart_type_name,
        difficulty=3,
    )
    manifest = source_manifest([asset])
    chart = {
        "game_type": "maimai",
        "song_name": "  Example Song  ",
        "artist": "Example Artist",
        "chart_type": chart_type,
        "level_index": 3,
    }

    matched = resolve_maimai_video(chart, manifest)

    assert chart_identity(chart) == ("Example Song", "Example Artist", chart_type_name, 3)
    assert matched["_chart_key"] == asset["chart_key"]
    assert matched["_origin"] == "metadata"
    assert matched["_platform"] == "bilibili"
    assert matched["p_index"] == 1
    assert matched["_page_count_known"] is False


def test_matching_has_no_casefold_artist_or_title_only_fallback():
    manifest = source_manifest()
    base_chart = {
        "game_type": "maimai",
        "song_name": "example song",
        "artist": "Example Artist",
        "chart_type": 0,
        "level_index": 0,
    }
    assert resolve_maimai_video(base_chart, manifest) is None
    base_chart["song_name"] = "Example Song"
    base_chart["artist"] = "Different Artist"
    assert resolve_maimai_video(base_chart, manifest) is None


def test_default_source_priority_and_platform_isolation():
    manifest = source_manifest()
    base_chart = {
        "game_type": "maimai",
        "song_name": "Example Song",
        "artist": "Example Artist",
        "chart_type": 0,
        "level_index": 0,
    }
    historical = dict(
        base_chart,
        chart_id=1,
        video_metadata={
            "id": "BV1cd411c7FG",
            "url": "https://www.bilibili.com/video/BV1cd411c7FG",
            "title": "User choice",
        },
    )
    youtube_history = dict(
        base_chart,
        chart_id=2,
        video_metadata={
            "id": "https://www.youtube.com/watch?v=abcdefghijk",
            "pure_id": "abcdefghijk",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
        },
    )
    missing = dict(base_chart, chart_id=3, artist="Other Artist")

    results, counts = resolve_maimai_video_sources(
        [historical, youtube_history, missing],
        manifest,
    )

    assert results[1]["source_kind"] == "history"
    assert results[1]["video_info_match"]["id"] == "BV1cd411c7FG"
    assert results[2]["source_kind"] == "metadata"
    assert results[2]["video_info_match"]["_platform"] == "bilibili"
    assert 3 not in results
    assert counts == {"history": 1, "metadata": 1, "missing": 1, "incompatible": 1}


def test_unreadable_manifest_keeps_historical_bilibili_sources_available():
    no_history = {
        "chart_id": 1,
        "game_type": "maimai",
        "song_name": "Missing",
        "artist": "Artist",
        "chart_type": 0,
        "level_index": 0,
    }
    history = dict(
        no_history,
        chart_id=2,
        video_metadata={
            "id": "BV1cd411c7FG",
            "url": "https://www.bilibili.com/video/BV1cd411c7FG",
        },
    )

    results, counts = resolve_maimai_video_sources(
        [no_history, history],
        {"invalid": "manifest"},
    )

    assert 1 not in results
    assert results[2]["source_kind"] == "history"
    assert counts["history"] == 1
    assert counts["missing"] == 1

def test_manual_bilibili_parses_bv_url_and_page_without_network():
    bv = parse_bilibili_reference("BV1ab411c7DE", title="Song", requested_pid=3)
    url = parse_bilibili_reference(
        "https://www.bilibili.com/video/BV1ab411c7DE?p=7&spm_id_from=333",
        title="Song",
    )

    assert (bv["id"], bv["p_index"], bv["_origin"]) == ("BV1ab411c7DE", 2, "manual")
    assert (url["id"], url["p_index"], url["_platform"]) == ("BV1ab411c7DE", 6, "bilibili")
    assert video_info_platform(url) == "bilibili"
    with pytest.raises(VideoMetadataError):
        parse_bilibili_reference("https://youtube.com/watch?v=abcdefghijk", title="Song")


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_update_installs_valid_manifest_and_only_then_updates_timestamp(tmp_path):
    destination = tmp_path / "asset-manifest.json"
    state_path = tmp_path / "state.json"
    now = datetime(2026, 8, 11, 10, 0, 0)
    payload = build_desktop_manifest(source_manifest())

    result = update_video_manifest(
        destination=destination,
        state_path=state_path,
        request_get=lambda url, timeout: FakeResponse(payload),
        now=now,
    )

    assert result.updated is True
    assert load_video_manifest(destination)["metadata_store_version"] == "test-v1"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["video_metadata_last_update"] == now.isoformat()
    assert should_update_video_manifest(now=now + timedelta(hours=23), state_path=state_path) is False
    assert should_update_video_manifest(
        now=now + VIDEO_METADATA_UPDATE_INTERVAL,
        state_path=state_path,
    ) is True


def test_update_failure_preserves_installed_file_and_timestamp(tmp_path):
    destination = tmp_path / "asset-manifest.json"
    state_path = tmp_path / "state.json"
    old_payload = build_desktop_manifest(source_manifest())
    destination.write_text(json.dumps(old_payload), encoding="utf-8")
    old_state = {"video_metadata_last_update": "2026-08-10T10:00:00"}
    state_path.write_text(json.dumps(old_state), encoding="utf-8")

    result = update_video_manifest(
        destination=destination,
        state_path=state_path,
        request_get=lambda url, timeout: FakeResponse(error=RuntimeError("offline")),
    )

    assert result.updated is False
    assert json.loads(destination.read_text(encoding="utf-8")) == old_payload
    assert json.loads(state_path.read_text(encoding="utf-8")) == old_state


def test_update_rejects_invalid_remote_fields_and_preserves_local_copy(tmp_path):
    destination = tmp_path / "asset-manifest.json"
    state_path = tmp_path / "state.json"
    old_payload = build_desktop_manifest(source_manifest())
    destination.write_text(json.dumps(old_payload), encoding="utf-8")
    invalid_remote = dict(old_payload, assets=[])

    result = update_video_manifest(
        destination=destination,
        state_path=state_path,
        request_get=lambda url, timeout: FakeResponse(invalid_remote),
    )

    assert result.updated is False
    assert json.loads(destination.read_text(encoding="utf-8")) == old_payload
    assert not state_path.exists()


def test_bundled_manifest_is_valid_for_offline_startup():
    bundled = load_video_manifest()
    assert bundled["game_type"] == "maimai"
    assert bundled["metadata_store_version"]
    assert len(bundled["assets"]) > 0


def test_maimai_source_modes_are_exclusive_and_reset_session_results():
    assert is_valid_maimai_source_state(MAIMAI_METADATA_MODE, "bilibili") is True
    assert is_valid_maimai_source_state(MAIMAI_YOUTUBE_MODE, "youtube") is True
    assert is_valid_maimai_source_state(MAIMAI_METADATA_MODE, "youtube") is False
    assert is_valid_maimai_source_state(MAIMAI_YOUTUBE_MODE, "bilibili") is False
    assert is_valid_maimai_source_state(None, "bilibili") is False
    assert {
        "downloader",
        "video_source_results",
        "video_session_overrides",
        "search_results",
        "download_completed",
        "current_index",
    }.issubset(MAIMAI_SOURCE_RESET_KEYS)


def test_bilibili_cached_credential_failure_falls_back_to_anonymous():
    calls = []

    def factory(*, no_credential, skip_login, **kwargs):
        calls.append((no_credential, skip_login, kwargs))
        if not no_credential:
            raise RuntimeError("credential unreadable")
        return {"anonymous": True}

    downloader, warning = build_metadata_bilibili_downloader(
        factory,
        proxy=None,
        credential_path="cred.pkl",
    )

    assert downloader == {"anonymous": True}
    assert str(warning) == "credential unreadable"
    assert [call[:2] for call in calls] == [(False, True), (True, True)]


def test_authenticated_bilibili_downloader_attaches_verified_credential():
    class FakeDownloader:
        def __init__(self, *, no_credential, skip_login, **kwargs):
            assert no_credential is True
            assert skip_login is True
            self.credential = None
            self.username = None

        def set_credential(self, credential):
            self.credential = credential

    credential = object()
    downloader = build_authenticated_bilibili_downloader(
        FakeDownloader,
        credential,
        "test-user",
    )

    assert downloader.credential is credential
    assert downloader.username == "test-user"


def test_bilibili_high_res_login_only_counts_terminal_failures_and_falls_back_at_three():
    assert classify_bilibili_login_result(False, None, "等待扫码...") == "pending"
    assert classify_bilibili_login_result(False, None, "已扫描，请确认") == "pending"
    assert classify_bilibili_login_result(True, object(), "登录成功") == "success"
    assert classify_bilibili_login_result(False, None, "二维码已过期") == "failure"

    failures = 0
    for expected in range(1, BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES + 1):
        failures, should_fallback = register_bilibili_login_failure(failures)
        assert failures == expected
        assert should_fallback is (expected == BILIBILI_HIGH_RES_LOGIN_MAX_FAILURES)


def test_confirmation_puts_unmatched_charts_first_and_summarizes_sources():
    metadata_match = {
        "chart_id": 1,
        "video_info_match": {
            "id": "BV1ab411c7DE",
            "url": "https://www.bilibili.com/video/BV1ab411c7DE",
            "_platform": "bilibili",
            "_origin": "metadata",
        },
    }
    first_missing = {"chart_id": 2}
    history_match = {
        "chart_id": 3,
        "video_info_match": {
            "id": "BV1cd411c7FG",
            "url": "https://www.bilibili.com/video/BV1cd411c7FG",
            "_platform": "bilibili",
            "_origin": "legacy",
        },
    }
    wrong_platform = {
        "chart_id": 4,
        "video_info_match": {
            "id": "https://www.youtube.com/watch?v=abcdefghijk",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "_platform": "youtube",
        },
    }

    ordered = prioritize_unmatched_charts(
        [metadata_match, first_missing, history_match, wrong_platform],
        "bilibili",
    )
    summary = summarize_chart_video_matches(ordered, "bilibili")

    assert [chart["chart_id"] for chart in ordered] == [2, 4, 1, 3]
    assert summary == {
        "total": 4,
        "matched": 2,
        "unmatched": 2,
        "metadata": 1,
        "history_or_manual": 1,
        "unmatched_chart_ids": [2, 4],
    }
    assert is_chart_video_matched(metadata_match, "bilibili") is True
    assert is_chart_video_matched(wrong_platform, "bilibili") is False
