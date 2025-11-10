# DELTARUNE 한글 패치

DELTARUNE 게임을 한국어로 패치할 수 있는 윈도우용 패처입니다.  
PyInstaller를 이용해 독립 실행 파일로 배포할 수 있습니다.

**소스 코드에는 한국어 패치 파일이 없습니다.**



## 기능
- 그런걸 왜 찾는거죠?



## 실행 파일 요구 사항
- Windows 10 이상 (또는 [Wine](https://www.winehq.org/) 이용)

## 빌드 요구 사항
- Windows 10 이상 (Linux 미지원, 아마도.)
- Python 3.12 이상
- 필수 모듈
  - `customtkinter`
  - `Pillow`
  - `win32clipboard`
  - `hPyT`
- XDelta3 실행 파일 (패치 적용용)

## 빌드 방법

1. 필요한 라이브러리 설치
```bash
pip install -r requirements.txt
```

2. 빌드 명령어 실행하기
```bash
./build.bat
```

빌드 성공 시, `dist/` 폴더에 저장되어 있습니다.

---
<sub>행복한 하루 되세요!</sub>
