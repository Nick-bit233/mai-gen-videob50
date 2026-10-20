"""Public-client OAuth for the local app. Credentials never leave process memory."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import requests


class OAuthError(ValueError):
    """A safe, user-facing error (never include provider bodies or credentials)."""


PROVIDERS = {
    "fish": ("https://auth.diving-fish.com", 8766),
    "lxns": ("https://maimai.lxns.net", 8767),
}
TIMEOUT = 20
FLOW_TTL = 600
MAX_SCORES = 20000


def request_json(method, url, *, stage, **kwargs):
    try:
        response = requests.request(method, url, timeout=TIMEOUT, allow_redirects=False, **kwargs)
    except requests.RequestException:
        raise OAuthError(f"{stage}失败：网络连接异常，请重新授权后重试。") from None
    if response.status_code != 200:
        messages = {401: "授权已失效或应用配置不正确", 403: "未获得成绩读取权限",
                    429: "查分器请求过于频繁，请稍后再试"}
        reason = messages.get(response.status_code, "查分器请求失败")
        raise OAuthError(f"{stage}失败：{reason}（HTTP {response.status_code}）。")
    try:
        payload = response.json()
    except ValueError:
        raise OAuthError(f"{stage}失败：查分器返回了无效 JSON。") from None
    if isinstance(payload, dict) and (payload.get("error") or payload.get("success") is False):
        raise OAuthError(f"{stage}失败：查分器拒绝了请求，请检查授权或重新尝试。")
    return payload


def load_public_config(provider):
    """Only public application identifiers, never SaaS client secrets."""
    _, port = PROVIDERS[provider]
    root = Path(__file__).resolve().parents[1]
    try:
        config = {}
        for path in (root / "static/oauth_public_clients.json", root / "oauth_config.json"):
            if path.exists():
                section = json.loads(path.read_text(encoding="utf-8")).get(provider, {})
                if set(section) - {"client_id", "port"}:
                    raise ValueError
                config.update(section)
        client_id = os.environ.get(f"MAIGEN_{provider.upper()}_OAUTH_CLIENT_ID", config.get("client_id", ""))
        port = int(os.environ.get(f"MAIGEN_{provider.upper()}_OAUTH_PORT", config.get("port", port)))
        if not isinstance(client_id, str) or not 1024 <= port <= 65535:
            raise ValueError
    except (OSError, ValueError, TypeError, AttributeError):
        raise OAuthError("OAuth 配置无效，请检查 oauth_config.json 中的 client_id 和 port。") from None
    return client_id.strip(), port


def discover(provider):
    authority, _ = PROVIDERS[provider]
    payload = request_json("GET", authority + "/.well-known/openid-configuration", stage="读取授权配置")
    if not isinstance(payload, dict) or str(payload.get("issuer", "")).rstrip("/") != authority:
        raise OAuthError("查分器 OAuth 发行者不匹配。")
    endpoints = []
    for key in ("authorization_endpoint", "token_endpoint"):
        value = payload.get(key)
        try:
            parsed = urlsplit(value) if isinstance(value, str) else None
            valid = (parsed and parsed.scheme == "https" and parsed.hostname == urlsplit(authority).hostname
                     and parsed.port in (None, 443) and not parsed.username and not parsed.password
                     and not parsed.query and not parsed.fragment
                     and parsed.path.startswith(("/oauth/", "/api/v0/oauth/")))
        except ValueError:
            valid = False
        if not valid:
            raise OAuthError("查分器返回了无效的 OAuth 端点。")
        endpoints.append(value)
    return tuple(endpoints)


def score_list(payload, provider, game_type):
    if not isinstance(payload, dict):
        raise OAuthError("查分器未返回完整成绩对象。")
    rows = payload.get("records" if provider == "fish" else "data")
    if provider == "fish" and game_type == "chunithm" and isinstance(rows, dict):
        rows = rows.get("best")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise OAuthError("查分器未返回完整成绩列表，已停止导入。")
    if len(rows) > MAX_SCORES or payload.get("has_more") or payload.get("next"):
        raise OAuthError("查分器成绩超出单次完整导入范围，已停止导入。")
    return rows


@dataclass(repr=False)
class ScoreSnapshot:
    provider: str
    game_type: str
    payload: dict
    context: dict


def fetch_full_scores(provider, game_type, access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    if provider == "fish":
        game = "maimaidxprober" if game_type == "maimai" else "chunithmprober"
        base = f"https://www.diving-fish.com/api/{game}"
        payload = request_json("GET", base + "/player/records", headers=headers, stage="读取全部成绩")
        score_list(payload, provider, game_type)
        if game_type == "maimai":
            # SaaS uses the provider's new-chart membership, not local song versions.
            new_scores = request_json("GET", base + "/player/records", headers=headers,
                                      params={"is_new": "true", "song_id": "..99999", "level_index": "0..4"},
                                      stage="读取新版本成绩分组")
            score_list(new_scores, provider, game_type)
            context = {"new_scores": new_scores}
        else:
            context = {"catalog": request_json("GET", base + "/music_data", stage="读取中二曲库"),
                       "latest": request_json("GET", base + "/latest_version", stage="读取中二版本")}
    else:
        base = "https://maimai.lxns.net/api/v0"
        payload = request_json("GET", f"{base}/user/{game_type}/player/scores", headers=headers, stage="读取全部成绩")
        score_list(payload, provider, game_type)
        catalog = request_json("GET", f"{base}/{game_type}/song/list", stage="读取谱面版本")
        context = {"catalog": catalog}
    # Whitelist score data; an unexpected token field in a provider response is never cached.
    rows = score_list(payload, provider, game_type)
    return ScoreSnapshot(provider, game_type, {"records": rows}, context)


@dataclass(repr=False)
class OAuthFlow:
    provider: str
    game_type: str
    owner: str
    client_id: str
    redirect_uri: str
    token_endpoint: str
    scope: str
    state: str = field(repr=False)
    verifier: str = field(repr=False)
    authorization_url: str = ""
    status: str = "awaiting_authorization"
    error: str = ""
    snapshot: ScoreSnapshot | None = None
    deadline: float = field(default_factory=lambda: time.monotonic() + FLOW_TTL)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _server: HTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def cancel(self):
        with self._lock:
            self.status = "cancelled"
            self.state = self.verifier = self.authorization_url = ""
            self.snapshot = None
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def complete(self, query):
        with self._lock:
            if self.status != "awaiting_authorization":
                raise OAuthError("本次授权已处理，请返回应用重新发起授权。")
            if time.monotonic() >= self.deadline:
                self.status, self.error = "failed", "授权已超时，请重新发起授权。"
                self.state = self.verifier = self.authorization_url = ""
                raise OAuthError(self.error)
            state = query.get("state", [])
            if len(state) != 1 or not secrets.compare_digest(state[0].encode("utf-8"), self.state.encode("ascii")):
                raise OAuthError("授权 state 不匹配，请使用当前应用生成的授权链接。")
            self.status = "fetching"
            verifier = self.verifier
            self.state = self.verifier = self.authorization_url = ""
        try:
            if "error" in query:
                raise OAuthError("授权被取消或拒绝，请重新发起授权。")
            codes = query.get("code", [])
            if len(codes) != 1 or not codes[0] or len(codes[0]) > 4096:
                raise OAuthError("授权回调缺少有效授权码，请重新发起授权。")
            tokens = request_json("POST", self.token_endpoint, stage="兑换授权码", data={
                "grant_type": "authorization_code", "client_id": self.client_id,
                "redirect_uri": self.redirect_uri, "code": codes[0], "code_verifier": verifier,
            })
            if not isinstance(tokens, dict):
                raise OAuthError("查分器未返回有效访问令牌。")
            token = tokens.get("access_token")
            valid = (isinstance(token, str) and token and "\r" not in token and "\n" not in token
                     and str(tokens.get("token_type", "")).lower() == "bearer"
                     and ("scope" not in tokens or self.scope in str(tokens["scope"]).split()))
            tokens.clear()  # No refresh tokens are retained or written to disk.
            if not valid:
                raise OAuthError("访问令牌无效或缺少成绩读取权限，请重新授权。")
            snapshot = fetch_full_scores(self.provider, self.game_type, token)
            with self._lock:
                if self.status == "fetching":
                    self.snapshot, self.status = snapshot, "ready"
        except Exception as exc:
            message = str(exc) if isinstance(exc, OAuthError) else "处理授权数据失败，请重新授权后重试。"
            with self._lock:
                if self.status == "fetching":
                    self.error, self.status = message, "failed"
            raise OAuthError(message) from None


class _CallbackServer(HTTPServer):
    allow_reuse_address = False

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(2)
        return sock, address

    def handle_error(self, request, client_address):
        pass  # Never print requests, callback URLs, or credential-bearing tracebacks.


def start_oauth(provider, game_type, owner, client_id, port):
    if provider not in PROVIDERS or game_type not in ("maimai", "chunithm"):
        raise OAuthError("不支持的查分器或游戏类型。")
    if not client_id.strip():
        raise OAuthError("请先配置开源版 OAuth 公开客户端的 client_id。")
    authorize, token = discover(provider)
    scope = ("prober.records.read" if game_type == "maimai" else "chunithm.records.read") if provider == "fish" else "read_player"
    verifier = secrets.token_urlsafe(64)
    # Protocol-required PKCE S256 only; no file, data, history, or state hashes.
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    flow = OAuthFlow(provider, game_type, owner, client_id.strip(), "", token, scope,
                     secrets.token_urlsafe(32), verifier)

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            try:
                query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=10)
                flow.complete(query)
                status, message = 200, "授权处理完成，请关闭此页并返回视频生成器，选择分表后保存存档。"
            except (OAuthError, ValueError) as exc:
                status = 400
                message = str(exc) if isinstance(exc, OAuthError) else "授权回调参数无效。"
            body = ("<!doctype html><meta charset='utf-8'><title>查分器授权</title><p>" + message + "</p>").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    try:
        server = _CallbackServer(("127.0.0.1", int(port)), Callback)
    except (OSError, ValueError, OverflowError):
        raise OAuthError("无法启动本机授权回调端口，请结束其他授权或在配置中更换端口。") from None
    server.timeout = 0.25
    flow.redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    flow.authorization_url = authorize + "?" + urlencode({
        "response_type": "code", "client_id": flow.client_id, "redirect_uri": flow.redirect_uri,
        "scope": scope, "state": flow.state, "code_challenge": challenge, "code_challenge_method": "S256",
    })
    flow._server = server

    def listen():
        try:
            while flow.status == "awaiting_authorization" and time.monotonic() < flow.deadline:
                server.handle_request()
            with flow._lock:
                if flow.status == "awaiting_authorization":
                    flow.status, flow.error = "failed", "授权已超时，请重新发起授权。"
                flow.state = flow.verifier = flow.authorization_url = ""
        finally:
            server.server_close()

    flow._thread = threading.Thread(target=listen, name="score-oauth-callback", daemon=True)
    flow._thread.start()
    return flow
