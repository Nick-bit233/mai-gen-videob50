"""Anonymous maimai release updates; publish a complete local version in one switch."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit
from urllib.parse import unquote
from uuid import uuid4

import requests

from utils.diagnostics import capture_exception

ACTIVE_RELEASE_URL = 'https://nickbit-maigen-images.oss-cn-shanghai.aliyuncs.com/metadata_json/active-release.json'
FILES = {'chart_metadata': 'mai_fusion_data.json', 'asset_manifest': 'asset-manifest.json'}
_snapshot = ContextVar('metadata_release_snapshot', default=None)
_update_lock = threading.Lock()
MAX_JSON_BYTES = 32 * 1024 * 1024


class MetadataReleaseError(ValueError):
    pass


def _base(root=None):
    return Path(root or Path.cwd()).resolve()


def _pointer_path(root):
    return root / 'music_metadata' / 'current-release.json'


def _read_pointer(root):
    path = _pointer_path(root)
    if not path.exists():
        return None
    try:
        pointer = json.loads(path.read_text(encoding='utf-8'))
        folder = pointer['directory']
        if not isinstance(folder, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', folder) or folder in {'.', '..'}:
            raise ValueError('invalid local release directory')
        directory = root / 'music_metadata' / 'releases' / folder
        if not all((directory / name).is_file() for name in (*FILES.values(), 'release.json')):
            raise ValueError('incomplete local release')
        return pointer
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MetadataReleaseError('当前元数据指针损坏，请重新更新；内置快照仍保留。') from exc


@contextmanager
def metadata_snapshot(root=None):
    root = _base(root)
    try:
        pointer = _read_pointer(root)
    except MetadataReleaseError:
        pointer = None
    token = _snapshot.set((root, pointer))
    try:
        yield
    finally:
        _snapshot.reset(token)


def resolve_metadata_file(filename, root=None):
    if filename not in FILES.values():
        raise MetadataReleaseError('未知的舞萌元数据文件。')
    root = _base(root)
    snapshot = _snapshot.get()
    if snapshot and snapshot[0] == root:
        pointer = snapshot[1]
    else:
        try:
            pointer = _read_pointer(root)
        except MetadataReleaseError:
            pointer = None
    if pointer:
        return root / 'music_metadata' / 'releases' / pointer['directory'] / filename
    return root / ('video_metadata' if filename == FILES['asset_manifest'] else 'music_metadata') / filename


def validate_pointer(payload):
    if not isinstance(payload, dict) or type(payload.get('schema_version')) is not int or payload['schema_version'] != 1 or payload.get('game_type') != 'maimai':
        raise MetadataReleaseError('公开索引格式或游戏类型无效。')
    if payload.get('kind') != 'catalog_active_release':
        raise MetadataReleaseError('不支持的公开索引类型。')
    revision = payload.get('release_revision')
    if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', revision):
        raise MetadataReleaseError('发布版本标识无效。')
    if not isinstance(payload.get('metadata_store_version'), str) or not payload['metadata_store_version']:
        raise MetadataReleaseError('索引缺少元数据版本。')
    if type(payload.get('state_row_version')) is not int or payload['state_row_version'] < 1:
        raise MetadataReleaseError('索引并发版本无效。')
    return {k: payload.get(k) for k in ('kind', 'schema_version', 'game_type', 'release_id', 'release_revision', 'metadata_store_version', 'state_row_version')}


def validate_charts(charts):
    if not isinstance(charts, list) or not charts:
        raise MetadataReleaseError('舞萌谱面数据必须是非空数组。')
    identities = set()
    for song in charts:
        if not isinstance(song, dict) or not isinstance(song.get('title'), str) or not song['title'].strip() or not isinstance(song.get('artist'), str):
            raise MetadataReleaseError('谱面歌曲字段无效。')
        chart_list = song.get('charts_info')
        if not isinstance(chart_list, list):
            raise MetadataReleaseError('谱面列表缺失。')
        for chart in chart_list:
            if not isinstance(chart, dict) or chart.get('type') not in {'standard', 'dx', 'utage', 'buddy'} or type(chart.get('difficulty')) is not int:
                raise MetadataReleaseError('谱面类型或难度无效。')
            identity = (song['title'].strip(), song['artist'].strip(), chart['type'], chart['difficulty'])
            if identity in identities:
                raise MetadataReleaseError(f'谱面身份重复：{identity}')
            identities.add(identity)
    return identities


def _fetch_json(client, url):
    response = client.get(url, timeout=30, allow_redirects=False, stream=True)
    try:
        if response.status_code != 200:
            raise MetadataReleaseError(f'匿名读取失败：HTTP {response.status_code}，{url}')
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > MAX_JSON_BYTES:
                raise MetadataReleaseError('元数据超出下载大小限制。')
        return json.loads(data.decode('utf-8-sig'))
    finally:
        response.close()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '-' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def should_update_release(root=None, now=None):
    try:
        pointer = _read_pointer(_base(root))
        last = datetime.fromisoformat(pointer['checked_at']) if pointer else None
        return not last or (now or datetime.now(timezone.utc)) - last >= timedelta(hours=24)
    except (ValueError, KeyError, TypeError):
        return True


def update_release(*, url=None, files_root=None, root=None, session=None, allow_local_http=False):
    from utils.video_metadata import build_desktop_manifest, clear_video_manifest_cache, validate_desktop_manifest
    root = _base(root)
    if not _update_lock.acquire(blocking=False):
        return {'updated': False, 'message': '已有元数据更新正在进行，请稍后重试。'}
    own_session = session is None
    client = session or requests.Session()
    if own_session:
        client.trust_env = False
    staging = None
    try:
        config_file = root / 'static' / 'metadata_release_config.json'
        config = json.loads(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
        url = url or config.get('index_url') or ACTIVE_RELEASE_URL
        parsed = urlsplit(url)
        local = allow_local_http and parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
        if not (parsed.scheme == 'https' or local) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.endswith('/active-release.json'):
            raise MetadataReleaseError('舞萌发布入口必须是无凭据的 HTTPS active-release.json。')
        pointer = validate_pointer(_fetch_json(client, url))
        revision = pointer['release_revision']
        try:
            installed = _read_pointer(root)
        except MetadataReleaseError:
            installed = None
        if installed and installed.get('source') == url and all(installed.get(k) == pointer.get(k) for k in ('release_revision','metadata_store_version','state_row_version')):
            directory = root/'music_metadata/releases'/installed['directory']
            try:
                validate_charts(json.loads((directory/FILES['chart_metadata']).read_text(encoding='utf-8')))
                cached = validate_desktop_manifest(json.loads((directory/FILES['asset_manifest']).read_text(encoding='utf-8')))
                descriptor = json.loads((directory/'release.json').read_text(encoding='utf-8'))
                if cached['metadata_store_version'] != pointer['metadata_store_version'] or descriptor['release_revision'] != revision:
                    raise MetadataReleaseError('本地版本不一致。')
            except (OSError, ValueError, KeyError, TypeError):
                pass  # A damaged local copy must be repaired by downloading the pair.
            else:
                installed['checked_at'] = datetime.now(timezone.utc).isoformat()
                _write_json(_pointer_path(root), installed)
                return {'updated':True, 'changed':False, 'metadata_store_version':cached['metadata_store_version'],
                        'generated_at':cached['generated_at'], 'usable_asset_count':len(cached['assets']),
                        'message':'已检查舞萌发布索引，当前版本无变化。'}
        configured_root = files_root if files_root is not None else config.get('files_root')
        prefix = configured_root.replace('{revision}', revision) if configured_root else url.rsplit('/', 1)[0] + '/releases/' + revision + '/'
        candidate = urlsplit(prefix)
        if (candidate.scheme, candidate.netloc) != (parsed.scheme, parsed.netloc) or candidate.query or candidate.fragment or candidate.username or candidate.password or '..' in unquote(candidate.path).split('/') or not candidate.path.endswith('/'):
            raise MetadataReleaseError('公开版本文件路径必须是发现入口同源的 HTTPS 目录。')
        descriptor = _fetch_json(client, prefix + 'release.json')
        if not isinstance(descriptor, dict) or descriptor.get('game_type') != 'maimai' or descriptor.get('schema_version') != 1 or descriptor.get('release_revision') != revision or descriptor.get('metadata_store_version') != pointer['metadata_store_version'] or descriptor.get('files') != FILES:
            raise MetadataReleaseError('发布描述与索引不一致。')
        charts = _fetch_json(client, prefix + FILES['chart_metadata'])
        identities = validate_charts(charts)
        raw_manifest = _fetch_json(client, prefix + FILES['asset_manifest'])
        if not isinstance(raw_manifest, dict) or raw_manifest.get('metadata_store_version') != pointer['metadata_store_version'] or raw_manifest.get('release_revision', revision) != revision:
            raise MetadataReleaseError('视频清单与发布索引版本不一致。')
        manifest = build_desktop_manifest(raw_manifest)
        for asset in manifest['assets']:
            identity = (asset['song_title'], asset['artist'], asset['chart_type'], asset['difficulty'])
            if identity not in identities:
                raise MetadataReleaseError(f'视频素材未匹配到同版本谱面：{identity}')
        parent = root / 'music_metadata' / 'releases'
        parent.mkdir(parents=True, exist_ok=True)
        staging = parent / (revision + '-' + uuid4().hex)
        staging.mkdir()
        _write_json(staging / FILES['chart_metadata'], charts)
        _write_json(staging / FILES['asset_manifest'], manifest)
        _write_json(staging / 'release.json', {k: descriptor.get(k) for k in ('schema_version', 'game_type', 'release_revision', 'metadata_store_version', 'files')})
        try:
            installed = _read_pointer(root)
        except MetadataReleaseError:
            installed = None
        if installed and installed.get('state_row_version', 0) > pointer['state_row_version']:
            raise MetadataReleaseError('更新候选旧于本地版本，未替换现有数据。')
        pointer.update(directory=staging.name, checked_at=datetime.now(timezone.utc).isoformat(), source=url)
        _write_json(_pointer_path(root), pointer)
        staging = None  # Published directory must survive later failures.
        clear_video_manifest_cache()
        from utils.DataUtils import load_metadata
        load_metadata.cache_clear()
        return {'updated': True, 'metadata_store_version': manifest['metadata_store_version'],
                'generated_at': manifest['generated_at'], 'usable_asset_count': len(manifest['assets']),
                'message': '舞萌谱面与视频匹配数据已按同一 release 更新。'}
    except Exception as exc:
        capture_exception(exc, '舞萌元数据更新')
        return {'updated': False, 'message': f'舞萌更新失败，继续使用本地完整版本：{exc}'}
    finally:
        if staging is not None and staging.is_relative_to(root / 'music_metadata' / 'releases'):
            shutil.rmtree(staging)
        if own_session:
            client.close()
        _update_lock.release()
