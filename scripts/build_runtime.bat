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
echo [1/7] Downloading Python %PYTHON_VERSION% Embedded...
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_EMBED%.zip
if not exist "%PYTHON_EMBED%.zip" (
    echo       URL: %PYTHON_URL%
    curl -L -o %PYTHON_EMBED%.zip %PYTHON_URL%
    if errorlevel 1 (
        echo [ERROR] Failed to download Python Embedded!
        pause
        exit /b 1
    )
) else (
    echo       Already downloaded, skipping.
)

:: 2. 清理并创建 runtime 目录
echo [2/7] Preparing runtime directory...
if exist "%RUNTIME_DIR%" (
    rmdir /s /q "%RUNTIME_DIR%"
)
mkdir "%RUNTIME_DIR%"

:: 3. 解压 Python Embedded (使用 PowerShell)
echo [3/7] Extracting Python Embedded...
powershell -Command "Expand-Archive -Path %PYTHON_EMBED%.zip -DestinationPath %RUNTIME_DIR% -Force"
if errorlevel 1 (
    echo [ERROR] Failed to extract Python Embedded!
    pause
    exit /b 1
)

:: 4. 查找并配置 ._pth 文件
echo [4/7] Configuring pip support...
cd %RUNTIME_DIR%
set PTH_FILE=
for %%f in (*._pth) do set PTH_FILE=%%f

if "%PTH_FILE%"=="" (
    echo [ERROR] Cannot find ._pth file!
    pause
    exit /b 1
)

echo       Found: %PTH_FILE%
echo       Adding pip paths...

:: 备份原文件并添加新内容
copy %PTH_FILE% %PTH_FILE%.bak >nul
(
    echo %PYTHON_VERSION%
    echo Lib
    echo Lib\site-packages
    echo.
    echo import site
) > %PTH_FILE%

:: 5. 下载并安装 pip
echo [5/7] Installing pip...
if not exist "get-pip.py" (
    curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
)
python.exe get-pip.py --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Failed to install pip!
    pause
    exit /b 1
)

:: 6. 安装项目依赖
echo [6/7] Installing dependencies from requirements.txt...
echo       This may take several minutes...
python.exe -m pip install -r ..\..\requirements.txt --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

:: 显示安装的包数量
echo.
echo Installed packages:
for /f %%i in ('python.exe -m pip list --format=freeze ^| find /c /v ""') do echo       Total: %%i packages

:: 7. 清理临时文件
echo.
echo [7/7] Cleaning up...
del get-pip.py 2>nul
del %PTH_FILE%.bak 2>nul

:: 8. 打包
echo       Creating archive...
cd ..
if exist "%RUNTIME_DIR%.zip" del "%RUNTIME_DIR%.zip"
powershell -Command "Compress-Archive -Path %RUNTIME_DIR% -DestinationPath %RUNTIME_DIR%.zip -CompressionLevel Optimal"

:: 完成
echo.
echo ============================================
echo   Build complete!
echo   Output: %RUNTIME_DIR%.zip
for %%A in (%RUNTIME_DIR%.zip) do echo   Size: %%~zA bytes
echo ============================================
echo.

pause
