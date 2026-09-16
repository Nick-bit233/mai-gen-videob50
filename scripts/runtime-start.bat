@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0st_app.py" (
  echo Please extract this runtime into the application directory containing st_app.py.
  pause
  exit /b 1
)
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "FFMPEG_BINARY=%~dp0ffmpeg.exe"
set "IMAGEIO_FFMPEG_EXE=%~dp0ffmpeg.exe"
set "PATH=%~dp0;%~dp0runtime;%~dp0runtime\Scripts;%PATH%"
"%~dp0runtime\python.exe" -m streamlit run "%~dp0st_app.py" %*
if errorlevel 1 pause
