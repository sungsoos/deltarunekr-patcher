#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${SCRIPT_DIR}/dist"
RELEASE_DIR="${SCRIPT_DIR}/target/release"

echo "=== cargo로 빌드 중... ==="
cargo build --release

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

OS_NAME="$(uname -s)"

case "${OS_NAME}" in
    Linux*)
        echo "=== 바이너리 복사 중 ==="
        cp "${RELEASE_DIR}/deltarunekr_patcher" "${DIST_DIR}/Linux-Patcher-bin"
        chmod +x "${DIST_DIR}/Linux-Patcher-bin"
        echo "[+] 리눅스 바이너리 복사됨: ${DIST_DIR}/Linux-Patcher-bin"

        ;;

    Darwin*)
        echo "=== .app 번들 생성 중 ==="
        APP_BUNDLE="${DIST_DIR}/MacOS-Patcher.app"
        mkdir -p "${APP_BUNDLE}/Contents/MacOS"
        mkdir -p "${APP_BUNDLE}/Contents/Resources"

        cp "${RELEASE_DIR}/deltarunekr_patcher" "${APP_BUNDLE}/Contents/MacOS/"

        # macOS 패치 파일만 복사 (용량 최적화)
        mkdir -p "${APP_BUNDLE}/Contents/MacOS/patch"
        if [ -f "${SCRIPT_DIR}/patch/deterwill.json" ]; then
            cp "${SCRIPT_DIR}/patch/deterwill.json" "${APP_BUNDLE}/Contents/MacOS/patch/"
        fi
        if [ -d "${SCRIPT_DIR}/patch/lang_mac" ]; then
            cp -r "${SCRIPT_DIR}/patch/lang_mac" "${APP_BUNDLE}/Contents/MacOS/patch/"
        fi
        if [ -d "${SCRIPT_DIR}/patch/xdelta_mac" ]; then
            cp -r "${SCRIPT_DIR}/patch/xdelta_mac" "${APP_BUNDLE}/Contents/MacOS/patch/"
        fi

        # assets 복사 및 타 플랫폼 바이너리 제거
        cp -r "${SCRIPT_DIR}/assets" "${APP_BUNDLE}/Contents/MacOS/"
        rm -f "${APP_BUNDLE}/Contents/MacOS/assets/bin/xdelta3_win.exe" "${APP_BUNDLE}/Contents/MacOS/assets/bin/xdelta3_linux"
        chmod +x "${APP_BUNDLE}/Contents/MacOS/assets/bin/xdelta3_mac" 2>/dev/null || true
        chmod +x "${APP_BUNDLE}/Contents/MacOS/deltarunekr_patcher"

        if [ -f "${SCRIPT_DIR}/assets/icon.icns" ]; then
            cp "${SCRIPT_DIR}/assets/icon.icns" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
        fi

        cat <<EOF > "${APP_BUNDLE}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>deltarunekr_patcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>kr.deltarune.patcher</string>
    <key>CFBundleName</key>
    <string>델타룬 한국어 패처</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
</dict>
</plist>
EOF
        echo "[+] macOS .app 번들 생성됨: ${APP_BUNDLE}"
        ;;

    *)
        echo "[!] 지원되지 않는 플랫폼: ${OS_NAME}"
        ;;
esac

echo ""
echo "=== 빌드 성공 ==="
echo "${DIST_DIR}에 생성됨"
ls -lh "${DIST_DIR}"
