@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo Building DELTARUNE KR Patcher Windows Executable (.exe)
echo ========================================================

where pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: PyInstaller is not installed or not in PATH!
    echo Please install PyInstaller via: pip install pyinstaller
    exit /b 1
)

set SCRIPT_DIR=%~dp0
set ASSETS_DIR=%SCRIPT_DIR%orig\src\assets

if not exist "%ASSETS_DIR%" (
    set ASSETS_DIR=%SCRIPT_DIR%assets
)

echo Using assets directory: %ASSETS_DIR%

set PATCH_DIR=%SCRIPT_DIR%patch
set PATCH_DATA=
if exist "%PATCH_DIR%" (
    set PATCH_DATA=--add-data "%PATCH_DIR%;patch"
)

pyinstaller --noconfirm --onefile --windowed ^
    --name "DELTARUNE_KR_Patcher" ^
    --icon "%ASSETS_DIR%\icon.ico" ^
    --add-data "%ASSETS_DIR%;assets" ^
    !PATCH_DATA! ^
    "%SCRIPT_DIR%patcher.py"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build completed successfully!
    echo Executable generated at: %SCRIPT_DIR%dist\DELTARUNE_KR_Patcher.exe
) else (
    echo.
    echo Build failed with error code: %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
