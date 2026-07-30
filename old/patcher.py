import os
import sys
import shutil
import subprocess
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ----------------- PyInstaller & Development Resource Path -----------------
def resource_path(relative_path):
    """Get absolute path to resource, supporting development and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        # Development mode: check current directory first, then deltarunekr-patcher-main folder
        if os.path.exists(relative_path):
            return os.path.abspath(relative_path)
        alt_path = os.path.join("deltarunekr-patcher-main", relative_path)
        if os.path.exists(alt_path):
            return os.path.abspath(alt_path)
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------- Theme & Fonts -----------------
BG_COLOR = "#000000"         # Solid black for all visible, opaque UI widgets
TRANSPARENT_COLOR = "#000001" # Transparent chroma-key color for canvas and window background
FG_COLOR = "#FFFFFF"
BUTTON_HOVER = "#FFFF00"
ERROR_COLOR = "#FF5555"
PIXEL_FONT_FILE = resource_path("DeterminationSansK2.ttf")

TITLE_FONT_SIZE = 36
BUTTON_FONT_SIZE = 18
LOG_FONT_SIZE = 14

# ----------------- Text Image Generation for Pixel-Art Styling -----------------
def generate_text_image(text, font_path, font_size, fill=FG_COLOR):
    """Renders text into a PIL image using a specific pixel font for retro feel"""
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
    
    bbox = font.getbbox(text)
    width, height = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((-bbox[0], -bbox[1]), text, font=font, fill=fill)
    return img

# ----------------- Tkinter Native Image Button with Hover State -----------------
def create_image_button(parent, text, font_path, font_size, fg=FG_COLOR, hover=BUTTON_HOVER, command=None):
    """Creates a standard Tkinter label that behaves like an image-based button with hover effects"""
    normal_img = generate_text_image(text, font_path, font_size, fill=fg)
    hover_img = generate_text_image(text, font_path, font_size, fill=hover)
    
    img_normal = ImageTk.PhotoImage(normal_img)
    img_hover = ImageTk.PhotoImage(hover_img)

    label = tk.Label(parent, image=img_normal, bg=BG_COLOR, cursor="hand2", bd=0, highlightthickness=0)
    label.image_normal = img_normal
    label.image_hover = img_hover

    if command:
        label.bind("<Button-1>", lambda e: command())
    label.bind("<Enter>", lambda e: label.configure(image=img_hover))
    label.bind("<Leave>", lambda e: label.configure(image=img_normal))
    return label

# ----------------- Native Cross-Platform Clipboard Copy -----------------
def copy_log_to_clipboard(parent, messages):
    try:
        parent.clipboard_clear()
        parent.clipboard_append("\n".join(messages))
        parent.update()
        return True
    except Exception:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText("\n".join(messages))
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            return False

# ----------------- Path Truncation for Elegant Display -----------------
def truncate_path(path, max_len=45):
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len-3):]

# ----------------- Scrollable Pixel Log Display Component -----------------
class LogElement(tk.Frame):
    def __init__(self, parent, width=650, height=300):
        super().__init__(parent, bg=BG_COLOR, bd=0, highlightthickness=0)
        
        self._canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._vscroll = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._vscroll.grid(row=0, column=1, sticky="ns")

        self._hscroll = tk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._hscroll.grid(row=1, column=0, sticky="ew")

        self._canvas.configure(yscrollcommand=self._vscroll.set, xscrollcommand=self._hscroll.set)
        
        self._frame = tk.Frame(self._canvas, bg=BG_COLOR)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._frame, anchor="nw")
        
        self._frame.bind("<Configure>", self._update_scroll_region)
        self._canvas.bind("<Configure>", self._update_canvas_width)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.messages = []
        self.messages_plain = []
        self.message_images = [] # Keep references to prevent garbage collection

    def _update_scroll_region(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        if self._frame.winfo_reqwidth() > self._canvas.winfo_width():
            self._hscroll.grid()
        else:
            self._hscroll.grid_remove()

    def _update_canvas_width(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def log(self, text, color=FG_COLOR):
        font = ImageFont.truetype(PIXEL_FONT_FILE, LOG_FONT_SIZE)
        bbox = font.getbbox(text)
        width = max(1, bbox[2]-bbox[0])
        height = max(1, bbox[3]-bbox[1])
        
        img = Image.new("RGBA", (width, height), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((-bbox[0], -bbox[1]), text, font=font, fill=color)
        
        ctk_img = ImageTk.PhotoImage(img)
        self.message_images.append(ctk_img)
        
        lbl = tk.Label(self._frame, image=ctk_img, bg=BG_COLOR, bd=0, highlightthickness=0)
        lbl.image = ctk_img
        lbl.pack(side="top", anchor="w", pady=2)
        
        self.messages.append(lbl)
        self.messages_plain.append(text)
        self.update_idletasks()
        self._canvas.yview_moveto(1.0)

    def clear(self):
        for lbl in self.messages:
            lbl.destroy()
        self.messages.clear()
        self.messages_plain.clear()
        self.message_images.clear()
        self._canvas.yview_moveto(0.0)

# ----------------- Combined 9-Slice Border Window & Patcher Application -----------------
class DeltaruneKoreanPatcher(tk.Tk):
    def __init__(self, border_image_path, border_thickness=1):
        super().__init__()
        
        # 1. Remove standard Windows borders
        self.title("DELTARUNE 한글 패치")
        self.overrideredirect(True)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        if os.name == "nt":
            self.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
            self.after(10, self.set_appwindow)
        
        # 2. Window sizing & centering
        self.border_thick = border_thickness
        self.bg_color = TRANSPARENT_COLOR
        
        width, height = 700, 600
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Load and prepare the base 9-slice border image
        self.base_image = Image.open(border_image_path).convert("RGBA")
        
        # Create a canvas that fills the entire window
        self.canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind resize event to recalculate the 9-slice border
        self.canvas.bind("<Configure>", self.draw_9_slice_border)
        
        # 3. Custom Title Bar / Draggable area inside the border (Solid Black bg)
        self.title_bar = tk.Frame(self.canvas, bg=BG_COLOR, height=35)
        # Position it just inside the top border
        self.title_bar.place(x=self.border_thick, y=self.border_thick, 
                             relwidth=1.0, width=-(self.border_thick * 2))
        self.title_bar.pack_propagate(False)
        
        # Close Button
        self.close_btn = tk.Button(self.title_bar, text="✕", bg=BG_COLOR, fg="white", 
                                   bd=0, activebackground="#e81123", activeforeground="white",
                                   font=("Arial", 12, "bold"), command=self.destroy)
        self.close_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        # Window Title as Pixel Art
        self.title_img_pil = generate_text_image("DELTARUNE 한글 패치", PIXEL_FONT_FILE, 18, fill=FG_COLOR)
        self.title_img = ImageTk.PhotoImage(self.title_img_pil)
        self.title_label = tk.Label(self.title_bar, image=self.title_img, bg=BG_COLOR, bd=0, highlightthickness=0)
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        # 4. Window Content Area (Solid Black bg)
        self.content = tk.Frame(self.canvas, bg=BG_COLOR)
        self.content.place(x=self.border_thick, y=self.border_thick + 35, 
                           relwidth=1.0, relheight=1.0, 
                           width=-(self.border_thick * 2), height=-(self.border_thick * 2 + 35))
        
        # Bind window dragging events
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)

        # 5. Initialize Patcher Resources & Logic
        self.script_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.xdelta_path = shutil.which("xdelta3") or shutil.which("xdelta3.EXE") or resource_path("xdelta3.exe")
        
        # 6. Create inner UI elements
        self._create_ui()
        
        if not self.xdelta_path:
            self.log("* xdelta3 실행 파일을 찾을 수 없습니다.", color=ERROR_COLOR)
            messagebox.showerror("오류", "xdelta3 실행 파일을 찾을 수 없습니다.")
            return

        self.log("* 패치를 적용할 DELTARUNE 폴더를 선택해주세요.")
        self._auto_detect_folder()

    def draw_9_slice_border(self, event=None):
        """Slices the source image and stretches it to fit the current window size."""
        w = self.winfo_width()
        h = self.winfo_height()
        dst_t = self.border_thick
        
        img_w, img_h = self.base_image.size
        # Dynamically determine source border thickness based on image size (defaulting to 15 or 1/3 width)
        src_t = min(15, img_w // 3, img_h // 3)
        
        src_left = src_t
        src_right = img_w - src_t
        src_top = src_t
        src_bottom = img_h - src_t
        
        dst_right = w - dst_t
        dst_bottom = h - dst_t
        
        # Box definitions: (left, upper, right, lower)
        slices = {
            "top_left":     (0, 0, src_left, src_top),
            "top":          (src_left, 0, src_right, src_top),
            "top_right":    (src_right, 0, img_w, src_top),
            "left":         (0, src_top, src_left, src_bottom),
            "center":       (src_left, src_top, src_right, src_bottom),
            "right":        (src_right, src_top, img_w, src_bottom),
            "bottom_left":  (0, src_bottom, src_left, img_h),
            "bottom":       (src_left, src_bottom, src_right, img_h),
            "bottom_right": (src_right, src_bottom, img_w, img_h)
        }
        
        # Target sizes for scaling
        targets = {
            "top_left":     (dst_t, dst_t),
            "top":          (max(1, dst_right - dst_t), dst_t),
            "top_right":    (dst_t, dst_t),
            "left":         (dst_t, max(1, dst_bottom - dst_t)),
            "center":       (max(1, dst_right - dst_t), max(1, dst_bottom - dst_t)),
            "right":        (dst_t, max(1, dst_bottom - dst_t)),
            "bottom_left":  (dst_t, dst_t),
            "bottom":       (max(1, dst_right - dst_t), dst_t),
            "bottom_right": (dst_t, dst_t)
        }
        
        # Target placements on the Canvas
        positions = {
            "top_left":     (0, 0),
            "top":          (dst_t, 0),
            "top_right":    (dst_right, 0),
            "left":         (0, dst_t),
            "center":       (dst_t, dst_t),
            "right":        (dst_right, dst_t),
            "bottom_left":  (0, dst_bottom),
            "bottom":       (dst_t, dst_bottom),
            "bottom_right": (dst_right, dst_bottom)
        }
        
        # Render the slices
        self.canvas.delete("border") # Clear old border graphics
        self.images = {} # Keep references to prevent garbage collection
        
        for key in slices:
            part = self.base_image.crop(slices[key])
            part = part.resize(targets[key], Image.Resampling.NEAREST)
            self.images[key] = ImageTk.PhotoImage(part)
            self.canvas.create_image(positions[key][0], positions[key][1], 
                                     image=self.images[key], anchor=tk.NW, tags="border")
            
        # Lift UI elements back to the top layer above the background canvas graphics
        self.title_bar.lift()
        self.content.lift()

    # Window Dragging Logic
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    # Register Window in Taskbar and Alt+Tab
    def set_appwindow(self):
        try:
            from ctypes import windll
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            
            hwnd = windll.user32.GetParent(self.winfo_id())
            if hwnd == 0:
                hwnd = self.winfo_id()
                
            style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            
            windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            
            self.withdraw()
            self.after(10, self.deiconify)
        except Exception as e:
            self.log(f"* 태스크바 등록 실패: {e}", color="#FFFF00")

    # ----------------- Create Internal UI Elements -----------------
    def _create_ui(self):
        # Title Header Label
        pil_title = generate_text_image("* DELTARUNE 한글 패치", PIXEL_FONT_FILE, TITLE_FONT_SIZE)
        self.title_img_main = ImageTk.PhotoImage(pil_title)
        self.title_label_main = tk.Label(self.content, image=self.title_img_main, bg=BG_COLOR, bd=0, highlightthickness=0)
        self.title_label_main.pack(pady=(10, 15))

        # Folder Selection Row
        folder_frame = tk.Frame(self.content, bg=BG_COLOR)
        folder_frame.pack(fill="x", pady=5, padx=20)

        self.folder_btn = create_image_button(folder_frame, "폴더 선택", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.choose_folder)
        self.folder_btn.pack(side="left", padx=(0, 10))

        pil_selected = generate_text_image("* 선택된 폴더: 없음", PIXEL_FONT_FILE, LOG_FONT_SIZE)
        self.selected_img = ImageTk.PhotoImage(pil_selected)
        self.selected_folder_label = tk.Label(folder_frame, image=self.selected_img, bg=BG_COLOR, bd=0, highlightthickness=0)
        self.selected_folder_label.pack(side="left", fill="y")

        # Scrollable Log Display
        self.log_display = LogElement(self.content)
        self.log_display.pack(fill="both", expand=True, pady=10, padx=20)

        # Bottom Button Row
        button_frame = tk.Frame(self.content, bg=BG_COLOR)
        button_frame.pack(fill="x", pady=(5, 10), padx=20)

        self.close_btn_bottom = create_image_button(button_frame, "닫기", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.destroy)
        self.close_btn_bottom.pack(side="left")

        self.copy_btn = create_image_button(button_frame, "로그 복사", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, 
                                            command=lambda: self.copy_logs())
        self.copy_btn.pack(side="right", padx=(10, 0))

        self.clear_btn = create_image_button(button_frame, "로그 지우기", PIXEL_FONT_FILE, BUTTON_FONT_SIZE, command=self.log_display.clear)
        self.clear_btn.pack(side="right")

    # ----------------- Utility Logging -----------------
    def log(self, msg, color=FG_COLOR):
        self.log_display.log(msg, color=color)

    def copy_logs(self):
        if copy_log_to_clipboard(self, self.log_display.messages_plain):
            self.log("* 로그가 클립보드에 복사되었습니다!")
        else:
            self.log("* 로그 복사 실패!", color=ERROR_COLOR)

    # ----------------- Game Auto Detection -----------------
    def _auto_detect_folder(self):
        try:
            exe_in_script = os.path.join(self.script_dir, "DELTARUNE.exe")
            if os.path.isfile(exe_in_script):
                self.log(f"* 패처 폴더에서 DELTARUNE 발견: {exe_in_script}")
                if messagebox.askyesno("DELTARUNE 감지", "델타룬이 감지되었습니다. 바로 패치를 시작할까요?"):
                    self.patch_game(self.script_dir)
                    return

            if os.name == "nt":
                pf86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
                steam_path = os.path.join(pf86, "Steam", "steamapps", "common", "DELTARUNE")
                exe_in_steam = os.path.join(steam_path, "DELTARUNE.exe")
                if os.path.isfile(exe_in_steam):
                    self.log(f"* Steam 설치 경로에서 DELTARUNE.exe 발견: {exe_in_steam}")
                    if messagebox.askyesno("자동 감지", "Steam으로 설치된 델타룬을 감지했습니다. 바로 패치를 시작할까요?"):
                        self.update_folder_label(steam_path)
                        self.patch_game(steam_path)
        except Exception as e:
            self.log(f"* 자동 감지 오류: {e}", color=ERROR_COLOR)

    # ----------------- Folder Label Update -----------------
    def update_folder_label(self, path):
        display_text = f"* 선택된 폴더: {truncate_path(path)}"
        pil_selected = generate_text_image(display_text, PIXEL_FONT_FILE, LOG_FONT_SIZE)
        self.selected_img = ImageTk.PhotoImage(pil_selected)
        self.selected_folder_label.configure(image=self.selected_img)

    # ----------------- Folder Chooser -----------------
    def choose_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            self.log("* 폴더 선택 취소", color="#BBBBBB")
            return
        
        self.log(f"* 선택된 폴더: {folder}")
        self.update_folder_label(folder)

        exe_path = os.path.join(folder, 'DELTARUNE.exe')
        if not os.path.isfile(exe_path):
            self.log("* DELTARUNE.exe를 찾을 수 없음!", color=ERROR_COLOR)
            messagebox.showerror("오류", "잘못된 경로입니다! DELTARUNE.exe가 들어있는 폴더를 선택해주세요.")
            return
        
        self.patch_game(folder)

    # ----------------- Apply Patch Sequences -----------------
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
            lang_src = resource_path('lang')
            if not os.path.isdir(lang_src):
                self.log("'lang' 폴더 없음!", color=ERROR_COLOR)
                raise FileNotFoundError("'lang' 폴더가 존재하지 않습니다.")

            for d in os.listdir(lang_src):
                src = os.path.join(lang_src, d)
                dst = os.path.join(target_dir, d)
                if os.path.isdir(src):
                    self.log(f"* 복사: {src} -> {dst}")
                    shutil.copytree(src, dst, dirs_exist_ok=True)

            self.log("* 한글 패치 완료!")
            if messagebox.askyesno("완료", "패치가 성공적으로 완료되었습니다! 지금 게임을 실행할까요?"):
                subprocess.Popen([os.path.join(target_dir, 'DELTARUNE.exe')], cwd=target_dir)
        except Exception as e:
            self.log(f"* 오류 발생: {e}", color=ERROR_COLOR)
            messagebox.showerror("오류", f"패치 도중 오류가 발생했습니다:\n{e}")

    # ----------------- XDelta Application & Checksum -----------------
    def verify_and_apply_xdelta(self, delta_file, target_file, expected_sha1=None):
        if not os.path.exists(target_file):
            self.log(f"* 대상 파일 없음: {target_file}", color=ERROR_COLOR)
            raise FileNotFoundError(f"파일 없음: {target_file}")

        if not os.path.exists(delta_file):
            self.log(f"* 패치 파일(xdelta) 없음: {os.path.basename(delta_file)} (챕터 미지원 혹은 누락)", color="#FFFF00")
            return

        # Calculate SHA1
        sha1 = hashlib.sha1()
        with open(target_file, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        current_sha1 = sha1.hexdigest()
        self.log(f"* 대상 SHA1: {current_sha1}")

        if expected_sha1 and current_sha1 != expected_sha1:
            self.log("* 경고: SHA1 불일치! 이미 패치되었거나 파일이 변경됨", color=ERROR_COLOR)
            if not messagebox.askyesno("체크섬 불일치", "SHA1이 예상과 다릅니다. 계속 진행할까요?"):
                raise ValueError("체크섬 불일치로 패치 중단")

        tmp_file = target_file + ".tmp"
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

        # 1. Try applying patch using pyxdelta (Python native)
        try:
            import pyxdelta
            self.log(f"* pyxdelta로 패치 적용 시도 중...")
            pyxdelta.decode(target_file, delta_file, tmp_file)
            self.log(f"* 패치 완료: {os.path.basename(target_file)} (pyxdelta)")
        except (ImportError, Exception) as pyx_err:
            # 2. Fallback to external xdelta3 executable
            self.log(f"* pyxdelta 사용 불가 또는 오류: {pyx_err}. xdelta3 실행 파일로 시도합니다.", color="#FFFF00")
            
            xdelta_exe = self.xdelta_path
            if not xdelta_exe:
                self.log("* xdelta3 실행 파일을 찾을 수 없습니다!", color=ERROR_COLOR)
                raise FileNotFoundError("xdelta3.exe 필요")

            cmd = [xdelta_exe, '-d', '-s', target_file, delta_file, tmp_file]
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            try:
                subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, check=True)
                self.log(f"* 패치 완료: {os.path.basename(target_file)} (xdelta3)")
            except subprocess.CalledProcessError as e:
                if "XD3_INVALID_INPUT" in e.stderr or "invalid input file" in e.stderr.lower():
                    self.log("* 이미 패치되었거나 변조된 파일입니다!", color=ERROR_COLOR)
                else:
                    self.log(f"* 패치 실패: {e.stderr.strip()}", color=ERROR_COLOR)
                raise

        os.replace(tmp_file, target_file)

if __name__ == "__main__":
    # Ensure correct working directory context and load the border texture image
    border_img_path = resource_path("border_texture.png")
    
    # Run application
    app = DeltaruneKoreanPatcher(border_img_path, border_thickness=45)
    app.mainloop()
