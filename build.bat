@echo off
chcp 65001 >nul
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

set "SCRIPT_DIR=%~dp0"
set "ASSETS_DIR=%SCRIPT_DIR%orig\src\assets"

if not exist "%ASSETS_DIR%" (
    set "ASSETS_DIR=%SCRIPT_DIR%assets"
)

echo Using assets directory: %ASSETS_DIR%

pyinstaller --noconfirm "%SCRIPT_DIR%DELTARUNE_KR_Patcher.spec"
if %ERRORLEVEL% NEQ 0 (
    echo Build failed during PyInstaller execution.
    exit /b %ERRORLEVEL%
)

where upx >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Compressing executable with UPX...
    upx "%SCRIPT_DIR%dist\DELTARUNE_KR_Patcher.exe" 2>nul
)

echo.
echo Build completed successfully!
echo Executable generated at: %SCRIPT_DIR%dist\DELTARUNE_KR_Patcher.exe
