"""Streamlit checks in a marked disposable application copy, never user data."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def element(elements, label):
    return next(item for item in elements if item.label == label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root', required=True, type=Path)
    args = parser.parse_args()
    root = args.app_root.resolve()
    if not (root / '.runtime-acceptance-workspace').is_file():
        parser.error('Refusing to seed data outside a marked disposable application copy')
    os.chdir(root)
    sys.path.insert(0, str(root))
    home = root / 'test-home'
    prefs = home / '.mai-gen-videob50'
    prefs.mkdir(parents=True, exist_ok=True)
    (prefs / 'metadata_update.json').write_text(json.dumps({'last_update': datetime.datetime.now().isoformat()}))
    (root / 'music_metadata').mkdir(exist_ok=True)
    for name in ['mai_fusion_data.json', 'chuni_fusion_data.json']:
        (root / 'music_metadata' / name).write_text('[]')
    from streamlit.testing.v1 import AppTest
    from db_utils.DatabaseDataHandler import get_database_handler, DatabaseDataHandler
    import utils.VideoUtils as videos
    import yaml
    with patch.object(Path, 'home', return_value=home):
        app = AppTest.from_file(str(root / 'st_app.py'))
        app.session_state['game_type'] = 'maimai'
        app.session_state['video_metadata_auto_update_attempted'] = True
        app.run(timeout=45)
        assert not app.exception, app.exception
        assert any('v1.2.6' in caption.value for caption in app.caption)
        assert app.session_state['taichi_accel_installed']
        handler = get_database_handler()
        archive_id, name = handler.create_new_archive('runtime-ui-test')
        page = AppTest.from_file(str(root / 'st_pages/Composite_Videos.py'))
        for key, value in dict(game_type='maimai', username='runtime-ui-test',
                               archive_name=name, archive_id=archive_id).items():
            page.session_state[key] = value
        configs = ([{'clip_title_name': 'fixture'}], [{'duration': 1}], [{'duration': 1}])
        with patch.object(DatabaseDataHandler, 'load_full_config_for_composite_video', return_value=configs), \
             patch.object(videos, 'render_complete_full_video',
                          return_value={'status': 'error', 'info': 'injected decode error'}) as renderer:
            page.run(timeout=45)
            assert not page.exception, page.exception
            element(page.checkbox, '启用 Taichi GPU 加速').check().run(timeout=45)
            element(page.selectbox, 'GPU 后端').select('vulkan').run(timeout=45)
            element(page.button, '开始生成视频').click().run(timeout=45)
            assert not page.exception, page.exception
            assert renderer.call_args.kwargs['taichi_backend'] == 'vulkan'
            assert renderer.call_args.kwargs['use_gpu_accel'] is True
            assert any('injected decode error' in error.value for error in page.error)
            assert not any('完整视频生成结束' in item.value for item in page.success)
            config = yaml.full_load((root / 'global_config.yaml').read_text(encoding='utf-8'))
            assert config['TAICHI_BACKEND'] == 'vulkan'
    result = {'homepage': 'passed', 'version': '1.2.6', 'gpu_installed': True,
              'backend_selection_and_save': 'passed', 'error_not_success': 'passed'}
    (root / 'ui-verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
