@echo off
setlocal enabledelayedexpansion

:: ============================================
::  mai-gen-videob50 Runtime Builder
::  用于构建 Windows 嵌入式 Python 运行环境
:: ============================================

set VERSION=v1.1
set PYTHON_VERSION=3.12.8
set PYTHON_EMBED=python-%PYTHON_VERSION%-embed-amd64
set RUNTIME_DIR=runtime_%VERSION%

echo.
echo ============================================
echo   mai-gen-videob50 Runtime Builder
echo   Version: %VERSION%
echo   Python:  %PYTHON_VERSION%
echo ============================================
echo.

:: 检查 requirements.txt 是否存在
if not exist "..\requirements.txt" (
    echo [ERROR] requirements.txt not found!
    echo Please run this script from the scripts directory.
    pause
    exit /b 1
)

:: 1. 下载 Python Embedded
echo [1/6] Downloading Python %PYTHON_VERSION% Embedded...
if not exist "%PYTHON_EMBED%.zip" (
    curl -L -o %PYTHON_EMBED%.zip https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_EMBED%.zip
    if errorlevel 1 (
        echo [ERROR] Failed to download Python Embedded!
        pause
        exit /b 1
    )
) else (
    echo       Already downloaded, skipping.
)

:: 2. 清理并创建 runtime 目录
echo [2/6] Preparing runtime directory...
if exist "%RUNTIME_DIR%" (
    rmdir /s /q "%RUNTIME_DIR%"
)
mkdir "%RUNTIME_DIR%"

:: 3. 解压 Python Embedded
echo [3/6] Extracting Python Embedded...
tar -xf %PYTHON_EMBED%.zip -C %RUNTIME_DIR%
if errorlevel 1 (
    echo [ERROR] Failed to extract Python Embedded!
    pause
    exit /b 1
)

:: 4. 配置 pip 支持（修改 ._pth 文件）
echo [4/6] Configuring pip support...
cd %RUNTIME_DIR%
set PTH_FILE=python%PYTHON_VERSION:~0,1%%PYTHON_VERSION:~2,2%._pth
if not exist "%PTH_FILE%" (
    :: 尝试查找 ._pth 文件
    for %%f in (*._pth) do set PTH_FILE=%%f
)

echo %PYTHON_VERSION%>> %PTH_FILE%
echo Lib>> %PTH_FILE%
echo Lib\site-packages>> %PTH_FILE%
echo.>> %PTH_FILE%
echo import site>> %PTH_FILE%
echo       Configured %PTH_FILE%

:: 5. 安装 pip
echo [5/6] Installing pip...
if not exist "get-pip.py" (
    curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
)
python.exe get-pip.py --no-warn-script-location -q
if errorlevel 1 (
    echo [ERROR] Failed to install pip!
    pause
    exit /b 1
)

:: 6. 安装项目依赖
echo [6/6] Installing dependencies...
python.exe -m pip install -r ..\..\requirements.txt --no-warn-script-location -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

:: 显示安装的包
echo.
echo Installed packages:
python.exe -m pip list --format=freeze

:: 7. 打包
echo.
echo [7/6] Creating archive...
cd ..
if exist "%RUNTIME_DIR%.zip" del "%RUNTIME_DIR%.zip"
tar -a -c -f %RUNTIME_DIR%.zip %RUNTIME_DIR%

:: 完成
echo.
echo ============================================
echo   Build complete!
echo   Output: %RUNTIME_DIR%.zip
echo ============================================
echo.

:: 显示文件大小
for %%A in (%RUNTIME_DIR%.zip) do echo Size: %%~zA bytes (approx. %%~zAKB)

pause
