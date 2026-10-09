"""1.2.8 behavioral coverage: actual child processes and local anonymous HTTP."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import zipfile

from utils.diagnostics import begin_report, diagnostic_scope, execute, package_report, upload_report, redact_text, ReportUploadConflict
from utils.excel_import import ExcelCell, ExcelTable, suggest_mapping, convert_rows


class DiagnosticTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows sharing-handle regression')
    def test_manifest_publication_survives_real_windows_read_lock(self):
        import ctypes
        with tempfile.TemporaryDirectory() as directory, diagnostic_scope(root=directory):
            report = begin_report('sharing test', directory)
            path = report.directory/'report.json'
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                           ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
            kernel.CreateFileW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            def release():
                time.sleep(.1)
                kernel.CloseHandle(handle)
            reader = threading.Thread(target=release)
            reader.start()
            import os
            try:
                with patch('utils.diagnostics.os.replace', wraps=os.replace) as replacement:
                    report.note('after_lock', 'complete manifest')
                    self.assertGreater(replacement.call_count, 1)
            finally:
                reader.join()
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['events'][-1]['value'], 'complete manifest')
            self.assertEqual(list(report.directory.glob('*.tmp')), [])

    def test_full_stderr_and_first_failure_survive_later_success(self):
        with tempfile.TemporaryDirectory() as directory, diagnostic_scope(root=directory):
            report = begin_report('test', directory)
            command = [sys.executable, '-c', "import sys; sys.stderr.write('unsupported device\\n' + 'x'*18000 + '\\nlast error'); sys.exit(7)"]
            with self.assertRaises(RuntimeError):
                execute(command, 'hardware')
            execute([sys.executable, '-c', "print('software succeeded')"], 'software')
            saved = json.loads((report.directory / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual([a['returncode'] for a in saved['attempts']], [7, 0])
            self.assertEqual(saved['attempts'][0]['category'], 'unsupported_device')
            raw = (report.directory / saved['attempts'][0]['stderr']).read_text()
            self.assertIn('unsupported device', raw)
            self.assertIn('last error', raw)
            self.assertGreater(len(raw), 18000)
            with zipfile.ZipFile(io.BytesIO(package_report(report.directory))) as archive:
                self.assertIn('last error', archive.read(saved['attempts'][0]['stderr']).decode())

    def test_launch_failure_and_timeout_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory, diagnostic_scope(root=directory):
            report = begin_report('test', directory)
            with self.assertRaises(OSError):
                execute([str(Path(directory) / 'missing-program')], 'missing')
            with self.assertRaises(subprocess.TimeoutExpired):
                execute([sys.executable, '-c', 'import time; time.sleep(3)'], 'timeout', timeout=0.03)
            self.assertEqual(len(report.manifest['attempts']), 2)
            self.assertTrue(all(a['status'] == 'failed' for a in report.manifest['attempts']))
            self.assertEqual(len(list(report.directory.glob('exception-*.txt'))), 2)

    def test_package_whitelist_and_credentials_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            report = begin_report('test', directory)
            report.note('fixture', {'token': 'secret-one', 'Authorization': 'Bearer secret-two'})
            (report.directory / 'database.db').write_bytes(b'private database')
            (report.directory / 'exception-0010.txt').write_text(
                'Authorization: Bearer secret-three\nCookie: session=secret-four\nhttps://oss.example/object?Signature=secret-five\nuser@example.com')
            package = package_report(report.directory)
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                self.assertNotIn('database.db', archive.namelist())
                text = '\n'.join(archive.read(n).decode() for n in archive.namelist())
                for secret in ('secret-one', 'secret-two', 'secret-three', 'secret-four', 'secret-five', 'user@example.com'):
                    self.assertNotIn(secret, text)
                json.loads(archive.read('report.json'))


class ReportHTTPTests(unittest.TestCase):
    def setUp(self):
        self.objects = {}
        self.requests = []
        self.forbidden = False
        self.public_read = False
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_PUT(self):
                owner.requests.append(('PUT', self.path, dict(self.headers)))
                data = self.rfile.read(int(self.headers['Content-Length']))
                if owner.forbidden or not self.path.startswith('/reports/'):
                    self.send_response(403)
                    self.end_headers()
                    return
                if owner.delay:
                    time.sleep(owner.delay)
                if self.path in owner.objects:
                    self.send_response(409)
                else:
                    owner.objects[self.path] = data
                    self.send_response(200)
                self.send_header('x-oss-request-id', 'local-request')
                self.end_headers()

            def do_GET(self):
                owner.requests.append(('GET', self.path, dict(self.headers)))
                self.send_response(200 if owner.public_read else 403)
                self.end_headers()

            def do_HEAD(self):
                owner.requests.append(('HEAD', self.path, dict(self.headers)))
                self.send_response(403)
                self.end_headers()

            def do_DELETE(self):
                owner.requests.append(('DELETE', self.path, dict(self.headers)))
                self.send_response(403)
                self.end_headers()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_write_only_upload_and_conflicts_never_read_or_overwrite(self):
        args = (b'complete diagnostic', '20261008T123456-abc', self.endpoint)
        first = upload_report(*args, allow_local_http=True)
        with self.assertRaises(ReportUploadConflict) as repeated:
            upload_report(*args, allow_local_http=True)
        self.assertEqual(first['object_key'], repeated.exception.object_key)
        with self.assertRaisesRegex(ReportUploadConflict, '无法确认'):
            upload_report(b'changed', args[1], self.endpoint, allow_local_http=True)
        self.assertEqual(len(self.objects), 1)
        self.assertEqual(self.objects['/'+first['object_key']], args[0])
        self.assertEqual([method for method, _, _ in self.requests], ['PUT', 'PUT', 'PUT'])
        self.assertTrue(all('Authorization' not in headers for _, _, headers in self.requests))
        self.assertTrue(all(headers['x-oss-forbid-overwrite'] == 'true' for _, _, headers in self.requests))

    def test_network_acceptance_checks_write_only_policy(self):
        import requests
        from scripts.verify_release128_network import check_report_policy
        uploaded = upload_report(b'synthetic report', 'policy-test', self.endpoint, allow_local_http=True)
        with requests.Session() as client:
            client.trust_env = False
            checks = check_report_policy(client, uploaded, self.endpoint, 'reports', check_negative=True)
        self.assertEqual({k: v for k, v in checks.items() if k != 'outside_test_key'},
                         {'get': 403, 'head': 403, 'list': 403, 'delete_synthetic_report': 403, 'outside_prefix_put': 403})
        self.assertEqual(len(self.objects), 1)
        self.assertTrue(all('Authorization' not in headers for _, _, headers in self.requests))

    def test_network_acceptance_rejects_public_read_and_preserves_failure_evidence(self):
        from scripts import verify_release128_network as verifier
        self.public_read = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'static').mkdir()
            (root/'static/error_report_config.json').write_text(
                json.dumps({'endpoint': self.endpoint, 'prefix': 'reports'}), encoding='utf-8')
            def submit(data, report_id, endpoint, prefix):
                return upload_report(data, report_id, endpoint, prefix, allow_local_http=True)
            with patch.object(verifier, 'ROOT', root), \
                    patch.object(verifier, 'upload_report', side_effect=submit), \
                    patch.object(sys, 'argv', ['verify', '--submit-test-report', '--check-negative-policy']), \
                    diagnostic_scope(root=root/'diagnostics'):
                with self.assertRaisesRegex(RuntimeError, 'write-only policy check failed'):
                    verifier.main()
            evidence = next((root/'test_output').glob('release128-network-*/verification.json'))
            saved = json.loads(evidence.read_text(encoding='utf-8'))
            self.assertEqual(saved['status'], 'failed')
            self.assertEqual(saved['negative_policy']['get'], 200)
            self.assertNotIn('anonymous_read_denied', saved['report'])

    def test_invalid_config_or_oversize_never_sends_request(self):
        for endpoint, prefix, size in ((self.endpoint, 'reports', 100), ('https://host', '../other', 100),
                                      ('https://user:pass@host', 'reports', 100), ('https://host', 'reports', 1)):
            with self.assertRaises(ValueError):
                upload_report(b'bytes', 'report', endpoint, prefix, max_bytes=size)
        self.assertEqual(self.requests, [])

    def test_report_page_consent_failure_success_and_duplicate_session(self):
        from streamlit.testing.v1 import AppTest
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory, diagnostic_scope(root=directory):
            report = begin_report('synthetic page test', directory)

            def submit(data, report_id, endpoint, prefix):
                # Only the transport is redirected to the actual local write-only server.
                return upload_report(data, report_id, self.endpoint, prefix, allow_local_http=True)

            with patch('utils.diagnostics.reports_root', return_value=Path(directory)), \
                    patch('utils.diagnostics.upload_report', side_effect=submit):
                page = AppTest.from_file(str(root/'st_pages/Error_Reports.py')).run(timeout=30)
                def button():
                    return next(item for item in page.button if item.label == '确认提交错误报告')
                self.assertFalse(page.exception)
                self.assertTrue(button().disabled)
                self.assertEqual(self.requests, [])
                page.checkbox[0].check().run(timeout=30)
                self.forbidden = True
                button().click().run(timeout=30)
                self.assertFalse(page.exception)
                self.assertTrue(page.error)
                self.assertFalse(page.success)
                self.assertNotIn(f'submitted_{report.report_id}', page.session_state)
                self.forbidden = False
                button().click().run(timeout=30)
                self.assertFalse(page.exception)
                self.assertTrue(page.success)
                page.run(timeout=30)
                self.assertTrue(button().disabled)
                self.assertEqual(len(self.requests), 2)
                self.assertEqual(len(self.objects), 1)

                # A new session cannot verify an existing object and must show a warning.
                page = AppTest.from_file(str(root/'st_pages/Error_Reports.py')).run(timeout=30)
                page.checkbox[0].check().run(timeout=30)
                button().click().run(timeout=30)
                self.assertFalse(page.exception)
                self.assertTrue(page.warning)
                self.assertFalse(page.success)
                self.assertNotIn(f'submitted_{report.report_id}', page.session_state)
                self.assertTrue(all(method == 'PUT' for method, _, _ in self.requests))
                self.assertEqual(len(self.objects), 1)

    def test_http_forbidden_and_timeout_preserve_local_payload_for_retry(self):
        data=b'complete local evidence'
        self.forbidden=True
        with self.assertRaisesRegex(RuntimeError,'403'):
            upload_report(data,'20261008T123456-error',self.endpoint,allow_local_http=True)
        self.assertEqual(self.objects,{})
        self.forbidden=False
        self.delay=.15
        import requests
        with self.assertRaises(requests.Timeout):
            upload_report(data,'20261008T123456-timeout',self.endpoint,allow_local_http=True,timeout=.02)
        time.sleep(.2)  # The server accepted this timed-out request; its reply was lost.
        self.delay=0
        with self.assertRaises(ReportUploadConflict):
            upload_report(data,'20261008T123456-timeout',self.endpoint,allow_local_http=True)
        self.assertTrue(all(method == 'PUT' for method, _, _ in self.requests))
        self.assertEqual(len(self.objects), 1)
        self.assertEqual(data,b'complete local evidence')


class ExcelConversionTests(unittest.TestCase):
    def table(self, headers, values):
        return ExcelTable(headers, [(2, [v if isinstance(v, ExcelCell) else ExcelCell(v) for v in values])], ['Sheet1'], 'Sheet1')

    def test_shipped_workbooks_read_and_round_trip_their_typed_fields(self):
        from utils.excel_import import read_excel
        root = Path(__file__).resolve().parents[1]
        for game in ('maimai','chunithm'):
            table = read_excel((root / f'static/import_templates/{game}_custom_import.xlsx').read_bytes())
            mapping, _ = suggest_mapping(table.headers,game)
            rows, preview = convert_rows(table,mapping,game)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['raw_data']['source_song_id'],'00001')
            self.assertEqual(rows[0]['achievement'],100.5 if game == 'maimai' else 1009000)
            self.assertFalse(any(row['状态'] == '无法导入' for row in preview))

    def test_percentage_precision_explicit_rating_and_leading_zero_source_id(self):
        table = self.table(['曲名','曲师','定数','达成率','Rating','歌曲ID'],
                           ['曲目','曲师',14.5,ExcelCell(1.005,'0.0000%'),234,'000123'])
        mapping, _ = suggest_mapping(table.headers, 'maimai')
        rows, preview = convert_rows(table, mapping, 'maimai')
        self.assertEqual(rows[0]['achievement'], 100.5)
        self.assertEqual(rows[0]['dx_rating'], 234)
        self.assertEqual(rows[0]['raw_data']['source_song_id'], '000123')
        self.assertTrue(rows[0]['chart_data']['song_id'].startswith('custom_excel_'))
        self.assertNotEqual(rows[0]['chart_data']['song_id'], '000123')

    def test_uncached_formula_invalid_enums_and_score_are_visible_defaults(self):
        table = self.table(['曲名','曲师','定数','成绩','难度','FC'],
                           ['曲目','曲师','?',ExcelCell(None,uncached_formula=True),'impossible','wrong'])
        mapping, _ = suggest_mapping(table.headers, 'chunithm')
        rows, preview = convert_rows(table, mapping, 'chunithm')
        self.assertEqual(rows[0]['achievement'], 0)
        self.assertEqual(rows[0]['chuni_rating'], 0)
        self.assertEqual(rows[0]['chart_data']['level_index'], 3)
        self.assertIn('公式无缓存', preview[0]['提示'])
        self.assertIn('无法识别', preview[0]['提示'])

    def test_duplicate_field_mapping_rejected_and_fuzzy_is_only_candidate(self):
        mapping, suggestions = suggest_mapping(['曲名','song_name','achievemen'], 'maimai')
        self.assertIsNone(mapping[0])
        self.assertIsNone(mapping[1])
        self.assertIsNone(mapping[2])
        self.assertIn('achievement', suggestions[2])
        with self.assertRaisesRegex(ValueError, '重复列映射'):
            convert_rows(self.table(['a','b'],['a','b']), {0:'song_name',1:'song_name'}, 'maimai')

    def test_jacket_survives_original_deletion_and_failed_save_rolls_back(self):
        from PIL import Image
        from db_utils.DatabaseManager import DatabaseManager
        from db_utils.record_transaction import save_archive_records
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = DatabaseManager(str(root / 'fixture.db'))
            with db.get_connection() as conn:
                user = conn.execute("INSERT INTO users(username) VALUES ('fixture')").lastrowid
                archive = conn.execute("INSERT INTO archives(user_id,archive_name,game_type) VALUES (?, 'import','maimai')", (user,)).lastrowid
                conn.commit()
            image = root / '中文 曲绘.png'
            Image.new('RGB', (240,120), 'red').save(image)
            table = self.table(['曲名','曲师','定数','曲绘路径'], ['导入','曲师',14.5,str(image)])
            mapping, _ = suggest_mapping(table.headers, 'maimai')
            rows, _ = convert_rows(table, mapping, 'maimai')
            save_archive_records(db, archive, rows)
            with db.get_connection() as conn:
                saved = conn.execute("SELECT file_path FROM assets WHERE asset_type='custom_jacket'").fetchone()[0]
            image.unlink()
            with Image.open(saved) as retained:
                self.assertEqual(retained.size, (400,400))
            image2 = root / 'another.png'
            Image.new('RGB',(20,20),'blue').save(image2)
            candidate = dict(rows[0], _import_jacket_path=str(image2))
            broken = dict(rows[0], chart_data={'game_type':'chunithm','song_id':'wrong'})
            broken.pop('_import_jacket_path', None)
            with self.assertRaisesRegex(ValueError, '游戏类型'):
                save_archive_records(db, archive, [candidate, broken])
            with db.get_connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT record_count FROM archives WHERE id=?',(archive,)).fetchone()[0], 1)
            self.assertEqual(len(list((root/'static/assets/custom_jackets').glob('*.png'))), 1)


class MetadataReleaseTests(unittest.TestCase):
    def test_default_video_update_delegates_to_release_without_legacy_http(self):
        from utils.video_metadata import update_video_manifest
        with patch('utils.metadata_release.update_release', return_value={
                'updated':True,'metadata_store_version':'paired-release','generated_at':'2026-10-09T00:00:00Z',
                'usable_asset_count':2,'message':'paired'}) as updater, \
                patch('utils.video_metadata.get_video_manifest_status', return_value={}), \
                patch('utils.video_metadata.requests.get', side_effect=AssertionError('unexpected legacy GET')):
            result = update_video_manifest()
        updater.assert_called_once_with()
        self.assertEqual(result.metadata_store_version, 'paired-release')
        self.assertTrue(result.updated)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.documents = {}
        self.paths = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def do_GET(self):
                owner.paths.append(self.path)
                document = owner.documents.get(self.path)
                self.send_response(200 if document is not None else 403)
                self.end_headers()
                if document is not None:
                    self.wfile.write(json.dumps(document).encode())
        self.server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/metadata_json/active-release.json'
        self.publish('r1', 1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.folder.cleanup()

    def publish(self, revision, row_version):
        from utils.metadata_release import FILES
        self.documents['/metadata_json/active-release.json'] = {'kind':'catalog_active_release','schema_version':1,'game_type':'maimai','release_id':'local',
            'release_revision':revision,'metadata_store_version':revision,'state_row_version':row_version}
        prefix = f'/metadata_json/releases/{revision}/'
        self.documents[prefix+'release.json'] = {'schema_version':1,'game_type':'maimai','release_revision':revision,'metadata_store_version':revision,'files':FILES}
        self.documents[prefix+'mai_fusion_data.json'] = [{'title':'Example','artist':'Composer','charts_info':[{'type':'dx','difficulty':3}]}]
        self.documents[prefix+'asset-manifest.json'] = {'game_type':'maimai','generated_at':'2026-10-08T00:00:00Z','metadata_store_version':revision,'release_revision':revision,
          'assets':[{'chart_key':'chart','asset_id':'asset','song_title':'Example','artist':'Composer','chart_type':'dx','difficulty':3,
                     'source_type':'bilibili','source_id':'BV1NYtKeXEad','source_pid':1,'source_url':'https://www.bilibili.com/video/BV1NYtKeXEad?p=1','review_status':'reviewed',
                     'internal_oss_key':'PRIVATE-KEY'}]}

    def test_pair_published_atomically_and_failed_update_keeps_existing_pair(self):
        from utils.metadata_release import update_release, resolve_metadata_file
        first = update_release(url=self.url, root=self.root, allow_local_http=True)
        self.assertTrue(first['updated'], first)
        old_charts = resolve_metadata_file('mai_fusion_data.json', self.root)
        old_manifest = resolve_metadata_file('asset-manifest.json', self.root)
        self.assertEqual(old_charts.parent,old_manifest.parent)
        self.assertNotIn('PRIVATE-KEY', old_manifest.read_text())
        self.assertEqual(self.paths.count('/metadata_json/active-release.json'),1)
        self.publish('r2',2)
        self.documents['/metadata_json/releases/r2/asset-manifest.json']['metadata_store_version'] = 'wrong'
        failed = update_release(url=self.url, root=self.root, allow_local_http=True)
        self.assertFalse(failed['updated'])
        self.assertEqual(resolve_metadata_file('mai_fusion_data.json',self.root),old_charts)
        self.assertEqual(resolve_metadata_file('asset-manifest.json',self.root),old_manifest)
        self.assertEqual(len(list((self.root/'music_metadata/releases').iterdir())),1)

    def test_operation_snapshot_keeps_old_pair_during_successful_update(self):
        from utils.metadata_release import update_release, resolve_metadata_file, metadata_snapshot
        self.assertTrue(update_release(url=self.url,root=self.root,allow_local_http=True)['updated'])
        with metadata_snapshot(self.root):
            old = resolve_metadata_file('mai_fusion_data.json',self.root)
            self.publish('r2',2)
            self.assertTrue(update_release(url=self.url,root=self.root,allow_local_http=True)['updated'])
            self.assertEqual(resolve_metadata_file('mai_fusion_data.json',self.root),old)
            self.assertEqual(resolve_metadata_file('asset-manifest.json',self.root).parent,old.parent)
        self.assertNotEqual(resolve_metadata_file('mai_fusion_data.json',self.root),old)

    def test_public_catalog_null_artist_and_fullwidth_title_remain_exactly_matchable(self):
        from copy import deepcopy
        from utils.metadata_release import update_release, resolve_metadata_file
        from utils.video_metadata import resolve_maimai_video
        prefix = '/metadata_json/releases/r1/'
        charts = [{'title':'\u3000','artist':'x0o0x_','charts_info':[{'type':'dx','difficulty':3}]},
                  {'title':'Link(CoF)','artist':None,'charts_info':[{'type':'dx','difficulty':2}]}]
        self.documents[prefix+'mai_fusion_data.json'] = charts
        original = deepcopy(charts)
        manifest = self.documents[prefix+'asset-manifest.json']
        first = manifest['assets'][0]
        first.update(song_title='\u3000', artist='x0o0x_')
        manifest['assets'].append(dict(first, chart_key='unknown-artist', asset_id='second',
                                       song_title='Link(CoF)', artist=None, difficulty=2))
        result = update_release(url=self.url, root=self.root, allow_local_http=True)
        self.assertTrue(result['updated'], result)
        saved = json.loads(resolve_metadata_file('mai_fusion_data.json', self.root).read_text(encoding='utf-8'))
        self.assertEqual(saved[0]['title'], '\u3000')
        self.assertEqual(saved[1]['artist'], '')
        self.assertEqual(charts, original)
        videos = json.loads(resolve_metadata_file('asset-manifest.json', self.root).read_text(encoding='utf-8'))
        for title, artist, difficulty in (('\u3000','x0o0x_',3),('Link(CoF)',None,2)):
            matched = resolve_maimai_video({'game_type':'maimai','song_name':title,'artist':artist,
                                            'chart_type':1,'level_index':difficulty}, videos)
            self.assertIsNotNone(matched)
            self.assertEqual(matched['id'], first['source_id'])
        self.publish('r2', 2)
        self.documents['/metadata_json/releases/r2/mai_fusion_data.json'][0]['title'] = ' '
        self.assertFalse(update_release(url=self.url, root=self.root, allow_local_http=True)['updated'])
        self.assertEqual(resolve_metadata_file('mai_fusion_data.json', self.root).parent,
                         resolve_metadata_file('asset-manifest.json', self.root).parent)

    def test_wrong_game_or_traversal_cannot_download_or_publish_release(self):
        from utils.metadata_release import update_release
        for changes in ({'game_type':'chunithm'},{'release_revision':'../other'}):
            self.publish('r1',1)
            self.documents['/metadata_json/active-release.json'].update(changes)
            result=update_release(url=self.url,root=self.root,allow_local_http=True)
            self.assertFalse(result['updated'])
        self.assertFalse((self.root/'music_metadata/current-release.json').exists())
        self.assertTrue(all(path.endswith('/active-release.json') for path in self.paths))

    def test_unchanged_release_fetches_only_pointer_and_creates_no_duplicate(self):
        from utils.metadata_release import update_release
        self.assertTrue(update_release(url=self.url,root=self.root,allow_local_http=True)['updated'])
        before=len(self.paths)
        result=update_release(url=self.url,root=self.root,allow_local_http=True)
        self.assertTrue(result['updated'])
        self.assertFalse(result['changed'])
        self.assertEqual(self.paths[before:],['/metadata_json/active-release.json'])
        self.assertEqual(len(list((self.root/'music_metadata/releases').iterdir())),1)

    def test_separate_public_projection_and_export_keep_private_inputs_untouched(self):
        from utils.metadata_release import update_release
        from scripts.export_public_metadata_release import export_release
        source=self.root/'private-input'
        source.mkdir()
        for filename in ('mai_fusion_data.json','asset-manifest.json','release.json'):
            (source/filename).write_text(json.dumps(self.documents['/metadata_json/releases/r1/'+filename]),encoding='utf-8')
        before=(source/'asset-manifest.json').read_bytes()
        output=self.root/'public-output'
        export_release(source,output)
        self.assertEqual((source/'asset-manifest.json').read_bytes(),before)
        self.assertNotIn('PRIVATE-KEY',(output/'asset-manifest.json').read_text())
        for filename in ('mai_fusion_data.json','asset-manifest.json','release.json'):
            self.documents['/desktop/releases/r1/'+filename]=json.loads((output/filename).read_text())
            self.documents.pop('/metadata_json/releases/r1/'+filename)
        base=self.url.rsplit('/metadata_json',1)[0]+'/desktop/releases/{revision}/'
        result=update_release(url=self.url,files_root=base,root=self.root,allow_local_http=True)
        self.assertTrue(result['updated'],result)
        self.assertTrue(any(path.startswith('/desktop/releases/r1/') for path in self.paths))


if __name__ == '__main__':
    unittest.main()
