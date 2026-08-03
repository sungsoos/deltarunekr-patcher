from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QFrame, QSizePolicy
from PySide6.QtGui import QFontDatabase, QFont, QIcon, QGuiApplication, QPainter, QPixmap, QColor
from PySide6.QtCore import Qt, QPoint, Signal, QObject, QTimer, QRect
import subprocess
import threading
import pyxdelta
import getpass
import shutil
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

        t = threading.Thread(target=self.run_patch_process, daemon=True)
        t.start()

    def run_patch_process(self):
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
