@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ===============
echo 패처 빌드 중...
echo ===============

set "SCRIPT_DIR=%~dp0"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "RELEASE_DIR=%SCRIPT_DIR%target\release"

echo === cargo로 빌드 ===
cargo build --release
if %ERRORLEVEL% NEQ 0 (
    echo 오류: Cargo 빌드 실패!
    exit /b %ERRORLEVEL%
)

if exist "%DIST_DIR%" rd /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"

echo === 파일 복사 중 ===
copy "%RELEASE_DIR%\deltarunekr_patcher.exe" "%DIST_DIR%\Windows-Patcher.exe" >nul
if %ERRORLEVEL% NEQ 0 (
    echo 오류: .exe 복사 실패!
    exit /b %ERRORLEVEL%
)

echo.
echo 빌드 성공!
exit /b 0
