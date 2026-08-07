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

        echo "=== AppImage 생성 중 ==="
        if command -v appimagetool >/dev/null 2>&1; then
            APPDIR="${DIST_DIR}/AppDir"
            mkdir -p "${APPDIR}/usr/bin"
            mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

            cp "${RELEASE_DIR}/deltarunekr_patcher" "${APPDIR}/usr/bin/"
            cp -r "${SCRIPT_DIR}/patch" "${APPDIR}/usr/bin/"
            cp -r "${SCRIPT_DIR}/assets" "${APPDIR}/usr/bin/"
            cp "${SCRIPT_DIR}/assets/icon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/deltarunekr_patcher.png"
            cp "${SCRIPT_DIR}/assets/icon.png" "${APPDIR}/deltarunekr_patcher.png"

            cat <<EOF > "${APPDIR}/deltarunekr_patcher.desktop"
[Desktop Entry]
Name=델타룬 한국어 패처
Exec=deltarunekr_patcher
Icon=deltarunekr_patcher
Type=Application
Categories=Game;Utility;
Comment=델타룬 한국어 패처
EOF

            cat <<'EOF' > "${APPDIR}/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/deltarunekr_patcher" "$@"
EOF
            chmod +x "${APPDIR}/AppRun"

            ARCH=x86_64 appimagetool "${APPDIR}" "${DIST_DIR}/Linux-Patcher.AppImage"
            rm -rf "${APPDIR}"
            echo "[+] AppImage 생성됨: ${DIST_DIR}/Linux-Patcher.AppImage"
        else
            echo "[-] 경고: appimagetool이 없습니다. AppImage 빌드 건너뜀."
        fi
        ;;

    Darwin*)
        echo "=== .app 번들 생성 중 ==="
        APP_BUNDLE="${DIST_DIR}/MacOS-Patcher.app"
        mkdir -p "${APP_BUNDLE}/Contents/MacOS"
        mkdir -p "${APP_BUNDLE}/Contents/Resources"

        cp "${RELEASE_DIR}/deltarunekr_patcher" "${APP_BUNDLE}/Contents/MacOS/"
        cp -r "${SCRIPT_DIR}/patch" "${APP_BUNDLE}/Contents/MacOS/"
        cp -r "${SCRIPT_DIR}/assets" "${APP_BUNDLE}/Contents/MacOS/"
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
