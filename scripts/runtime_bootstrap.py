"""Portable-runtime preflight and launch using only the bundled interpreter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from datetime import datetime


def preflight(root: Path):
    runtime = root / "runtime"
    executable = runtime / "python.exe"
    if Path(sys.executable).resolve() != executable.resolve():
        raise RuntimeError("请使用包内 runtime/python.exe 启动，不要使用系统 Python。")
    pth = runtime / f"python{sys.version_info.major}{sys.version_info.minor}._pth"
    if not pth.is_file():
        raise RuntimeError("运行环境缺少隔离配置 _pth，请完整替换 runtime 目录。")
    for line in pth.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line == "import site":
            continue
        if line.startswith("import ") or not (runtime / line).resolve().is_relative_to(root):
            raise RuntimeError("运行环境搜索路径包含包外路径，请完整替换 runtime 目录。")
    import importlib.util
    modules = ('_distutils_hack', 'setuptools', 'streamlit', 'openpyxl', 'cv2', 'numpy',
               'moviepy', 'taichi', 'lxml', 'PIL', 'bilibili_api', 'pytubefix', 'pilmoji',
               'jieba', 'streamlit_sortables', 'streamlit_searchbox')
    for module in modules:
        spec = importlib.util.find_spec(module)
        if not spec or not spec.origin or not Path(spec.origin).resolve().is_relative_to(runtime):
            raise RuntimeError(f"运行环境缺少或混用了 {module}（来源：{getattr(spec, 'origin', None)}）；请完整重新解压程序和 runtime，检查同名文件，不要向系统 Python 安装依赖。")
    import _distutils_hack  # noqa: F401
    # setuptools before importing third-party modules verifies its .pth companion.
    import setuptools  # noqa: F401
    import streamlit  # noqa: F401
    import openpyxl  # noqa: F401
    if not (root / "st_app.py").is_file():
        raise RuntimeError("运行环境需要解压到含 st_app.py 的应用目录。")


def main():
    root = Path(__file__).resolve().parent
    if not (root / "st_app.py").exists() and (root.parent / "st_app.py").exists():
        root = root.parent
    logs = root / "logs" / "startup"
    logs.mkdir(parents=True, exist_ok=True)
    evidence = {"executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix,
                "sys_path": sys.path, "isolated": sys.flags.isolated,
                "environment": {key: os.environ.get(key) for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE")}}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (logs / f"{stamp}-environment.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        preflight(root)
    except Exception:
        error = traceback.format_exc()
        (logs / f"{stamp}-error.txt").write_text(error, encoding="utf-8")
        print(error, file=sys.stderr)
        return 1
    environment = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PYTHONSTARTUP"):
        environment.pop(key, None)
    cmd = [sys.executable, "-I", "-X", "utf8", "-m", "streamlit", "run", str(root / "st_app.py"), *sys.argv[1:]]
    with (logs / f"{stamp}-console.txt").open("wb") as log:
        process = subprocess.Popen(cmd, cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for line in iter(process.stdout.readline, b""):
                log.write(line)
                log.flush()
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
