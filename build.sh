#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/orig/src/assets"
if [ ! -d "$ASSETS_DIR" ]; then
    ASSETS_DIR="$SCRIPT_DIR/assets"
fi

echo "========================================================"
echo " Building DELTARUNE KR Patcher (AppImage & .app)"
echo "========================================================"

if ! command -v pyinstaller &> /dev/null; then
    echo "Error: PyInstaller is not installed!"
    echo "Install via: pip install pyinstaller"
    exit 1
fi

OS_NAME="$(uname -s)"

if [ "$OS_NAME" = "Linux" ]; then
    echo "--- Building Linux Onefile Binary & AppImage ---"
    
    # 1. PyInstaller build using spec file
    pyinstaller --noconfirm "$SCRIPT_DIR/DELTARUNE_KR_Patcher.spec"

    if command -v upx &> /dev/null; then
        echo "Compressing executable binary with UPX..."
        upx "$SCRIPT_DIR/dist/Patcher" 2>/dev/null || true
    fi

    # 2. Build AppImage if appimagetool is available
    APP_DIR="$SCRIPT_DIR/dist/Patcher.AppDir"
    mkdir -p "$APP_DIR/usr/bin"
    cp "$SCRIPT_DIR/dist/Patcher" "$APP_DIR/usr/bin/"
    
    cat << 'EOF' > "$APP_DIR/AppRun"
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/Patcher" "$@"
EOF
    chmod +x "$APP_DIR/AppRun"

    cat << 'EOF' > "$APP_DIR/patcher.desktop"
[Desktop Entry]
Name=Patcher
Exec=AppRun
Icon=icon
Type=Application
Categories=Game;
EOF

    if [ -f "$ASSETS_DIR/icon.png" ]; then
        cp "$ASSETS_DIR/icon.png" "$APP_DIR/icon.png"
        cp "$ASSETS_DIR/icon.png" "$APP_DIR/.DirIcon"
    elif [ -f "$ASSETS_DIR/icon.ico" ]; then
        python3 -c "from PySide6.QtGui import QImage; img = QImage('$ASSETS_DIR/icon.ico'); img.save('$APP_DIR/icon.png')" 2>/dev/null || cp "$ASSETS_DIR/icon.ico" "$APP_DIR/icon.ico"
        if [ -f "$APP_DIR/icon.png" ]; then
            cp "$APP_DIR/icon.png" "$APP_DIR/.DirIcon"
        fi
    fi

    if command -v appimagetool &> /dev/null; then
        echo "Creating AppImage with appimagetool..."
        rm -f "$SCRIPT_DIR/dist/Patcher.AppImage"
        appimagetool "$APP_DIR" "$SCRIPT_DIR/dist/Patcher.AppImage"
        echo "AppImage created: $SCRIPT_DIR/dist/Patcher.AppImage"
    else
        echo "Standalone single executable created at:"
        echo "  $SCRIPT_DIR/dist/Patcher"
    fi

elif [ "$OS_NAME" = "Darwin" ]; then
    echo "--- Building macOS .app & Standalone Binary ---"
    
    pyinstaller --noconfirm "$SCRIPT_DIR/DELTARUNE_KR_Patcher.spec"
        
    echo "macOS Application Bundle created at:"
    echo "  $SCRIPT_DIR/dist/Patcher.app"

else
    echo "Unsupported OS: $OS_NAME for build.sh script."
fi

echo "========================================================"
echo " Build process finished."
echo "========================================================"
