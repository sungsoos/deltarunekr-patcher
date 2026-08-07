# 델타룬 한글 패처
최적화된 델타룬 한글 패처
> 웹 버전 패처: [https://dtkr.sungsoos.kr](https://dtkr.sungsoos.kr/)

## 실행 및 사용 방법

### 1. 미리 빌드된 프로그램 실행
1.  [여기서](http://git.sungsoos.kr/sungsoos/deltarunekr_patcher/releases/latest) 최신 버전을 다운로드 받으세요.
2. 실행하세요.
> Windows Server 2025, MacOS 15, Ubuntu 24.04에서 빌드되었습니다 (Github Actions)

  

### 2. 소스 코드로 실행하기
```bash
cargo run
```

## 델타룬 패치 폴더 구조
패처 빌드 & 실행(릴리즈된 파일 제외)시 `patch/` 디렉터리에 아래와 같은 패치 파일들이 준비되어 있어야 합니다.

```text
patch/
├── lang/ # 게임 내 적용될 한글 언어 파일/폴더 (Windows/Linux)
│
├── lang_mac/ # macOS 전용 한글 언어 파일/폴더
│
├── xdelta/ # xdelta 바이너리 패치 파일 (Windows/Linux)
│ ├── launcher.xdelta # 런처 데이터 패치 파일
│ └── ch<i>.xdelta # 챕터 <i> 패치 파일
│
└── xdelta_mac/ # macOS 전용 xdelta 바이너리 패치 파일
   ├── launcher.xdelta # macOS 런처 데이터 패치 파일
   └── ch<i>.xdelta # macOS 챕터 <i> 패치 파일
```

## 요구 사항
### 미리 빌드된 파일을 실행할 시
- 수정되지 않은 델타룬 게임
- Windows 10+ 혹은 MacOS 15+ (테스트 필요) 혹은 AppImage를 실행할 수 있는 Linux 배포판
### 소스코드 실행 시
- **Rust**: 1.75 이상 (stable)
- `cargo`가 설치되어 있어야 합니다. ([rustup.rs](https://rustup.rs) 에서 설치)
- Linux의 경우 추가 시스템 패키지 필요:
```bash
sudo apt-get install build-essential pkg-config libx11-dev libxcb1-dev libxcursor-dev libxinerama-dev libxi-dev libxrandr-dev libfontconfig1-dev
```
> *다른 배포판의 경우는 알아서 찾아 보시길...*

## 패치 적용 방법
1. 프로그램을 실행하면 델타룬이 자동으로 감지되어 표시됩니다.
2. 자동 감지가 되지 않은 경우 **[폴더 선택]** 버튼을 눌러 DELTARUNE이 설치된 폴더를 직접 선택합니다.
3.  **[패치 적용]** 버튼을 클릭하여 패치를 진행합니다.
4. 하단 로그 창에서 패치 진행 상황을 확인하고 완료 메시지가 뜨면 게임을 실행합니다.

## 실행 파일 빌드
`build.sh` (Linux/macOS) 또는 `build.bat` (Windows) 스크립트로 릴리즈 바이너리를 빌드합니다.
빌드 결과물은 `dist/` 디렉터리에 생성됩니다.

### 사전 준비
- **Rust** (stable): [rustup.rs](https://rustup.rs) 에서 설치
- **Linux 추가 패키지**:
```bash
sudo apt-get install build-essential pkg-config libx11-dev libxcb1-dev libxcursor-dev libxinerama-dev libxi-dev libxrandr-dev libfontconfig1-dev libfuse2 desktop-file-utils
```
> *다른 배포판의 경우는 알아서 찾아 보시길...*
- **Linux AppImage 생성 시 추가**:
```bash
sudo wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /usr/local/bin/appimagetool
sudo chmod +x /usr/local/bin/appimagetool
```

### Windows (`.exe` 빌드)
```cmd
build.bat
```
- 빌드 결과물: `dist/Windows-Patcher.exe`

### Linux (단일 바이너리 & AppImage 빌드)
```bash
chmod +x build.sh
./build_all.sh
```
- 빌드 결과물: `dist/Linux-Patcher-bin`, `dist/Linux-Patcher.AppImage`

### macOS (`.app` 번들 빌드)
```bash
chmod +x build.sh
./build_all.sh
```
- 빌드 결과물: `dist/MacOS-Patcher.app`

### 직접 cargo로 빌드 (모든 플랫폼)
```bash
cargo build --release
```
- 빌드 결과물: `target/release/deltarunekr_patcher` (Linux/macOS) / `target/release/deltarunekr_patcher.exe` (Windows)
- `patch/`, `assets/` 디렉터리가 바이너리와 같은 위치에 있어야 합니다.

## 구조
```text
deltarunekr_patcher/
├── assets/               # UI 리소스 (폰트, 테두리 텍스처, 아이콘)
│   ├── DeltaDotumKR.ttf
│   ├── border_texture.png
│   └── icon.ico
├── patch/                # 패치 파일 저장용 디렉터리
│   ├── lang/
│   └── xdelta/
├── src/
│   └── main.rs           # Rust 메인 애플리케이션
├── ui/
│   └── appwindow.slint   # Slint UI 정의
├── build.rs              # Cargo 빌드 스크립트 (리소스 번들링)
├── Cargo.toml
├── build.bat             # Windows 빌드 스크립트
├── build.sh          # Linux / macOS 빌드 스크립트
└── README.md
```

## 📜 라이선스 및 참고 사항 (Notice)
- 델타돋움체: qhtjr1116 제작, 링크: [https://eocnd1116.github.io/qhtjrFont/index.html?type=1&n=0](https://eocnd1116.github.io/qhtjrFont/index.html?type=1&n=0)
- 한국어 패치: dtkrpatchteam 제작, 링크: [https://www.deltarunekr.kro.kr/](https://www.deltarunekr.kro.kr/)
- DELTARUNE의 원작권은 **Toby Fox**에게 있습니다.