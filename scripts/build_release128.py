"""Build local application/runtime ZIPs from explicit distributable file sets."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.app_version import APP_VERSION


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
    parser.add_argument('--application-only',action='store_true',help='Rebuild only the app after documentation-only edits')
    args=parser.parse_args()
    runtime_application=args.runtime_application.resolve()
    if not runtime_application.is_relative_to(ROOT/'test_output') or not (runtime_application/'runtime/python.exe').is_file():
        parser.error('Use the isolated, validated runtime application under test_output')
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'dist'):
        parser.error('Local release output must be within dist')
    output.mkdir(parents=True,exist_ok=True)
    listed=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
    roots=('utils/','db_utils/','st_pages/','static/assets/','static/import_templates/','video_metadata/','md_res/','docs/')
    files={'st_app.py','README.md','LICENSE','requirements.txt','requirements-gpu.txt','global_config.yaml',
           'static/error_report_config.json','static/metadata_release_config.json','scripts/runtime_bootstrap.py',
           'scripts/export_public_metadata_release.py','scripts/verify_release128_network.py'}
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
    for name in ('st_app.py','static/error_report_config.json','static/metadata_release_config.json',
                 'static/import_templates/maimai_custom_import.xlsx','static/import_templates/chunithm_custom_import.xlsx',
                 'video_metadata/asset-manifest.json'):
        if name not in application:
            raise ValueError(f'Required application resource is not included: {name}')
    runtime={}
    for file in (runtime_application/'runtime').rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
            runtime[file.relative_to(runtime_application).as_posix()]=file
    for name in ('ffmpeg.exe','ffprobe.exe'):
        runtime[name]=runtime_application/name
    runtime['start.bat']=ROOT/'scripts/runtime-start.bat'
    runtime['runtime_bootstrap.py']=ROOT/'scripts/runtime_bootstrap.py'
    runtime['runtime-requirements.txt']=ROOT/'requirements.txt'
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
        'Local acceptance build: online endpoints and final CHUNITHM materials remain pending.\n').encode()
    app_zip=output/f'maigen_release_v{APP_VERSION}_local.zip'
    runtime_zip=output/f'runtime_v{APP_VERSION}_windows_x64_local.zip'
    write_archive(app_zip,application)
    if not args.application_only:
        write_archive(runtime_zip,runtime)
    report={'version':APP_VERSION,'status':'local_acceptance','application':str(app_zip),'runtime':str(runtime_zip),
            'application_file_count':len(application),'runtime_file_count':len(runtime),
            'runtime_archive_created':not args.application_only}
    (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
