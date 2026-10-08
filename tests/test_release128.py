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

from utils.diagnostics import begin_report, diagnostic_scope, execute, package_report, upload_report, redact_text
from utils.excel_import import ExcelCell, ExcelTable, suggest_mapping, convert_rows


class DiagnosticTests(unittest.TestCase):
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
        self.delay = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_PUT(self):
                owner.requests.append((self.path, dict(self.headers)))
                data = self.rfile.read(int(self.headers['Content-Length']))
                if owner.forbidden:
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
                self.send_response(200 if self.path in owner.objects else 404)
                self.end_headers()
                self.wfile.write(owner.objects.get(self.path, b''))

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def test_anonymous_put_retry_same_object_and_conflict(self):
        args = (b'complete diagnostic', '20261008T123456-abc', self.endpoint)
        first = upload_report(*args, allow_local_http=True)
        second = upload_report(*args, allow_local_http=True)
        self.assertEqual(first['object_key'], second['object_key'])
        self.assertEqual(len(self.objects), 1)
        self.assertTrue(all('Authorization' not in headers for _, headers in self.requests))
        self.assertTrue(all(headers['x-oss-forbid-overwrite'] == 'true' for _, headers in self.requests))
        with self.assertRaisesRegex(RuntimeError, '内容不同'):
            upload_report(b'changed', args[1], self.endpoint, allow_local_http=True)

    def test_invalid_config_or_oversize_never_sends_request(self):
        for endpoint, prefix, size in ((self.endpoint, 'reports', 100), ('https://host', '../other', 100),
                                      ('https://user:pass@host', 'reports', 100), ('https://host', 'reports', 1)):
            with self.assertRaises(ValueError):
                upload_report(b'bytes', 'report', endpoint, prefix, max_bytes=size)
        self.assertEqual(self.requests, [])

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
