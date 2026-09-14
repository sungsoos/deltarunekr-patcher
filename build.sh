#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${SCRIPT_DIR}/dist"
RELEASE_DIR="${SCRIPT_DIR}/target/release"

TARGET="${1:-}"

echo "=== cargo로 빌드 중... ==="
if [ -n "${TARGET}" ]; then
    cargo build --release --target "${TARGET}"
    RELEASE_DIR="${SCRIPT_DIR}/target/${TARGET}/release"
else
    cargo build --release
    RELEASE_DIR="${SCRIPT_DIR}/target/release"
fi

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

OS_NAME="$(uname -s)"

case "${OS_NAME}" in
    Linux*)
        echo "=== 바이너리 복사 중 ==="
        cp "${RELEASE_DIR}/deltarunekr_patcher" "${DIST_DIR}/Linux-Patcher-bin"
        chmod +x "${DIST_DIR}/Linux-Patcher-bin"
        echo "[+] 리눅스 단일 바이너리 생성됨: ${DIST_DIR}/Linux-Patcher-bin"
        ;;

    Darwin*)
        echo "=== 바이너리 복사 중 ==="
        case "${TARGET}" in
            x86_64*)
                BIN_NAME="MacOS-Patcher-x86_64"
                ;;
            aarch64*|arm64*)
                BIN_NAME="MacOS-Patcher-arm64"
                ;;
            *)
                case "$(uname -m)" in
                    x86_64) BIN_NAME="MacOS-Patcher-x86_64" ;;
                    arm64)  BIN_NAME="MacOS-Patcher-arm64" ;;
                    *)      BIN_NAME="MacOS-Patcher-bin" ;;
                esac
                ;;
        esac
        cp "${RELEASE_DIR}/deltarunekr_patcher" "${DIST_DIR}/${BIN_NAME}"
        chmod +x "${DIST_DIR}/${BIN_NAME}"
        echo "[+] macOS 단일 바이너리 생성됨: ${DIST_DIR}/${BIN_NAME}"
        ;;

    *)
        echo "[!] 지원되지 않는 플랫폼: ${OS_NAME}"
        ;;
esac

echo ""
echo "=== 빌드 성공 ==="
echo "${DIST_DIR}에 생성됨"
ls -lh "${DIST_DIR}"
