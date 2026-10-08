"""Save an archive and imported jackets using one SQLite transaction."""
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image
from utils.custom_jackets import prepare_jacket

CHART_FIELDS = ('game_type', 'song_id', 'chart_type', 'level_index', 'difficulty', 'song_name', 'artist', 'max_dx_score', 'video_path', 'video_metadata')
RECORD_FIELDS = ('order_in_archive', 'achievement', 'fc_status', 'fs_status', 'dx_score', 'dx_rating', 'chuni_rating', 'play_count', 'clip_title_name', 'raw_data')


def _value(field, value):
    return json.dumps(value, ensure_ascii=False) if field in {'video_metadata', 'raw_data'} and isinstance(value, (dict, list)) else value


def save_archive_records(db, archive_id, records):
    asset_root = Path(db.db_path).parent / 'static' / 'assets' / 'custom_jackets'
    prepared = {}
    created = []
    committed_ids = {}
    try:
        for index, record in enumerate(records):
            if source := record.get('_import_jacket_path'):
                asset_root.mkdir(parents=True, exist_ok=True)
                target = asset_root / (uuid4().hex + '.png')
                created.append(target)
                prepare_jacket(source).save(target, 'PNG')
                prepared[index] = target
        with db.get_connection() as conn:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('BEGIN IMMEDIATE')
            try:
                archive = conn.execute('SELECT game_type FROM archives WHERE id=?', (archive_id,)).fetchone()
                if not archive:
                    raise ValueError('存档不存在。')
                existing = {r['chart_id']: r['id'] for r in conn.execute('SELECT id, chart_id FROM records WHERE archive_id=?', (archive_id,))}
                kept = set()
                for index, record in enumerate(records):
                    chart = dict(record.get('chart_data') or {})
                    chart.setdefault('game_type', archive['game_type'])
                    if not chart or chart.get('game_type') != archive['game_type'] or not chart.get('song_id'):
                        raise ValueError('谱面缺失或游戏类型与存档不一致。')
                    key = tuple(chart.get(k) for k in CHART_FIELDS[:4])
                    found = conn.execute('SELECT id FROM charts WHERE game_type=? AND song_id=? AND chart_type=? AND level_index=?', key).fetchone()
                    if found:
                        chart_id = found['id']
                    else:
                        fields = [f for f in CHART_FIELDS if chart.get(f) is not None]
                        values = [_value(f, chart[f]) for f in fields]
                        cursor = conn.execute(f"INSERT INTO charts ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", values)
                        chart_id = cursor.lastrowid
                    if chart_id in kept:
                        raise ValueError('同一谱面在存档中重复，请先检查记录。')
                    kept.add(chart_id)
                    committed_ids[index] = chart_id
                    fields = [f for f in RECORD_FIELDS if record.get(f) is not None]
                    values = [_value(f, record[f]) for f in fields]
                    if chart_id in existing:
                        record_id = existing[chart_id]
                        if fields:
                            conn.execute(f"UPDATE records SET {','.join(f+'=?' for f in fields)} WHERE id=?", values + [record_id])
                    else:
                        columns = ['archive_id', 'chart_id', *fields]
                        cursor = conn.execute(f"INSERT INTO records ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [archive_id, chart_id, *values])
                        record_id = cursor.lastrowid
                    if index in prepared:
                        for asset in conn.execute("SELECT id,metadata FROM assets WHERE archive_id=? AND asset_type='custom_jacket'", (archive_id,)):
                            metadata = json.loads(asset['metadata'] or '{}')
                            if metadata.get('chart_id') == chart_id:
                                conn.execute('DELETE FROM assets WHERE id=?', (asset['id'],))
                        path = prepared[index]
                        conn.execute('INSERT INTO assets (record_id,archive_id,asset_type,file_path,file_size,metadata) VALUES (?,?,?,?,?,?)',
                                     (record_id, archive_id, 'custom_jacket', str(path), path.stat().st_size,
                                      json.dumps({'chart_id': chart_id, 'source': 'excel_import'})))
                for chart_id, record_id in existing.items():
                    if chart_id not in kept:
                        conn.execute('DELETE FROM records WHERE id=?', (record_id,))
                conn.execute('UPDATE archives SET record_count=? WHERE id=?', (len(records), archive_id))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        # Only consume draft file references after every row and association committed.
        for index, record in enumerate(records):
            record['chart_id'] = committed_ids[index]
            record['chart_data']['id'] = committed_ids[index]
            record.pop('_import_jacket_path', None)
        return archive_id
    except Exception:
        for file in created:
            if file.resolve().is_relative_to(asset_root.resolve()):
                file.unlink(missing_ok=True)
        raise
