"""File-backed diagnostic reports. No file/state hashes or automatic uploads."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import quote, urlsplit
from uuid import uuid4
import zipfile
import shutil

import requests

from utils.app_version import APP_VERSION

_active: ContextVar[DiagnosticReport | None] = ContextVar("diagnostic_report", default=None)
_scope = ContextVar("diagnostic_scope_settings", default=("操作", None))
_ui_enabled = ContextVar('diagnostic_ui_enabled', default=False)
MAX_REPORT_BYTES = 10 * 1024 * 1024


def prune_reports(root, keep=20, max_bytes=128*1024*1024, max_age_days=30):
    """Prune only owned, completed report directories; never inspect media or hashes."""
    root = Path(root).resolve()
    if not root.is_dir():
        return
    active = _active.get()
    candidates = []
    for directory in root.iterdir():
        if not directory.is_dir() or directory.is_symlink() or not re.fullmatch(r'\d{8}T\d{6}-[a-f0-9]{32}', directory.name):
            continue
        if active is not None and directory == active.directory:
            continue
        try:
            manifest = json.loads((directory/'report.json').read_text(encoding='utf-8'))
            if manifest.get('report_id') != directory.name or any(a.get('status') == 'running' for a in manifest.get('attempts', [])):
                continue
            created = datetime.fromisoformat(manifest['created_at']).timestamp()
            size = sum(f.stat().st_size for f in directory.iterdir() if f.is_file())
            candidates.append((created,size,directory))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    candidates.sort(reverse=True)
    total = sum(row[1] for row in candidates)
    for index,(created,size,directory) in enumerate(candidates):
        if index < keep:
            continue
        if total > max_bytes or time.time()-created > max_age_days*86400:
            if directory.resolve().parent == root:
                shutil.rmtree(directory)
                total -= size


def reports_root() -> Path:
    return Path.cwd() / "logs" / "error_reports"


def _write_json(path: Path, payload):
    temporary = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except OSError as exc:
                # Windows readers/indexers can briefly hold a handle without
                # FILE_SHARE_DELETE. Retry that lock, never an unrelated error.
                if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 5:
                    raise
                time.sleep(.025 * 2**attempt)
    finally:
        temporary.unlink(missing_ok=True)


def classify_error(message: str) -> str:
    value = message.lower()
    for category, markers in (
        ("input_or_filter", ("do not match", "matches no streams", "invalid data found", "error initializing complex filters", "failed to configure", "error reinitializing filters")),
        ("driver", ("minimum required nvidia driver", "driver does not support", "required nvenc api", "cannot load libcuda", "cannot load nvcuda")),
        ("unsupported_device", ("unsupported device", "no capable devices", "no nvenc capable", "no device available")),
        ("encoder_missing", ("unknown encoder", "encoder not found")),
        ("output", ("permission denied", "no space left", "access is denied")),
        ("resources", ("out of memory", "too many concurrent sessions", "resource temporarily unavailable")),
        ("parameters", ("invalid argument", "unsupported pixel format", "invalid preset")),
    ):
        if any(marker in value for marker in markers):
            return category
    return "unknown"


def _tail(path: Path, count=8000) -> str:
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - count))
        return stream.read().decode("utf-8", errors="replace")


class DiagnosticReport:
    def __init__(self, stage="操作", root: Path | str | None = None):
        self.report_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex
        root = Path(root or reports_root()).resolve()
        prune_reports(root)
        self.directory = root / self.report_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.lock = threading.RLock()
        self.manifest = {
            "schema_version": 1, "app_version": APP_VERSION,
            "report_id": self.report_id, "stage": stage,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": {"platform": platform.platform(), "python": sys.version,
                            "executable": sys.executable, "prefix": sys.prefix,
                            "base_prefix": sys.base_prefix, "sys_path": list(sys.path)},
            "attempts": [], "events": [], "media": {},
        }
        self.save()

    def save(self):
        with self.lock:
            _write_json(self.directory / "report.json", self.manifest)

    def note(self, name, value):
        with self.lock:
            self.manifest["events"].append({"name": name, "value": value})
            self.save()

    def media(self, path, probe):
        with self.lock:
            self.manifest["media"][str(Path(path).resolve())] = probe
            self.save()

    def attempt(self, cmd, stage):
        return ProcessAttempt(self, cmd, stage)

    def exception(self, exc, stage=None):
        with self.lock:
            name = f"exception-{len(self.manifest['events']):04d}.txt"
            (self.directory / name).write_text(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), encoding="utf-8")
            self.manifest["events"].append({"name": "exception", "stage": stage,
                                            "file": name, "category": classify_error(str(exc))})
            self.save()


class ProcessAttempt:
    def __init__(self, report, cmd, stage):
        self.report = report
        self.started = time.perf_counter()
        self.finished = False
        with report.lock:
            index = len(report.manifest["attempts"])
            self.item = {"stage": stage, "command": [str(v) for v in cmd],
                         "started_at": datetime.now(timezone.utc).isoformat(),
                         "stdout": f"attempt-{index:04d}.stdout.txt",
                         "stderr": f"attempt-{index:04d}.stderr.txt", "status": "running"}
            report.manifest["attempts"].append(self.item)
            self.stdout = (report.directory / self.item["stdout"]).open("wb")
            self.stderr = (report.directory / self.item["stderr"]).open("wb")
            report.save()

    def finish(self, code=None, error=None):
        if self.finished:
            return
        self.finished = True
        self.stdout.close()
        self.stderr.close()
        stderr = _tail(self.report.directory / self.item["stderr"])
        # Classify from the beginning as well as the end; never truncate saved evidence.
        with (self.report.directory / self.item["stderr"]).open("rb") as stream:
            beginning = stream.read(65536).decode("utf-8", errors="replace")
        with self.report.lock:
            self.item.update(status="success" if code == 0 and error is None else "failed",
                             returncode=code, returncode_hex=f"0x{code & 0xffffffff:08X}" if code is not None else None,
                             duration_seconds=time.perf_counter() - self.started,
                             category=classify_error(beginning + stderr + str(error or "")))
            if error is not None:
                self.item["exception"] = str(error)
                self.report.exception(error, self.item["stage"])
            self.report.save()


def current_report(create=True):
    report = _active.get()
    if report is not None and not report.directory.is_dir():
        report = None
    if report is None and create:
        report = DiagnosticReport(*_scope.get())
        _active.set(report)
    return report


@contextmanager
def diagnostic_scope(stage="操作", root=None):
    token = _active.set(None)
    scope_token = _scope.set((stage, root))
    ui_token = _ui_enabled.set(True)
    try:
        yield
    except Exception as exc:
        capture_exception(exc, stage)
        raise
    finally:
        _active.reset(token)
        _scope.reset(scope_token)
        _ui_enabled.reset(ui_token)


def install_streamlit_error_capture():
    import streamlit as st
    if getattr(st.error, '_diagnostic_capture', False):
        return
    original = st.error
    def error(body, *args, **kwargs):
        if _ui_enabled.get():
            try:
                report = current_report()
                report.note('page_error', str(body))
                if exc := sys.exc_info()[1]:
                    report.exception(exc, '页面错误')
                st.session_state['last_diagnostic_report'] = report.report_id
            except OSError:
                pass  # Report storage must not replace the original page error.
        return original(body, *args, **kwargs)
    error._diagnostic_capture = True
    st.error = error


def begin_report(stage="操作", root=None, settings=None):
    report = DiagnosticReport(stage, root)
    _active.set(report)
    if settings:
        report.note("settings", settings)
    return report


def capture_exception(exc, stage=None):
    report = current_report()
    report.exception(exc, stage)
    return report


def execute(cmd, stage, *, timeout=None, check=True):
    report = current_report()
    attempt = report.attempt(cmd, stage)
    try:
        process = subprocess.run([str(v) for v in cmd], stdout=attempt.stdout,
                                 stderr=attempt.stderr, timeout=timeout)
    except Exception as exc:
        attempt.finish(error=exc)
        raise
    attempt.finish(process.returncode)
    stdout_path = report.directory / attempt.item["stdout"]
    # stdout is used for small ffprobe/version JSON; full raw streams remain on disk.
    with stdout_path.open("rb") as stream:
        stdout = stream.read(8 * 1024 * 1024).decode("utf-8", errors="replace")
    stderr = _tail(report.directory / attempt.item["stderr"])
    result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    if check and process.returncode:
        raise RuntimeError(f"{stage} 失败，返回码 {process.returncode}: {stderr[-2000:]}\n诊断编号: {report.report_id}")
    return result


_SECRETS = re.compile(r'''(?i)(["']?(?:authorization|proxy-authorization|cookie|set-cookie|(?:access[_-]?)?token|access[_-]?key(?:[_-]?secret|[_-]?id)?|password|secret|signature)["']?\s*[=:]\s*)("[^"\r\n]*"|'[^'\r\n]*'|[^\r\n,;]+)''')


def redact_text(text: str, extra_paths=()) -> str:
    for path, alias in [*sorted(extra_paths, key=lambda pair: len(pair[0]), reverse=True), (str(Path.home()), "<USER>"), (str(Path.cwd()), "<APP>")]:
        if path:
            for variant in {path, path.replace("\\", "/"), path.replace("\\", "\\\\")}:
                text = text.replace(variant, alias)
    text = re.sub(r"(https?://[^\s\"'?#]+)\?[^\s\"']+", r"\1?<REDACTED>", text)
    text = re.sub(r"https?://[^/@\s]+:[^/@\s]+@", "https://<REDACTED>@", text)
    text = re.sub(r'(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*[:=])[^\r\n]*', r'\1 <REDACTED>', text)
    text = _SECRETS.sub(r'\1"<REDACTED>"', text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<EMAIL>", text)
    return text


def package_report(directory: Path | str) -> bytes:
    directory = Path(directory)
    manifest = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    paths = list(manifest.get('media', {}))
    for attempt in manifest.get('attempts', []):
        command = attempt.get('command', [])
        candidates = ([command[-1]] if command else []) + [command[i+1] for i,v in enumerate(command[:-1]) if v == '-i']
        for candidate in candidates:
            if Path(candidate).is_absolute() and candidate not in paths:
                paths.append(candidate)
    aliases = [(path, f"<FILE_{index:04d}>") for index, path in enumerate(paths)]
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(directory.iterdir()):
            if file.is_file() and (file.name == "report.json" or re.fullmatch(r"(?:attempt-\d+\.(?:stdout|stderr)|exception-\d+)\.txt", file.name)):
                archive.writestr(file.name, redact_text(file.read_text(encoding="utf-8", errors="replace"), aliases))
    return data.getvalue()


class ReportUploadConflict(RuntimeError):
    """An existing object cannot be verified through an anonymous write-only bucket."""

    def __init__(self, report_id, object_key, request_id=""):
        self.report_id = report_id
        self.object_key = object_key
        self.request_id = request_id
        super().__init__(
            f"报告编号 {report_id} 已存在，未覆盖远端文件。无法确认既有报告内容，"
            "请保留报告编号供维护者核对；本地诊断包仍可下载。")


def upload_report(data: bytes, report_id: str, endpoint: str, prefix="reports", *, timeout=30,
                  max_bytes=MAX_REPORT_BYTES, allow_local_http=False, session=None):
    """Explicit write-only anonymous PUT; retries never download or overwrite objects."""
    if not endpoint:
        raise ValueError("尚未配置日志桶地址，请先下载本地诊断包。")
    parsed = urlsplit(endpoint)
    local = allow_local_http and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not (parsed.scheme == "https" or local) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("日志地址必须是无凭据的 HTTPS 桶地址。")
    parts = prefix.strip("/").split("/")
    if not parts or any(not part or part in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError("日志前缀无效。")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", report_id):
        raise ValueError("诊断编号无效。")
    if not data or len(data) > max_bytes:
        raise ValueError("诊断包为空或超过上传上限，请保留完整本地日志。")
    date = report_id[:8]
    key = "/".join(parts + ([date[:4], date[4:6], date[6:8]] if date.isdigit() else []) + [report_id + ".zip"])
    url = endpoint.rstrip("/") + "/" + quote(key, safe="/")
    own_session = session is None
    client = session or requests.Session()
    if own_session:
        client.trust_env = False  # Never inherit .netrc authentication for anonymous storage.
    try:
        response = client.put(url, data=data, headers={"Content-Type": "application/zip", "x-oss-forbid-overwrite": "true"}, timeout=timeout, allow_redirects=False)
        if response.status_code == 409:
            raise ReportUploadConflict(report_id, key, response.headers.get("x-oss-request-id", ""))
        elif response.status_code not in {200, 201, 204}:
            raise RuntimeError(f"日志提交失败，HTTP {response.status_code}；本地诊断包仍可下载。")
        return {"report_id": report_id, "object_key": key, "url": url,
                "request_id": response.headers.get("x-oss-request-id", ""), "status": "submitted"}
    finally:
        if own_session:
            client.close()
