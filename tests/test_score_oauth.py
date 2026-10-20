"""OAuth transport, real loopback callbacks, full-score selection and local saves."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

from utils.score_oauth import OAuthError, ScoreSnapshot, fetch_full_scores, start_oauth
from utils.score_selection import build_oauth_archive, select_scores
from utils.user_gamedata_handlers import fetch_user_gamedata


def fish_row(i, *, ra=300, fc="ap", difficulty=3, chart_type="DX"):
    return {"song_id": i, "title": f"Song {i}", "type": chart_type, "level_index": difficulty,
            "ra": ra, "ds": 14.0, "achievements": 100.5, "fc": fc, "fs": "", "dxScore": 1000}


def fish_snapshot(rows, new_rows=()):
    return ScoreSnapshot("fish", "maimai", {"records": rows},
                         {"new_scores": {"records": list(new_rows), "filters": {"is_new": ["true"]}}})


def lxns_row(i, *, rating=300.9, fc="ap", difficulty=3, chart_type="dx"):
    return {"id": i, "song_name": f"Song {i}", "type": chart_type, "level_index": difficulty,
            "dx_rating": rating, "achievements": 100.5, "fc": fc, "fs": None, "dx_score": 1000}


def lxns_song(i, version=24000, **extra):
    return {"id": i, "title": f"Song {i}", "version": 10000, "difficulties": {
        "dx": [{"difficulty": 3, "level_value": 14.0, "version": version}]}, **extra}


def lxns_snapshot(rows, songs):
    return ScoreSnapshot("lxns", "maimai", {"records": rows}, {"catalog": {
        "versions": [{"version": 25000}], "songs": songs}})


class SelectionTests(unittest.TestCase):
    def test_b50_quotas_and_ap_outside_normal_b50(self):
        old = [fish_row(i, ra=400-i, fc="fc") for i in range(1, 46)]
        new = [fish_row(i, ra=600-i, fc="fcp") for i in range(101, 126)]
        ap = [fish_row(i, ra=200, fc="app" if i % 2 else "ap") for i in range(201, 261)]
        snapshot = fish_snapshot(old + new + ap, new)
        before = copy.deepcopy(snapshot.payload)
        b50 = select_scores(snapshot)
        self.assertEqual(len(b50), 50)
        self.assertEqual([r["clip_title_name"] for r in b50],
                         [f"PastBest_{i}" for i in range(1, 36)] + [f"NewBest_{i}" for i in range(1, 16)])
        apb50 = select_scores(snapshot, "apb50")
        self.assertEqual(len(apb50), 50)
        self.assertTrue(all(r["fc"] in ("ap", "app") for r in apb50))
        self.assertTrue(all(r["song_id"] >= 201 for r in apb50))
        self.assertEqual(snapshot.payload, before)

    def test_underfilled_ap_dedup_ties_and_utage(self):
        rows = [fish_row(1, ra=300), fish_row(1, ra=300), fish_row(2, ra=300, fc="ap+"),
                fish_row(3, ra=999, difficulty=10), fish_row(100001, ra=999),
                fish_row(4, ra=999, chart_type="utage"), fish_row(5, fc="notap")]
        rows[2]["ds"] = 14.1
        rows.append({**fish_row(6, ra=999), "level_label": "UTAGE"})
        selected = select_scores(fish_snapshot(rows), "apb50")
        self.assertEqual([r["song_id"] for r in selected], [2, 1])
        self.assertEqual(selected[0]["fc"], "app")

    def test_waterfish_new_group_echo_required_and_baseline_preserved(self):
        snapshot = fish_snapshot([fish_row(1, ra=100)], [fish_row(1, ra=500), fish_row(2)])
        rows = select_scores(snapshot)
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(row for row in rows if row["song_id"] == 1)["ra"], 100)
        self.assertTrue(all(row["clip_title_name"].startswith("NewBest") for row in rows))
        snapshot.context["new_scores"]["filters"] = {}
        with self.assertRaisesRegex(OAuthError, "筛选条件"):
            select_scores(snapshot)

    def test_lxns_chart_version_not_song_version_and_floor_before_sort(self):
        rows = [lxns_row(1, rating=300.99), lxns_row(2, rating=300.01), lxns_row(3)]
        songs = [lxns_song(1), lxns_song(2, version=25000), lxns_song(3, disabled=True)]
        songs[1]["difficulties"]["dx"][0]["level_value"] = 14.1
        snapshot = lxns_snapshot(rows, songs)
        selected = select_scores(snapshot)
        self.assertEqual([r["clip_title_name"] for r in selected], ["PastBest_1", "NewBest_1"])
        ap = select_scores(snapshot, "apb50")
        self.assertEqual([r["id"] for r in ap], [2, 1])
        self.assertEqual([r["dx_rating"] for r in ap], [300, 300])

    def test_lxns_missing_current_chart_must_not_be_guessed(self):
        with self.assertRaisesRegex(OAuthError, "无法识别"):
            select_scores(lxns_snapshot([lxns_row(1)], []))

    def test_lxns_retirement_confirmed_from_cached_history(self):
        snapshot = lxns_snapshot([lxns_row(1), lxns_row(2)], [lxns_song(1)])
        snapshot.context["catalog"]["versions"].append({"version": 24000})
        snapshot.context["history"] = {24000: {"versions": [{"version": 24000}],
                                                     "songs": [lxns_song(2, disabled=True)]}}
        with patch("utils.score_selection.request_json") as request:
            self.assertEqual(len(select_scores(snapshot)), 1)
            request.assert_not_called()

    def test_invalid_numbers_empty_ap_and_chunithm_mode(self):
        for value in (float("nan"), float("inf"), None, -1):
            with self.subTest(value=value), self.assertRaises(OAuthError):
                select_scores(fish_snapshot([fish_row(1, ra=value)]))
        with self.assertRaisesRegex(OAuthError, "类型"):
            select_scores(fish_snapshot([fish_row(1, chart_type="unknown")]))
        with self.assertRaisesRegex(OAuthError, "没有符合"):
            select_scores(fish_snapshot([fish_row(1, fc="fc")]), "apb50")
        snapshot = ScoreSnapshot("fish", "chunithm", {"records": []}, {})
        with self.assertRaises(OAuthError):
            select_scores(snapshot, "apb50")

    def test_chunithm_full_scores_partition(self):
        rows = [{"mid": i, "title": f"C{i}", "level_index": 3, "ds": 14, "ra": 16,
                 "score": 1009000, "fc": "alljustice"} for i in range(1, 56)]
        catalog = [{"id": i, "basic_info": {"from": "new" if i > 35 else "old"}} for i in range(1, 56)]
        snapshot = ScoreSnapshot("fish", "chunithm", {"records": rows},
                                 {"catalog": catalog, "latest": {"version": ["new"]}})
        selected = select_scores(snapshot)
        self.assertEqual(len(selected), 50)
        self.assertEqual(selected[29]["clip_title_name"], "PastBest_30")
        self.assertEqual(selected[-1]["clip_title_name"], "NewBest_20")

    def test_archive_rating_cache_and_actual_conversion(self):
        metadata = [{"title": "Song 1", "artist": "Artist", "id_lx": 1, "charts_info": [
            {"type": "dx", "difficulty": 3, "level_value_cn": 13.0, "note_counts": {"total": 1000}}]}]
        with patch("utils.DataUtils.load_metadata", return_value=metadata), tempfile.TemporaryDirectory() as temp:
            snapshot = lxns_snapshot([lxns_row(1)], [lxns_song(1)])
            path = Path(temp) / "raw.json"
            archive = fetch_user_gamedata(path, "local-name", {"oauth_snapshot": snapshot,
                "selection": "apb50", "type": "maimai"}, "lxns")
            self.assertEqual(archive["rating_mai"], 300)
            self.assertEqual(archive["sub_type"], "ap")
            record = archive["initial_records"][0]
            self.assertEqual(record["chart_data"]["difficulty"], "14.0")
            self.assertEqual(record["chart_data"]["max_dx_score"], 3000)
            self.assertEqual(record["order_in_archive"], 1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot.payload)
        with self.assertRaises(OAuthError):
            fetch_user_gamedata("unused", "a", {"api_key": "legacy"}, "lxns")


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return copy.deepcopy(self.payload)


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.flows = []

    def tearDown(self):
        for flow in self.flows:
            flow.cancel()
            flow._thread.join(2)

    def provider(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("openid-configuration"):
            authority = url.split("/.well-known")[0]
            return Response({"issuer": authority, "authorization_endpoint": authority + "/oauth/authorize",
                             "token_endpoint": authority + "/oauth/token"})
        if url.endswith("/oauth/token"):
            return Response({"access_token": "secret-access-token", "refresh_token": "secret-refresh-token",
                             "token_type": "Bearer", "scope": "prober.records.read read_player"})
        if url.endswith("/player/records"):
            return Response({"records": [fish_row(1)], "filters": {"is_new": ["true"]}})
        if url.endswith("/player/scores"):
            return Response({"success": True, "data": [lxns_row(1)]})
        if url.endswith("/song/list"):
            return Response({"versions": [{"version": 25000}], "songs": [lxns_song(1)]})
        raise AssertionError(f"Unexpected endpoint: {url}")

    def flow(self, provider="fish"):
        flow = start_oauth(provider, "maimai", "local-user", "public-client", 0)
        self.flows.append(flow)
        return flow

    def callback(self, flow, params):
        connection = http.client.HTTPConnection("127.0.0.1", urlsplit(flow.redirect_uri).port, timeout=5)
        connection.request("GET", "/callback?" + urlencode(params))
        response = connection.getresponse()
        result = response.status, response.read().decode("utf-8")
        connection.close()
        return result

    def test_real_loopback_both_providers_pkce_single_use_no_secrets(self):
        for provider in ("fish", "lxns"):
            with self.subTest(provider=provider), patch("utils.score_oauth.requests.request", side_effect=self.provider):
                flow = self.flow(provider)
                query = parse_qs(urlsplit(flow.authorization_url).query)
                self.assertEqual(query["code_challenge_method"], ["S256"])
                self.assertRegex(query["code_challenge"][0], r"^[A-Za-z0-9_-]{43}$")
                self.assertNotIn("code_verifier", query)
                self.assertNotIn("client_secret", query)
                verifier, state = flow.verifier, flow.state
                status, body = self.callback(flow, {"state": state, "code": "secret-code"})
                self.assertEqual(status, 200)
                self.assertEqual(flow.status, "ready")
                self.assertEqual(flow.state, "")
                self.assertEqual(flow.verifier, "")
                self.assertIsNotNone(flow.snapshot)
                serialized = json.dumps(flow.snapshot.payload) + repr(flow) + body
                for secret in (verifier, state, "secret-code", "secret-access-token", "secret-refresh-token"):
                    self.assertNotIn(secret, serialized)
                with self.assertRaises(OAuthError):
                    flow.complete({"state": [state], "code": ["secret-code"]})
                token_call = next(call for call in reversed(self.calls) if call[1].endswith("/oauth/token"))
                self.assertEqual(token_call[2]["data"]["code_verifier"], verifier)
                self.assertNotIn("client_secret", token_call[2]["data"])
                self.assertTrue(all(call[2]["allow_redirects"] is False for call in self.calls))
                self.assertTrue(all("query/player" not in call[1] for call in self.calls))
                flow._thread.join(2)
                self.assertFalse(flow._thread.is_alive())

    def test_bad_state_rejected_without_consuming_valid_flow_then_denial(self):
        with patch("utils.score_oauth.requests.request", side_effect=self.provider):
            flow = self.flow()
            self.assertEqual(self.callback(flow, {"state": "wrong", "code": "code"})[0], 400)
            self.assertEqual(flow.status, "awaiting_authorization")
            self.assertEqual(self.callback(flow, {"state": flow.state, "error": "access_denied"})[0], 400)
            self.assertEqual(flow.status, "failed")
            self.assertFalse(any(call[0] == "POST" for call in self.calls))

    def test_page_start_callback_and_ready_selection(self):
        from streamlit.testing.v1 import AppTest

        code = """
from utils.score_oauth_ui import render_score_oauth
render_score_oauth('fish', 'maimai', 'local-user', lambda *args, **kwargs: None)
"""
        with patch("utils.score_oauth.requests.request", side_effect=self.provider), \
             patch("utils.score_oauth_ui.load_public_config", return_value=("public-client", 8766)), \
             patch("utils.score_oauth_ui.start_oauth", side_effect=lambda *args: self.flow()):
            page = AppTest.from_string(code).run(timeout=15)
            next(item for item in page.button if item.label == "授权并获取全部成绩").click().run(timeout=15)
            self.assertFalse(page.exception, page.exception)
            flow = page.session_state["score_oauth_fish"]
            self.assertEqual(flow.status, "awaiting_authorization")
            self.assertEqual(len(page.get("link_button")), 1)
            self.assertEqual(len(page.radio), 0)
            self.assertEqual(self.callback(flow, {"state": flow.state, "code": "code"})[0], 200)
            page.run(timeout=15)
            self.assertFalse(page.exception, page.exception)
            self.assertEqual(page.radio[0].value, "b50")
            self.assertTrue(any("已获取全部成绩" in item.value for item in page.success))

    def test_expiry_cancellation_and_provider_failures(self):
        with patch("utils.score_oauth.requests.request", side_effect=self.provider):
            flow = self.flow()
            flow.deadline = time.monotonic() - 1
            flow._thread.join(2)
            self.assertEqual(flow.status, "failed")
            self.assertEqual(flow.verifier, "")
            cancelled = self.flow()
            cancelled.cancel()
            self.assertEqual(cancelled.status, "cancelled")
            self.assertFalse(cancelled._thread.is_alive())
            failed = self.flow()
            state = failed.state
            with patch("utils.score_oauth.fetch_full_scores", side_effect=RuntimeError("secret-provider-body")):
                status, body = self.callback(failed, {"state": state, "code": "secret-code"})
            self.assertEqual(status, 400)
            self.assertEqual(failed.status, "failed")
            self.assertNotIn("secret", body + failed.error)

    def test_no_redirect_or_legacy_fallback_on_bad_payload(self):
        with patch("utils.score_oauth.requests.request", return_value=Response({}, 302)):
            with self.assertRaises(OAuthError):
                fetch_full_scores("fish", "maimai", "token")
        with patch("utils.score_oauth.requests.request", return_value=Response({"records": None})):
            with self.assertRaises(OAuthError):
                fetch_full_scores("fish", "maimai", "token")
        with patch("utils.score_oauth.requests.request", return_value=Response({
                "issuer": "https://auth.diving-fish.com", "authorization_endpoint": "https://evil.test/oauth/authorize",
                "token_endpoint": "https://auth.diving-fish.com/oauth/token"})):
            with self.assertRaises(OAuthError):
                self.flow()


class PageTests(unittest.TestCase):
    def test_setup_page_default_b50_ap_and_real_sqlite_save(self):
        from streamlit.testing.v1 import AppTest
        from db_utils.DatabaseDataHandler import DatabaseDataHandler

        metadata = [{"title": "Song 1", "artist": "Artist", "id_lx": 1, "charts_info": [
            {"type": "dx", "difficulty": 3, "level_value_cn": 14.0, "note_counts": {"total": 1000}}]}]
        snapshot = fish_snapshot([fish_row(1)])
        flow = SimpleNamespace(provider="fish", game_type="maimai", owner="oauth-page-test",
                               status="ready", snapshot=snapshot, cancel=Mock())
        with tempfile.TemporaryDirectory() as temp:
            handler = DatabaseDataHandler(str(Path(temp) / "scores.db"))
            with patch("db_utils.DatabaseDataHandler.get_database_handler", return_value=handler), \
                 patch("utils.PathUtils.get_user_base_dir", return_value=temp), \
                 patch("utils.DataUtils.load_metadata", return_value=metadata), \
                 patch("utils.score_oauth_ui.load_public_config", return_value=("public-client", 8766)):
                page = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "st_pages/Setup_Achievements.py"))
                for key, value in {"game_type": "maimai", "username": "oauth-page-test",
                                   "safe_username": "oauth-page-test", "config_saved": True,
                                   "score_oauth_fish": flow}.items():
                    page.session_state[key] = value
                page.run(timeout=15)
                self.assertFalse(page.exception, page.exception)
                radio = next(item for item in page.radio if item.label == "筛选分表")
                self.assertEqual(radio.value, "b50")
                radio.set_value("apb50").run(timeout=15)
                self.assertFalse(page.exception, page.exception)
                self.assertEqual(page.dataframe[-1].value.iloc[0]["抬头"], "APBest_1")
                self.assertFalse(any(item.label in ("好友码", "API密钥") for item in page.text_input))
                next(item for item in page.button if item.label == "将所选分表保存为新存档").click().run(timeout=15)
                self.assertFalse(page.exception, page.exception)
                archives = handler.get_user_save_list("oauth-page-test", "maimai")
                self.assertEqual(len(archives), 1)
                self.assertEqual(archives[0]["sub_type"], "ap")
                stored = handler.db.get_records_with_extented_data(archives[0]["id"])
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0]["clip_title_name"], "APBest_1")
                self.assertEqual(stored[0]["fc_status"], "ap")

    def test_switch_local_user_clears_authorized_snapshot(self):
        from streamlit.testing.v1 import AppTest

        flow = SimpleNamespace(game_type="maimai", owner="old-user", status="ready",
                               snapshot=fish_snapshot([fish_row(1)]), cancel=Mock())
        code = """
from utils.score_oauth_ui import render_score_oauth
render_score_oauth('fish', 'maimai', 'new-user', lambda *args, **kwargs: None)
"""
        with patch("utils.score_oauth_ui.load_public_config", return_value=("public-client", 8766)):
            page = AppTest.from_string(code)
            page.session_state["score_oauth_fish"] = flow
            page.session_state["score_oauth_fish_selection"] = "apb50"
            page.run(timeout=15)
            self.assertFalse(page.exception, page.exception)
            flow.cancel.assert_called_once()
            self.assertNotIn("score_oauth_fish", page.session_state)
            self.assertFalse(any(item.label == "将所选分表保存为新存档" for item in page.button))


if __name__ == "__main__":
    unittest.main()
