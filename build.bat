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

pyinstaller --noconfirm "%SCRIPT_DIR%DELTARUNE_KR_Patcher.spec"

where upx >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Compressing executable with UPX (maximum compression --best)...
    upx --best "%SCRIPT_DIR%dist\델타룬 한글 패처.exe" 2>nul
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build completed successfully!
    echo Executable generated at: %SCRIPT_DIR%dist\DELTARUNE_KR_Patcher.exe
    echo Compressing executable into ZIP...
    powershell -Command "Compress-Archive -Path '%SCRIPT_DIR%dist\델타룬 한글 패처.exe' -DestinationPath '%SCRIPT_DIR%dist\windows-2.1.3.zip' -Force"
    echo Compressed release archive created at: %SCRIPT_DIR%dist\windows-2.1.3.zip
) else (
    echo.
    echo Build failed with error code: %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
