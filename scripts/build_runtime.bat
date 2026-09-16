@echo off
python "%~dp0build_runtime.py" %*
exit /b %errorlevel%
