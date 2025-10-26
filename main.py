import os
import sys
import shutil
import subprocess
import hashlib
import win32clipboard
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont
import hPyT

# ----------------- PyInstaller 리소스 경로 -----------------
def resource_path(relative_path):
    """PyInstaller에서 번들된 파일 경로 가져오기"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------- 테마 및 폰트 -----------------
BG_COLOR = "#000000"
FG_COLOR = "#FFFFFF"
BUTTON_HOVER = "#FFFF00"
ERROR_COLOR = "#FF5555"
PIXEL_FONT_FILE = resource_path("DeterminationSansK2.ttf")

TITLE_FONT_SIZE = 40
BUTTON_FONT_SIZE = 20
LOG_FONT_SIZE = 14

# ----------------- 텍스트 이미지 생성 -----------------
def generate_text_image(text, font_path, font_size, fill=FG_COLOR):
    font = ImageFont.truetype(font_path, font_size)
    bbox = font.getbbox(text)
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((-bbox[0], -bbox[1]), text, font=font, fill=fill)
    return img

# ----------------- 이미지 버튼 -----------------
def create_image_button(parent, text, font_path, font_size, fg=FG_COLOR, hover=BUTTON_HOVER, command=None):
    normal_img = generate_text_image(text, font_path, font_size, fill=fg)
    hover_img = generate_text_image(text, font_path, font_size, fill=hover)
    img_normal = ctk.CTkImage(light_image=normal_img, size=normal_img.size)
    img_hover = ctk.CTkImage(light_image=hover_img, size=hover_img.size)

    label = ctk.CTkLabel(parent, image=img_normal, bg_color="transparent", cursor="hand2", text="")
    label.image_normal = img_normal
    label.image_hover = img_hover

    if command:
        label.bind("<Button-1>", lambda e: command())
    label.bind("<Enter>", lambda e: label.configure(image=img_hover))
    label.bind("<Leave>", lambda e: label.configure(image=img_normal))
    return label

# ----------------- 클립보드 복사 -----------------
def copy_log_to_clipboard(messages):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText("\n".join(messages))
    win32clipboard.CloseClipboard()

# ----------------- 로그 표시 -----------------
class LogElement(ctk.CTkFrame):
    def __init__(self, parent, width=650, height=300):
        super().__init__(parent, fg_color=BG_COLOR)
        self._canvas = ctk.CTkCanvas(self, bg=BG_COLOR, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._vscroll = ctk.CTkScrollbar(self, orientation="vertical", command=self._canvas.yview)
        self._vscroll.grid(row=0, column=1, sticky="ns")
        self._hscroll = ctk.CTkScrollbar(self, orientation="horizontal", command=self._canvas.xview)
        self._hscroll.grid(row=1, column=0, sticky="ew")

        self._canvas.configure(yscrollcommand=self._vscroll.set, xscrollcommand=self._hscroll.set)
        self._frame = ctk.CTkFrame(self._canvas, fg_color=BG_COLOR)
        self._canvas.create_window((0, 0), window=self._frame, anchor="nw")
        self._frame.bind("<Configure>", self._update_scroll_region)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.messages = []
        self.messages_plain = []

    def _update_scroll_region(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        if self._frame.winfo_reqwidth() > self._canvas.winfo_width():
            self._hscroll.grid()
        else:
            self._hscroll.grid_remove()

    def log(self, text, color=FG_COLOR):
        font = ImageFont.truetype(PIXEL_FONT_FILE, LOG_FONT_SIZE)
        bbox = font.getbbox(text)
        img = Image.new("RGBA", (bbox[2]-bbox[0], bbox[3]-bbox[1]), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((-bbox[0], -bbox[1]), text, font=font, fill=color)
        ctk_img = ctk.CTkImage(light_image=img, size=img.size)
        lbl = ctk.CTkLabel(self._frame, image=ctk_img, bg_color="transparent", text="")
        lbl.image = ctk_img
        lbl.pack(side="top", anchor="w", pady=2)
        self.messages.append(lbl)
        self.messages_plain.append(text)
        self._canvas.yview_moveto(1.0)

    def clear(self):
        for lbl in self.messages:
            lbl.destroy()
        self.messages.clear()
        self.messages_plain.clear()
        self._canvas.yview_moveto(0.0)

# ----------------- 메인 패처 -----------------
class DeltaruneKoreanPatcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.iconbitmap(resource_path("icon.ico"))
        self.configure(fg_color=BG_COLOR)
        self.title("DELTARUNE 한글 패치")
        self.geometry("700x600")
        self.resizable(False, False)

        hPyT.all_stuffs.hide(self)
        hPyT.title_bar_color.set(self, "#000000")
        hPyT.title_bar_text_color.set(self, "#000000")
        hPyT.corner_radius.set(self, "square")
        hPyT.border_color.set(self, "#ffffff")

        self.script_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.xdelta_path = shutil.which("xdelta3") or shutil.which("xdelta3.EXE") or resource_path("xdelta3.exe")
        if not self.xdelta_path:
            messagebox.showerror("오류", "xdelta3 실행 파일을 찾을 수 없습니다.")
            self.destroy()
            return

        self._create_ui()
        self.log("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요.")
        self._auto_detect_folder()

        self._drag_start_x = 0
        self._drag_start_y = 0
        self.bind("<Button-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_motion)

    # ----------------- 드래그 -----------------
    def _drag_start(self, event):
        if event.widget not in (self, self.log_display._canvas):
            return
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _drag_motion(self, event):
        if event.widget not in (self, self.log_display._canvas):
            return
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        self.geometry(f"+{self.winfo_x()+dx}+{self.winfo_y()+dy}")
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    # ----------------- UI -----------------
    def _create_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        pil_title = generate_text_image("* DELTARUNE 한글 패치", PIXEL_FONT_FILE, TITLE_FONT_SIZE)
        title_img = ctk.CTkImage(light_image=pil_title, size=pil_title.size)
        self.title_label = ctk.CTkLabel(main_frame, image=title_img, bg_color="transparent", text="")
        self.title_label.image = title_img
        self.title_label.pack(pady=10)

        folder_frame = ctk.CTkFrame(main_frame, fg_color=BG_COLOR)
        folder_frame.pack(fill="x", pady=5)

        self.folder_btn = create_image_button(folder_frame, "폴더 선택", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.choose_folder)
        self.folder_btn.pack(side="left", padx=5)

        pil_selected = generate_text_image("* 선택된 폴더: 없음", PIXEL_FONT_FILE, LOG_FONT_SIZE)
        selected_img = ctk.CTkImage(light_image=pil_selected, size=pil_selected.size)
        self.selected_folder_label = ctk.CTkLabel(folder_frame, image=selected_img, bg_color="transparent", text="")
        self.selected_folder_label.image = selected_img
        self.selected_folder_label.pack(side="left", padx=10)

        self.log_display = LogElement(main_frame)
        self.log_display.pack(fill="both", expand=True, pady=10)

        button_frame = ctk.CTkFrame(main_frame, fg_color=BG_COLOR)
        button_frame.pack(fill="x", pady=5)
        button_frame.grid_columnconfigure(0, weight=1)

        self.copy_btn = create_image_button(button_frame, "로그 복사", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=lambda: copy_log_to_clipboard(self.log_display.messages_plain))
        self.copy_btn.pack(side="right", padx=5)

        self.clear_btn = create_image_button(button_frame, "로그 지우기", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.log_display.clear)
        self.clear_btn.pack(side="right", padx=5)

        self.close_btn = create_image_button(button_frame, "닫기", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.destroy)
        self.close_btn.pack(side="left", padx=5)


    # ----------------- 로그 -----------------
    def log(self, msg, color=FG_COLOR):
        self.log_display.log(msg, color=color)

    # ----------------- 자동 감지 -----------------
    def _auto_detect_folder(self):
        try:
            exe_in_script = os.path.join(self.script_dir, "DELTARUNE.exe")
            if os.path.isfile(exe_in_script):
                self.log(f"* 패처 폴더에서 DELTARUNE 발견: {exe_in_script}")
                if messagebox.askyesno("DELTARUNE 감지", "델타룬이 감지되었습니다. 바로 패치를 시작할까요?"):
                    self.patch_game(self.script_dir)

            if os.name == "nt":
                pf86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
                steam_path = os.path.join(pf86, "Steam", "steamapps", "common", "DELTARUNE")
                exe_in_steam = os.path.join(steam_path, "DELTARUNE.exe")
                if os.path.isfile(exe_in_steam):
                    self.log(f"* Steam 설치 경로에서 DELTARUNE.exe 발견: {exe_in_steam}")
                    if messagebox.askyesno("자동 감지", "Steam으로 설치된 델타룬을 감지했습니다. 바로 패치를 시작할까요?"):
                        self.patch_game(steam_path)
        except Exception as e:
            self.log(f"* 자동 감지 오류: {e}", color=ERROR_COLOR)

    # ----------------- 폴더 선택 -----------------
    def choose_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            self.log("* 폴더 선택 취소", color="#BBBBBB")
            return
        self.log(f"* 선택된 폴더: {folder}")

        pil_selected = generate_text_image(f"* 선택된 폴더: {folder}", PIXEL_FONT_FILE, LOG_FONT_SIZE)
        selected_img = ctk.CTkImage(light_image=pil_selected, size=pil_selected.size)
        self.selected_folder_label.configure(image=selected_img)
        self.selected_folder_label.image = selected_img

        exe_path = os.path.join(folder, 'DELTARUNE.exe')
        if not os.path.isfile(exe_path):
            self.log("* DELTARUNE.exe를 찾을 수 없음!", color=ERROR_COLOR)
            messagebox.showerror("오류", "* 잘못된 경로입니다!")
            return
        self.patch_game(folder)

    # ----------------- 패치 적용 -----------------
    def patch_game(self, target_dir):
        try:
            self.log("--- 런처 패치 시작 ---")
            launcher_delta = resource_path('launcher.xdelta')
            launcher_target = os.path.join(target_dir, 'data.win')
            self.verify_and_apply_xdelta(launcher_delta, launcher_target)

            for i in range(1, 5):
                self.log(f"--- 챕터 {i} 패치 시작 ---")
                delta = resource_path(f'ch{i}.xdelta')
                orig = os.path.join(target_dir, f'chapter{i}_windows', 'data.win')
                self.verify_and_apply_xdelta(delta, orig)

            self.log("--- 언어 파일 복사 ---")
            lang_src = resource_path('언어파일들')
            if not os.path.isdir(lang_src):
                self.log("'언어파일들' 폴더 없음!", color=ERROR_COLOR)
                raise FileNotFoundError("'언어파일들' 폴더 필요")

            for d in os.listdir(lang_src):
                src = os.path.join(lang_src, d)
                dst = os.path.join(target_dir, d)
                if os.path.isdir(src):
                    self.log(f"* 복사: {src} -> {dst}")
                    shutil.copytree(src, dst, dirs_exist_ok=True)

            self.log("* 한글 패치 완료!")
            if messagebox.askyesno("완료", "패치 완료! 지금 실행?"):
                subprocess.Popen([os.path.join(target_dir, 'DELTARUNE.exe')], cwd=target_dir)
        except Exception as e:
            self.log(f"* 오류 발생: {e}", color=ERROR_COLOR)
            messagebox.showerror("오류", f"* 오류 발생: {e}")

    # ----------------- XDelta 체크섬 확인 -----------------
    def verify_and_apply_xdelta(self, delta_file, target_file, expected_sha1=None):
        if not os.path.exists(target_file):
            self.log(f"* 대상 파일 없음: {target_file}", color="#FF5555")
            raise FileNotFoundError(f"파일 없음: {target_file}")

        sha1 = hashlib.sha1()
        with open(target_file, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        current_sha1 = sha1.hexdigest()
        self.log(f"* 대상 SHA1: {current_sha1}")

        if expected_sha1 and current_sha1 != expected_sha1:
            self.log("* 경고: SHA1 불일치! 이미 패치되었거나 파일이 변경됨", color="#FF5555")
            if not messagebox.askyesno("체크섬 불일치", "SHA1이 예상과 다릅니다. 계속 진행할까요?"):
                raise ValueError("체크섬 불일치로 패치 중단")

        tmp_file = target_file + ".tmp"
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        xdelta_exe = self.xdelta_path
        if not xdelta_exe:
            self.log("* xdelta3 실행 파일을 찾을 수 없습니다!", color="#FF5555")
            raise FileNotFoundError("xdelta3.exe 필요")

        cmd = [xdelta_exe, '-d', '-s', target_file, delta_file, tmp_file]
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, check=True)
            self.log(f"* 패치 완료: {os.path.basename(target_file)}")
        except subprocess.CalledProcessError as e:
            if "XD3_INVALID_INPUT" in e.stderr or "invalid input file" in e.stderr.lower():
                self.log("* 이미 패치되었거나 변조된 파일입니다!", color="#FF5555")
            else:
                self.log(f"* 패치 실패: {e.stderr.strip()}", color="#FF5555")
            raise

        os.replace(tmp_file, target_file)

# ----------------- 실행 -----------------
if __name__ == "__main__":
    app = DeltaruneKoreanPatcher()
    app.mainloop()
