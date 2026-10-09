"""Exercise actual Streamlit widgets and save/reload in an isolated application."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def element(items, label):
    return next(item for item in items if item.label == label)


def healthy(page):
    assert not page.exception, page.exception


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--application',required=True,type=Path)
    args=parser.parse_args()
    root=args.application.resolve()
    if not root.name.startswith('release128') or not (root/'runtime/python.exe').is_file():
        parser.error('Use an independent release128 acceptance application')
    os.chdir(root)
    os.environ['USERPROFILE']=str(root/'test-home')
    (root/'test-home').mkdir(exist_ok=True)
    sys.path.insert(0,str(root))
    from streamlit.testing.v1 import AppTest
    from db_utils.DatabaseDataHandler import DatabaseDataHandler
    from utils.diagnostics import begin_report
    handler=DatabaseDataHandler(str(root/'mai_gen_videob50.db'))
    results=[]
    for game in ('maimai','chunithm'):
        archive_id,name=handler.create_new_archive('ui-'+game,game_type=game,sub_type='custom')
        page=AppTest.from_file(str(root/'st_pages/Make_Custom_Save.py'))
        page.session_state['game_type']=game
        page.session_state['username']='ui-'+game
        page.session_state['archive_name']=name
        page.session_state['archive_meta']={'game_type':game,'sub_type':'custom','game_version':'latest'}
        page.session_state['config_saved']=True
        class Upload(io.BytesIO):
            name=game+'_custom_import.xlsx'
        data=(root/f'static/import_templates/{game}_custom_import.xlsx').read_bytes()
        # AppTest has no file-picker driver. Only the file transport is injected;
        # parser, mapping, preview, widgets, transaction and reload run unchanged.
        def picker(*args, **kwargs):
            return Upload(data) if kwargs.get('type') == ['xlsx'] else None
        with patch('streamlit.file_uploader',side_effect=picker):
            page.run(timeout=60)
            healthy(page)
            element(page.button,'预览导入结果').click().run(timeout=60)
            healthy(page)
            element(page.checkbox,'我已检查预览并接受显示的默认值和跳过项').check().run(timeout=60)
            element(page.button,'导入到当前存档草稿').click().run(timeout=60)
            healthy(page)
            assert len(page.session_state['records']) == 2
            assert element(page.radio,'选择元数据和成绩数据的填充方式').value == '手动填写'
            assert element(page.button,'导入到当前存档草稿').disabled
            with handler.db.get_connection() as conn:
                assert conn.execute('SELECT COUNT(*) FROM records WHERE archive_id=?',(archive_id,)).fetchone()[0] == 0
            element(page.button,'提交存档修改').click().run(timeout=60)
            assert not page.error, page.error
            healthy(page)
            with handler.db.get_connection() as conn:
                stored=conn.execute('SELECT achievement,order_in_archive FROM records WHERE archive_id=? ORDER BY order_in_archive',(archive_id,)).fetchall()
                assert len(stored)==2
                assert stored[0]['achievement']==(100.5 if game=='maimai' else 1009000)
            element(page.button,'加载此存档进行编辑').click().run(timeout=60)
            healthy(page)
            assert len(page.session_state['records'])==2
            results.append({'game':game,'draft_did_not_write':True,'save_reload_passed':True,'manual_editor_selected':True})
    report=begin_report('UI report',root/'logs/error_reports')
    report.note('fixture','local diagnostic')
    config_path=root/'static/error_report_config.json'
    original_config=config_path.read_bytes()
    try:
        # Exercise unconfigured behavior without depending on the shipped live endpoint.
        # This is an isolated acceptance application; restore its config afterwards.
        config_path.write_text(json.dumps({'endpoint':'','prefix':'reports'}),encoding='utf-8')
        report_page=AppTest.from_file(str(root/'st_pages/Error_Reports.py'))
        report_page.run(timeout=60)
        healthy(report_page)
        assert element(report_page.button,'确认提交错误报告').disabled
        assert any('日志桶尚未配置' in item.value for item in report_page.info)
        element(report_page.checkbox,'我已查看提交内容，确认提交此报告').check().run(timeout=60)
        assert element(report_page.button,'确认提交错误报告').disabled
    finally:
        config_path.write_bytes(original_config)
    results.append({'report_page':True,'unconfigured_upload_disabled':True})
    (root/'release128-ui-verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':
    main()
