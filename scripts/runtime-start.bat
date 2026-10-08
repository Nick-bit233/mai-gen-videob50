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
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUSERBASE="
set "PYTHONSTARTUP="
set "FFMPEG_BINARY=%~dp0ffmpeg.exe"
set "IMAGEIO_FFMPEG_EXE=%~dp0ffmpeg.exe"
set "PATH=%~dp0;%~dp0runtime;%~dp0runtime\Scripts;%PATH%"
if not exist "%~dp0logs\startup" mkdir "%~dp0logs\startup"
if not exist "%~dp0runtime\python312._pth" (
  echo Runtime isolation file is missing. Replace the complete runtime directory.
  echo Runtime isolation file is missing.>"%~dp0logs\startup\launcher-error.txt"
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" -I -X utf8 "%~dp0runtime_bootstrap.py" %* 2>"%~dp0logs\startup\launcher-error.txt"
if errorlevel 1 (
  echo Startup failed. See logs\startup\launcher-error.txt and the startup diagnostic files.
  pause
)
