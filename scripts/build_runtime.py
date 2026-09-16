"""Build a fresh, portable Windows x64 runtime; never modify an existing install."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.2.6'
PYTHON_VERSION = '3.12.10'  # Last python.org 3.12 Windows embeddable release.


def run(args, cwd=None):
    subprocess.run([str(v) for v in args], cwd=cwd, check=True)


def validate(stage):
    python = stage / 'runtime/python.exe'
    run([python, '-m', 'pip', 'check'], stage)
    run([python, '-c',
         'import cv2, numpy, moviepy, taichi, streamlit, lxml, PIL, '
         'bilibili_api, pytubefix, pilmoji, jieba, streamlit_sortables, streamlit_searchbox; '
         'assert cv2.__version__ == "4.14.0"; '
         'assert numpy.__version__ == "2.2.6"; '
         'print("Runtime imports OK")'], stage)
    for name in ('ffmpeg', 'ffprobe'):
        run([stage / f'{name}.exe', '-version'], stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / f'dist/runtime_v{VERSION}_windows_x64')
    parser.add_argument('--python-zip', type=Path)
    parser.add_argument('--ffmpeg-dir', type=Path)
    parser.add_argument('--ffmpeg-license', type=Path)
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--archive-only', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Resume only a marked staging directory from this version')
    parser.add_argument('--index-url', help='Optional pip package index for building the wheelhouse')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('This builder produces a Windows x64 runtime. Linux uses requirements-gpu.txt.')
    stage = args.output_dir.resolve()
    if not args.archive_only:
        marker = stage / '.runtime-build-version'
        if stage.exists() and not (args.resume and marker.is_file() and marker.read_text().strip() == VERSION):
            parser.error(f'Refusing to overwrite an existing directory: {stage}')
        if sys.version_info[:2] != (3, 12):
            parser.error('Use a full Python 3.12 interpreter to build the Windows wheelhouse.')
        if not args.ffmpeg_dir or not args.ffmpeg_license:
            parser.error('--ffmpeg-dir and --ffmpeg-license are required')
        for name in ('ffmpeg.exe', 'ffprobe.exe'):
            if not (args.ffmpeg_dir / name).is_file():
                parser.error(f'Missing {name}')
        runtime = stage / 'runtime'
        runtime.mkdir(parents=True, exist_ok=True)
        marker.write_text(VERSION, encoding='ascii')
        cache = ROOT / 'build/runtime-downloads'
        cache.mkdir(parents=True, exist_ok=True)
        archive = args.python_zip or cache / f'python-{PYTHON_VERSION}-embed-amd64.zip'
        if not archive.exists():
            urllib.request.urlretrieve(
                f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip', archive)
        with zipfile.ZipFile(archive) as z:
            # Reject unexpected archive paths rather than allowing extraction outside runtime.
            for entry in z.infolist():
                if not (runtime / entry.filename).resolve().is_relative_to(runtime):
                    raise ValueError(f'Unsafe Python archive entry: {entry.filename}')
            if not (runtime / 'python.exe').exists():
                z.extractall(runtime)
        (runtime / 'python312._pth').write_text(
            'python312.zip\n.\n..\nLib\nLib/site-packages\nimport site\n', encoding='utf-8')
        bootstrap = cache / 'get-pip.py'
        if not bootstrap.exists():
            urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', bootstrap)
        python = runtime / 'python.exe'
        if not (runtime / 'Lib/site-packages/pip/__init__.py').is_file():
            run([python, bootstrap, '--no-warn-script-location'], stage)
        wheels = ROOT / 'build/runtime-wheels'
        wheels.mkdir(parents=True, exist_ok=True)
        constraints = ROOT / 'scripts/runtime-constraints-win-py312.txt'
        wheel_command = [sys.executable, '-m', 'pip', 'wheel', '--disable-pip-version-check',
                         '--wheel-dir', wheels, '--find-links', wheels, '-c', constraints,
                         'setuptools==80.9.0', 'wheel==0.45.1',
                         '-r', ROOT / 'requirements-gpu.txt']
        if args.index_url:
            wheel_command += ['--index-url', args.index_url]
        run(wheel_command, ROOT)
        # Build pure-Python source packages with a full interpreter, never inside
        # the embedded distribution (whose isolated ._pth cannot run build envs).
        run([python, '-m', 'pip', 'install', '--no-index', '--find-links', wheels,
             '--no-warn-script-location', '-c', constraints, 'setuptools==80.9.0', 'wheel==0.45.1',
             '-r', ROOT / 'requirements-gpu.txt'], stage)
        for name in ('ffmpeg.exe', 'ffprobe.exe'):
            shutil.copy2(args.ffmpeg_dir / name, stage / name)
        licenses = stage / 'runtime-licenses'
        licenses.mkdir(exist_ok=True)
        shutil.copy2(args.ffmpeg_license, licenses / 'FFmpeg-LICENSE.txt')
        (licenses / 'SOURCES.txt').write_text(
            'Python 3.12.10: https://www.python.org/downloads/release/python-31210/\n'
            'FFmpeg 7.1 Windows full build: https://www.gyan.dev/ffmpeg/builds/\n'
            'FFmpeg source: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz\n'
            'Python and package licenses are also retained inside runtime.\n', encoding='utf-8')
        shutil.copy2(ROOT / 'scripts/runtime-start.bat', stage / 'start.bat')
        shutil.copy2(ROOT / 'requirements.txt', stage / 'runtime-requirements.txt')
        (stage / 'runtime-gpu-requirements.txt').write_text(
            (ROOT / 'requirements-gpu.txt').read_text(encoding='utf-8').replace(
                '-r requirements.txt', '-r runtime-requirements.txt'), encoding='utf-8')
        shutil.copy2(constraints, stage / 'runtime-build-constraints.txt')
        frozen = subprocess.check_output([str(python), '-m', 'pip', 'freeze', '--all'], text=True)
        (stage / 'runtime-installed.txt').write_text(frozen, encoding='utf-8')
        (stage / 'RUNTIME-README.txt').write_text(
            f'mai-gen-videob50 runtime v{VERSION} (Windows x64)\n\n'
            'Extract all contents into the v1.2.6 application directory, then run start.bat.\n'
            'For upgrades, rename the previous runtime directory before extracting; do not mix old DLLs/packages.\n'
            'Includes Python 3.12.10, Taichi 1.7.4, OpenCV 4.14.0.94, NumPy 2.2.6, MoviePy 2.2.1, FFmpeg/FFprobe 7.1.\n'
            'No system Python or separate Taichi install is required. GPU use is optional.\n'
            'GPU drivers are provided by your GPU vendor. CPU rendering remains available.\n'
            'Linux: use Python 3.10-3.12, requirements-gpu.txt, and system FFmpeg/FFprobe.\n'
            'Advanced ffmpeg-concat Node.js plugins remain optional and are not included.\n'
            'runtime-installed.txt records the full dependency set; runtime-licenses contains source/license information.\n',
            encoding='utf-8')
    validate(stage)
    if not args.stage_only:
        archive = stage.parent / (stage.name + '.zip')
        if archive.exists():
            parser.error(f'Refusing to overwrite an existing archive: {archive}')
        # Use a content-root archive: extraction goes directly alongside st_app.py.
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for file in sorted(stage.rglob('*')):
                if (file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc'
                        and file.name != '.runtime-build-version'):
                    z.write(file, file.relative_to(stage))
        print(f'Archive: {archive} ({archive.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
