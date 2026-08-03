# 델타룬 한글 패처
최적화된 델타룬 한글 패처

## 실행 및 사용 방법

### 1. 미리 빌드된 프로그램 실행
1.  [여기서](http://git.sungsoos.kr/sungsoos/deltarunekr_patcher/releases/latest) 최신 버전은 다운로드 받으세요.
2. 실행하세요.
> Windows Server 2025, MacOS 15, Ubuntu 24.04에서 빌드되었습니다 (Github Actions)

  

### 2. 소스 코드로 실행하기
```bash
python patcher.py
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
-  **Python**: 3.10 이상 권장
-  **필수 패키지**:
```bash
pip install PySide6 pyxdelta
```

## 패치 적용 방법
1. 프로그램을 실행하면 델타룬이 자동으로 감지되어 표시됩니다.
2. 자동 감지가 되지 않은 경우 **[폴더 선택]** 버튼을 눌러 DELTARUNE이 설치된 폴더를 직접 선택합니다.
3.  **[패치 적용]** 버튼을 클릭하여 패치를 진행합니다.
4. 하단 로그 창에서 패치 진행 상황을 확인하고 완료 메시지가 뜨면 게임을 실행합니다.

## 실행 파일 빌드
PyInstaller를 이용해 Windows, Linux, macOS용 단일 실행 파일 및 앱 패키지를 생성할 수 있습니다.
빌드 완료 시 UPX로 압축된 .AppImage + 바이너리 혹은 .exe 혹은 .app 형태로 배포 파일이 자동 생성됩니다.

### 사전 준비 (도구 및 패키지 설치)
-  **Python 패키지**:
```bash
pip install pyinstaller PySide6 pyxdelta
```
-  **빌드 및 압축 도구 (선택/권장)**:
	-  `upx`: 바이너리 실행 파일 용량 압축용
	-  `tar` / `xz` (`xz-utils`): 배포용 `.tar.xz` 아카이브 생성용
	-  `appimagetool`: Linux `.AppImage` 생성용 (선택)

### Windows (`.exe` 빌드)
`build.bat` 스크립트를 실행합니다.
```cmd
build.bat
```
- 빌드 결과물: `dist/DELTARUNE_KR_Patcher.exe`

### Linux (단일 바이너리 & AppImage 빌드)
`build.sh` 스크립트를 실행합니다.
```bash
chmod  +x  build.sh
./build.sh
```
- 빌드 결과물: `dist/DELTARUNE_KR_Patcher` (필요 시 `appimagetool`이 설치되어 있으면 `.AppImage`도 자동 생성)

### macOS (`.app` 번들 빌드)
`build.sh` 스크립트를 실행합니다.
```bash
chmod  +x  build.sh
./build.sh
```
- 빌드 결과물: `dist/DELTARUNE_KR_Patcher.app`

## 구조
```text
deltarunekr_patcher/
├── assets/ # UI 리소스 (폰트, 테두리 텍스처, 아이콘)
│ ├── DeltaDotumKR.ttf
│ ├── border_texture.png
│ └── icon.ico
├── patch/ # 패치 파일 저장용 디렉터리
│ ├── lang/
│ └── xdelta/
├── patcher.py # PySide6 GUI 메인 애플리케이션
├── build.bat # Windows 빌드 스크립트
├── build.sh # Linux / macOS 빌드 스크립트
├── DELTARUNE_KR_Patcher.spec # PyInstaller 설정 파일
└── README.md
```

## 📜 라이선스 및 참고 사항 (Notice)
- 델타돋움체: qhtjr1116 제작, 링크: [https://eocnd1116.github.io/qhtjrFont/index.html?type=1&n=0](https://eocnd1116.github.io/qhtjrFont/index.html?type=1&n=0)
- 한국어 패치: dtkrpatchteam 제작, 링크: [https://www.deltarunekr.kro.kr/](https://www.deltarunekr.kro.kr/)
- DELTARUNE의 원작권은 **Toby Fox**에게 있습니다.# 현재 웹 기반 패처도 제작중입니다!
