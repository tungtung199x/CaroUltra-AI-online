import sys
import ctypes
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import subprocess
import threading
import queue
import time
import os
import json
import shutil

try:
    import websocket
except ImportError:
    websocket = None

# ==================== BẬT CHẾ ĐỘ NÉT CAO (HIGH-DPI) ====================
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
# =======================================================================

ctk.set_appearance_mode("System")  
ctk.set_default_color_theme("blue")  

winsound = None
if sys.platform == "win32":
    try: 
        import winsound
    except ImportError: 
        pass

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==================== CẤU HÌNH SERVER ONLINE ====================
SERVER_URL = "wss://caroultra-ai-online.onrender.com" 
# ================================================================

ENGINE_FILENAME = "pbrain-rapfi-windows-avx2.exe" if sys.platform == "win32" else "pbrain-rapfi-mac"
ENGINE_PATH = os.path.join(BASE_DIR, ENGINE_FILENAME)
TING_SOUND_PATH = os.path.join(BASE_DIR, "ting.wav")
VICTORY_SOUND_PATH = os.path.join(BASE_DIR, "victory.wav")
IDEA_SOUND_PATH = os.path.join(BASE_DIR, "idea.wav")
TIME_SOUND_PATH = os.path.join(BASE_DIR, "time.wav")
ICON_ICO_PATH = os.path.join(BASE_DIR, "Ultra.ico")
ICON_ICNS_PATH = os.path.join(BASE_DIR, "Ultra.icns")

if sys.platform == "win32":
    app_data_dir = os.path.join(os.environ.get("APPDATA", BASE_DIR), "CaroUltraAI")
elif sys.platform == "darwin":
    app_data_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "CaroUltraAI")
else:
    app_data_dir = BASE_DIR

os.makedirs(app_data_dir, exist_ok=True)
CONFIG_PATH = os.path.join(app_data_dir, "caro_ultra_ai_settings.json")

DEFAULT_DIFF = {"Kiện tướng (0.2s)": 200, "Khó (5s)": 5000, "Đỉnh cao (12s)": 12000, "Tối thượng (20s)": 20000}
DEFAULT_LANG = {
    "mode": "Chế độ:", "mode_ai": "Ultra-AI", "mode_2p": "2 Người", "mode_ai_vs_ai": "AI vs AI", "mode_online": "Online", "symbol": "Quân:", 
    "symbol_x": "X", "symbol_o": "O", "board": "Bàn cờ:", "diff": "Độ khó:", "diff_x": "Độ khó X:", "diff_o": "Độ khó O:", "rule": "Luật:", "time_limit": "Thời Gian:",
    "new_game": "VÁN MỚI (F5)", "undo": "LÙI (1)", "redo": "TIẾN (2)", "hint": "GỢI Ý (H)",
    "pause": "⏸ DỪNG (SPACE)", "start": "▶ BẮT ĐẦU (SPACE)", "resume": "▶ TIẾP TỤC (SPACE)", "ai_match_paused": "⏸️ Trận đấu đang tạm dừng",
    "init_status": "", "turn_your": "Lượt của bạn ({})", "turn_2p": "Lượt của ({})", "turn_ai_vs_ai": "AI vs AI: Lượt của ({})", 
    "piece_x_status": "X", "piece_o_status": "O", "ai_thinking": "Ultra-AI đang suy nghĩ", "ai_taking_over": "Ultra-AI đang tiếp quản và suy nghĩ",
    "ai_rethinking": "Ultra-AI đang suy nghĩ lại", "hint_calculating": "💡 Ultra-AI đang tìm nước đi gợi ý",
    "hint_result": "💡 Đã tìm thấy nước đi gợi ý tốt nhất trên bàn cờ!", "hint_err": "Không thể tính toán gợi ý lúc này.",
    "win_msg": "NGƯỜI CHƠI ({}) THẮNG!", "ai_win_msg": "ULTRA-AI ({}) THẮNG!", "ai_vs_ai_win": "AI ({}) GIÀNH CHIẾN THẮNG!",
    "timeout_msg": "HẾT GIỜ! NGƯỜI CHƠI ({}) THẮNG DO ĐỐI THỦ CẠN THỜI GIAN!", "resgin_status": "ULTRA-AI ({}) XIN THUA!", 
    "err_title": "Lỗi", "limit_warn": "Kích thước bàn cờ hỗ trợ tối đa là 20x20!", "warning_title": "Thông báo", "rules_list": ["Tiêu chuẩn", "Chặn 2 đầu"],
    "sound_on": "🔊 Bật", "sound_off": "🔇 Tắt", "ai_ready": "Sẵn sàng! Bấm BẮT ĐẦU để AI đấu.", "unlimited_time": "⏱ Không giới hạn thời gian",
    "block_rule_warn": "Ultra-AI hiện chưa được huấn luyện theo luật 'Chặn 2 đầu' và vẫn sẽ thao tác theo luật tiêu chuẩn. Để có trải nghiệm trọn vẹn nhất với luật này, bạn nên ưu tiên trải nghiệm ở chế độ 2 người nhé!",
    "engine_err": "Lỗi khởi động engine", "ai_not_resp": "Ultra-AI chưa trả nước đi", "ai_err": "Lỗi AI", "sync_err": "Lỗi đồng bộ AI",
    "undo_msg": "Đã LÙI 1 BƯỚC. ", "redo_msg": "Đã TIẾN 1 BƯỚC. "
}

TRANSLATIONS_PATH = os.path.join(BASE_DIR, "translations.json")
try:
    with open(TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
        trans_data = json.load(f)
        DIFFICULTY = trans_data.get("DIFFICULTY", {"VI": DEFAULT_DIFF})
        LANG = trans_data.get("LANG", {"VI": DEFAULT_LANG})
except Exception:
    DIFFICULTY, LANG = {"VI": DEFAULT_DIFF}, {"VI": DEFAULT_LANG}

if sys.platform == "darwin":
    try:
        if os.path.exists(ENGINE_PATH):
            os.chmod(ENGINE_PATH, 0o755)
    except Exception:
        pass

EMPTY, HUMAN, AI = 0, 1, 2

class UltraAIEngine:
    def __init__(self, path, board_size=20, time_turn=50, rule=0):
        self.path = path
        self.board_size = board_size
        self.time_turn = time_turn
        self.rule = rule
        self.proc = None
        self.running = False
        self.q = queue.Queue()

    def start(self):
        if not os.path.exists(self.path): 
            raise FileNotFoundError(f"Không tìm thấy engine tại: {self.path}")
            
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(
            [self.path], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1, 
            creationflags=creation_flags
        )
        self.running = True
        threading.Thread(target=self._reader, daemon=True).start()
        
        self.send(f"START {self.board_size}")
        time.sleep(0.1)
        for _ in range(4):
            resp = self.get_response(timeout=0.3)
            if resp and "OK" in resp.upper(): 
                break
                
        thread_num = max(14, min(os.cpu_count() or 14, 32))
        self.send(f"INFO timeout_turn {self.time_turn}\nINFO rule {self.rule}\nINFO max_memory 4294967296\nINFO thread_num {thread_num}\nINFO time_left 99999999")
        time.sleep(0.05)

    def _reader(self):
        while self.running and self.proc and self.proc.poll() is None:
            try:
                line = self.proc.stdout.readline().strip()
                if line: 
                    self.q.put(line)
            except (ValueError, OSError): 
                break

    def send(self, cmd):
        if self.proc and self.proc.poll() is None:
            try: 
                self.proc.stdin.write(cmd + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError): 
                pass

    def get_response(self, timeout=6):
        try: 
            return self.q.get(timeout=timeout)
        except queue.Empty: 
            return None

    def stop(self):
        self.running = False
        if self.proc:
            try: 
                self.send("END")
                self.proc.terminate()
            except (OSError, ValueError): 
                pass
            self.proc = None

class CaroUltraAI:
    def __init__(self, root):
        self.root = root
        self.root.title("Caro Ultra-AI (Bản Online)")
        
        # === THÊM ĐOẠN NÀY ĐỂ CĂN GIỮA MÀN HÌNH KHI MỞ APP ===
        window_width = 980
        window_height = 1280
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_crd = int((screen_width / 2) - (window_width / 2))
        y_crd = int((screen_height / 2) - (window_height / 2))
        self.root.geometry(f"{window_width}x{window_height}+{x_crd}+{y_crd}")
        # ====================================================

        self.root.minsize(900, 950)
        try:
            if sys.platform == "win32" and os.path.exists(ICON_ICO_PATH):
                self.root.iconbitmap(ICON_ICO_PATH)
            elif sys.platform == "darwin" and os.path.exists(ICON_ICNS_PATH):
                self.root.iconbitmap(ICON_ICNS_PATH)
        except Exception:
            pass

        self.board_size = 20
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        
        self.game_over = self.is_ai_thinking = self.engine_synced = False
        self.is_ai_match_paused = True
        
        self.last_move = self.hover_cell = self.hint_cell = None
        self.winning_cells = []
        self.history = []
        
        self.engine = None
        self.current_turn = HUMAN
        self.sound_enabled = True
        
        self.timer_job = self.dot_animation_job = None
        self.dot_count = 0
        self.current_thinking_msg_key = ""
        self.time_remaining = {"X": 0, "O": 0}
        
        self.turn_time_limit = 35
        self.turn_time_remaining = {"X": 35, "O": 35}
        
        self.turn_timer_job = None
        self.holding_action = None
        
        self._last_pause_sig = self._last_btn_new_sig = None
        self._current_status_data = {}

        self.ws = None
        self.is_online_connected = False
        self.is_online_turn = False
        self.online_symbol = None
        self.opponent_name = "Đối thủ"  # overwritten by t("default_opp") after lang load
        self.score_me = 0
        self.score_opp = 0
        self.my_ready_for_rematch = False
        self.opponent_ready_for_rematch = False

        self.lang_var = ctk.StringVar(value="VI")
        self.game_mode_var = ctk.StringVar(value="Ultra-AI")
        self.player_symbol_var = ctk.StringVar(value="X")
        self.auto_rotate_var = ctk.BooleanVar(value=True)
        self.difficulty_var = ctk.StringVar(value="Kiện tướng (0.2s)")
        self.difficulty_x_var = ctk.StringVar(value="Kiện tướng (0.2s)")
        self.difficulty_o_var = ctk.StringVar(value="Kiện tướng (0.2s)")
        self.rule_var = ctk.StringVar(value="Tiêu chuẩn")
        self.time_minutes_var = ctk.StringVar(value="1")
        self.ui_style_var = ctk.StringVar(value="Cổ điển")
        self.board_size_var = ctk.StringVar(value="20x20")
        self.theme_var = ctk.StringVar(value="Sáng")
        self.room_id_var = ctk.StringVar(value="")
        self.player_name_var = ctk.StringVar(value="Tùng")
        
        # Bật tính năng theo dõi khi gõ phím để giới hạn 16 ký tự
        self.player_name_var.trace_add("write", self.limit_name_length)

        self.load_settings()
        self.board_margin = 22
        self.cell_size = 48
        self._resize_timer = None
        
        self.create_ui()
        self.new_game()
        self.change_theme_init()
        self.change_ui_style_init()
        
        self._bind_shortcuts()

    @property
    def is_dark_mode(self):
        return self.theme_var.get() in ["Tối", "Dark"]

    @property
    def is_standard_rule(self):
        return any(w in self.rule_var.get().lower() for w in ["standard", "tiêu chuẩn"])

    def _bind_shortcuts(self):
        self.root.bind("1", self.undo_move)
        self.root.bind("2", self.redo_move)
        self.root.bind("<Configure>", self.on_window_resize)
        self.root.bind("<F5>", self.request_new_game)
        self.root.bind("h", self.get_hint)
        self.root.bind("H", self.get_hint)
        self.root.bind("<space>", self.toggle_pause_resume)

    def _transition_with_fade(self, action_callback):
        # Lấy màu nền hiện tại trước khi đổi theme
        current_bg = "#0b141d" if self.is_dark_mode else "#ebebeb"
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        self.root.update_idletasks()
        geo = f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}"
        overlay.geometry(geo)
        overlay.configure(bg=current_bg)
        overlay.attributes("-alpha", 1.0)
        if sys.platform == "win32":
            overlay.transient(self.root)
        else:
            overlay.attributes("-topmost", True)
        self.root.update_idletasks()

        # Đổi theme ngay dưới lớp phủ
        action_callback()
        self.root.update_idletasks()

        # Fade mượt hơn: bước nhỏ + thời gian dài hơn
        def fade_out(alpha):
            try:
                if alpha > 0.02:
                    overlay.attributes("-alpha", alpha)
                    self.root.after(12, lambda: fade_out(alpha - 0.06))
                else:
                    overlay.destroy()
            except Exception:
                try:
                    overlay.destroy()
                except Exception:
                    pass
        fade_out(1.0)

    def t(self, key): 
        return LANG.get(self.lang_var.get(), LANG.get("VI", {})).get(key, key)
    
    def display_status(self, key, color=None, format_args=None, prefix_key=None, raw_text=False):
        if raw_text:
            text = key
            self._current_status_data = {"type": "raw", "text": text, "color": color}
        else:
            self._current_status_data = {"type": "static", "key": key, "color": color, "format_args": format_args or [], "prefix_key": prefix_key}
            text = self.t(key)
            if format_args: text = text.format(*format_args)
            if prefix_key: text = self.t(prefix_key) + text
            
        self.status.configure(text=text, text_color=color if color else ("black", "white"))

    def update_turn_status(self, mode_type=None, symbol=None):
        mode = self.game_mode_var.get()
        if mode == "Online":
            sym_to_check = self.online_symbol if self.is_online_turn else ("O" if self.online_symbol == "X" else "X")
            col = ("#22d3ee" if sym_to_check == "X" else "#ef4444") if self.is_dark_mode else ("#3498db" if sym_to_check == "X" else "#e74c3c")
            my_name = self.player_name_var.get().strip() or "Bạn"
            opp_name = self.opponent_name.strip() or "Đối thủ"
            turn_name = my_name if self.is_online_turn else opp_name
            
            # CHẾ ĐỘ ONLINE: Chỉ hiện "Lượt của [Tên]"
            self.display_status(self.t("online_turn").format(turn_name), color=col, raw_text=True)
            self.update_score_display()
            return

        # AI vs AI: Cố định tuyệt đối: X luôn là AI 1, O luôn là AI 2 bất kể ai đi trước
        if mode == "AI vs AI" or mode_type == "ai_vs_ai":
            first_sym = self.player_symbol_var.get() if hasattr(self, 'player_symbol_var') else "X"
            second_sym = "O" if first_sym == "X" else "X"
            
            # Xác định quân đi ở lượt hiện tại
            symbol = first_sym if len(self.history) % 2 == 0 else second_sym
            
            # ĐÍCH XÁC: X là AI 1, O là AI 2
            ai_name = "AI 1" if symbol == "X" else "AI 2"
            
            # CHẾ ĐỘ AI VS AI: Bỏ đuôi (X - Xanh)
            text = f"Lượt của {ai_name}"
            col = self.status_color_for_symbol(symbol)
            self.status.configure(text=text, text_color=col)
            self._current_status_data = {"type": "turn", "symbol": symbol, "mode_type": "ai_vs_ai"}
            return

        if symbol is None: symbol = self.player_symbol if self.current_turn == HUMAN else self.ai_symbol
        if mode_type is None: mode_type = "2p" if mode == "2 Người" else "ai"
        
        self._current_status_data = {"type": "turn", "symbol": symbol, "mode_type": mode_type}
        status_text = self.turn_status_text(symbol, mode_type=mode_type)
        self.status.configure(text=status_text, text_color=self.status_color_for_symbol(symbol))

    def turn_status_text(self, symbol, mode_type="ai"):
        # CHẾ ĐỘ 2 NGƯỜI
        if mode_type == "2p": 
            return "Lượt của Người 1" if symbol == "X" else "Lượt của Người 2"
            
        # CHẾ ĐỘ AI VS AI (Dự phòng)
        if mode_type == "ai_vs_ai": 
            return "Lượt của AI 1" if symbol == "X" else "Lượt của AI 2"
            
        # CHẾ ĐỘ ULTRA-AI
        if symbol == getattr(self, "player_symbol", "X"):
            return "Lượt của Bạn"
        else:
            return "Lượt của Ultra-AI"

    def status_color_for_symbol(self, symbol): 
        return ("#22d3ee" if symbol == "X" else "#ef4444") if self.is_dark_mode else ("#3498db" if symbol == "X" else "#e74c3c")

    def start_thinking_animation(self, msg_key, raw_text=False):
        self.current_thinking_msg_key = msg_key
        self.dot_count = 0
        self._is_raw_thinking = raw_text
        self._update_thinking_dots()

    def _update_thinking_dots(self):
        if (not self.is_ai_thinking and not getattr(self, '_is_waiting_online', False)) or self.is_ai_match_paused: return
        dots = '.' * (self.dot_count % 4)
        spaces = ' ' * (3 - len(dots))
        base_text = self.current_thinking_msg_key if getattr(self, '_is_raw_thinking', False) else self.t(self.current_thinking_msg_key)
        self.status.configure(text=f"{base_text}{dots}{spaces}", text_color="#ef4444")
        self.dot_count += 1
        self.dot_animation_job = self.root.after(400, self._update_thinking_dots)

    def stop_thinking_animation(self):
        if self.dot_animation_job:
            self.root.after_cancel(self.dot_animation_job)
            self.dot_animation_job = None
        self._is_waiting_online = False

    def play_sound(self, path):
        if not self.sound_enabled: return
        try:
            if sys.platform == "win32" and winsound: winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif sys.platform == "darwin": subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("paplay"): subprocess.Popen(["paplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("aplay"): subprocess.Popen(["aplay", "-q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError): pass

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.btn_sound.configure(text=self.t("sound_on") if self.sound_enabled else self.t("sound_off"))
        self.save_settings()

    def update_minus_button_color(self):
        try: val = int(float(self.time_minutes_var.get().strip())) if self.time_minutes_var.get().strip() else 0
        except ValueError: val = 0
        self.btn_minus.configure(fg_color="#e74c3c" if val > 0 else "#7f8c8d", hover_color="#c0392b" if val > 0 else "#95a5a6")

    def set_time_controls_enabled(self, enabled: bool):
        """Khóa / mở khóa: thời gian + bàn cờ + luật — dùng cho Online khi đã có quân"""
        if not hasattr(self, "btn_minus"):
            return
        is_dark = self.is_dark_mode
        disabled_bg = "#21262d" if is_dark else "#e2e8f0"
        disabled_fg = "#6e7681" if is_dark else "#64748b"

        state = "normal" if enabled else "disabled"

        # Nút thời gian
        if enabled:
            self.btn_minus.configure(state="normal")
            self.btn_plus.configure(state="normal", fg_color="#2980b9", hover_color="#3498db", text_color="white")
            self.time_entry.configure(state="normal")
            self.update_minus_button_color()
        else:
            self.btn_minus.configure(state="disabled", fg_color=disabled_bg, hover_color=disabled_bg, text_color=disabled_fg)
            self.btn_plus.configure(state="disabled", fg_color=disabled_bg, hover_color=disabled_bg, text_color=disabled_fg)
            self.time_entry.configure(state="disabled")

        # Bàn cờ + Luật
        if hasattr(self, "size_menu"):
            self.size_menu.configure(state=state)
        if hasattr(self, "rule_menu"):
            self.rule_menu.configure(state=state)
        if hasattr(self, "lbl_board"):
            self.lbl_board.configure(text_color=("black", "white") if enabled else "gray")
        if hasattr(self, "lbl_rule"):
            self.lbl_rule.configure(text_color=("black", "white") if enabled else "gray")
        if hasattr(self, "lbl_time_limit"):
            self.lbl_time_limit.configure(text_color=("black", "white") if enabled else "gray")

    def change_time(self, delta):
        # Không cho đổi thời gian khi đang Online và đã có quân cờ
        if self.game_mode_var.get() == "Online" and (self.history or self.game_over):
            return
        try: current = int(float(self.time_minutes_var.get().strip())) if self.time_minutes_var.get().strip() else 0
        except ValueError: current = 0
        new_time = max(0, current + delta)
        self.time_minutes_var.set(str(new_time))
        self.update_minus_button_color()
        self.save_settings()
        self.init_match_timers()

        # Báo cho server khi đổi setting Online (chỉ khi chưa đánh)
        if self.game_mode_var.get() == "Online" and self.ws and self.is_online_connected:
            try:
                self.ws.send(json.dumps({
                    "type": "update_settings",
                    "board_size": self.board_size_var.get(),
                    "rule": self.rule_var.get(),
                    "time_limit": self.get_selected_time_limit_seconds()
                }))
            except Exception:
                pass

    def on_time_entry_change(self, event=None):
        if self.game_mode_var.get() == "Online" and (self.history or self.game_over):
            return
        self.update_minus_button_color()
        self.save_settings()
        self.init_match_timers()

        # Gửi setting mới lên server nếu đang chơi online
        if self.game_mode_var.get() == "Online" and self.ws and self.is_online_connected:
            try:
                self.ws.send(json.dumps({
                    "type": "update_settings",
                    "board_size": self.board_size_var.get(),
                    "rule": self.rule_var.get(),
                    "time_limit": self.get_selected_time_limit_seconds()
                }))
            except Exception:
                pass

    def start_hold_change(self, delta):
        self.change_time(delta); self.holding_action = self.root.after(400, lambda: self.keep_changing(delta))

    def keep_changing(self, delta):
        if self.holding_action:
            self.change_time(delta); self.holding_action = self.root.after(150, lambda: self.keep_changing(delta))

    def stop_hold_change(self, event=None):
        if self.holding_action: self.root.after_cancel(self.holding_action); self.holding_action = None

    def get_selected_time_limit_seconds(self):
        try:
            val = int(float(self.time_minutes_var.get().strip())) if self.time_minutes_var.get().strip() else 0
            return 0 if val <= 0 else val * 60
        except (ValueError, TypeError): return 0

    def init_match_timers(self):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        if self.turn_timer_job:
            self.root.after_cancel(self.turn_timer_job)
            self.turn_timer_job = None

        limit_secs = self.get_selected_time_limit_seconds()
        self.time_remaining = {"X": limit_secs, "O": limit_secs}
        self.turn_time_remaining = {"X": self.turn_time_limit, "O": self.turn_time_limit}
        self.update_timer_display()
        self.update_turn_bar()

        if self.history:
            self.start_turn_timer()
        elif self.game_mode_var.get() != "Online" and (self.history or self.game_mode_var.get() in ("2 Người", "AI vs AI")):
            self.start_turn_timer()

        if limit_secs > 0 and len(self.history) > 0:
            self.run_match_timer()

    def get_current_symbol(self):
        mode = self.game_mode_var.get()
        if mode == "Online":
            return self.online_symbol if self.is_online_turn else ("O" if self.online_symbol == "X" else "X")
        return "X" if self.current_turn == HUMAN else "O" if mode in ("2 Người", "AI vs AI") else (self.player_symbol if self.current_turn == HUMAN else self.ai_symbol)

    def start_turn_timer(self, symbol=None, turn_secs=None, deadline=None):
        if self.turn_timer_job:
            try: self.root.after_cancel(self.turn_timer_job)
            except Exception: pass
            self.turn_timer_job = None
        
        # Kiểm tra xem tổng thời gian ván đấu có được bật hay không (> 0)
        limit_secs = self.get_selected_time_limit_seconds()
        if limit_secs == 0:
            return

        if self.game_mode_var.get() == "Online" and not self.history:
            return

        symbol = symbol or self.get_current_symbol()
        
        # CỐ ĐỊNH thời gian đếm ngược cho mỗi lượt đi là 35 giây
        self.turn_time_limit = int(turn_secs) if turn_secs else 35

        # Online: dùng deadline từ server — chỉ người đang đi đếm, bên kia đứng yên full
        if self.game_mode_var.get() == "Online" and deadline:
            self._turn_deadline = float(deadline)
            remaining = max(0, int(round(self._turn_deadline - time.time())))
            other = "O" if symbol == "X" else "X"
            self.turn_time_remaining = {symbol: remaining, other: self.turn_time_limit}
        else:
            self._turn_deadline = None
            self.turn_time_remaining = {"X": self.turn_time_limit, "O": self.turn_time_limit}

        self.update_turn_bar()
        if not self.game_over and not self.is_ai_match_paused:
            # Online tick 250ms cho mượt + chính xác hơn; offline 1000ms
            interval = 250 if self.game_mode_var.get() == "Online" else 1000
            self.turn_timer_job = self.root.after(interval, self.run_turn_timer)

    def run_turn_timer(self):
        if self.game_over or self.is_ai_match_paused:
            self.turn_timer_job = None
            return
            
        is_online = self.game_mode_var.get() == "Online"
        current_sym = (getattr(self, "_server_turn_symbol", None) or self.get_current_symbol()) if is_online else self.get_current_symbol()

        if is_online and getattr(self, "_turn_deadline", None):
            # Tính remaining theo deadline server — không bị lệch do lag tick
            remaining = max(0, int(round(self._turn_deadline - time.time())))
            prev = self.turn_time_remaining.get(current_sym, remaining)
            other = "O" if current_sym == "X" else "X"
            self.turn_time_remaining = {current_sym: remaining, other: self.turn_time_limit}
            if prev > 5 >= remaining:
                self.play_sound(TIME_SOUND_PATH)
        else:
            self.turn_time_remaining[current_sym] -= 1
            if self.turn_time_remaining[current_sym] == 5:
                self.play_sound(TIME_SOUND_PATH)

        self.update_turn_bar()
        
        if self.turn_time_remaining.get(current_sym, 0) <= 0:
            if is_online and self.ws and self.is_online_connected:
                # Online: gửi timeout lên server, đợi server xác nhận (tránh double)
                try:
                    self.ws.send(json.dumps({
                        "type": "timeout",
                        "loser": current_sym
                    }))
                except Exception:
                    pass
                # Vẫn xử lý local nếu server chậm, handle_timeout có guard game_over
                self.handle_timeout(current_sym)
            else:
                self.handle_timeout(current_sym)
            return
            
        interval = 250 if is_online else 1000
        self.turn_timer_job = self.root.after(interval, self.run_turn_timer)

    def update_turn_bar(self):
        if not hasattr(self, "turn_bar_left"): return
        
        limit_secs = self.get_selected_time_limit_seconds() if hasattr(self, "get_selected_time_limit_seconds") else 0
        if limit_secs == 0:
            for widget_name in ["turn_bar_left", "turn_bar_right", "lbl_turn_left", "lbl_turn_right"]:
                if hasattr(self, widget_name):
                    w = getattr(self, widget_name)
                    if w.winfo_exists() and w.winfo_ismapped():
                        setattr(self, f"_{widget_name}_info", w.pack_info())
                        w.pack_forget()
            
            if hasattr(self, "lbl_turn_left"): self.lbl_turn_left.configure(text="")
            if hasattr(self, "lbl_turn_right"): self.lbl_turn_right.configure(text="")
            if hasattr(self, "turn_bar_left"): self.turn_bar_left.set(1.0)
            # 1. Trả giá trị dự phòng về 0.0 (vì thanh đã đảo màu)
            if hasattr(self, "turn_bar_right"): self.turn_bar_right.set(0.0) 
            return

        # 2. Khôi phục đúng thứ tự pack để đối xứng
        for widget_name, is_bar in [("lbl_turn_left", False), ("turn_bar_left", True), ("turn_bar_right", True), ("lbl_turn_right", False)]:
            if hasattr(self, widget_name):
                w = getattr(self, widget_name)
                if w.winfo_exists() and not w.winfo_ismapped():
                    info = getattr(self, f"_{widget_name}_info", None)
                    if info:
                        w.pack(**info)
                    else:
                        if widget_name == "lbl_turn_left":
                            w.pack(side="left", padx=(0, 6))
                        elif widget_name == "turn_bar_left":
                            w.pack(side="left", fill="x", expand=True, pady=(4, 0))
                        elif widget_name == "turn_bar_right":
                            w.pack(side="left", fill="x", expand=True, pady=(4, 0))
                        elif widget_name == "lbl_turn_right":
                            w.pack(side="left", padx=(6, 0))

        turn_limit = getattr(self, "turn_time_limit", 0)
        if turn_limit <= 0:
            turn_limit = limit_secs
            self.turn_time_limit = limit_secs

        my_sym = self.online_symbol if self.game_mode_var.get() == "Online" and self.online_symbol else (self.player_symbol if self.game_mode_var.get() == "Ultra-AI" else "X")
        opp_sym = "O" if my_sym == "X" else "X"
        
        left_secs = self.turn_time_remaining.get(my_sym, turn_limit)
        right_secs = self.turn_time_remaining.get(opp_sym, turn_limit)
        
        # BÊN TRÁI: Chạy thuận (xanh cạn dần về bên trái)
        self.turn_bar_left.set(max(0, min(1, left_secs / turn_limit)))
        
        # 3. BÊN PHẢI: Sử dụng "1.0 -" để thanh xanh cạn dần về bên phải
        self.turn_bar_right.set(1.0 - max(0, min(1, right_secs / turn_limit)))
        
        if hasattr(self, "lbl_turn_left"): 
            self.lbl_turn_left.configure(text=f'{left_secs}s')
            self.lbl_turn_left.configure(text_color="#ef4444" if left_secs <= 5 else ("#475569", "#cbd5e1"))
        if hasattr(self, "lbl_turn_right"): 
            self.lbl_turn_right.configure(text=f'{right_secs}s')
            self.lbl_turn_right.configure(text_color="#ef4444" if right_secs <= 5 else ("#475569", "#cbd5e1"))

        current = self.get_current_symbol()
        self.update_active_score_card(current)

    def update_active_score_card(self, current_sym):
        if not hasattr(self, "score_left_card"): return
        
        # ĐÃ THÊM: Nếu ván đấu đã kết thúc, luôn bắt viền xanh sáng ở thẻ đang giữ quân X (vì X sẽ đi trước)
        if getattr(self, "game_over", False):
            current_sym = "X"
            
        my_sym = self.online_symbol if self.game_mode_var.get() == "Online" and self.online_symbol else (self.player_symbol if self.game_mode_var.get() == "Ultra-AI" else "X")
        left_active = current_sym == my_sym
        
        active_border = "#22c55e" if not self.is_dark_mode else "#4ade80"
        normal_border = "#cbd5e1" if not self.is_dark_mode else "#334155"
        try:
            self.score_left_card.configure(border_width=2 if left_active else 1, border_color=active_border if left_active else normal_border)
            self.score_right_card.configure(border_width=2 if not left_active else 1, border_color=active_border if not left_active else normal_border)
        except Exception: pass

    def run_match_timer(self):
        if self.game_over or self.is_ai_match_paused: return

        # Online: đồng hồ tổng suy ra từ base times + deadline server (không tự trừ mù)
        if self.game_mode_var.get() == "Online":
            base = getattr(self, "_match_base_times", None)
            deadline = getattr(self, "_turn_deadline", None)
            turn_secs = getattr(self, "turn_time_limit", 35)
            current_sym = getattr(self, "_server_turn_symbol", None) or self.get_current_symbol()
            if base and deadline and self.get_selected_time_limit_seconds() > 0:
                elapsed = max(0.0, turn_secs - max(0.0, deadline - time.time()))
                display = {
                    "X": int(base.get("X", 0)),
                    "O": int(base.get("O", 0))
                }
                display[current_sym] = max(0, int(round(display.get(current_sym, 0) - elapsed)))
                self.time_remaining = display
                self.update_timer_display()
            self.timer_job = self.root.after(250, self.run_match_timer)
            return

        current_sym = self.get_current_symbol()
        if self.time_remaining[current_sym] > 0:
            self.time_remaining[current_sym] -= 1
            if self.time_remaining[current_sym] == 5:
                self.play_sound(TIME_SOUND_PATH)
            self.update_timer_display()
            if self.time_remaining[current_sym] <= 0:
                self.handle_timeout(current_sym)
                return
        self.timer_job = self.root.after(1000, self.run_match_timer)

    def update_timer_display(self):
        limit_secs = self.get_selected_time_limit_seconds()
        if limit_secs == 0:
            if hasattr(self, "lbl_score_left_time"): self.lbl_score_left_time.configure(text="∞")
            if hasattr(self, "lbl_score_right_time"): self.lbl_score_right_time.configure(text="∞")
            # Ẩn hoặc làm trống thanh tiến trình thời gian khi không giới hạn thời gian
            if hasattr(self, "turn_bar_left") and self.turn_bar_left.winfo_exists():
                self.turn_bar_left.pack_forget()
            if hasattr(self, "turn_bar_right") and self.turn_bar_right.winfo_exists():
                self.turn_bar_right.pack_forget()
        else:
            mx, sx = divmod(max(0, self.time_remaining.get("X", 0)), 60)
            mo, so = divmod(max(0, self.time_remaining.get("O", 0)), 60)
            x_text, o_text = f"⏱ {mx:02d}:{sx:02d}", f"⏱ {mo:02d}:{so:02d}"
            mode = self.game_mode_var.get()
            if hasattr(self, "lbl_score_left_time"):
                if mode == "Online":
                    my_sym = self.online_symbol or "X"
                    self.lbl_score_left_time.configure(text=x_text if my_sym == "X" else o_text)
                    self.lbl_score_right_time.configure(text=o_text if my_sym == "X" else x_text)
                else:
                    self.lbl_score_left_time.configure(text=x_text); self.lbl_score_right_time.configure(text=o_text)
            if hasattr(self, "lbl_timer"): self.lbl_timer.configure(text="")
            self.update_turn_bar()

    def add_score(self, winning_symbol):
        mode = self.game_mode_var.get()
        if mode == "Online":
            if winning_symbol == self.online_symbol:
                self.score_me += 1
            else:
                self.score_opp += 1
        else:
            if winning_symbol == "X": self.score_me += 1
            elif winning_symbol == "O": self.score_opp += 1
        self.update_score_display()

    def update_score_display(self):
        if not hasattr(self, 'lbl_score_left'): return
        mode = self.game_mode_var.get()
        p_name = self.player_name_var.get().strip() or "Bạn"
        opp_name = self.opponent_name.strip() or "Đối thủ"
        
        x_color = "#22d3ee" if self.is_dark_mode else "#3498db"
        o_color = "#ef4444" if self.is_dark_mode else "#e74c3c"

        if mode == "Online":
            my_sym = self.online_symbol if self.online_symbol else "X"
            opp_sym = "O" if my_sym == "X" else "X"
        elif mode == "Ultra-AI":
            my_sym = self.player_symbol
            opp_sym = self.ai_symbol
        else:
            my_sym = "X"
            opp_sym = "O"

        if mode == "Online":
            left_text = p_name
            right_text = opp_name
            left_color = x_color if my_sym == "X" else o_color
            right_color = x_color if opp_sym == "X" else o_color
        elif mode == "Ultra-AI":
            left_text = p_name
            right_text = "Ultra-AI"
            left_color = x_color if my_sym == "X" else o_color
            right_color = x_color if opp_sym == "X" else o_color
        elif mode == "2 Người":
            # Đã xóa [X] và [O] ở đây
            left_text = "Người 1"
            right_text = "Người 2"
            left_color, right_color = x_color, o_color
        else:
            # Chế độ AI vs AI (Đã xóa [X] và [O])
            left_text = "AI 1"
            right_text = "AI 2"
            left_color, right_color = x_color, o_color
            
        self.lbl_score_left.configure(text=left_text, text_color=left_color)
        self.lbl_score_right.configure(text=right_text, text_color=right_color)
        self.lbl_score_left_points.configure(text=str(self.score_me), text_color=left_color)
        self.lbl_score_right_points.configure(text=str(self.score_opp), text_color=right_color)
        self.lbl_score_left_symbol.configure(text=my_sym, fg_color=left_color)
        self.lbl_score_right_symbol.configure(text=opp_sym, fg_color=right_color)
        self.update_timer_display()
        self.update_active_score_card(self.get_current_symbol())

    def handle_timeout(self, loser_sym):
        if self.game_over: return
        if self.timer_job: self.root.after_cancel(self.timer_job); self.timer_job = None
        if self.turn_timer_job: self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
        winner_sym = "O" if loser_sym == "X" else "X"
        
        self.add_score(winner_sym)
        self.display_status("timeout_msg", color=self.status_color_for_symbol(winner_sym), format_args=[winner_sym])
        self.game_over = True
        if self.game_mode_var.get() == "AI vs AI":
            self.is_ai_thinking = False
            self.stop_thinking_animation()
        self.update_pause_btn_state()
        self.play_sound(VICTORY_SOUND_PATH)
        self.modern_canvas.configure(cursor="hand2")

    def on_rule_change(self, value):
        if self.game_mode_var.get() == "Online" and (self.history or self.game_over):
            return
        self.save_settings()
        if any(w in value.lower() for w in ["chặn 2 đầu", "block"]):
            messagebox.showwarning(self.t("warning_title"), self.t("block_rule_warn"))
        # Sync rule lên server khi Online
        if self.game_mode_var.get() == "Online" and self.ws and self.is_online_connected:
            try:
                self.ws.send(json.dumps({
                    "type": "update_settings",
                    "board_size": self.board_size_var.get(),
                    "rule": self.rule_var.get(),
                    "time_limit": self.get_selected_time_limit_seconds()
                }))
            except Exception:
                pass

    def load_settings(self):
        if not os.path.exists(CONFIG_PATH): return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f: data = json.load(f)
            lang = data.get("lang", "VI") if data.get("lang") in ("VI", "EN") else "VI"
            self.lang_var.set(lang)
            saved_mode = data.get("game_mode", "Ultra-AI")
            if saved_mode not in ("Ultra-AI", "2 Người", "AI vs AI", "Online"): saved_mode = "Ultra-AI"
            self.game_mode_var.set(saved_mode)
            self.player_symbol_var.set(data.get("player_symbol", "X") if data.get("player_symbol") in ("X", "O") else "X")
            self.board_size_var.set(data.get("board_size", "20x20") if data.get("board_size") in ("15x15", "19x19", "20x20") else "20x20")
            self.player_name_var.set(data.get("player_name", "Tùng"))
            
            diff_map = DIFFICULTY.get(lang, DIFFICULTY.get("VI", {}))
            default_diff = list(diff_map.keys())[0] if diff_map else ""
            for var, key in ((self.difficulty_var, "difficulty_ms"), (self.difficulty_x_var, "difficulty_x_ms"), (self.difficulty_o_var, "difficulty_o_ms")):
                saved_ms = data.get(key, 200)
                matched_label = next((label for label, ms in diff_map.items() if ms == saved_ms), default_diff)
                if matched_label: var.set(matched_label)
            
            rules = LANG.get(lang, LANG.get("VI", {})).get("rules_list", ["Tiêu chuẩn", "Chặn 2 đầu"])
            idx = data.get("rule_index", 0)
            self.rule_var.set(rules[idx] if 0 <= idx < len(rules) else rules[0])
            self.ui_style_var.set("Cổ điển" if data.get("ui_style") == "classic" else "Hiện đại")
            self.theme_var.set("Tối" if data.get("theme") == "dark" else "Sáng")
            self.sound_enabled = data.get("sound_enabled", True)
            self.time_minutes_var.set(str(data.get("time_minutes", 0)))
            self.auto_rotate_var.set(data.get("auto_rotate", True))
            if hasattr(self, 'btn_auto_rotate'):
                is_rot = self.auto_rotate_var.get()
                self.btn_auto_rotate.configure(
                    fg_color="#27ae60" if is_rot else "#7f8c8d",
                    hover_color="#2ecc71" if is_rot else "#95a5a6",
                    text="Xoay" if is_rot else "Tắt"
                )
        except (json.JSONDecodeError, OSError): pass

    def save_settings(self, value=None):
        try:
            lang = self.lang_var.get()
            rules = LANG.get(lang, LANG.get("VI", {})).get("rules_list", ["Tiêu chuẩn", "Chặn 2 đầu"])
            diff_map = DIFFICULTY.get(lang, DIFFICULTY.get("VI", {}))
            config_data = {
                "lang": lang, "game_mode": self.game_mode_var.get(), "player_symbol": self.player_symbol_var.get(), "board_size": self.board_size_var.get(),
                "player_name": self.player_name_var.get(),
                "difficulty_ms": diff_map.get(self.difficulty_var.get(), 200), "difficulty_x_ms": diff_map.get(self.difficulty_x_var.get(), 200),
                "difficulty_o_ms": diff_map.get(self.difficulty_o_var.get(), 200),
                "rule_index": rules.index(self.rule_var.get()) if self.rule_var.get() in rules else 0,
                "ui_style": "classic" if self.ui_style_var.get() in ("Cổ điển", "Classic") else "modern",
                "theme": "dark" if self.is_dark_mode else "light", "sound_enabled": self.sound_enabled, "time_minutes": self.time_minutes_var.get, "auto_rotate": self.auto_rotate_var.get()
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(config_data, f, ensure_ascii=False, indent=2)
            self.update_score_display()
        except (OSError, TypeError): pass

    def select_game_mode(self, mode):
        if self.is_ai_thinking or getattr(self, '_is_waiting_online', False): return
        if self.is_online_connected and mode != "Online":
            return
        self.game_mode_var.set(mode)
        self.update_mode_buttons()
        self.on_mode_change()

    def update_mode_buttons(self):
        if not hasattr(self, 'btn_mode_ai'): return
        hover_trans = "#34495e" if self.is_dark_mode else "#e0e0e0"
        border_col = "#34495e" if self.is_dark_mode else "#bdc3c7"
        current_mode = self.game_mode_var.get()
        
        button_map = [(self.btn_mode_ai, "Ultra-AI"), (self.btn_mode_2p, "2 Người"), (self.btn_mode_ai_vs_ai, "AI vs AI"), (self.btn_mode_online, "Online")]
        for btn, m_val in button_map:
            if current_mode == m_val:
                btn.configure(fg_color="#2980b9", hover_color="#2471a3", text_color="white", border_width=0, state="normal")
            else:
                if self.is_online_connected:
                    disabled_bg = "#21262d" if self.is_dark_mode else "#e2e8f0"
                    disabled_border = "#334155" if self.is_dark_mode else "#cbd5e1"
                    btn.configure(fg_color=disabled_bg, hover_color=disabled_bg, text_color="gray", border_width=2, border_color=disabled_border, state="disabled")
                else:
                    btn.configure(fg_color="transparent", hover_color=hover_trans, text_color=("black", "white"), border_width=2, border_color=border_col, state="normal")

    def create_ui(self):
        main_font, bold_font = ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        status_font, timer_display_font = ctk.CTkFont(family="Segoe UI", size=22, weight="bold"), ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        
        # KHUNG CODE MỚI THAY THẾ
        self.control_frame = ctk.CTkFrame(self.root, corner_radius=12, height=175) 
        self.control_frame.pack_propagate(False) 
        self.control_frame.pack(pady=(8, 4), padx=15, fill="x")

        self.main_config_container = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.main_config_container.pack(pady=8, padx=12, fill="x")

        self.right_panel = ctk.CTkFrame(self.main_config_container, fg_color="transparent")
        self.right_panel.pack(side="right", anchor="ne", padx=(15, 0))

        buttons_info = [
            ("btn_lang", self.get_lang_btn_text, self.toggle_language, "#8e44ad", "#9b59b6", (0, 5)),
            ("btn_sound", lambda: self.t("sound_on") if self.sound_enabled else self.t("sound_off"), self.toggle_sound, "#d35400", "#e67e22", (0, 5)),
            ("btn_theme", self.get_theme_btn_text, self.toggle_theme, "#34495e", "#2c3e50", (0, 5)),
            ("btn_style", self.get_style_btn_text, self.toggle_ui_style, "#16a085", "#1abc9c", None),
        ]
        for name, text_fn, command, fg, hover, pady in buttons_info:
            btn = ctk.CTkButton(
                self.right_panel, text=text_fn(), command=command, 
                font=bold_font, fg_color=fg, hover_color=hover, 
                width=100, height=35, corner_radius=10,
                anchor="center"
            )
            btn.pack(pady=pady, fill="none", expand=True)
            setattr(self, name, btn)

        # === KHUNG CHAT ONLINE (chỗ trống giữa left panel và nút phải) ===
        self.chat_frame = ctk.CTkFrame(self.main_config_container, fg_color=("gray92", "gray17"), corner_radius=10, width=220, height=150)
        self.chat_frame.pack_propagate(False)
        # Không pack ngay — chỉ hiện khi Online

        chat_font = ctk.CTkFont(family="Segoe UI", size=12)
        self.chat_box = ctk.CTkTextbox(self.chat_frame, font=chat_font, wrap="word", activate_scrollbars=True, height=110, corner_radius=8)
        self.chat_box.pack(fill="both", expand=True, padx=6, pady=(6, 4))
        self.chat_box.configure(state="disabled")

        self.chat_input_row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.chat_input_row.pack(fill="x", padx=6, pady=(0, 6))
        self.chat_entry = ctk.CTkEntry(self.chat_input_row, font=chat_font, height=28, placeholder_text="Chat...")
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", self.send_chat_message)
        self.btn_chat_send = ctk.CTkButton(self.chat_input_row, text="➤", width=36, height=28, corner_radius=8,
                                           fg_color="#2980b9", hover_color="#3498db", command=self.send_chat_message)
        self.btn_chat_send.pack(side="right")
        # ================================================================

        self.left_panel = ctk.CTkFrame(self.main_config_container, fg_color="transparent")
        self.left_panel.pack(side="left", anchor="nw", fill="x", expand=True)

        self.row1 = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.row1.pack(pady=(0, 8), anchor="w")
        
        self.lbl_mode = ctk.CTkLabel(self.row1, text=self.t("mode"), font=bold_font); self.lbl_mode.pack(side="left", padx=(0, 8))
        self.btn_mode_ai = ctk.CTkButton(self.row1, text=self.t("mode_ai"), font=bold_font, width=90, height=32, corner_radius=16, command=lambda: self.select_game_mode("Ultra-AI"))
        self.btn_mode_ai.pack(side="left", padx=(0, 6))
        self.btn_mode_2p = ctk.CTkButton(self.row1, text=self.t("mode_2p"), font=bold_font, width=90, height=32, corner_radius=16, command=lambda: self.select_game_mode("2 Người"))
        self.btn_mode_2p.pack(side="left", padx=(0, 6))
        self.btn_mode_ai_vs_ai = ctk.CTkButton(self.row1, text=self.t("mode_ai_vs_ai"), font=bold_font, width=90, height=32, corner_radius=16, command=lambda: self.select_game_mode("AI vs AI"))
        self.btn_mode_ai_vs_ai.pack(side="left", padx=(0, 6))
        
        mode_online_text = self.t("mode_online") if "mode_online" in LANG.get("VI", {}) else "Online"
        self.btn_mode_online = ctk.CTkButton(self.row1, text=mode_online_text, font=bold_font, width=90, height=32, corner_radius=16, command=lambda: self.select_game_mode("Online"))
        self.btn_mode_online.pack(side="left", padx=(0, 18))

        self.symbol_frame = ctk.CTkFrame(self.row1, fg_color="transparent")
        self.symbol_frame.pack(side="left")
        self.btn_toggle_symbol = ctk.CTkButton(self.symbol_frame, text=self.t("symbol_x"), font=bold_font, width=38, height=32, corner_radius=8, command=self.toggle_symbol_action)
        self.btn_toggle_symbol.pack(side="left", padx=(0, 8))
        self.btn_auto_rotate = ctk.CTkButton(
            self.symbol_frame, text="🔄", font=bold_font, width=38, height=32, corner_radius=8,
            fg_color="#27ae60", hover_color="#2ecc71", command=self.toggle_auto_rotate
        )
        self.btn_auto_rotate.pack(side="left", padx=(0, 8))
        self.row2 = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.row2.pack(pady=(0, 8), anchor="w")
        self.lbl_board = ctk.CTkLabel(self.row2, text=self.t("board"), font=bold_font); self.lbl_board.pack(side="left", padx=(0, 6))
        self.size_menu = ctk.CTkOptionMenu(self.row2, variable=self.board_size_var, values=["15x15", "19x19", "20x20"], font=main_font, dropdown_font=main_font, command=self.on_board_size_change, width=95, height=30); self.size_menu.pack(side="left", padx=(0, 18))
        
        self.lbl_rule = ctk.CTkLabel(self.row2, text=self.t("rule"), font=bold_font); self.lbl_rule.pack(side="left", padx=(0, 6))
        
        rule_vals = self.t("rules_list")
        if not isinstance(rule_vals, list) or not rule_vals: 
            rule_vals = ["Tiêu chuẩn", "Chặn 2 đầu"]
        self.rule_menu = ctk.CTkOptionMenu(self.row2, variable=self.rule_var, values=rule_vals, font=main_font, dropdown_font=main_font, command=self.on_rule_change, width=135, height=30)
        self.rule_menu.pack(side="left", padx=(0, 18))
        
        self.lbl_time_limit = ctk.CTkLabel(self.row2, text=self.t("time_limit"), font=bold_font); self.lbl_time_limit.pack(side="left", padx=(0, 6))
        
        self.time_spin_box = ctk.CTkFrame(self.row2, fg_color="transparent"); self.time_spin_box.pack(side="left")
        self.btn_minus = ctk.CTkButton(self.time_spin_box, text="-", font=bold_font, width=30, height=30, fg_color="#7f8c8d", hover_color="#95a5a6", corner_radius=8); self.btn_minus.pack(side="left", padx=(0, 3)); self.btn_minus.bind("<ButtonPress-1>", lambda e: self.start_hold_change(-1)); self.btn_minus.bind("<ButtonRelease-1>", self.stop_hold_change)
        self.time_entry = ctk.CTkEntry(self.time_spin_box, textvariable=self.time_minutes_var, font=bold_font, width=46, height=30, justify="center"); self.time_entry.pack(side="left", padx=(0, 3)); self.time_entry.bind("<FocusOut>", self.on_time_entry_change); self.time_entry.bind("<Return>", self.on_time_entry_change)
        self.btn_plus = ctk.CTkButton(self.time_spin_box, text="+", font=bold_font, width=30, height=30, fg_color="#2980b9", hover_color="#3498db", corner_radius=8); self.btn_plus.pack(side="left"); self.btn_plus.bind("<ButtonPress-1>", lambda e: self.start_hold_change(1)); self.btn_plus.bind("<ButtonRelease-1>", self.stop_hold_change)

        self.online_room_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        
        self.lbl_name = ctk.CTkLabel(self.online_room_frame, text=self.t("name_label"), font=bold_font)
        self.lbl_name.pack(side="left", padx=(0, 6))
        
        self.name_entry = ctk.CTkEntry(self.online_room_frame, textvariable=self.player_name_var, font=bold_font, width=90, height=32, justify="center")
        self.name_entry.pack(side="left", padx=(0, 12))
        self.name_entry.bind("<FocusOut>", self.save_settings)

        self.lbl_room = ctk.CTkLabel(self.online_room_frame, text=self.t("room_label"), font=bold_font)
        self.lbl_room.pack(side="left", padx=(0, 6))
        self.room_entry = ctk.CTkEntry(self.online_room_frame, textvariable=self.room_id_var, font=bold_font, width=70, height=32, justify="center")
        self.room_entry.pack(side="left", padx=(0, 10))
        
        self.btn_join = ctk.CTkButton(self.online_room_frame, text=self.t("join_room"), font=bold_font, width=90, height=32, fg_color="#27ae60", hover_color="#2ecc71", corner_radius=8, command=self.join_online_room)
        self.btn_join.pack(side="left", padx=(0, 8))
        
        self.btn_leave_online = ctk.CTkButton(self.online_room_frame, text=self.t("leave_online"), font=bold_font, width=100, height=32, fg_color="#64748b", hover_color="#475569", corner_radius=8, command=self.exit_online_mode)
        self.btn_leave_online.pack(side="left")

        # KHỞI TẠO HÀNG 3: ĐỘ KHÓ
        self.row3 = ctk.CTkFrame(self.left_panel, fg_color="transparent", height=32)
        self.row3.pack(anchor="w", fill="x", pady=(0, 4))
        self.row3.pack_propagate(False)

        # Khung chế độ 1 AI (Ultra-AI & 2 Người)
        self.diff_single_frame = ctk.CTkFrame(self.row3, fg_color="transparent", width=350, height=32)
        self.diff_single_frame.pack_propagate(False)
        
        self.lbl_diff = ctk.CTkLabel(self.diff_single_frame, text=self.t("diff"), font=bold_font, width=110, anchor="w")
        self.lbl_diff.pack(side="left", padx=(0, 6))
        
        diff_values = list(DIFFICULTY.get(self.lang_var.get(), DIFFICULTY.get("VI", DEFAULT_DIFF)).keys())
        if not diff_values: diff_values = ["Kiện tướng (0.2s)"]
            
        self.diff_menu = ctk.CTkOptionMenu(self.diff_single_frame, variable=self.difficulty_var, values=diff_values, font=main_font, dropdown_font=main_font, command=self.save_settings, width=175, height=30)
        self.diff_menu.pack(side="left")

        # Khung chế độ AI vs AI
        self.diff_vs_frame = ctk.CTkFrame(self.row3, fg_color="transparent", width=650, height=32)
        self.diff_vs_frame.pack_propagate(False)
        
        self.lbl_diff_x = ctk.CTkLabel(self.diff_vs_frame, text=self.t("diff_x"), font=bold_font, width=110, anchor="w")
        self.lbl_diff_x.pack(side="left", padx=(0, 6))
        
        self.diff_x_menu = ctk.CTkOptionMenu(self.diff_vs_frame, variable=self.difficulty_x_var, values=diff_values, font=main_font, dropdown_font=main_font, command=self.save_settings, width=175, height=30)
        self.diff_x_menu.pack(side="left", padx=(0, 10))
        
        self.btn_swap_diff = ctk.CTkButton(self.diff_vs_frame, text="⇄", command=self.swap_ai_difficulties, font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"), fg_color="#8e44ad", hover_color="#9b59b6", width=38, height=30, corner_radius=8)
        self.btn_swap_diff.pack(side="left", padx=(4, 10))
        
        self.lbl_diff_o = ctk.CTkLabel(self.diff_vs_frame, text=self.t("diff_o"), font=bold_font)
        self.lbl_diff_o.pack(side="left", padx=(0, 6))
        
        self.diff_o_menu = ctk.CTkOptionMenu(self.diff_vs_frame, variable=self.difficulty_o_var, values=diff_values, font=main_font, dropdown_font=main_font, command=self.save_settings, width=175, height=30)
        self.diff_o_menu.pack(side="left")

        # KHỞI TẠO HÀNG 4: CÁC NÚT ĐIỀU KHIỂN
        self.row4 = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.row4.pack(anchor="w", pady=(7, 4))  # Tăng khoảng cách phía trên từ 4 lên 7 để hạ thấp thêm chút nữa
        
        self.btn_new = ctk.CTkButton(self.row4, text=self.t("new_game"), command=self.request_new_game, font=bold_font, fg_color="#e74c3c", hover_color="#c0392b", width=135, height=35, corner_radius=10)
        self.btn_new.pack(side="left", padx=(0, 8))
        
        # Đưa nút Bắt đầu / Dừng / Tiếp tục lên trước nút Lùi - Tiến
        disabled_bg = "#21262d" if self.is_dark_mode else "#e2e8f0"
        disabled_fg = "#6e7681" if self.is_dark_mode else "#64748b"
        self.btn_pause_resume = ctk.CTkButton(
            self.row4, text=self.t("start"), command=self.toggle_pause_resume, 
            font=bold_font, width=175, height=35, corner_radius=10,
            fg_color=disabled_bg, text_color=disabled_fg, state="disabled"
        )
        self.btn_pause_resume.pack(side="left", padx=(0, 8))
        
        self.btn_undo = ctk.CTkButton(self.row4, text=self.t("undo"), command=self.undo_move, font=bold_font, fg_color="#e67e22", hover_color="#d35400", width=85, height=35, corner_radius=10)
        self.btn_undo.pack(side="left", padx=(0, 8))
        
        self.btn_redo = ctk.CTkButton(self.row4, text=self.t("redo"), command=self.redo_move, font=bold_font, fg_color="#2980b9", hover_color="#2471a3", width=85, height=35, corner_radius=10)
        self.btn_redo.pack(side="left", padx=(0, 8))
        
        self.btn_hint = ctk.CTkButton(self.row4, text=self.t("hint"), command=self.get_hint, font=bold_font, fg_color="#8e44ad", hover_color="#9b59b6", width=110, height=35, corner_radius=10)
        self.btn_hint.pack(side="left", padx=(0, 8))

        self.status_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.status_container.pack(pady=(2, 4), fill="x", padx=10)
        self.status = ctk.CTkLabel(self.status_container, text="", font=status_font); self.status.pack(anchor="center", pady=(0, 2)); self.display_status("init_status", color="#3498db")
        
# KHỞI TẠO KHUNG TỈ SỐ VÀ THỜI GIAN CHUNG Ở GIỮA
        self.score_bg = ctk.CTkFrame(self.status_container, fg_color="transparent")
        self.score_bg.pack(anchor="center", fill="x", pady=(0, 2), padx=5)
        
        # THÊM uniform="card" ĐỂ ÉP 2 BÊN LUÔN BẰNG NHAU 100%
        self.score_bg.grid_columnconfigure(0, weight=1, uniform="card")
        self.score_bg.grid_columnconfigure(1, weight=0, minsize=65)
        self.score_bg.grid_columnconfigure(2, weight=1, uniform="card")

        card_fg = ("#f1f5f9", "#1e293b")
        card_border = ("#cbd5e1", "#334155")

        self.score_left_card = ctk.CTkFrame(
            self.score_bg, fg_color=card_fg, border_width=1,
            border_color=card_border, corner_radius=14, height=76
        )
        self.score_left_card.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.score_left_card.grid_propagate(False)

        self.score_right_card = ctk.CTkFrame(
            self.score_bg, fg_color=card_fg, border_width=1,
            border_color=card_border, corner_radius=14, height=76
        )
        self.score_right_card.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.score_right_card.grid_propagate(False)

        name_font = ctk.CTkFont(family="Segoe UI", size=23, weight="bold")
        time_font = ctk.CTkFont(family="Segoe UI", size=23, weight="bold")  # Đổi từ 18 thành 23
        score_font = ctk.CTkFont(family="Segoe UI", size=36, weight="bold")  
        symbol_font = ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        bar_font = ctk.CTkFont(family="Segoe UI", size=15, weight="bold") # Tăng lên 15 cho to rõ

        self.score_left_top = ctk.CTkFrame(self.score_left_card, fg_color="transparent", height=42)
        self.score_left_top.pack(fill="x", padx=12, pady=(6, 0))
        self.score_left_top.pack_propagate(False)
        # Cấu hình các cột tỷ lệ/cố định cho thẻ trái để định vị đồng hồ đứng yên
        self.score_left_top.grid_columnconfigure(0, weight=0, minsize=38)  # Ô icon quân cờ
        self.score_left_top.grid_columnconfigure(1, weight=0, minsize=110) # Ô tên người chơi
        self.score_left_top.grid_columnconfigure(2, weight=1)              # Khoảng trống co giãn để giữ đồng hồ đúng giữa
        self.score_left_top.grid_columnconfigure(3, weight=0, minsize=90)  # Ô chứa đồng hồ 01:00 (Cố định tuyệt đối)
        self.score_left_top.grid_columnconfigure(4, weight=0, minsize=45)  # Ô điểm số

        self.score_right_top = ctk.CTkFrame(self.score_right_card, fg_color="transparent", height=42)
        self.score_right_top.pack(fill="x", padx=12, pady=(6, 0))
        self.score_right_top.pack_propagate(False)
        # Cấu hình các cột tỷ lệ/cố định cho thẻ phải
        self.score_right_top.grid_columnconfigure(0, weight=0, minsize=45)  # Ô điểm số
        self.score_right_top.grid_columnconfigure(1, weight=0, minsize=90)  # Ô chứa đồng hồ 01:00 (Cố định tuyệt đối)
        self.score_right_top.grid_columnconfigure(2, weight=1)              # Khoảng trống co giãn
        self.score_right_top.grid_columnconfigure(3, weight=0, minsize=110) # Ô tên đối thủ
        self.score_right_top.grid_columnconfigure(4, weight=0, minsize=38)  # Ô icon quân cờ

        # --- THẺ ĐIỂM BÊN TRÁI (BẠN) ---
        self.lbl_score_left_symbol = ctk.CTkLabel(
            self.score_left_top, text="X", width=38, height=38,
            corner_radius=8, fg_color="#3498db", text_color="white", font=symbol_font
        )
        self.lbl_score_left_symbol.grid(row=0, column=0, sticky="w")

        self.lbl_score_left = ctk.CTkLabel(
            self.score_left_top, text="Tùng", font=name_font, anchor="w",
            text_color="#3498db"
        )
        self.lbl_score_left.grid(row=0, column=1, sticky="w", padx=(6, 0))

        # Đồng hồ thời gian được neo cố định vào cột 3, không bị xê dịch bởi tên dài/ngắn
        self.lbl_score_left_time = ctk.CTkLabel(
            self.score_left_top, text="⏱ 01:00", font=time_font, anchor="center",
            text_color=("#334155", "#e2e8f0")
        )
        self.lbl_score_left_time.grid(row=0, column=3, sticky="ew")

        self.lbl_score_left_points = ctk.CTkLabel(
            self.score_left_top, text="0", font=score_font, text_color="#3498db", anchor="center"
        )
        self.lbl_score_left_points.grid(row=0, column=4, sticky="e", padx=(6, 0))


        # --- THẺ ĐIỂM BÊN PHẢI (ĐỐI THỦ) ---
        self.lbl_score_right_symbol = ctk.CTkLabel(
            self.score_right_top, text="O", width=38, height=38,
            corner_radius=8, fg_color="#e74c3c", text_color="white", font=symbol_font
        )
        # Đã sửa lỗi sai tên biến ở dòng này
        self.lbl_score_right_symbol.grid(row=0, column=4, sticky="e")

        self.lbl_score_right = ctk.CTkLabel(
            self.score_right_top, text="Đối thủ", font=name_font, anchor="e",
            text_color="#e74c3c"
        )
        self.lbl_score_right.grid(row=0, column=3, sticky="e", padx=(0, 6))

        # Đồng hồ thời gian được neo cố định vào cột 1 bên phải
        self.lbl_score_right_time = ctk.CTkLabel(
            self.score_right_top, text="⏱ 01:00", font=time_font, anchor="center",
            text_color=("#334155", "#e2e8f0")
        )
        self.lbl_score_right_time.grid(row=0, column=1, sticky="ew")

        self.lbl_score_right_points = ctk.CTkLabel(
            self.score_right_top, text="0", font=score_font, text_color="#e74c3c", anchor="center"
        )
        self.lbl_score_right_points.grid(row=0, column=0, sticky="w", padx=(0, 6))


        # --- CÁC HÀNG THANH TIẾN TRÌNH & CHỮ TỈ SỐ Ở GIỮA ---
        
        # KHUNG CHỨA BÊN TRÁI
        self.score_left_timer_row = ctk.CTkFrame(self.score_left_card, fg_color="transparent", height=24)
        self.score_left_timer_row.pack(fill="x", padx=10, pady=(0, 2))
        self.score_left_timer_row.pack_propagate(False)
        
        # BÊN TRÁI: Nhãn số trước, thanh sau (Bỏ bo góc corner_radius=0 để đồng bộ)
        self.lbl_turn_left = ctk.CTkLabel(self.score_left_timer_row, text="35s", width=36, font=bar_font)
        self.lbl_turn_left.pack(side="left", padx=(0, 6))
        
        self.turn_bar_left = ctk.CTkProgressBar(
            self.score_left_timer_row, height=6, corner_radius=0, 
            progress_color="#22c55e", fg_color=("#dbe4ee", "#334155")
        )
        self.turn_bar_left.pack(side="left", fill="x", expand=True, pady=(4, 0))
        self.turn_bar_left.set(1.0)


        # KHUNG CHỨA BÊN PHẢI (Đoạn này bị thiếu gây ra lỗi)
        self.score_right_timer_row = ctk.CTkFrame(self.score_right_card, fg_color="transparent", height=24)
        self.score_right_timer_row.pack(fill="x", padx=10, pady=(0, 2))
        self.score_right_timer_row.pack_propagate(False)
        
        # BÊN PHẢI: Thanh trước, nhãn số sau (ĐẢO MÀU và BỎ BO GÓC corner_radius=0)
        self.turn_bar_right = ctk.CTkProgressBar(
            self.score_right_timer_row, height=6, corner_radius=0, 
            progress_color=("#dbe4ee", "#334155"), fg_color="#22c55e" 
        )
        self.turn_bar_right.pack(side="left", fill="x", expand=True, pady=(4, 0))
        
        self.lbl_turn_right = ctk.CTkLabel(self.score_right_timer_row, text="35s", width=36, font=bar_font)
        self.lbl_turn_right.pack(side="left", padx=(6, 0))
        self.turn_bar_right.set(0.0)

        self.lbl_score_dash = ctk.CTkLabel(
            self.score_bg, text="TỈ SỐ", width=65,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=("#334155", "#f1f5f9")
        )
        self.lbl_score_dash.grid(row=0, column=1)

        self.info_row = ctk.CTkFrame(self.status_container, fg_color="transparent")
        self.lbl_timer = ctk.CTkLabel(self.info_row, text="")

        self.update_minus_button_color(); self.update_mode_buttons(); self.refresh_mode_visibility()
        
        self.update_minus_button_color(); self.update_mode_buttons(); self.refresh_mode_visibility()
        
        self.board_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.board_container.pack(fill="both", expand=True, padx=10, pady=(2, 2))

        self.modern_canvas = tk.Canvas(self.board_container, highlightthickness=0, cursor="hand2", bd=0)
        self.modern_canvas.place(relx=0.5, rely=0.5, anchor="center")
        
        self.modern_canvas.bind("<Button-1>", self.modern_click)
        self.modern_canvas.bind("<Motion>", self.on_canvas_motion)
        self.modern_canvas.bind("<Leave>", self.on_canvas_leave)

    def update_pause_btn_state(self):
        if not hasattr(self, 'btn_pause_resume') or not self.btn_pause_resume.winfo_exists(): return
        mode, is_dark = self.game_mode_var.get(), self.is_dark_mode
        disabled_bg, disabled_fg = ("#21262d" if is_dark else "#e2e8f0"), ("#6e7681" if is_dark else "#64748b")

        # 1. Xử lý riêng cho nút VÁN MỚI (Cho phép sáng lên khi có nước đi hoặc khi ván đấu đã kết thúc ở mọi chế độ)
        is_game_finished_or_has_moves = (len(self.history) > 0) or self.game_over
        new_btn_new_sig = (is_game_finished_or_has_moves, is_dark)
        if getattr(self, '_last_btn_new_sig', None) != new_btn_new_sig:
            if hasattr(self, 'btn_new') and self.btn_new.winfo_exists():
                if not is_game_finished_or_has_moves:
                    self.btn_new.configure(state="disabled", fg_color=disabled_bg, hover_color=disabled_bg, text_color=disabled_fg)
                else:
                    self.btn_new.configure(state="normal", fg_color="#e74c3c", hover_color="#c0392b", text_color="white")
            self._last_btn_new_sig = new_btn_new_sig

        # 2. Nếu là chế độ Online, vô hiệu hóa nút Tạm dừng/Bắt đầu và kết thúc hàm tại đây
        if mode == "Online":
            self.btn_pause_resume.configure(state="disabled", fg_color=disabled_bg, text_color=disabled_fg)
            return

        # 3. Xử lý cho các chế độ Offline (Ultra-AI, 2 Người, AI vs AI)
        if self.game_over: btn_text, btn_fg, btn_hover, btn_state = self.t("start"), "#27ae60", "#2ecc71", "normal"
        elif len(self.history) == 0:
            if mode == "AI vs AI":
                if not self.is_ai_match_paused: btn_text, btn_fg, btn_hover, btn_state = self.t("pause"), "#e74c3c", "#c0392b", "normal"
                else: btn_text, btn_fg, btn_hover, btn_state = self.t("start"), "#27ae60", "#2ecc71", "normal"
            else: btn_text, btn_fg, btn_hover, btn_state = self.t("start"), disabled_bg, disabled_bg, "disabled"
        else:
            btn_text, btn_fg, btn_hover, btn_state = (self.t("resume") if self.is_ai_match_paused else self.t("pause")), ("#27ae60" if self.is_ai_match_paused else "#e74c3c"), ("#2ecc71" if self.is_ai_match_paused else "#c0392b"), "normal"

        new_pause_sig = (btn_text, btn_fg, btn_hover, btn_state, is_dark)
        if getattr(self, '_last_pause_sig', None) != new_pause_sig:
            self.btn_pause_resume.configure(text=btn_text, fg_color=btn_fg, hover_color=btn_hover, text_color="white" if btn_state == "normal" else disabled_fg, state=btn_state)
            self._last_pause_sig = new_pause_sig

    def toggle_symbol_action(self):
        if self.is_ai_thinking or getattr(self, '_is_waiting_online', False): return
        
        # Cho phép bấm chọn khi đang ở sảnh hoặc khi ván đã xong
        if self.game_mode_var.get() == "Online" and self.is_online_connected and not self.game_over: return
        
        current_sym = self.player_symbol_var.get()
        new_sym = "O" if current_sym == "X" else "X"
        self.player_symbol_var.set(new_sym)

        if self.game_mode_var.get() == "Online":
            self._manually_chose_symbol = True
            self.online_symbol = new_sym
            
            # Gửi thông báo ép đối thủ lật quân tương ứng
            if self.ws and self.is_online_connected:
                try:
                    self.ws.send(json.dumps({
                        "type": "update_settings",
                        "symbol": new_sym
                    }))
                except Exception:
                    pass
                    
        self.apply_symbols()

    def refresh_mode_visibility(self):
        mode = self.game_mode_var.get()
        
        if mode == "Online":
            # Giữ nguyên nút chọn quân X/O trong chế độ Online
            if not self.symbol_frame.winfo_ismapped():
                self.symbol_frame.pack(side="left")

            # Ẩn độ khó
            self.row3.pack_forget()

            # Hiện khung Online (Tên + Mã phòng)
            self.online_room_frame.pack(anchor="w", pady=(0, 4), before=self.row4)

            # Ẩn các nút: Bắt đầu, Lùi, Tiến, Gợi ý
            self.btn_pause_resume.pack_forget()
            self.btn_undo.pack_forget()
            self.btn_redo.pack_forget()
            self.btn_hint.pack_forget()

            # Chỉ giữ nút VÁN MỚI
            self.btn_new.pack(side="left", padx=(0, 8))

            # Hiện khung chat
            if hasattr(self, "chat_frame") and not self.chat_frame.winfo_ismapped():
                self.chat_frame.pack(side="right", anchor="ne", padx=(10, 0), before=self.right_panel)

            # Nếu chưa có quân thì mở nút thời gian, đã có quân thì khóa
            self.set_time_controls_enabled(not bool(self.history) and not self.game_over)

        else:
            # Hiện lại khung chọn quân
            if not self.symbol_frame.winfo_ismapped():
                self.symbol_frame.pack(side="left")

            # Ẩn khung Online
            self.online_room_frame.pack_forget()

            # Hiện lại hàng độ khó
            self.row3.pack(anchor="w", fill="x", pady=(0, 4), before=self.row4)

            # Hiện lại các nút điều khiển
            self.btn_new.pack(side="left", padx=(0, 8))
            self.btn_pause_resume.pack(side="left", padx=(0, 8))
            self.btn_undo.pack(side="left", padx=(0, 8))
            self.btn_redo.pack(side="left", padx=(0, 8))

            # Ẩn khung chat
            if hasattr(self, "chat_frame") and self.chat_frame.winfo_ismapped():
                self.chat_frame.pack_forget()

            # Mở lại nút thời gian khi không còn Online
            self.set_time_controls_enabled(True)

            if mode == "AI vs AI":
                self.diff_single_frame.pack_forget()
                self.diff_vs_frame.pack(side="left")
                self.btn_hint.pack_forget()
            elif mode == "2 Người":
                self.diff_vs_frame.pack_forget()
                self.diff_single_frame.pack(side="left")
                self.lbl_diff.configure(text_color="gray")
                self.diff_menu.configure(state="disabled")
                self.btn_hint.pack(side="left", padx=(0, 8))
            else:  # Ultra-AI
                self.diff_vs_frame.pack_forget()
                self.diff_single_frame.pack(side="left")
                self.lbl_diff.configure(text_color=("black", "white"))
                self.diff_menu.configure(state="normal")
                self.btn_hint.pack(side="left", padx=(0, 8))

        self.update_pause_btn_state()

    def append_chat(self, name, text, is_self=False):
        if not hasattr(self, "chat_box"):
            return
        self.chat_box.configure(state="normal")
        prefix = "Bạn" if is_self else (name or "???")
        self.chat_box.insert("end", f"{prefix}: {text}\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def send_chat_message(self, event=None):
        if not hasattr(self, "chat_entry"):
            return
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        if len(msg) > 120:
            msg = msg[:120]
        self.chat_entry.delete(0, "end")
        my_name = self.player_name_var.get().strip() or "Bạn"
        self.append_chat(my_name, msg, is_self=True)
        if self.ws and self.is_online_connected:
            try:
                self.ws.send(json.dumps({
                    "type": "chat",
                    "text": msg,
                    "name": my_name
                }))
            except Exception:
                pass

    def clear_chat(self):
        if hasattr(self, "chat_box"):
            self.chat_box.configure(state="normal")
            self.chat_box.delete("1.0", "end")
            self.chat_box.configure(state="disabled")

    def exit_online_mode(self):
        if self.ws:
            try: self.ws.close()
            except: pass
            self.ws = None
        self.is_online_connected = False
        self._is_waiting_online = False
        self.my_ready_for_rematch = False
        self.opponent_ready_for_rematch = False
        
        # === MỞ KHÓA VÀ KHÔI PHỤC LẠI KHẢ NĂNG NHẬP KHI THOÁT ===
        normal_color = ("black", "white")
        self.name_entry.configure(text_color=normal_color)
        self.room_entry.configure(text_color=normal_color)
        self.name_entry.unbind("<Key>")
        self.name_entry.unbind("<Button-1>")
        self.name_entry.bind("<FocusOut>", self.save_settings)
        self.room_entry.unbind("<Key>")
        self.room_entry.unbind("<Button-1>")
        self.btn_join.configure(state="normal")
        # ========================================================

        self.stop_thinking_animation()
        self.modern_canvas.configure(cursor="hand2")
        self.update_mode_buttons()
        self.set_time_controls_enabled(True)  # Mở lại nút thời gian khi thoát Online
        self.new_game()

    def toggle_auto_rotate(self):
        current_state = self.auto_rotate_var.get()
        new_state = not current_state
        self.auto_rotate_var.set(new_state)
        
        # Đổi màu giao diện nút: Bật (Xanh lá), Tắt (Xám)
        if new_state:
            self.btn_auto_rotate.configure(fg_color="#27ae60", hover_color="#2ecc71", text="🔄")
        else:
            self.btn_auto_rotate.configure(fg_color="#7f8c8d", hover_color="#95a5a6", text="⏸")
        self.save_settings()

    def new_game(self):
        self.stop_thinking_animation()
        if self.turn_timer_job:
            self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
        if self.engine: self.engine.stop(); self.engine = None
        
        # === TỰ ĐỘNG ĐẢO QUÂN KHI KẾT THÚC VÁN NẾU BẬT TÍNH NĂNG XOAY VÒNG ===
        if self.game_over and self.auto_rotate_var.get():
            current_sym = self.player_symbol_var.get()
            new_sym = "O" if current_sym == "X" else "X"
            self.player_symbol_var.set(new_sym)
        # ======================================================================

        self.rebuild_board_widgets()
        
        self.game_over = self.is_ai_thinking = self.engine_synced = False
        self.is_ai_match_paused = True
        self.last_move = self.hover_cell = self.hint_cell = None
        self.winning_cells, self.history = [], []
        self.current_turn = HUMAN
            
        self.modern_canvas.configure(cursor="hand2")
        self.apply_symbols(); self.update_ui(); self.init_match_timers(); self.update_pause_btn_state()

        mode = self.game_mode_var.get()
        if mode == "Online":
            if not self.is_online_connected:
                self.display_status(self.t("online_enter_room"), color="#f39c12", raw_text=True)
            return
            
        if mode == "2 Người": self.update_turn_status(mode_type="2p", symbol=self.player_symbol); return
        if mode == "AI vs AI":
            self.display_status("ai_ready", color="#f39c12")
            if self.init_engine(): self.engine_synced = True
            return

        if self.init_engine(): self.engine_synced = True; self.update_turn_status(symbol=self.player_symbol)

    def toggle_pause_resume(self, event=None):
        mode = self.game_mode_var.get()
        if mode == "Online": return
        if self.game_over or (mode == "AI vs AI" and not self.history):
            self.new_game()
            self.is_ai_match_paused = False
            self.update_pause_btn_state()
            if mode == "AI vs AI" or (mode == "Ultra-AI" and self.current_turn == AI):
                self.is_ai_thinking = True
                self.modern_canvas.configure(cursor="watch")
                self.start_thinking_animation("ai_thinking" if mode == "AI vs AI" else "ai_taking_over")
                threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
            return
        if not self.history: return
        self.is_ai_match_paused = not self.is_ai_match_paused
        
        if self.is_ai_match_paused:
            if self.timer_job: self.root.after_cancel(self.timer_job); self.timer_job = None
            if self.turn_timer_job: self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
            self.update_pause_btn_state(); self.stop_thinking_animation()
            if mode == "AI vs AI": self.is_ai_thinking = False
            self.display_status("ai_match_paused", color="#f39c12")
            self.modern_canvas.configure(cursor="hand2")
        else:
            self.update_pause_btn_state()
            if mode == "AI vs AI":
                self.update_turn_status(mode_type="ai_vs_ai")
                self.is_ai_thinking = True
                self.modern_canvas.configure(cursor="watch")
                self.start_thinking_animation("ai_thinking")
                if not self.history: self.engine_synced = False
                
                # CHỈNH SỬA Ở ĐÂY: Xóa logic cũ và luôn dùng ai_board_sync_turn
                threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
                if self.engine_synced and self.history: threading.Thread(target=self.ai_turn, args=(self.history[-1][1], self.history[-1][0]), daemon=True).start()
                else: threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
            elif mode == "2 Người": self.update_turn_status(mode_type="2p")
            else:
                self.update_turn_status()
                if self.current_turn == AI:
                    self.is_ai_thinking = True
                    self.modern_canvas.configure(cursor="watch")
                    self.start_thinking_animation("ai_taking_over")
                    threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
            if len(self.history) > 0 and self.get_selected_time_limit_seconds() > 0 and not self.timer_job: self.run_match_timer()
            if not self.game_over and not self.turn_timer_job: self.start_turn_timer()

    def get_theme_btn_text(self): return ("☀ Sáng" if not self.is_dark_mode else "☾ Tối") if self.lang_var.get() == "VI" else ("☀ Light" if not self.is_dark_mode else "☾ Dark")

    def toggle_theme(self):
        def action():
            self.theme_var.set("Sáng" if self.is_dark_mode else "Tối")
            ctk.set_appearance_mode("dark" if self.is_dark_mode else "light")
            self.btn_theme.configure(text=self.get_theme_btn_text())
            self.apply_symbols()
            self.update_mode_buttons()
            self.update_ui()

            # Force reset signature để nút VÁN MỚI + BẮT ĐẦU nhận màu đúng theo theme mới
            self._last_pause_sig = self._last_btn_new_sig = None
            self.update_pause_btn_state()

            self.save_settings()
        self._transition_with_fade(action)

    def change_theme_init(self):
        ctk.set_appearance_mode("dark" if self.is_dark_mode else "light")
        self.btn_theme.configure(text=self.get_theme_btn_text())
        self.apply_symbols()
        self.update_mode_buttons()
        self.update_ui()
        self._last_pause_sig = self._last_btn_new_sig = None
        self.update_pause_btn_state()

    def get_lang_btn_text(self): return "🌐 VI" if self.lang_var.get() == "VI" else "🌐 EN"

    def toggle_language(self):
        self.lang_var.set("EN" if self.lang_var.get() == "VI" else "VI")
        self.change_language_action()

    def change_language_action(self):
        lang = self.lang_var.get()
        for widget, key in {
            self.lbl_mode: "mode", self.btn_mode_ai: "mode_ai", self.btn_mode_2p: "mode_2p", self.btn_mode_ai_vs_ai: "mode_ai_vs_ai",
            self.lbl_symbol: "symbol", self.lbl_board: "board", self.lbl_diff: "diff", self.lbl_diff_x: "diff_x", self.lbl_diff_o: "diff_o",
            self.lbl_rule: "rule", self.lbl_time_limit: "time_limit", self.btn_new: "new_game", self.btn_hint: "hint",
            self.btn_undo: "undo", self.btn_redo: "redo",
            self.lbl_name: "name_label", self.lbl_room: "room_label",
            self.btn_join: "join_room", self.btn_leave_online: "leave_online",
        }.items():
            if hasattr(widget, "configure"):
                try:
                    widget.configure(text=self.t(key))
                except Exception:
                    pass

        self.btn_mode_online.configure(text=self.t("mode_online"))

        if hasattr(self, 'btn_pause_resume') and self.btn_pause_resume.winfo_exists(): 
            self._last_pause_sig = self._last_btn_new_sig = None
            self.update_pause_btn_state()
            
        self.btn_sound.configure(text=self.t("sound_on") if self.sound_enabled else self.t("sound_off"))
        if hasattr(self, 'btn_toggle_symbol'):
            self.btn_toggle_symbol.configure(text=self.t("symbol_x") if self.player_symbol_var.get() == "X" else self.t("symbol_o"))

        fallback_diff = {"Kiện tướng (0.2s)": 200, "Khó (5s)": 5000, "Đỉnh cao (12s)": 12000, "Tối thượng (20s)": 20000}
        d_old = DIFFICULTY.get("VI" if lang == "EN" else "EN", fallback_diff)
        d_new = DIFFICULTY.get(lang, fallback_diff)
        if not isinstance(d_old, dict): d_old = fallback_diff
        if not isinstance(d_new, dict): d_new = fallback_diff
        old_keys = list(d_old.keys())
        new_keys = list(d_new.keys())
        for var in (self.difficulty_var, self.difficulty_x_var, self.difficulty_o_var): self._translate_option(var, old_keys, new_keys)
        for menu in (self.diff_menu, self.diff_x_menu, self.diff_o_menu): menu.configure(values=new_keys)

        fallback_rules = ["Tiêu chuẩn", "Chặn 2 đầu"]
        old_rules = LANG.get("EN" if lang == "VI" else "VI", {}).get("rules_list", fallback_rules)
        new_rules = LANG.get(lang, {}).get("rules_list", fallback_rules)
        if not isinstance(old_rules, list): old_rules = fallback_rules
        if not isinstance(new_rules, list): new_rules = fallback_rules
        
        self._translate_option(self.rule_var, old_rules, new_rules)
        self.rule_menu.configure(values=new_rules)

        for btn, text in zip((self.btn_style, self.btn_theme, self.btn_lang), (self.get_style_btn_text(), self.get_theme_btn_text(), self.get_lang_btn_text())): btn.configure(text=text)

        if not self.is_ai_thinking and not getattr(self, '_is_waiting_online', False) and hasattr(self, '_current_status_data'):
            data = self._current_status_data
            if data.get("type") == "turn": self.update_turn_status(mode_type=data.get("mode_type"), symbol=data.get("symbol"))
            elif data.get("type") == "raw": self.display_status(data["text"], color=data.get("color"), raw_text=True)
            else: self.display_status(data["key"], color=data.get("color"), format_args=data.get("format_args"), prefix_key=data.get("prefix_key"))

        self.update_timer_display(); self.save_settings()

    def _translate_option(self, var, old_options, new_options):
        if not old_options or not new_options: return
        current = var.get()
        var.set(new_options[old_options.index(current)] if current in old_options else new_options[0])

    def get_style_btn_text(self):
        return ("🎨 Hiện đại" if self.ui_style_var.get() in ["Hiện đại", "Modern"] else "🎨 Cổ điển") if self.lang_var.get() == "VI" else ("🎨 Modern" if self.ui_style_var.get() in ["Hiện đại", "Modern"] else "🎨 Classic")

    def toggle_ui_style(self):
        self.ui_style_var.set("Cổ điển" if self.ui_style_var.get() in ["Hiện đại", "Modern"] else "Hiện đại")
        self.btn_style.configure(text=self.get_style_btn_text())
        self.adjust_board_size()
        self.modern_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.save_settings()

    def change_ui_style_init(self):
        self.adjust_board_size()
        self.modern_canvas.place(relx=0.5, rely=0.5, anchor="center")

    def on_window_resize(self, event):
        if event.widget == self.root:
            if getattr(self, '_last_win_w', 0) == self.root.winfo_width() and getattr(self, '_last_win_h', 0) == self.root.winfo_height(): return
            self._last_win_w, self._last_win_h = self.root.winfo_width(), self.root.winfo_height()
            if self._resize_timer: self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(15, self.adjust_board_size)

    def _calculate_board_geometry(self):
        available_w = max(350, self.root.winfo_width() - 15)
        control_h = self.control_frame.winfo_reqheight() if hasattr(self, 'control_frame') else 130
        status_h = self.status_container.winfo_reqheight() if hasattr(self, 'status_container') else 65
        # Giảm trừ thêm một chút ở available_h để canvas tự dịch không gian lên trên
        available_h = max(350, self.root.winfo_height() - control_h - status_h - 10)
        
        if self.ui_style_var.get() in ["Hiện đại", "Modern"]:
            spans = max(1, self.board_size - 1)
        else:
            spans = max(1, self.board_size)
            
        self.cell_size = max(24, min(available_w, available_h) - 2 * self.board_margin) // spans
        self.board_pixels = 2 * self.board_margin + spans * self.cell_size

    def adjust_board_size(self):
        self._calculate_board_geometry()
        self.modern_canvas.config(width=self.board_pixels, height=self.board_pixels)
        # Bổ sung lệnh place này để mỗi khi đổi kích thước, canvas được ép nằm giữa tâm container
        self.modern_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.update_ui()

    def rebuild_board_widgets(self):
        requested_size = int(self.board_size_var.get().split("x")[0])
        if self.game_mode_var.get() == "Ultra-AI" and requested_size > 20:
            messagebox.showwarning(self.t("warning_title"), self.t("limit_warn"))
            self.board_size_var.set("20x20"); requested_size = 20
        self.board_size = requested_size
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]
        self.adjust_board_size()

    def on_board_size_change(self, value=None):
        if self.game_mode_var.get() == "Online" and (self.history or self.game_over):
            return
        self.save_settings()
        # Sync board size lên server khi Online
        if self.game_mode_var.get() == "Online" and self.ws and self.is_online_connected:
            try:
                self.ws.send(json.dumps({
                    "type": "update_settings",
                    "board_size": self.board_size_var.get(),
                    "rule": self.rule_var.get(),
                    "time_limit": self.get_selected_time_limit_seconds()
                }))
            except Exception:
                pass
            # Online: chỉ rebuild board, không gọi new_game (tránh reset connection)
            self.rebuild_board_widgets()
            self.update_ui()
        else:
            self.new_game()

    def _cell_from_canvas(self, event):
        x, y, m, s = self.modern_canvas.canvasx(event.x), self.modern_canvas.canvasy(event.y), self.board_margin, self.cell_size
        if self.ui_style_var.get() in ["Hiện đại", "Modern"]:
            col, row = int(round((x - m) / s)), int(round((y - m) / s))
            if 0 <= row < self.board_size and 0 <= col < self.board_size:
                if abs(x - (m + col * s)) <= s * 0.48 and abs(y - (m + row * s)) <= s * 0.48: 
                    return (row, col)
        else:
            col, row = int((x - m) // s), int((y - m) // s)
            if 0 <= row < self.board_size and 0 <= col < self.board_size: 
                return (row, col)
        return None

    def on_canvas_motion(self, event):
        if self.game_over or self.is_ai_thinking or self.game_mode_var.get() == "AI vs AI" or getattr(self, '_is_waiting_online', False): return
        cell = self._cell_from_canvas(event)
        if cell is not None and self.board[cell[0]][cell[1]] != EMPTY: cell = None
        if cell != self.hover_cell: self.hover_cell = cell; self.update_ui()

    def on_canvas_leave(self, event=None):
        if self.hover_cell is not None: self.hover_cell = None; self.update_ui()

    def modern_click(self, event):
        if self.game_mode_var.get() != "AI vs AI":
            if cell := self._cell_from_canvas(event): self.click(*cell)

    def draw_classic_board(self):
        cv = self.modern_canvas
        cv.delete("all")
        bg_color, grid_color, last_move_bg, hover_color = ("#0b141d", "#243447", "#1e3a5f", "#526574") if self.is_dark_mode else ("#f0f0f0", "#b0b0b0", "#fae19c", "#cccccc")
        m, s = self.board_margin, self.cell_size
        end = m + self.board_size * s
        cv.configure(bg=bg_color)

        if self.last_move:
            r, c = self.last_move
            cv.create_rectangle(m + c * s, m + r * s, m + (c + 1) * s, m + (r + 1) * s, fill=last_move_bg, outline="")

        for i in range(self.board_size + 1):
            p = m + i * s
            cv.create_line(p, m, p, end, fill=grid_color, width=1)
            cv.create_line(m, p, end, p, fill=grid_color, width=1)
            
        for wr, wc in self.winning_cells: 
            cv.create_rectangle(m + wc * s, m + wr * s, m + (wc + 1) * s, m + (wr + 1) * s, outline="#ffb300" if self.is_dark_mode else "#e67e22", width=2)
        if self.hint_cell: 
            hr, hc = self.hint_cell
            cv.create_rectangle(m + hc * s, m + hr * s, m + (hc + 1) * s, m + (hr + 1) * s, outline="#f39c12", width=3, dash=(4, 2))

        if self.hover_cell and self.game_mode_var.get() != "AI vs AI" and (self.game_mode_var.get() != "Online" or self.is_online_turn):
            hr, hc = self.hover_cell
            if 0 <= hr < self.board_size and 0 <= hc < self.board_size and self.board[hr][hc] == EMPTY: 
                cv.create_rectangle(m + hc * s + 1, m + hr * s + 1, m + (hc + 1) * s - 1, m + (hr + 1) * s - 1, outline=hover_color, width=2)

        font = ("Segoe UI", max(15, int(s * 0.58)), "bold")
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != EMPTY:
                    sym = self.player_symbol if self.board[r][c] == HUMAN else self.ai_symbol
                    color = ("#22d3ee" if sym == "X" else "#ef4444") if self.is_dark_mode else ("#3498db" if sym == "X" else "#e74c3c")
                    cv.create_text(m + c * s + s / 2, m + r * s + s / 2, text=sym, fill=color, font=font)

    def draw_modern_board(self):
        cv = self.modern_canvas
        cv.delete("all")
        bg_color, grid_color, dot_color, hover_color, piece_bg_dark = ("#0b141d", "#243447", "#243447", "#526574", "#060e16") if self.is_dark_mode else ("#fafafa", "#b0b0b0", "#b0b0b0", "#888888", "")
        m, s = self.board_margin, self.cell_size
        end = m + (self.board_size - 1) * s
        cv.configure(bg=bg_color)

        for i in range(self.board_size):
            p = m + i * s
            cv.create_line(p, m, p, end, fill=grid_color, width=1)
            cv.create_line(m, p, end, p, fill=grid_color, width=1)

        if self.board_size >= 15:
            mid = self.board_size // 2
            for r, c in [(3, 3), (3, self.board_size - 4), (mid, mid), (self.board_size - 4, 3), (self.board_size - 4, self.board_size - 4)]: 
                cv.create_oval(m + c * s - 3, m + r * s - 3, m + c * s + 3, m + r * s + 3, fill=dot_color, outline="")

        if self.hint_cell: 
            hr, hc = self.hint_cell
            hx, hy, rr = m + hc * s, m + hr * s, max(6, int(s * 0.45))
            cv.create_oval(hx - rr, hy - rr, hx + rr, hy + rr, outline="#f39c12", width=3, dash=(4, 2))

        if self.hover_cell and self.game_mode_var.get() != "AI vs AI" and (self.game_mode_var.get() != "Online" or self.is_online_turn):
            hr, hc = self.hover_cell
            if 0 <= hr < self.board_size and 0 <= hc < self.board_size and self.board[hr][hc] == EMPTY: 
                hx, hy, rr = m + hc * s, m + hr * s, max(4, int(s * 0.18))
                cv.create_oval(hx - rr, hy - rr, hx + rr, hy + rr, outline=hover_color, width=2)

        radius = int(s * 0.45)
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] == EMPTY: continue
                
                # Tính toán tọa độ tâm, chặn không cho bán kính vượt quá lề bàn cờ
                x = m + c * s
                y = m + r * s
                
                if self.is_dark_mode: 
                    cv.create_oval(x - radius - 1, y - radius - 1, x + radius + 1, y + radius + 1, fill=piece_bg_dark, outline="")
                
                is_human_piece = (self.board[r][c] == HUMAN)
                sym = self.player_symbol if is_human_piece else self.ai_symbol
                
                piece_color = ("#22d3ee" if sym == "X" else "#ef4444") if self.is_dark_mode else ("#3498db" if sym == "X" else "#e74c3c")
                cv.create_oval(x - radius, y - radius, x + radius, y + radius, fill=piece_color, outline="")
                
                if self.last_move == (r, c): 
                    cv.create_oval(x - max(2, int(s * 0.15)), y - max(2, int(s * 0.15)), x + max(2, int(s * 0.15)), y + max(2, int(s * 0.15)), fill=bg_color, outline="")

        for wr, wc in self.winning_cells: 
            wx, wy = m + wc * s, m + wr * s
            cv.create_oval(wx - radius - 3, wy - radius - 3, wx + radius + 3, wy + radius + 3, outline="#f1c40f", width=3)

    def update_ui(self): 
        if self.ui_style_var.get() in ["Hiện đại", "Modern"]:
            self.draw_modern_board()
        else:
            self.draw_classic_board()

    def on_mode_change(self):
        if self.is_ai_thinking or getattr(self, '_is_waiting_online', False): return
        mode = self.game_mode_var.get()
        
        if mode != "Online" and self.ws:
            try: self.ws.close()
            except: pass
            self.ws = None
            
        self.score_me = 0
        self.score_opp = 0
        self.update_score_display()

        if mode in ("Ultra-AI", "AI vs AI") and self.board_size > 20: self.board_size_var.set("20x20"); self.save_settings(); self.new_game(); return
        
        self.is_ai_match_paused = not self.history
        self.refresh_mode_visibility(); self.update_mode_buttons(); self.apply_symbols(); self.save_settings()

        if mode == "Online":
            self.new_game()
            return

        if self.game_over or not self.history:
            if mode == "AI vs AI": self.display_status("ai_ready", color="#f39c12")
            else: self.update_turn_status()
            return

        if mode in ("Ultra-AI", "AI vs AI"):
            self.engine_synced, self.is_ai_thinking = False, True
            self.modern_canvas.configure(cursor="watch"); self.start_thinking_animation("ai_taking_over")
            threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
        else:
            if self.engine: self.engine.stop(); self.engine = None
            self.update_turn_status(mode_type="2p")

    def apply_symbols(self):
        mode = self.game_mode_var.get()
        if mode == "Online":
            self.player_symbol = self.online_symbol if self.online_symbol else "X"
            self.ai_symbol = "O" if self.player_symbol == "X" else "X"
            self.player_symbol_var.set(self.player_symbol) # Cập nhật hiển thị của nút
        else:
            if self.player_symbol_var.get() == "X": self.player_symbol, self.ai_symbol = "X", "O"
            else: self.player_symbol, self.ai_symbol = "O", "X"
            
        self.update_ui()
        self.update_score_display()
        
        if hasattr(self, 'btn_toggle_symbol') and self.btn_toggle_symbol.winfo_exists():
            x_bg, x_hov = ("#2980b9", "#2471a3") if self.is_dark_mode else ("#3498db", "#2980b9")
            o_bg, o_hov = ("#c0392b", "#a93226") if self.is_dark_mode else ("#e74c3c", "#c0392b")

            if self.player_symbol_var.get() == "X":
                self.btn_toggle_symbol.configure(fg_color=x_bg, hover_color=x_hov, text="X")
            else:
                self.btn_toggle_symbol.configure(fg_color=o_bg, hover_color=o_hov, text="O")
        
        # ĐÃ SỬA: Phân định rõ chế độ AI vs AI để gọi đúng tên AI 1 / AI 2
        if not self.game_over and not self.is_ai_thinking and not getattr(self, '_is_waiting_online', False):
            if mode == "AI vs AI": 
                self.update_turn_status(mode_type="ai_vs_ai")
            elif mode == "2 Người":
                self.update_turn_status(mode_type="2p")
            elif mode != "Online": 
                self.update_turn_status()
                
        self.save_settings()

    def swap_ai_difficulties(self):
        val_x, val_o = self.difficulty_x_var.get(), self.difficulty_o_var.get()
        self.difficulty_x_var.set(val_o); self.difficulty_o_var.set(val_x)
        if hasattr(self, 'diff_x_menu'): self.diff_x_menu.set(val_o)
        if hasattr(self, 'diff_o_menu'): self.diff_o_menu.set(val_x)
        self.save_settings()

    def get_time_turn(self, side=None): 
        mode, diff_map = self.game_mode_var.get(), DIFFICULTY.get(self.lang_var.get(), DIFFICULTY.get("VI", {}))
        if mode == "AI vs AI":
            return int(diff_map.get(self.difficulty_x_var.get() if (side == "X" if side is not None else len(self.history) % 2 == 0) else self.difficulty_o_var.get(), 200))
        return int(diff_map.get(self.difficulty_var.get(), 200))

    def init_engine(self):
        try:
            self.engine = UltraAIEngine(ENGINE_PATH, self.board_size, self.get_time_turn(), 1 if self.is_standard_rule else 0)
            self.engine.start(); return True
        except Exception as e:
            messagebox.showerror(self.t("err_title"), str(e)); self.display_status("engine_err", color="#e74c3c"); return False

    def request_new_game(self, event=None):
        mode = self.game_mode_var.get()
        if mode == "Online":
            if not self.ws or not self.is_online_connected or getattr(self, '_is_waiting_online', False):
                return

            # Chỉ cho bấm khi ván đã kết thúc hoặc đối thủ đã sẵn sàng
            if not self.game_over and not self.opponent_ready_for_rematch:
                return

            # Tự động đảo quân nếu kết thúc ván mà người chơi không bấm chọn quân tay
            # CHỈ ĐẢO khi đối thủ chưa gửi yêu cầu Ván Mới (tránh bị lật 2 lần về lại như cũ)
            if self.game_over and not getattr(self, '_manually_chose_symbol', False) and not self.opponent_ready_for_rematch:
                current_sym = self.player_symbol_var.get()
                new_sym = "O" if current_sym == "X" else "X"
                self.player_symbol_var.set(new_sym)
                self.online_symbol = new_sym

            # Tạo payload chứa yêu cầu rematch và quân cờ hiện tại
            payload = {"type": "rematch", "symbol": self.player_symbol_var.get()}

            if self.opponent_ready_for_rematch:
                self.my_ready_for_rematch = True
                try: self.ws.send(json.dumps(payload))
                except Exception: pass
                self.trigger_online_rematch()
            else:
                self.my_ready_for_rematch = True
                try: self.ws.send(json.dumps(payload))
                except Exception: pass
                self.display_status(self.t("online_ready_wait"), color="#f39c12", raw_text=True)

                if hasattr(self, "btn_new") and self.btn_new.winfo_exists():
                    is_dark = self.is_dark_mode
                    disabled_bg = "#21262d" if is_dark else "#e2e8f0"
                    disabled_fg = "#6e7681" if is_dark else "#64748b"
                    self.btn_new.configure(state="disabled", fg_color=disabled_bg, hover_color=disabled_bg, text_color=disabled_fg)
        else:
            if self.history:
                self.new_game()

    def trigger_online_rematch(self):
        self.my_ready_for_rematch = False
        self.opponent_ready_for_rematch = False

        self.rebuild_board_widgets()
        self.game_over = False
        self.last_move = self.hover_cell = self.hint_cell = None
        self.winning_cells, self.history = [], []

        # Reset cờ đánh dấu bấm chọn quân cho ván tiếp theo
        self._manually_chose_symbol = False
        
        # Đảm bảo luật: Quân X luôn luôn được đi trước
        self.is_online_turn = (self.online_symbol == "X")

        self.apply_symbols()
        self.modern_canvas.configure(cursor="hand2" if self.is_online_turn else "watch")
        self.update_turn_status(mode_type="online", symbol=self.online_symbol)
        self.init_match_timers()
        self.update_pause_btn_state()
        self.set_time_controls_enabled(True)

    def new_game(self):
        self.stop_thinking_animation()
        if self.turn_timer_job:
            self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
        if self.engine: self.engine.stop(); self.engine = None
        self.rebuild_board_widgets()
        
        self.game_over = self.is_ai_thinking = self.engine_synced = False
        self.is_ai_match_paused = True
        self.last_move = self.hover_cell = self.hint_cell = None
        self.winning_cells, self.history = [], []
        self.current_turn = HUMAN
            
        self.modern_canvas.configure(cursor="hand2")
        self.apply_symbols(); self.update_ui(); self.init_match_timers(); self.update_pause_btn_state()

        mode = self.game_mode_var.get()
        if mode == "Online":
            if not self.is_online_connected:
                self.display_status(self.t("online_enter_room"), color="#f39c12", raw_text=True)
            return
            
        if mode == "2 Người": self.update_turn_status(mode_type="2p", symbol=self.player_symbol); return
        if mode == "AI vs AI":
            self.display_status("ai_ready", color="#f39c12")
            if self.init_engine(): self.engine_synced = True
            return

        if self.init_engine(): self.engine_synced = True; self.update_turn_status(symbol=self.player_symbol)

    def get_winning_line(self, r, c, piece):
        rule = self.rule_var.get().lower()
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            cells, blocked_pos, blocked_neg = [(r, c)], False, False
            nr, nc = r + dr, c + dc
            while 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                if self.board[nr][nc] == piece: cells.append((nr, nc)); nr += dr; nc += dc
                else: blocked_pos = (self.board[nr][nc] != EMPTY); break
            else: blocked_pos = True

            nr, nc = r - dr, c - dc
            while 0 <= nr < self.board_size and 0 <= nc < self.board_size:
                if self.board[nr][nc] == piece: cells.insert(0, (nr, nc)); nr -= dr; nc -= dc
                else: blocked_neg = (self.board[nr][nc] != EMPTY); break
            else: blocked_neg = True

            if len(cells) >= 5:
                if "standard" in rule or "tiêu chuẩn" in rule: return cells
                if ("chặn 2 đầu" in rule or "block" in rule) and (blocked_pos and blocked_neg): continue
                return cells
        return []

    def find_urgent_move(self, side):
        for side_check in (side, HUMAN if side == AI else AI):
            for r in range(self.board_size):
                for c in range(self.board_size):
                    if self.board[r][c] == EMPTY:
                        self.board[r][c] = side_check
                        is_win = self.get_winning_line(r, c, side_check)
                        self.board[r][c] = EMPTY
                        if is_win: return (r, c)
        return None

    def join_online_room(self):
        if websocket is None:
            messagebox.showerror("Lỗi hệ thống", "Môi trường khởi chạy đang thiếu thư viện mạng 'websocket-client'.\n\nBạn vui lòng cài đặt bằng lệnh:\npip install websocket-client")
            return
            
        room_id = self.room_id_var.get().strip()
        if not room_id:
            self.display_status(self.t("online_need_room"), color="#ef4444", raw_text=True)
            return

        if self.ws:
            try: self.ws.close()
            except: pass
            self.ws = None

        self.score_me = 0
        self.score_opp = 0
        self.my_ready_for_rematch = False
        self.opponent_ready_for_rematch = False
        self.update_score_display()
        self.clear_chat()
        
        # === LÀM MỜ VÀ CHẶN SỬA TÊN, MÃ PHÒNG AN TOÀN ===
        dim_color = "#64748b" if self.is_dark_mode else "#94a3b8"
        self.name_entry.configure(text_color=dim_color)
        self.room_entry.configure(text_color=dim_color)
        self.name_entry.bind("<Key>", lambda e: "break")
        self.name_entry.bind("<Button-1>", lambda e: "break")
        self.room_entry.bind("<Key>", lambda e: "break")
        self.room_entry.bind("<Button-1>", lambda e: "break")
        self.btn_join.configure(state="disabled")
        # ===============================================

        self._is_waiting_online = True
        self.start_thinking_animation(self.t("online_connecting"), raw_text=True)
        self.modern_canvas.configure(cursor="watch")
        
        threading.Thread(target=self._ws_thread, args=(room_id,), daemon=True).start()

    def _ws_thread(self, room_id):
        try:
            self.ws = websocket.WebSocketApp(SERVER_URL,
                on_message=self._ws_on_message,
                on_error=self._ws_on_error,
                on_close=self._ws_on_close)
            p_name = self.player_name_var.get().strip() or "Tùng"
            
            # Gửi full setting lên server (time + board + rule + symbol)
            limit_secs = self.get_selected_time_limit_seconds()
            self.ws.on_open = lambda ws: ws.send(json.dumps({
                "action": "join",
                "room": room_id,
                "name": p_name,
                "symbol": self.player_symbol_var.get(), # <--- THÊM DÒNG NÀY 
                "time_limit": limit_secs,
                "board_size": self.board_size_var.get(),
                "rule": self.rule_var.get()
            }))
            
            self.ws.run_forever()
        except Exception as e:
            self.root.after(0, lambda: self.display_status(f"Lỗi mạng: {e}", color="#ef4444", raw_text=True))
            self.root.after(0, self.stop_thinking_animation)
            self.root.after(0, lambda: self.modern_canvas.configure(cursor="hand2"))

    def _ws_on_message(self, ws, message):
        data = json.loads(message)
        t = data.get("type")
        if t == "waiting":
            def apply_waiting():
                self.stop_thinking_animation()
                self.display_status(data.get("msg", "Đã vào phòng. Đang chờ đối thủ..."), color="#f39c12", raw_text=True)
                self.modern_canvas.configure(cursor="watch")
            self.root.after(0, apply_waiting)
            return

        if t == "error":
            self.root.after(0, lambda: self.display_status(data["msg"], color="#ef4444", raw_text=True))
            self.root.after(0, self.stop_thinking_animation)
            self.root.after(0, lambda: self.modern_canvas.configure(cursor="hand2"))
            ws.close()
            
        elif t == "start":
            self.online_symbol = data.get("symbol", self.player_symbol_var.get())
            self.player_symbol_var.set(self.online_symbol)
            # Chốt quyền đi trước: X đi trước, O đi sau
            self.is_online_turn = (self.online_symbol == "X") 
            
            opponent_name = (data.get("opponent_name") or data.get("opponent") or data.get("opponentName") or "").strip()
            if opponent_name:
                self.opponent_name = opponent_name

            # Đồng bộ board_size + rule + time từ server (setting của host)
            remote_board = data.get("board_size")
            remote_rule = data.get("rule")
            remote_time = data.get("time_limit")
            remote_times = data.get("times")
            
            def init_online_match():
                # Áp dụng setting từ server
                if remote_board and remote_board in ("15x15", "19x19", "20x20"):
                    if self.board_size_var.get() != remote_board:
                        self.board_size_var.set(remote_board)
                        self.rebuild_board_widgets()
                if remote_rule:
                    self.rule_var.set(remote_rule)
                if remote_time is not None:
                    minutes = int(remote_time // 60) if remote_time > 0 else 0
                    self.time_minutes_var.set(str(minutes))
                    self.update_minus_button_color()

                self.is_online_connected = True
                self.update_mode_buttons()
                self.stop_thinking_animation()
                self.apply_symbols()
                self.modern_canvas.configure(cursor="hand2" if self.is_online_turn else "watch")
                self.update_turn_status(mode_type="online", symbol=self.online_symbol)
                
                self.is_ai_match_paused = False
                self.turn_time_remaining = {"X": self.turn_time_limit, "O": self.turn_time_limit}
                self.init_match_timers()
                if remote_times and isinstance(remote_times, dict):
                    self._match_base_times = {
                        "X": int(remote_times.get("X", 0)),
                        "O": int(remote_times.get("O", 0))
                    }
                    self.time_remaining = dict(self._match_base_times)
                    self.update_timer_display()
                self.update_score_display()
            self.root.after(0, init_online_match)
            
        elif t == "turn_start":
            turn_symbol = data.get("symbol")
            turn_secs = data.get("turn_secs", 35)
            deadline = data.get("deadline")  # unix timestamp từ server
            times = data.get("times")
            def apply_turn_start():
                if self.game_over: return
                if self.online_symbol:
                    self.is_online_turn = (turn_symbol == self.online_symbol)
                self._server_turn_symbol = turn_symbol  # nguồn chuẩn cho timer

                # Đồng bộ đồng hồ tổng từ server — nguồn chuẩn
                if times and isinstance(times, dict):
                    self._match_base_times = {
                        "X": int(times.get("X", 0)),
                        "O": int(times.get("O", 0))
                    }
                    self.time_remaining = dict(self._match_base_times)
                    self.update_timer_display()
                    # Chạy interpolator match clock (Online)
                    if self.get_selected_time_limit_seconds() > 0:
                        if self.timer_job:
                            try: self.root.after_cancel(self.timer_job)
                            except Exception: pass
                            self.timer_job = None
                        if len(self.history) > 0:
                            self.run_match_timer()
                
                if len(self.history) > 0 and deadline:
                    self.start_turn_timer(turn_symbol, turn_secs=turn_secs, deadline=deadline)
                elif len(self.history) > 0:
                    self.start_turn_timer(turn_symbol, turn_secs=turn_secs)
                else:
                    self.turn_time_limit = int(turn_secs) if turn_secs else 35
                    self.turn_time_remaining = {"X": self.turn_time_limit, "O": self.turn_time_limit}
                    self._turn_deadline = None
                    self.update_turn_bar()

                self.modern_canvas.configure(cursor="hand2" if self.is_online_turn else "watch")
                self.update_turn_status(mode_type="online", symbol=turn_symbol)
                self.update_ui()
            self.root.after(0, apply_turn_start)

        elif t == "update_time_limit":
            new_limit_secs = data.get("time_limit", 0)
            def apply_remote_time():
                minutes = int(new_limit_secs // 60) if new_limit_secs > 0 else 0
                self.time_minutes_var.set(str(minutes))
                self.update_minus_button_color()
                self.init_match_timers()
                self.display_status(f"Đối thủ đã đổi thời gian thành {minutes} phút", color="#f39c12", raw_text=True)
            self.root.after(0, apply_remote_time)

        elif t == "update_settings":
            remote_board = data.get("board_size")
            remote_rule = data.get("rule")
            remote_time = data.get("time_limit")
            remote_symbol = data.get("symbol") # Nhận quân từ đối thủ

            def apply_remote_settings():
                msgs = []
                if remote_board and remote_board in ("15x15", "19x19", "20x20"):
                    if self.board_size_var.get() != remote_board:
                        self.board_size_var.set(remote_board)
                        if not self.history:
                            self.rebuild_board_widgets()
                        msgs.append(f"bàn {remote_board}")
                if remote_rule and self.rule_var.get() != remote_rule:
                    self.rule_var.set(remote_rule)
                    msgs.append(f"luật {remote_rule}")
                if remote_time is not None:
                    minutes = int(remote_time // 60) if remote_time > 0 else 0
                    self.time_minutes_var.set(str(minutes))
                    self.update_minus_button_color()
                    self.init_match_timers()
                    msgs.append(f"{minutes} phút" if minutes > 0 else "không giới hạn giờ")
                
                # Xử lý lật quân khi đối thủ đổi phe
                if remote_symbol:
                    my_new_sym = "O" if remote_symbol == "X" else "X"
                    if self.player_symbol_var.get() != my_new_sym:
                        self.player_symbol_var.set(my_new_sym)
                        self.online_symbol = my_new_sym
                        
                        # ĐÃ THÊM: Ghi nhớ rằng đối thủ đã chủ động chọn quân 
                        # để máy không tự động lật ngược lại khi bấm Ván Mới
                        self._manually_chose_symbol = True
                        
                        self.apply_symbols()
                        msgs.append(f"chọn quân {remote_symbol}")

                if msgs:
                    self.display_status("Đối thủ đổi: " + ", ".join(msgs), color="#f39c12", raw_text=True)
            self.root.after(0, apply_remote_settings)

        elif t == "move":
            r, c = data.get("r"), data.get("c")
            opponent_sym = "O" if self.online_symbol == "X" else "X"
            
            def apply_opp_move():
                if self.game_over: return
                self.board[r][c] = AI 
                self.last_move = (r, c)
                self.history.append((r, c, AI))
                self.play_sound(TING_SOUND_PATH)

                # Khóa nút thời gian ngay khi có quân đầu tiên
                self.set_time_controls_enabled(False)

                # Hủy timer local — đợi turn_start từ server (có deadline chuẩn)
                if self.turn_timer_job:
                    try: self.root.after_cancel(self.turn_timer_job)
                    except Exception: pass
                    self.turn_timer_job = None
                self._turn_deadline = None
                
                win_line = self.get_winning_line(r, c, AI)
                if win_line:
                    self.winning_cells = win_line
                    self.game_over = True
                    self.add_score(opponent_sym)
                    self.display_status(self.t("online_opp_win").format(opponent_sym), color="#ef4444", raw_text=True)
                    self.play_sound(VICTORY_SOUND_PATH)
                    self.update_pause_btn_state()   # ← Bật nút VÁN MỚI
                else:
                    self.is_online_turn = True
                    self.modern_canvas.configure(cursor="hand2")
                    self.update_turn_status(mode_type="online", symbol=self.online_symbol)
                self.update_ui()
            self.root.after(0, apply_opp_move)
            
        elif t == "sync_time":
            times = data.get("times")
            if times and not self.game_over:
                def apply_sync():
                    self.time_remaining = times
                    self.update_timer_display()
                self.root.after(0, apply_sync)
            
        elif t == "timeout":
            loser_sym = data.get("loser")
            times = data.get("times")
            def apply_timeout():
                if times and isinstance(times, dict):
                    self._match_base_times = {
                        "X": int(times.get("X", 0)),
                        "O": int(times.get("O", 0))
                    }
                    self.time_remaining = dict(self._match_base_times)
                    self.update_timer_display()
                if not self.game_over:
                    self.handle_timeout(loser_sym)
            self.root.after(0, apply_timeout)
            
        elif t == "rematch":
            # Đọc xem đối thủ đang yêu cầu cầm quân gì
            opp_sym = data.get("symbol")
            
            def apply_rematch():
                # Tự động gán cho bản thân quân cờ ngược lại với đối thủ
                if opp_sym in ("X", "O"):
                    my_new_sym = "O" if opp_sym == "X" else "X"
                    self.player_symbol_var.set(my_new_sym)
                    self.online_symbol = my_new_sym
                    self.apply_symbols()

                self.opponent_ready_for_rematch = True
                if self.my_ready_for_rematch:
                    self.trigger_online_rematch()
                else:
                    self.display_status(self.t("online_opp_ready"), color="#2ecc71", raw_text=True)
            self.root.after(0, apply_rematch)
            
        elif t == "chat":
            name = data.get("name") or "???"
            text = data.get("text") or ""
            def apply_chat():
                self.append_chat(name, text, is_self=False)
            self.root.after(0, apply_chat)

        elif t == "disconnect":
            def apply_dc():
                self.game_over = True
                if self.timer_job: self.root.after_cancel(self.timer_job); self.timer_job = None
                self.stop_thinking_animation()
                self.display_status(data["msg"], color="#f39c12", raw_text=True)
                self.modern_canvas.configure(cursor="hand2")
            self.root.after(0, apply_dc)

    def _ws_on_error(self, ws, error):
        self.root.after(0, lambda: self.display_status(self.t("online_disconnected"), color="#ef4444", raw_text=True))
        self.root.after(0, self.stop_thinking_animation)
        self.root.after(0, lambda: self.modern_canvas.configure(cursor="hand2"))

    def _ws_on_close(self, ws, close_status_code, close_msg):
        self.root.after(0, self.stop_thinking_animation)

    def click(self, r, c):
        if self.game_mode_var.get() == "AI vs AI" or self.game_over or self.is_ai_thinking or self.board[r][c] != EMPTY: return
        
        if self.game_mode_var.get() == "Online":
            if not self.is_online_turn or getattr(self, '_is_waiting_online', False): return
            
            self.board[r][c] = HUMAN
            self.last_move = (r, c)
            self.history.append((r, c, HUMAN))
            self.play_sound(TING_SOUND_PATH)
            self.is_online_turn = False

            # Khóa nút thời gian ngay khi có quân đầu tiên
            self.set_time_controls_enabled(False)
            
            # Hủy timer local — đợi turn_start từ server (có deadline chuẩn)
            if self.turn_timer_job:
                self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
            self._turn_deadline = None
            
            self.ws.send(json.dumps({
                "type": "move",
                "r": r,
                "c": c
            }))
            
            win_line = self.get_winning_line(r, c, HUMAN)
            if win_line:
                self.winning_cells = win_line
                self.game_over = True
                if self.turn_timer_job:
                    self.root.after_cancel(self.turn_timer_job); self.turn_timer_job = None
                self.add_score(self.online_symbol)
                self.display_status(self.t("online_you_win").format(self.online_symbol), color="#2ecc71", raw_text=True)
                self.play_sound(VICTORY_SOUND_PATH)
                self.modern_canvas.configure(cursor="hand2")
                self.update_pause_btn_state()   # ← Bật nút VÁN MỚI
            else:
                self.modern_canvas.configure(cursor="watch")
                self.update_turn_status(mode_type="online", symbol=self.online_symbol)
            self.update_ui()
            return
            
        self.hint_cell = None 
        if self.is_ai_match_paused:
            self.is_ai_match_paused = False
            self.start_turn_timer()

        self.board[r][c] = self.current_turn
        self.last_move = (r, c)
        self.history.append((r, c, self.current_turn))
        
        self.play_sound(TING_SOUND_PATH); self.update_ui(); self.update_pause_btn_state()
        if self.get_selected_time_limit_seconds() > 0 and not self.timer_job: self.run_match_timer()

        win_line = self.get_winning_line(r, c, self.current_turn)
        if win_line:
            if self.timer_job: self.root.after_cancel(self.timer_job)
            self.winning_cells = win_line; self.hover_cell = None; self.update_ui()
            winner_sym = self.player_symbol if self.current_turn == HUMAN else self.ai_symbol
            self.add_score(winner_sym)
            self.display_status("win_msg", color=self.status_color_for_symbol(winner_sym), format_args=[winner_sym])
            self.game_over = True; self.is_ai_thinking = False
            self.play_sound(VICTORY_SOUND_PATH); self.update_pause_btn_state()
            return

        self.current_turn = AI if self.current_turn == HUMAN else HUMAN
        self.start_turn_timer()
        if self.game_mode_var.get() == "2 Người": self.update_turn_status(mode_type="2p"); return

        self.is_ai_thinking = True; self.hover_cell = None; self.modern_canvas.configure(cursor="watch"); self.start_thinking_animation("ai_thinking")
        threading.Thread(target=self.ai_turn if self.engine_synced else self.ai_board_sync_turn, args=(((c, r) if self.engine_synced else ())), daemon=True).start()

    def _handle_ai_error(self, error_msg_key):
        self.stop_thinking_animation(); self.display_status(error_msg_key, color="#ef4444"); self.is_ai_thinking = False
        self.modern_canvas.configure(cursor="hand2"); self.update_pause_btn_state()

    def ai_resign(self, ai_side):
        self.stop_thinking_animation()
        if self.timer_job: self.root.after_cancel(self.timer_job)
        self.update_ui()
        sym = "X" if ai_side == HUMAN else "O" if self.game_mode_var.get() == "AI vs AI" else (self.player_symbol if ai_side == HUMAN else self.ai_symbol)
        
        winner_sym = "O" if sym == "X" else "X"
        self.add_score(winner_sym)
        
        self.display_status("resgin_status", color="#ef4444", format_args=[sym])
        self.game_over = True; self.is_ai_thinking = False; self.update_pause_btn_state(); self.modern_canvas.configure(cursor="hand2")

    def _process_engine_turn(self, ai_side, opp_side):
        for _ in range(40):
            if not self.engine or self.is_ai_match_paused: return
            response = self.engine.get_response(timeout=max(10, int(self.get_time_turn()) // 1000 + 3))
            if not self.engine or self.is_ai_match_paused: return
            if not response or any(k in response.upper() for k in ("ERROR", "MESSAGE")): continue
            if "RESIGN" in response.upper(): self.root.after(0, self.ai_resign, ai_side); return
            if "," in response:
                parts = response.replace(" ", "").split(",")
                if len(parts) >= 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
                    ax, ay = int(parts[0]), int(parts[1])
                    if 0 <= ax < self.board_size and 0 <= ay < self.board_size and self.board[ay][ax] == EMPTY:
                        if self.is_ai_match_paused: return 
                        self.board[ay][ax] = ai_side; self.last_move = (ay, ax); self.history.append((ay, ax, ai_side))
                        self.play_sound(TING_SOUND_PATH); self.current_turn = opp_side
                        self.root.after(0, self.finish_ai); return
        if self.engine and not self.is_ai_match_paused: self.root.after(0, self._handle_ai_error, "ai_not_resp")

    def ai_turn(self, x, y):
        try:
            urgent = self.find_urgent_move(self.current_turn)
            if urgent: self._apply_ai_move(*urgent, self.current_turn); return
            if self.game_mode_var.get() == "AI vs AI" and self.engine: self.engine.send(f"INFO timeout_turn {int(self.get_time_turn('X' if self.current_turn == HUMAN else 'O'))}")
            self.engine.send(f"TURN {x},{y}"); self._process_engine_turn(self.current_turn, HUMAN if self.current_turn == AI else AI)
        except Exception:
            if self.engine and not self.is_ai_match_paused: self.root.after(0, self._handle_ai_error, "ai_err")

    def ai_board_sync_turn(self):
        try:
            if self.engine: self.engine.stop(); self.engine = None
            if self.is_ai_match_paused: return
            
            mode = self.game_mode_var.get()
            if mode == "AI vs AI":
                first_sym = self.player_symbol_var.get() if hasattr(self, 'player_symbol_var') else "X"
                second_sym = "O" if first_sym == "X" else "X"
                # Xác định phe nào đánh ở lượt hiện tại dựa vào số bước đi
                current_sym = first_sym if len(self.history) % 2 == 0 else second_sym
                ai_side = HUMAN if current_sym == self.player_symbol else AI
            else:
                ai_side = self.current_turn

            self.engine = UltraAIEngine(ENGINE_PATH, self.board_size, int(self.get_time_turn("X" if ai_side == HUMAN else "O")), 1 if self.is_standard_rule else 0)
            self.engine.start(); self.engine_synced = True
            if urgent := self.find_urgent_move(ai_side): self._apply_ai_move(*urgent, ai_side); return
            if self.history:
                self.engine.send("BOARD")
                for r, c, p in self.history: self.engine.send(f"{c},{r},{1 if p == ai_side else 2}")
                self.engine.send("DONE")
            else: self.engine.send("BEGIN")
            self._process_engine_turn(ai_side, HUMAN if ai_side == AI else AI)
        except Exception:
            if self.engine and not self.is_ai_match_paused: self.root.after(0, self._handle_ai_error, "sync_err")

    def _apply_ai_move(self, r, c, ai_side):
        self.board[r][c] = ai_side
        self.last_move = (r, c)
        self.history.append((r, c, ai_side))
        self.play_sound(TING_SOUND_PATH)
        self.current_turn = HUMAN if ai_side == AI else AI
        self.root.after(0, self.finish_ai)

    def finish_ai(self):
        if self.is_ai_match_paused: return
        self.stop_thinking_animation(); self.update_ui(); self.update_pause_btn_state()
        if not self.game_over: self.start_turn_timer()
        if not self.history: return
        if len(self.history) == 1 and self.get_selected_time_limit_seconds() > 0 and not self.timer_job: self.run_match_timer()

        last_piece, lr, lc = self.history[-1][2], self.history[-1][0], self.history[-1][1]
        mode = self.game_mode_var.get()
        if win_line := self.get_winning_line(lr, lc, last_piece):
            if self.timer_job: self.root.after_cancel(self.timer_job)
            self.winning_cells = win_line; self.hover_cell = None; self.update_ui()
            winner_sym = self.player_symbol if last_piece == HUMAN else self.ai_symbol
            self.add_score(winner_sym)
            self.display_status("ai_vs_ai_win" if mode == "AI vs AI" else "ai_win_msg", color=self.status_color_for_symbol(winner_sym), format_args=[winner_sym])
            self.game_over = True; self.is_ai_thinking = False; self.play_sound(VICTORY_SOUND_PATH); self.modern_canvas.configure(cursor="hand2"); self.update_pause_btn_state()
        else:
            if mode == "AI vs AI" and not self.game_over and not self.is_ai_match_paused:
                self.update_turn_status(mode_type="ai_vs_ai"); self.is_ai_thinking = True; self.modern_canvas.configure(cursor="watch"); self.start_thinking_animation("ai_thinking")
                threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()
            else:
                self.update_turn_status(); self.is_ai_thinking = False; self.game_over = False; self.modern_canvas.configure(cursor="hand2"); self.update_pause_btn_state()

    def get_hint(self, event=None):
        if self.game_over or self.is_ai_thinking or self.game_mode_var.get() == "AI vs AI" or self.game_mode_var.get() == "Online": return
        self.hint_cell = None; self.is_ai_thinking = True; self.modern_canvas.configure(cursor="watch"); self.start_thinking_animation("hint_calculating")
        threading.Thread(target=self._calc_hint_thread, daemon=True).start()

    def _calc_hint_thread(self):
        try:
            temp_engine = UltraAIEngine(ENGINE_PATH, self.board_size, 500, 1 if self.is_standard_rule else 0)
            temp_engine.start()
            side = self.current_turn if self.game_mode_var.get() == "2 Người" else HUMAN
            if self.history:
                temp_engine.send("BOARD")
                for r, c, p in self.history: temp_engine.send(f"{c},{r},{1 if (p == side if self.game_mode_var.get() == '2 Người' else p == HUMAN) else 2}")
                temp_engine.send("DONE")
            else: temp_engine.send("BEGIN")
            for _ in range(40):
                resp = temp_engine.get_response(timeout=4)
                if not resp or any(k in resp.upper() for k in ("ERROR", "MESSAGE")): continue
                if "," in resp:
                    parts = resp.replace(" ", "").split(",")
                    if len(parts) >= 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
                        ax, ay = int(parts[0]), int(parts[1])
                        if 0 <= ax < self.board_size and 0 <= ay < self.board_size and self.board[ay][ax] == EMPTY: self.hint_cell = (ay, ax); break
            temp_engine.stop()
        except Exception: pass
        self.root.after(0, self.finish_hint)

    def finish_hint(self):
        self.stop_thinking_animation(); self.is_ai_thinking = False; self.modern_canvas.configure(cursor="hand2"); self.update_ui()
        if self.hint_cell: self.play_sound(IDEA_SOUND_PATH); self.display_status("hint_result", color="#ef4444")
        else: self.display_status("hint_err", color="#ef4444")

    def _stop_and_reset_ai(self):
        if self.is_ai_thinking:
            if self.engine: self.engine.stop(); self.engine = None
            self.is_ai_thinking = False; self.stop_thinking_animation(); self.modern_canvas.configure(cursor="hand2")

    def _finalize_history_action(self, msg_prefix_key):
        self.apply_symbols(); self.update_ui(); self.update_pause_btn_state()
        if not self.history:
            if self.game_mode_var.get() == "AI vs AI": self.display_status("ai_ready", color="#f39c12")
            else: self.update_turn_status()
        else: self.display_status("ai_match_paused", color="#f39c12", prefix_key=msg_prefix_key)

    def undo_move(self, event=None):
        mode = self.game_mode_var.get()
        # Chỉ chặn Online.
        if mode == "Online" or getattr(self, '_is_waiting_online', False):
            return
            
        # RẤT QUAN TRỌNG: Nếu đang đánh AI hoặc AI vs AI, phải DỪNG ván đấu hoặc đợi HẾT VÁN mới được lùi
        if self.is_ai_thinking and not self.is_ai_match_paused and not self.game_over:
            return
            
        if not self.history:
            return
            
        if not hasattr(self, 'redo_stack'): self.redo_stack = []

        # Ultra-AI lùi 2 bước (về lượt mình). AI vs AI và 2 Người lùi 1 bước.
        moves_to_undo = 1
        if mode == "Ultra-AI" and len(self.history) >= 2:
            moves_to_undo = 2

        if self.game_over and self.winning_cells:
            winner_sym = self.player_symbol if self.history[-1][2] == HUMAN else self.ai_symbol
            if winner_sym == "X": self.score_me = max(0, self.score_me - 1)
            else: self.score_opp = max(0, self.score_opp - 1)
            self.update_score_display()

        for _ in range(moves_to_undo):
            if self.history:
                r, c, piece = self.history.pop()
                self.board[r][c] = EMPTY
                self.redo_stack.append((r, c, piece))
                
        self.winning_cells = []
        self.game_over = False
        self.hint_cell = None
        self.last_move = (self.history[-1][0], self.history[-1][1]) if self.history else None
        
        # Đặt lại lượt
        if mode in ("2 Người", "AI vs AI"):
            self.current_turn = HUMAN if len(self.history) % 2 == 0 else AI
        elif mode == "Ultra-AI":
            if len(self.history) % 2 == 0:
                self.current_turn = HUMAN if self.player_symbol == "X" else AI
            else:
                self.current_turn = AI if self.player_symbol == "X" else HUMAN
                
            if self.current_turn == AI and not self.is_ai_match_paused:
                self.is_ai_thinking = True
                self.modern_canvas.configure(cursor="watch")
                self.start_thinking_animation("ai_taking_over")
                threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()

        self.update_ui()
        if not self.is_ai_thinking:
            if mode == "AI vs AI":
                self.update_turn_status(mode_type="ai_vs_ai")
            else:
                self.update_turn_status()
            self.modern_canvas.configure(cursor="hand2")
            
        self.update_pause_btn_state()
        if not self.is_ai_match_paused:
            self.start_turn_timer()

    def redo_move(self, event=None):
        mode = self.game_mode_var.get()
        if mode == "Online" or getattr(self, '_is_waiting_online', False):
            return
            
        if self.is_ai_thinking and not self.is_ai_match_paused and not self.game_over:
            return
            
        if not getattr(self, 'redo_stack', []):
            return

        moves_to_redo = 1
        if mode == "Ultra-AI" and len(self.redo_stack) >= 2:
            moves_to_redo = 2

        for _ in range(moves_to_redo):
            if self.redo_stack:
                r, c, piece = self.redo_stack.pop()
                self.board[r][c] = piece
                self.history.append((r, c, piece))
                self.last_move = (r, c)
                
                win_line = self.get_winning_line(r, c, piece)
                if win_line:
                    self.winning_cells = win_line
                    self.game_over = True
                    winner_sym = self.player_symbol if piece == HUMAN else self.ai_symbol
                    self.add_score(winner_sym)
                    self.display_status("win_msg" if mode != "AI vs AI" else "ai_vs_ai_win", color=self.status_color_for_symbol(winner_sym), format_args=[winner_sym])
                    self.play_sound(VICTORY_SOUND_PATH)
                    if self.timer_job: self.root.after_cancel(self.timer_job)

        self.hint_cell = None
        
        if not self.game_over:
            if mode in ("2 Người", "AI vs AI"):
                self.current_turn = HUMAN if len(self.history) % 2 == 0 else AI
            elif mode == "Ultra-AI":
                if len(self.history) % 2 == 0:
                    self.current_turn = HUMAN if self.player_symbol == "X" else AI
                else:
                    self.current_turn = AI if self.player_symbol == "X" else HUMAN
                    
                if self.current_turn == AI and not self.is_ai_match_paused:
                    self.is_ai_thinking = True
                    self.modern_canvas.configure(cursor="watch")
                    self.start_thinking_animation("ai_taking_over")
                    threading.Thread(target=self.ai_board_sync_turn, daemon=True).start()

        self.update_ui()
        if not self.game_over and not self.is_ai_thinking:
            if mode == "AI vs AI":
                self.update_turn_status(mode_type="ai_vs_ai")
            else:
                self.update_turn_status()
                
            if not self.is_ai_match_paused:
                self.start_turn_timer()
        self.update_pause_btn_state()

    def limit_name_length(self, *args):
        current_name = self.player_name_var.get()
        if len(current_name) > 16:
            self.player_name_var.set(current_name[:16])

    def on_close(self, event=None):
        self.stop_thinking_animation(); self.save_settings()
        if self.ws:
            try: self.ws.close()
            except: pass
        if self.timer_job: self.root.after_cancel(self.timer_job)
        if self.engine: self.engine.stop()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = ctk.CTk()
        app = CaroUltraAI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()

    except Exception as e:
        import traceback
        import tkinter as tk
        from tkinter import messagebox
        err_msg = traceback.format_exc()
        
        error_root = tk.Tk()
        error_root.withdraw()
        messagebox.showerror(
            "Phát hiện lỗi khởi động (Crash)", 
            f"App bị văng ngầm do lỗi sau:\n\n{err_msg}\n\n(Vui lòng chụp lại thông báo này để tìm cách sửa!)"
        )