from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QFrame, QSizePolicy, QLineEdit,
    QFormLayout, QDialog, QMessageBox
)
from PySide6.QtGui import QFontDatabase, QFont, QIcon, QGuiApplication, QPainter, QPixmap, QColor, QDesktopServices
from PySide6.QtCore import Qt, QPoint, Signal, QObject, QTimer, QRect, QUrl
import configparser
import subprocess
import threading
import pyxdelta
import getpass
import shutil
import json
import sys
import os
import re



def resource_path(relative_path: str) -> str:
    """파일 경로 구하기"""
    if hasattr(sys, '_MEIPASS'):
        path_meipass = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path_meipass):
            return path_meipass

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        exe_candidates = [
            os.path.join(exe_dir, relative_path),
            os.path.join(exe_dir, "..", "Resources", relative_path),
        ]
        for cand in exe_candidates:
            if os.path.exists(cand):
                return cand

    candidates = [
        os.path.join(os.path.dirname(__file__), relative_path),
        os.path.join(os.path.dirname(__file__), "orig", "src", relative_path),
        os.path.join(os.path.dirname(__file__), "src", relative_path),
        os.path.join(os.path.dirname(__file__), "assets", relative_path),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return os.path.join(os.path.dirname(__file__), relative_path)

def get_assets_dir() -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "assets")
    
    candidates = [
        os.path.join(os.path.dirname(__file__), "assets"),
        os.path.join(os.path.dirname(__file__), "orig", "src", "assets"),
        os.path.join(os.path.dirname(__file__), "src", "assets"),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return os.path.join(os.path.dirname(__file__), "assets")

def is_libraryfolders_vdf(vdf_path: str) -> list[str]:
    """libraryfolders.vdf로 스팀 경로 찾기"""
    paths = []
    if not os.path.exists(vdf_path):
        return paths
    try:
        with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                if '"path"' in line_str:
                    parts = line_str.split('"path"')
                    if len(parts) > 1:
                        path_val = parts[1].replace('"', '').strip()
                        path_val = os.path.realpath(os.path.normpath(path_val))
                        if os.path.exists(path_val) and path_val not in paths:
                            paths.append(path_val)
    except Exception as e:
        print(f"vdf를 파싱하는데 오류가 발생했습니다: {e}")
    return paths

def validate_deltarune_folder(target_dir: str) -> tuple[bool, str | None]:
    """델타룬 설치 폴더가 모든 게임 데이터 파일들을 포함하고 있는지 검증"""
    if not target_dir or not os.path.exists(target_dir):
        return False, "폴더가 존재하지 않습니다."

    is_mac = (sys.platform == "darwin")

    # 1. 런처 데이터 검증
    possible_launcher_targets = [
        os.path.join(target_dir, "data.win"),
        os.path.join(target_dir, "game.ios"),
        os.path.join(target_dir, "DELTARUNE.app", "Contents", "Resources", "game.ios"),
        os.path.join(target_dir, "DELTARUNE.app", "Contents", "Resources", "data.win"),
    ]
    has_launcher = any(os.path.exists(t) for t in possible_launcher_targets)
    if not has_launcher:
        return False, "런처 파일(data.win / game.ios)을 찾을 수 없습니다."

    # 2. 챕터 1~5 파일 검증
    for i in range(1, 6):
        if is_mac:
            folder_candidates = [f"chapter{i}_mac", f"chapter{i}_windows", f"chapter{i}"]
        else:
            folder_candidates = [f"chapter{i}_windows", f"chapter{i}"]

        found_target = False
        for fn in folder_candidates:
            cbase = os.path.join(target_dir, fn)
            for tf_name in ["data.win", "game.ios"]:
                if os.path.exists(os.path.join(cbase, tf_name)):
                    found_target = True
                    break
            if found_target:
                break

        if not found_target:
            return False, f"챕터 {i} 데이터 파일(chapter{i}_[windows/mac]/data.win)이 존재하지 않습니다."

    return True, None

def detect_deltarune() -> str | None:
    """설치된거 감지"""
    candidate_steam_dirs = []

    # 레지스트리 확인
    if sys.platform == "win32":
        try:
            import winreg
            for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for subkey in [r"SOFTWARE\WOW6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
                    try:
                        k = winreg.OpenKey(hkey, subkey)
                        val, _ = winreg.QueryValueEx(k, "InstallPath")
                        if val and os.path.exists(val):
                            candidate_steam_dirs.append(val)
                    except Exception: pass
        except Exception: pass

        # 자주 쓰는 드라이브
        for drive in ["C", "D", "E", "F"]:
            candidate_steam_dirs.extend([
                f"{drive}:\\Program Files (x86)\\Steam",
                f"{drive}:\\Program Files\\Steam",
                f"{drive}:\\Steam",
                f"{drive}:\\SteamLibrary",
            ])

    # 맥os (작동할거임, 아마.)
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        candidate_steam_dirs.extend([
            os.path.join(home, "Library", "Application Support", "Steam"),
        ])

    # 리눅스
    else:
        home = os.path.expanduser("~")
        candidate_steam_dirs.extend([
            os.path.join(home, ".steam", "steam"),
            os.path.join(home, ".steam", "root"),
            os.path.join(home, ".local", "share", "Steam"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
        ])

    # 심볼릭 링크 해제 및 중복 제거 후 탐색
    steam_libraries = []
    for s_dir in candidate_steam_dirs:
        if os.path.exists(s_dir):
            real_s_dir = os.path.realpath(s_dir)
            if real_s_dir not in steam_libraries:
                steam_libraries.append(real_s_dir)
            vdf = os.path.join(real_s_dir, "steamapps", "libraryfolders.vdf")
            for parsed_path in is_libraryfolders_vdf(vdf):
                if parsed_path not in steam_libraries:
                    steam_libraries.append(parsed_path)

    # steamapps/common/ 확인 (모든 필수 파일 검증 포함)
    for lib in steam_libraries:
        for folder_name in ["DELTARUNE", "Deltarune", "deltarune"]:
            common_path = os.path.realpath(os.path.join(lib, "steamapps", "common", folder_name))
            is_valid, _ = validate_deltarune_folder(common_path)
            if is_valid:
                return common_path

    return None

def redact_user_path(path_str: str) -> str:
    if not path_str:
        return path_str
    try:
        user_home = os.path.expanduser("~")
        if user_home and os.path.exists(user_home):
            path_str = path_str.replace(user_home, "~")
        username = getpass.getuser()
        if username:
            path_str = re.sub(re.escape(username), "<user>", path_str, flags=re.IGNORECASE)
    except Exception:
        pass
    return path_str

def fileinfo(file_path: str) -> str:
    if not os.path.exists(file_path):
        return "파일 없음"
    try:
        size = os.path.getsize(file_path)
        return f"크기: {size:,} 바이트"
    except Exception as e:
        return f"정보 취득 실패 ({e})"

def get_xdelta3_binary() -> str | None:
    assets_dir = get_assets_dir()
    if sys.platform == "win32":
        bundled = os.path.join(assets_dir, "bin", "xdelta3_win.exe")
    elif sys.platform == "darwin":
        bundled = os.path.join(assets_dir, "bin", "xdelta3_mac")
    else:
        bundled = os.path.join(assets_dir, "bin", "xdelta3_linux")

    if os.path.exists(bundled):
        return bundled

    return shutil.which("xdelta3")

def patchit(target_file: str, delta_file: str, log_cb=None):
    clean_target = redact_user_path(target_file)
    clean_delta = redact_user_path(delta_file)

    if not os.path.exists(target_file):
        raise RuntimeError(f"패치할 파일이 존재하지 않습니다: {clean_target}")
    if not os.path.exists(delta_file):
        raise RuntimeError(f"델타 파일이 존재하지 않습니다: {clean_delta}")
    
    if os.path.getsize(delta_file) == 0:
        raise RuntimeError(f"패치 파일이 비어있습니다 (0 byte): {clean_delta}")
    if os.path.getsize(target_file) == 0:
        raise RuntimeError(f"대상 파일이 비어있습니다 (0 byte): {clean_target}")

    tmp_file = target_file + ".tmp"
    if os.path.exists(tmp_file):
        try:
            os.remove(tmp_file)
        except Exception: pass

    patched_ok = False
    last_err = ""

    # 1차 시도: xdelta3 실행 파일 활용 (번들 및 시스템 CLI 표준 디코딩)
    xdelta3_bin = get_xdelta3_binary()
    if xdelta3_bin:
        try:
            cmd = [xdelta3_bin, "-d", "-f", "-s", target_file, delta_file, tmp_file]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0 and os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
                patched_ok = True
            else:
                if proc.stderr:
                    last_err = proc.stderr.strip()
        except Exception as exc:
            last_err = str(exc)

    # 2차 시도: 체크섬 불일치 시 xdelta3 -n 옵션으로 강제 디코딩 시도
    if not patched_ok and xdelta3_bin:
        try:
            cmd = [xdelta3_bin, "-d", "-f", "-n", "-s", target_file, delta_file, tmp_file]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0 and os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
                patched_ok = True
            else:
                if proc.stderr:
                    last_err = proc.stderr.strip()
        except Exception as exc:
            last_err = str(exc)

    # 3차 시도: CLI 디코딩 실패 시 pyxdelta 파이썬 C 바인딩 시도
    if not patched_ok:
        try:
            res = pyxdelta.decode(delta_file, target_file, tmp_file)
            if res == 0 and os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
                patched_ok = True
        except Exception as exc:
            if not last_err:
                last_err = str(exc)

    if not patched_ok or not os.path.exists(tmp_file):
        err_detail = f" ({last_err})" if last_err else ""
        raise RuntimeError(f"이미 패치되었거나 원본 파일 버전이 일치하지 않습니다.{err_detail}")

    shutil.copyfile(tmp_file, target_file)
    try:
        os.remove(tmp_file)
    except Exception: pass

def copy_folder(src_dir: str, dst_dir: str, log_cb):
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    for entry in os.listdir(src_dir):
        src_path = os.path.join(src_dir, entry)
        dst_path = os.path.join(dst_dir, entry)
        if os.path.isdir(src_path):
            copy_folder(src_path, dst_path, log_cb)
        else:
            shutil.copyfile(src_path, dst_path)
            log_cb(f"  * 복사 완료: {os.path.basename(dst_path)}", "#88FF88")

def adjust_josa(word: str, josa: str) -> str:
    """한국어 조사 교정 (매우 안정된 핵)"""
    if not word:
        return word + josa
    last_char = word[-1]
    if not ("가" <= last_char <= "힣"):
        return word + josa
    jongseong_idx = (ord(last_char) - ord("가")) % 28
    has_jongseong = jongseong_idx > 0
    is_rieul = (jongseong_idx == 8)

    if josa in ("을", "를"):
        return word + ("을" if has_jongseong else "를")
    elif josa in ("이", "가"):
        return word + ("이" if has_jongseong else "가")
    elif josa in ("은", "는"):
        return word + ("은" if has_jongseong else "는")
    elif josa in ("과", "와"):
        return word + ("과" if has_jongseong else "와")
    elif josa in ("으로", "로"):
        if has_jongseong and not is_rieul:
            return word + "으로"
        return word + "로"

    return word + josa

def replace_word_with_josa(text: str, old_word: str, new_word: str) -> str:
    """단어 치환 및 조사의 자동 교정 적용"""
    safe_old_word = re.escape(old_word)
    pattern = re.compile(rf"{safe_old_word}(을|를|이|가|은|는|으로|로|과|와)?")

    def replacer(match):
        matched_josa = match.group(1)
        if matched_josa:
            return adjust_josa(new_word, matched_josa)
        return new_word

    return pattern.sub(replacer, text)

def update_true_config(log_cb=None):
    """트루 콘픽 뭐시기 갱신"""
    config_paths = []
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            config_paths.append(os.path.join(local_app_data, "DELTARUNE", "true_config.ini"))
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        config_paths.append(os.path.join(home, "Library", "Application Support", "com.tobyfox.deltarune", "true_config.ini"))
        config_paths.append(os.path.join(home, "Library", "Application Support", "DELTARUNE", "true_config.ini"))
    else:
        home = os.path.expanduser("~")
        config_paths.append(os.path.join(home, ".local", "share", "DELTARUNE", "true_config.ini"))
        config_paths.append(os.path.join(home, ".config", "DELTARUNE", "true_config.ini"))

    for config_path in config_paths:
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            config = configparser.ConfigParser()
            config.optionxform = str
            if os.path.exists(config_path):
                config.read(config_path, encoding="utf-8")

            if not config.has_section("LANG"):
                config.add_section("LANG")

            config.set("LANG", "LANG", '"ja"')
            config.set("LANG", "KRDUB", '"1"')

            with open(config_path, "w", encoding="utf-8") as f:
                config.write(f, space_around_delimiters=False)
            if log_cb:
                log_cb(f"* true_config.ini 설정 변경 완료 ({redact_user_path(config_path)})", "#88FF88")
        except Exception as e:
            if log_cb:
                log_cb(f"* true_config.ini 설정 중 알림 (건너뜀): {e}", "#FFFF00")

def apply_custom_words(target_dir: str, custom_words: dict, log_cb=None):
    """사용자 지정 단어 (의지 / 결의 / 데스) 치환 및 조사 자동 수정"""
    deterwill_path = resource_path("assets/deterwill.json")
    if not os.path.exists(deterwill_path):
        deterwill_path = resource_path("patch/deterwill.json")
    if not os.path.exists(deterwill_path):
        deterwill_path = resource_path("deterwill.json")

    if not os.path.exists(deterwill_path):
        if log_cb:
            log_cb("* deterwill.json 치환 정의 파일을 찾을 수 없어 명칭 치환을 건너뜁니다.", "#FFFF00")
        return

    try:
        with open(deterwill_path, "r", encoding="utf-8") as f:
            deterwill = json.load(f)

        default_map = {"determination": "의지", "will": "결의", "dess": "데스"}
        is_mac = (sys.platform == "darwin")

        for ch_num in range(1, 6):
            ch_str = str(ch_num)
            if ch_str not in deterwill:
                continue

            if is_mac:
                folder_candidates = [f"chapter{ch_num}_mac", f"chapter{ch_num}_windows", f"chapter{ch_num}"]
            else:
                folder_candidates = [f"chapter{ch_num}_windows", f"chapter{ch_num}"]

            lang_path = None
            for fn in folder_candidates:
                cand_lang = os.path.join(target_dir, fn, "lang", "lang_ja.json")
                if os.path.exists(cand_lang):
                    lang_path = cand_lang
                    break

            if not lang_path or not os.path.exists(lang_path):
                continue

            with open(lang_path, "r", encoding="utf-8") as f:
                lang_data = json.load(f)

            modified = False
            for cat, old_word in default_map.items():
                new_word = custom_words.get(cat, old_word)
                if not new_word or new_word == old_word:
                    continue

                keys_to_change = deterwill[ch_str].get(cat, [])
                for key in keys_to_change:
                    if key in lang_data:
                        original_text = lang_data[key]
                        if isinstance(original_text, str):
                            new_text = replace_word_with_josa(original_text, old_word, new_word)
                            if original_text != new_text:
                                lang_data[key] = new_text
                                modified = True

            if modified:
                with open(lang_path, "w", encoding="utf-8") as f:
                    json.dump(lang_data, f, ensure_ascii=False, indent=4)
                if log_cb:
                    log_cb(f"* 챕터 {ch_num} 사용자 정의 명칭 치환 적용 완료", "#00FF00")

    except Exception as e:
        if log_cb:
            log_cb(f"* 명칭 치환 처리 중 오류: {e}", "#FF5555")

def clean_tmp_files(target_dir: str):
    """비정상 종료로 인한 잔여 파일(.tmp) 폭파"""
    if not target_dir or not os.path.exists(target_dir):
        return
    tmp_candidates = [
        os.path.join(target_dir, "data.win.tmp"),
        os.path.join(target_dir, "game.ios.tmp"),
    ]
    for i in range(1, 6):
        for fn in [f"chapter{i}_windows", f"chapter{i}_mac", f"chapter{i}"]:
            tmp_candidates.append(os.path.join(target_dir, fn, "data.win.tmp"))
            tmp_candidates.append(os.path.join(target_dir, fn, "game.ios.tmp"))
            tmp_candidates.append(os.path.join(target_dir, fn, "lang", "lang_ja.json.tmp"))
    for fpath in tmp_candidates:
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass

class PatchFinishedDialog(QDialog):
    """패치 완료 안내 및 게임 실행 팝업"""
    def __init__(self, parent=None, font_family="Courier"):
        super().__init__(parent)
        self.setWindowTitle("패치 완료")
        self.choice = None
        self.setMinimumWidth(440)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)

        stylesheet = f"""
            QDialog {{
                background-color: #050505;
                border: 3px solid #ffffff;
            }}
            QLabel {{
                color: #ffffff;
                font-family: "{font_family}", monospace;
                font-size: 28px;
            }}
            QPushButton {{
                background-color: #000000;
                color: #ffffff;
                border: 2px solid #ffffff;
                font-family: "{font_family}", monospace;
                font-size: 26px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                color: #ffff00;
                border-color: #ffff00;
            }}
        """
        self.setStyleSheet(stylesheet)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        msg_label = QLabel("* 한글 패치를 성공적으로 마쳤습니다!\n* 지금 바로 델타룬을 실행할까요?", self)
        msg_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg_label)

        btn_steam = QPushButton("스팀을 통해 실행하기", self)
        btn_steam.setCursor(Qt.PointingHandCursor)
        btn_steam.clicked.connect(self.choose_steam)
        layout.addWidget(btn_steam)

        btn_direct = QPushButton("직접 실행하기", self)
        btn_direct.setCursor(Qt.PointingHandCursor)
        btn_direct.clicked.connect(self.choose_direct)
        layout.addWidget(btn_direct)

        btn_close = QPushButton("닫기", self)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)

    def choose_steam(self):
        self.choice = "steam"
        self.accept()

    def choose_direct(self):
        self.choice = "direct"
        self.accept()


class SlicedWidget(QWidget):
    """9조각 창 렌더링을 위한 클래스"""
    def __init__(self, parent=None, texture_path=None, border_slice=15, border_width=45):
        super().__init__(parent)
        self.border_slice = border_slice
        self.border_width = border_width
        self.texture = None
        if texture_path and os.path.exists(texture_path):
            self.texture = QPixmap(texture_path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        
        if not self.texture or self.texture.isNull():
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            return

        tw = self.texture.width()
        th = self.texture.height()
        s = self.border_slice
        bw = self.border_width
        w = self.width()
        h = self.height()

        # 소스
        src_top_left = QRect(0, 0, s, s)
        src_top_mid = QRect(s, 0, tw - 2*s, s)
        src_top_right = QRect(tw - s, 0, s, s)

        src_mid_left = QRect(0, s, s, th - 2*s)
        src_center = QRect(s, s, tw - 2*s, th - 2*s)
        src_mid_right = QRect(tw - s, s, s, th - 2*s)

        src_bot_left = QRect(0, th - s, s, s)
        src_bot_mid = QRect(s, th - s, tw - 2*s, s)
        src_bot_right = QRect(tw - s, th - s, s, s)

        # 결과
        dst_top_left = QRect(0, 0, bw, bw)
        dst_top_mid = QRect(bw, 0, w - 2*bw, bw)
        dst_top_right = QRect(w - bw, 0, bw, bw)

        dst_mid_left = QRect(0, bw, bw, h - 2*bw)
        dst_center = QRect(bw, bw, w - 2*bw, h - 2*bw)
        dst_mid_right = QRect(w - bw, bw, bw, h - 2*bw)

        dst_bot_left = QRect(0, h - bw, bw, bw)
        dst_bot_mid = QRect(bw, h - bw, w - 2*bw, bw)
        dst_bot_right = QRect(w - bw, h - bw, bw, bw)

        # 그리기
        painter.drawPixmap(dst_center, self.texture, src_center)
        painter.drawPixmap(dst_top_left, self.texture, src_top_left)
        painter.drawPixmap(dst_top_mid, self.texture, src_top_mid)
        painter.drawPixmap(dst_top_right, self.texture, src_top_right)
        painter.drawPixmap(dst_mid_left, self.texture, src_mid_left)
        painter.drawPixmap(dst_mid_right, self.texture, src_mid_right)
        painter.drawPixmap(dst_bot_left, self.texture, src_bot_left)
        painter.drawPixmap(dst_bot_mid, self.texture, src_bot_mid)
        painter.drawPixmap(dst_bot_right, self.texture, src_bot_right)

class PatchSignalBridge(QObject):
    log_signal = Signal(str, str)
    finish_signal = Signal(bool)

class DeltarunePatcherWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(700, 500)
        self.resize(950, 750)
        self.center_window()

        self.selected_folder = None
        self.patching_in_progress = False
        self.rainbow_phase = 0
        self.loaded_font_family = "Courier" # fallback

        self.drag_position = QPoint()

        self.bridge = PatchSignalBridge()
        self.bridge.log_signal.connect(self.add_log)
        self.bridge.finish_signal.connect(self.finish_patch)

        self.load_custom_font()
        self.setup_ui()

        self.add_log("* DELTARUNE 한글 패처")
        
        # 설치 감지
        auto_detected = detect_deltarune()
        if auto_detected:
            self.selected_folder = auto_detected
            truncated = self.truncate_path(auto_detected)
            self.lbl_folder_path.setText(f"* 선택된 폴더: {truncated}")
            self.add_log(f"* DELTARUNE 설치 폴더 자동 감지 성공: {auto_detected}", "#00FF00")
            self.btn_start_patch.setEnabled(True)
        else:
            self.add_log("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요.")

        self.rainbow_timer = QTimer(self)
        self.rainbow_timer.timeout.connect(self.rainbowthing)
        self.rainbow_timer.start(250)

    def center_window(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def load_custom_font(self):
        font_path = resource_path("assets/DeltaDotumKR.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self.loaded_font_family = families[0]

        custom_font = QFont(self.loaded_font_family)
        custom_font.setStyleStrategy(QFont.PreferAntialias)
        custom_font.setHintingPreference(QFont.PreferFullHinting)
        QApplication.setFont(custom_font)

    def setup_ui(self):
        assets_dir = get_assets_dir()
        border_img_path = os.path.join(assets_dir, "border_texture.png")
        icon_path = resource_path("assets/icon.ico")
        
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

        # 보더
        self.border_widget = SlicedWidget(self, texture_path=border_img_path, border_slice=15, border_width=45)
        self.setCentralWidget(self.border_widget)

        font_fam = self.loaded_font_family

        stylesheet = f"""
            * {{
                font-family: "{font_fam}", "Courier New", monospace;
                color: #ffffff;
                selection-background-color: #444444;
            }}
            QLabel {{
                font-family: "{font_fam}", "Courier New", monospace;
            }}
            QPushButton {{
                background: transparent;
                color: #ffffff;
                border: none;
                font-family: "{font_fam}", "Courier New", monospace;
                font-size: 40px;
                padding: 0px;
            }}
            QPushButton:hover:enabled {{
                color: #ffff00;
            }}
            QPushButton:disabled {{
                color: #555555;
            }}
            QTextEdit {{
                background-color: #050505;
                border: 2px solid #ffffff;
                font-family: "{font_fam}", "Courier New", monospace;
                font-size: 50px;
                line-height: 1.3;
                padding: 8px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: #000000;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: #ffffff;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """
        self.border_widget.setStyleSheet(stylesheet)

        # 대충 계산된 마진
        main_layout = QVBoxLayout(self.border_widget)
        main_layout.setContentsMargins(50, 48, 50, 48)
        main_layout.setSpacing(16)

        # 타이틀바
        self.titlebar = QWidget(self)
        title_layout = QHBoxLayout(self.titlebar)
        title_layout.setContentsMargins(0, 0, 0, 8)

        self.title_label = QLabel("DELTARUNE 한글 패처", self)
        self.title_label.setStyleSheet("font-size: 45px; font-weight: normal; color: #ffffff;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        self.btn_close_top = QPushButton("x", self)
        self.btn_close_top.setStyleSheet("font-size: 45px; color: #ffffff; background: transparent;")
        self.btn_close_top.setCursor(Qt.PointingHandCursor)
        self.btn_close_top.clicked.connect(self.close)
        title_layout.addWidget(self.btn_close_top)

        main_layout.addWidget(self.titlebar)

        # 구분자
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; border-bottom: 2px dashed #444444;")
        main_layout.addWidget(sep)

        # 폴더 선택
        folder_section = QWidget(self)
        folder_layout = QHBoxLayout(folder_section)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(16)

        self.btn_select_folder = QPushButton("폴더 선택", self)
        self.btn_select_folder.setCursor(Qt.PointingHandCursor)
        self.btn_select_folder.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.btn_select_folder)

        self.lbl_folder_path = QLabel("* 선택된 폴더: 없음", self)
        self.lbl_folder_path.setStyleSheet("font-size: 35px; color: #cccccc;")
        self.lbl_folder_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        folder_layout.addWidget(self.lbl_folder_path)

        main_layout.addWidget(folder_section)

        # 고급 설정 입력 폼
        self.adv_widget = QWidget(self)
        adv_layout = QFormLayout(self.adv_widget)
        adv_layout.setContentsMargins(10, 4, 10, 4)
        adv_layout.setSpacing(8)

        lbl_det = QLabel("determination (기본: 의지):", self)
        lbl_det.setStyleSheet("font-size: 28px; color: #ffffff;")
        self.input_determination = QLineEdit("의지", self)
        self.input_determination.setStyleSheet("font-size: 28px; background-color: #050505; border: 2px solid #ffffff; color: #ffff00; padding: 2px 6px;")
        adv_layout.addRow(lbl_det, self.input_determination)

        lbl_will = QLabel("will (기본: 결의):", self)
        lbl_will.setStyleSheet("font-size: 28px; color: #ffffff;")
        self.input_will = QLineEdit("결의", self)
        self.input_will.setStyleSheet("font-size: 28px; background-color: #050505; border: 2px solid #ffffff; color: #ffff00; padding: 2px 6px;")
        adv_layout.addRow(lbl_will, self.input_will)

        lbl_dess = QLabel("dess (기본: 데스):", self)
        lbl_dess.setStyleSheet("font-size: 28px; color: #ffffff;")
        self.input_dess = QLineEdit("데스", self)
        self.input_dess.setStyleSheet("font-size: 28px; background-color: #050505; border: 2px solid #ffffff; color: #ffff00; padding: 2px 6px;")
        adv_layout.addRow(lbl_dess, self.input_dess)

        self.adv_widget.setVisible(False)
        main_layout.addWidget(self.adv_widget)

        # 로그
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text, stretch=1)

        # 버튼
        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_close_bot = QPushButton("닫기", self)
        self.btn_close_bot.setCursor(Qt.PointingHandCursor)
        self.btn_close_bot.clicked.connect(self.close)
        footer_layout.addWidget(self.btn_close_bot)

        footer_layout.addSpacing(16)

        self.btn_toggle_adv = QPushButton("고급 설정 열기", self)
        self.btn_toggle_adv.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_adv.clicked.connect(self.toggle_advanced_settings)
        footer_layout.addWidget(self.btn_toggle_adv)

        footer_layout.addStretch()

        self.btn_copy_log = QPushButton("로그 복사", self)
        self.btn_copy_log.setCursor(Qt.PointingHandCursor)
        self.btn_copy_log.clicked.connect(self.copy_log)
        footer_layout.addWidget(self.btn_copy_log)

        footer_layout.addSpacing(16)

        self.btn_start_patch = QPushButton("패치 적용", self)
        self.btn_start_patch.setCursor(Qt.PointingHandCursor)
        self.btn_start_patch.setEnabled(False)
        self.btn_start_patch.clicked.connect(self.start_patch_thread)
        footer_layout.addWidget(self.btn_start_patch)

        main_layout.addWidget(footer)

    def toggle_advanced_settings(self):
        is_vis = not self.adv_widget.isVisible()
        self.adv_widget.setVisible(is_vis)
        if is_vis:
            self.btn_toggle_adv.setText("고급 설정 닫기")
        else:
            self.btn_toggle_adv.setText("고급 설정 열기")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def truncate_path(self, path_str: str, max_len: int = 38) -> str:
        if len(path_str) <= max_len:
            return path_str
        return "..." + path_str[-(max_len - 3):]

    def add_log(self, msg: str, color: str = "#FFFFFF"):
        html_msg = f'<div style="color: {color}; margin-bottom: 4px; font-family: \'{self.loaded_font_family}\', monospace; font-size: 35px;">{msg}</div>'
        self.log_text.append(html_msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def select_folder(self):
        chosen = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if chosen:
            is_valid, err_msg = validate_deltarune_folder(chosen)
            truncated = self.truncate_path(redact_user_path(chosen))
            if is_valid:
                self.selected_folder = chosen
                self.lbl_folder_path.setText(f"* 선택된 폴더: {truncated}")
                self.add_log(f"* 선택된 폴더: {redact_user_path(chosen)}", "#00FF00")
                self.btn_start_patch.setEnabled(True)
            else:
                self.selected_folder = None
                self.lbl_folder_path.setText(f"* 선택된 폴더: 없음 (검증 실패)")
                self.add_log(f"* 검증 실패: {redact_user_path(chosen)} - {err_msg}", "#FF5555")
                self.btn_start_patch.setEnabled(False)
        else:
            self.add_log("* 폴더 선택 취소", "#BBBBBB")

    def copy_log(self):
        plain_text = self.log_text.toPlainText()
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(plain_text)
        self.add_log("* 로그가 클립보드에 복사되었습니다!")

    def rainbowthing(self):
        font_fam = self.loaded_font_family
        if self.btn_start_patch.isEnabled() and not self.patching_in_progress:
            colors = ["#ff0000", "#ff7f00", "#ffff00", "#00ff00", "#0000ff", "#8b00ff"]
            col = colors[self.rainbow_phase % len(colors)]
            self.btn_start_patch.setStyleSheet(f"QPushButton {{ color: {col}; font-size: 40px; font-family: '{font_fam}'; }} QPushButton:hover {{ color: #ffff00; }}")
            self.rainbow_phase += 1
        elif not self.btn_start_patch.isEnabled():
            self.btn_start_patch.setStyleSheet(f"QPushButton {{ color: #555555; font-size: 40px; font-family: '{font_fam}'; }}")

    def start_patch_thread(self):
        if not self.selected_folder or self.patching_in_progress:
            return
        self.patching_in_progress = True
        self.btn_start_patch.setEnabled(False)
        self.btn_select_folder.setEnabled(False)

        custom_words = {
            "enabled": self.adv_widget.isVisible(),
            "determination": self.input_determination.text().strip() or "의지",
            "will": self.input_will.text().strip() or "결의",
            "dess": self.input_dess.text().strip() or "데스",
        }

        t = threading.Thread(target=self.run_patch_process, args=(custom_words,), daemon=True)
        t.start()

    def run_patch_process(self, custom_words=None):
        target_dir = self.selected_folder
        patch_dir = resource_path("patch")
        xdelta_dir = os.path.join(patch_dir, "xdelta")

        def log_cb(msg, color="#FFFFFF"):
            self.bridge.log_signal.emit(msg, color)

        log_cb("--- 패치 작업 시작 ---", "#FFFF00")

        if not target_dir or not os.path.exists(target_dir):
            err = f"선택된 폴더가 존재하지 않거나 삭제되었습니다! ({target_dir})"
            log_cb(f"* 오류: {err}", "#FF5555")
            self.bridge.finish_signal.emit(False)
            return

        # 잔여 .tmp 임시 파일 자동 정리
        clean_tmp_files(target_dir)

        try:
            is_mac = (sys.platform == "darwin")

            xdelta_folder = "xdelta_mac" if (is_mac and (os.path.exists(os.path.join(patch_dir, "xdelta_mac")) or not os.path.exists(os.path.join(patch_dir, "xdelta")))) else "xdelta"
            xdelta_dir = os.path.join(patch_dir, xdelta_folder)

            lang_folder = "lang_mac" if (is_mac and (os.path.exists(os.path.join(patch_dir, "lang_mac")) or not os.path.exists(os.path.join(patch_dir, "lang")))) else "lang"
            lang_src = os.path.join(patch_dir, lang_folder)

            # launcher 검증
            launcher_delta = os.path.join(xdelta_dir, "launcher.xdelta")
            valid_launcher_target = None
            if os.path.exists(launcher_delta):
                possible_launcher_targets = [
                    os.path.join(target_dir, "data.win"),
                    os.path.join(target_dir, "game.ios"),
                    os.path.join(target_dir, "DELTARUNE.app", "Contents", "Resources", "game.ios"),
                    os.path.join(target_dir, "DELTARUNE.app", "Contents", "Resources", "data.win"),
                ]
                for t in possible_launcher_targets:
                    if os.path.exists(t):
                        valid_launcher_target = t
                        break

                if not valid_launcher_target:
                    err = "런처 데이터(data.win / game.ios)를 찾을 수 없습니다."
                    log_cb(f"* 검증 실패: {err}", "#FF5555")
                    self.bridge.finish_signal.emit(False)
                    return

            # 챕터 1-5 검증
            valid_chapter_targets = []
            for i in range(1, 6):
                delta = os.path.join(xdelta_dir, f"ch{i}.xdelta")
                if not os.path.exists(delta):
                    err = f"챕터 {i} 패치 파일({xdelta_folder}/ch{i}.xdelta)이 존재하지 않습니다."
                    log_cb(f"* 검증 실패: {err}", "#FF5555")
                    self.bridge.finish_signal.emit(False)
                    return

                # 데이터 파일
                if is_mac:
                    folder_candidates = [f"chapter{i}_mac", f"chapter{i}_windows", f"chapter{i}"]
                else:
                    folder_candidates = [f"chapter{i}_windows", f"chapter{i}"]

                found_target = None
                for fn in folder_candidates:
                    cbase = os.path.join(target_dir, fn)
                    for tf_name in ["data.win", "game.ios"]:
                        tf = os.path.join(cbase, tf_name)
                        if os.path.exists(tf):
                            found_target = tf
                            break
                    if found_target:
                        break

                if not found_target:
                    err = f"챕터 {i} 대상 파일([target]/chapter{i}_[mac/windows]/data.win)을 찾을 수 없습니다."
                    log_cb(f"* 검증 실패: {err}", "#FF5555")
                    self.bridge.finish_signal.emit(False)
                    return

                valid_chapter_targets.append({"chapter": i, "targetFile": found_target, "deltaFile": delta})

            if not os.path.exists(lang_src):
                err = f"패처에서 언어 폴더(./patch/{lang_folder})를 찾을 수 없습니다."
                log_cb(f"* 검증 실패: {err}", "#FF5555")
                self.bridge.finish_signal.emit(False)
                return

            # 런처 먼저 패치
            if valid_launcher_target and os.path.exists(launcher_delta):
                log_cb("--- 런처 패치 적용 중 ---", "#FFFF00")
                patchit(valid_launcher_target, launcher_delta, log_cb=log_cb)
                log_cb("* 런처 패치 완료!", "#00FF00")

            # 챕터 패치
            for item in valid_chapter_targets:
                log_cb(f"--- 챕터 {item['chapter']} 패치 적용 중 ---", "#FFFF00")
                patchit(item["targetFile"], item["deltaFile"], log_cb=log_cb)
                log_cb(f"* 챕터 {item['chapter']} 패치 완료!", "#00FF00")

            # 언어 파일 복사
            log_cb("--- 언어 파일 복사 중 ---", "#FFFF00")
            for item in os.listdir(lang_src):
                s_path = os.path.join(lang_src, item)
                d_path = os.path.join(target_dir, item)
                if os.path.isdir(s_path):
                    copy_folder(s_path, d_path, log_cb)
                else:
                    shutil.copyfile(s_path, d_path)
                    log_cb(f"  * 복사 완료: {item}", "#88FF88")

            # 사용자 정의 명칭 치환 (고급 설정)
            if custom_words and (custom_words.get("enabled") or custom_words.get("determination") != "의지" or custom_words.get("will") != "결의" or custom_words.get("dess") != "데스"):
                log_cb("--- 고급 설정 (사용자 정의 명칭 치환) 적용 중 ---", "#FFFF00")
                apply_custom_words(target_dir, custom_words, log_cb=log_cb)

            # 게임 설정 파일 (true_config.ini) 갱신
            log_cb("--- 게임 설정 (true_config.ini) 최신화 중 ---", "#FFFF00")
            update_true_config(log_cb=log_cb)

            log_cb("--- 패치가 성공적으로 완료되었습니다! ---", "#00FF00")
            log_cb("* 한글 패치가 성공적으로 완료되었습니다!", "#00FF00")
            self.bridge.finish_signal.emit(True)

        except Exception as e:
            log_cb(f"* 오류 발생: {str(e)}", "#FF5555")
            self.bridge.finish_signal.emit(False)

    def finish_patch(self, success: bool):
        self.patching_in_progress = False
        self.btn_select_folder.setEnabled(True)
        self.btn_start_patch.setEnabled(True)
        self.btn_start_patch.setText("패치 적용")


        if success:
            dialog = PatchFinishedDialog(self, font_family=self.loaded_font_family)
            if dialog.exec() == QDialog.Accepted:
                if dialog.choice == "steam":
                    QDesktopServices.openUrl(QUrl("steam://rungameid/1671210"))
                elif dialog.choice == "direct" and self.selected_folder:
                    if sys.platform == "win32":
                        exe_path = os.path.join(self.selected_folder, "DELTARUNE.exe")
                        if os.path.exists(exe_path):
                            subprocess.Popen([exe_path], cwd=self.selected_folder)
                    elif sys.platform == "darwin":
                        app_path = os.path.join(self.selected_folder, "DELTARUNE.app")
                        if os.path.exists(app_path):
                            subprocess.Popen(["open", app_path])
                    else:
                        exe_path = os.path.join(self.selected_folder, "DELTARUNE")
                        if os.path.exists(exe_path):
                            subprocess.Popen([exe_path], cwd=self.selected_folder)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 폰트
    font = app.font()
    font.setStyleStrategy(QFont.PreferAntialias)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    window = DeltarunePatcherWindow()
    window.show()
    sys.exit(app.exec())
