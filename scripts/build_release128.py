"""Build application/runtime ZIPs from tracked distributable file sets."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.app_version import APP_VERSION
from utils.themes import DEFAULT_STYLES
from utils.metadata_release import validate_charts
from utils.video_metadata import validate_desktop_manifest


def write_archive(target, entries):
    if target.exists():
        raise ValueError(f'Refusing to overwrite an existing archive: {target}')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,source in sorted(entries.items()):
            if isinstance(source,bytes):
                archive.writestr(name,source)
            else:
                archive.write(source,name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-application',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--application-only',action='store_true',help='Rebuild only the app when the validated runtime is unchanged')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--release',action='store_true',help='Build final release archives without acceptance labels')
    mode.add_argument('--manual-acceptance',action='store_true',help='Label the build for local human acceptance, without publishing')
    args=parser.parse_args()
    runtime_application=args.runtime_application.resolve()
    if not runtime_application.is_relative_to(ROOT/'test_output') or not (runtime_application/'runtime/python.exe').is_file():
        parser.error('Use the isolated, validated runtime application under test_output')
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'dist'):
        parser.error('Local release output must be within dist')
    output.mkdir(parents=True,exist_ok=True)
    listed=subprocess.check_output(['git','ls-files','--cached','-z'],cwd=ROOT).decode('utf-8').split('\0')
    roots=('utils/','db_utils/','st_pages/','static/assets/','static/import_templates/','video_metadata/','md_res/','docs/','external_scripts/')
    files={'st_app.py','README.md','LICENSE','requirements.txt','requirements-gpu.txt','global_config.yaml',
           'static/error_report_config.json','static/metadata_release_config.json','static/oauth_public_clients.json','scripts/runtime_bootstrap.py',
           'scripts/export_public_metadata_release.py'}
    application={}
    for name in listed:
        if name and (name.startswith(roots) or name in files) and '__pycache__' not in name and not name.endswith(('.db','.sqlite','.pyc')):
            source=ROOT/name
            if source.is_file() and source.resolve().is_relative_to(ROOT):
                application[name]=source
    # The default render settings must come from the repository, never a user's edited configuration.
    application['global_config.yaml']=subprocess.check_output(['git','show','HEAD:global_config.yaml'],cwd=ROOT)
    for game,filename in [('maimai','mai_fusion_data.json'),('chunithm','chuni_fusion_data.json')]:
        source=ROOT/'music_metadata'/filename
        payload=json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(payload,list) or not payload:
            raise ValueError(f'Missing bundled {game} chart snapshot')
        application[f'music_metadata/{filename}']=source
        if game == 'maimai':
            chart_identities = validate_charts(payload)
    manifest = validate_desktop_manifest(json.loads((ROOT/'video_metadata/asset-manifest.json').read_text(encoding='utf-8')))
    if any((a['song_title'],a['artist'],a['chart_type'],a['difficulty']) not in chart_identities for a in manifest['assets']):
        raise ValueError('Bundled video manifest does not match the bundled maimai charts')
    for styles in DEFAULT_STYLES.values():
        for style in styles:
            for key,value in style['asset_paths'].items():
                resource = (ROOT/value).resolve()
                if resource.is_dir():
                    continue
                if not resource.is_file() or not resource.is_relative_to(ROOT) or resource.relative_to(ROOT).as_posix() not in application:
                    raise ValueError(f"Missing preset resource: {style['style_name']} / {key} / {value}")
    for name in ('st_app.py','static/error_report_config.json','static/metadata_release_config.json','static/oauth_public_clients.json',
                 'static/import_templates/maimai_custom_import.xlsx','static/import_templates/chunithm_custom_import.xlsx',
                 'video_metadata/asset-manifest.json'):
        if name not in application:
            raise ValueError(f'Required application resource is not included: {name}')
    for level in range(5):
        name = f'static/assets/images/Chunithm/Frames/{level}.png'
        if name not in application:
            raise ValueError(f'Required CHUNITHM difficulty frame is not included: {name}')
    runtime={}
    for file in (runtime_application/'runtime').rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
            runtime[file.relative_to(runtime_application).as_posix()]=file
    for name in ('ffmpeg.exe','ffprobe.exe'):
        runtime[name]=runtime_application/name
    runtime['start.bat']=ROOT/'scripts/runtime-start.bat'
    runtime['runtime_bootstrap.py']=ROOT/'scripts/runtime_bootstrap.py'
    runtime['runtime-requirements.txt']=ROOT/'requirements.txt'
    runtime['runtime-gpu-requirements.txt']=(ROOT/'requirements-gpu.txt').read_text(encoding='utf-8').replace(
        '-r requirements.txt','-r runtime-requirements.txt').encode('utf-8')
    runtime['runtime-build-constraints.txt']=ROOT/'scripts/runtime-constraints-win-py312.txt'
    licenses=runtime_application/'runtime-licenses'
    if not (licenses/'FFmpeg-LICENSE.txt').is_file():
        raise ValueError('Validated runtime application must include runtime-licenses/FFmpeg-LICENSE.txt')
    for file in licenses.iterdir():
        if file.is_file():
            runtime['runtime-licenses/'+file.name]=file
    runtime['runtime-installed.txt']=subprocess.check_output([str(runtime_application/'runtime/python.exe'),'-m','pip','freeze','--all'])
    runtime['RUNTIME-README.txt']=(f'Runtime {APP_VERSION}, Windows x64. Extract beside st_app.py and run start.bat.\n'
        'For upgrades, rename the old runtime directory and extract the complete new runtime; do not mix packages.\n'
        'Python 3.12.10, NumPy 2.2.6, OpenCV 4.14.0.94, MoviePy 2.2.1, Taichi 1.7.4 and openpyxl 3.1.5.\n'
        'Includes FFmpeg/FFprobe 7.1; no system Python is required. GPU drivers are supplied by your GPU vendor.\n'
        'See README.md for usage and runtime-licenses for dependency source/license information.\n').encode('utf-8')
    label='' if args.release else ('_manual' if args.manual_acceptance else '_local')
    app_zip=output/f'maigen_release_v{APP_VERSION}{label}.zip'
    runtime_zip=output/f'runtime_v{APP_VERSION}_windows_x64{label}.zip'
    write_archive(app_zip,application)
    if not args.application_only:
        write_archive(runtime_zip,runtime)
    report={'version':APP_VERSION,'status':'release' if args.release else ('manual_acceptance_pending' if args.manual_acceptance else 'local_acceptance'),'application':str(app_zip),'runtime':None if args.application_only else str(runtime_zip),
            'application_file_count':len(application),'runtime_file_count':len(runtime),
            'runtime_archive_created':not args.application_only}
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
