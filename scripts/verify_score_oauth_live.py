"""Interactive real OAuth acceptance with actual page saves in an isolated SQLite DB.

Only the human completes provider login/consent. Raw score snapshots are stored in
the explicit ignored acceptance output; OAuth credentials never leave memory.
"""
import argparse
from dataclasses import asdict
import html
import json
import os
from pathlib import Path
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def verify_page(snapshot, application, output, provider, game):
    from streamlit.testing.v1 import AppTest
    from db_utils.DatabaseDataHandler import DatabaseDataHandler
    from utils.score_selection import select_scores

    handler = DatabaseDataHandler(str(output/'acceptance.sqlite'))
    report = {}
    for mode in (('b50', 'apb50') if game == 'maimai' else ('b50',)):
        selected = select_scores(snapshot, mode)
        username = f'acceptance-{provider}-{game}-{mode}'
        cache = output/'private'/username
        cache.mkdir(parents=True, exist_ok=True)
        flow = SimpleNamespace(provider=provider, game_type=game, owner=username,
                               status='ready', snapshot=snapshot, cancel=lambda: None)
        with patch('db_utils.DatabaseDataHandler.get_database_handler', return_value=handler), \
             patch('utils.PathUtils.get_user_base_dir', return_value=str(cache)):
            page = AppTest.from_file(str(application/'st_pages/Setup_Achievements.py'))
            for key, value in dict(game_type=game, username=username, safe_username=username,
                                   config_saved=True, **{f'score_oauth_{provider}': flow}).items():
                page.session_state[key] = value
            page.run(timeout=60)
            assert not page.exception, str(page.exception)
            radio = next(item for item in page.radio if item.key == f'score_oauth_{provider}_selection')
            assert radio.value == 'b50'
            if mode != 'b50':
                radio.set_value(mode).run(timeout=60)
                assert not page.exception, str(page.exception)
            button = next(item for item in page.button if item.key == f'score_oauth_{provider}_save')
            button.click().run(timeout=60)
            assert not page.exception and not page.error, str(page.exception or page.error)
            archives = handler.get_user_save_list(username, game)
            assert len(archives) == 1, len(archives)
            records = handler.db.get_records_with_extented_data(archives[0]['id'])
            assert len(records) == len(selected), (len(records), len(selected))
            if mode == 'apb50':
                assert all(row['fc_status'] in ('ap', 'app') for row in records)
            # Reload from a new page session, with no OAuth snapshot injection.
            reload_page = AppTest.from_file(str(application/'st_pages/Setup_Achievements.py'))
            for key, value in dict(game_type=game, username=username, safe_username=username,
                                   config_saved=True, archive_name=archives[0]['archive_name']).items():
                reload_page.session_state[key] = value
            reload_page.run(timeout=60)
            assert not reload_page.exception and not reload_page.error, str(reload_page.exception or reload_page.error)
            loaded_game, loaded = handler.load_archive_as_old_b50_config(username, archives[0]['archive_name'])
            loaded_records = loaded if isinstance(loaded, list) else loaded['records']
            assert loaded_game == game and len(loaded_records) == len(selected)
            report[mode] = {'status': 'passed', 'selected': len(selected), 'saved': len(records),
                            'reloaded': len(loaded_records),
                            'past': sum(r['clip_title_name'].startswith('PastBest') for r in selected),
                            'new': sum(r['clip_title_name'].startswith('NewBest') for r in selected)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--game', choices=('maimai', 'chunithm'), required=True)
    parser.add_argument('--offline-snapshots', type=Path,
                        help='Replay previously authorized real snapshots against an extracted package')
    args = parser.parse_args()
    output, application = args.output.resolve(), args.application.resolve()
    snapshot_source = args.offline_snapshots.resolve() if args.offline_snapshots else None
    if not output.is_relative_to(ROOT/'test_output') or not (application/'st_app.py').is_file():
        parser.error('Use an explicit test_output child and a complete application')
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(application)
    sys.path.insert(0, str(application))
    from utils.score_oauth import ScoreSnapshot, load_public_config, start_oauth
    if snapshot_source:
        result = {}
        for provider in ('fish', 'lxns'):
            snapshot = ScoreSnapshot(**json.loads((snapshot_source/f'{provider}-snapshot.json').read_text(encoding='utf-8')))
            assert snapshot.provider == provider and snapshot.game_type == args.game
            result[provider] = verify_page(snapshot, application, output, provider, args.game)
        (output/'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return
    flows, results = {}, {}
    guard = threading.RLock()
    stopped = threading.Event()

    def status():
        with guard:
            data = {provider: {'status': flow.status, 'error': flow.error,
                               'verification': results.get(provider)} for provider, flow in flows.items()}
        return json.dumps(data, ensure_ascii=False, indent=2)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, body, content='text/html; charset=utf-8', code=200):
            body = body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', content)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/status':
                self.respond(status(), 'application/json; charset=utf-8')
                return
            if self.path in ('/authorize/fish', '/authorize/lxns'):
                provider = self.path.rsplit('/', 1)[1]
                with guard:
                    flow = flows.get(provider)
                    if flow is None or flow.status in ('failed', 'cancelled'):
                        if flow:
                            flow.cancel()
                        client, port = load_public_config(provider)
                        flow = start_oauth(provider, args.game, 'isolated-acceptance', client, port)
                        flows[provider] = flow
                        results.pop(provider, None)
                    location = flow.authorization_url if flow.status == 'awaiting_authorization' else '/'
                self.send_response(302)
                self.send_header('Location', location)
                self.end_headers()
                return
            body = f'''<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="4">
<title>{args.game} 真实授权与存档验收</title><style>body{{font-family:system-ui;max-width:950px;margin:35px auto}}a{{display:inline-block;padding:12px;background:#1265b8;color:white;margin-right:20px}}pre{{white-space:pre-wrap;background:#eee;padding:20px}}</style>
<h1>{args.game}：真实授权与页面保存验收</h1>
<p>请分别登录并确认读取成绩。程序会自动在独立数据库测试页面保存、重新打开和加载。</p>
<a href="/authorize/fish" target="_blank">水鱼授权</a><a href="/authorize/lxns" target="_blank">落雪授权</a>
<p>仅在 test_output 验收目录保存成绩和测试存档，不修改正式用户数据库。OAuth 令牌只在内存中。</p>'''
            self.respond(body+'<pre>'+html.escape(status())+'</pre>')

        def do_POST(self):
            if self.path == '/shutdown':
                self.respond('验证服务已关闭。')
                stopped.set()
            else:
                self.respond('Not found', code=404)

    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f'{args.game} live acceptance: http://127.0.0.1:8765/', flush=True)
    deadline = time.monotonic()+3600
    try:
        while not stopped.wait(1) and time.monotonic() < deadline:
            for provider, flow in list(flows.items()):
                if flow.status == 'ready' and provider not in results:
                    results[provider] = {'status': 'checking'}
                    try:
                        (output/f'{provider}-snapshot.json').write_text(json.dumps(asdict(flow.snapshot), ensure_ascii=False), encoding='utf-8')
                        checks = verify_page(flow.snapshot, application, output, provider, args.game)
                        results[provider] = {'status': 'passed', 'full_scores': len(flow.snapshot.payload['records']), 'page_checks': checks}
                    except Exception as exc:
                        results[provider] = {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}
                    (output/'verification.json').write_text(status(), encoding='utf-8')
                    print(status(), flush=True)
    finally:
        (output/'verification.json').write_text(status(), encoding='utf-8')
        for flow in flows.values():
            flow.cancel()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
