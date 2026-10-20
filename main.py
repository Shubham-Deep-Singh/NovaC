import os
import json
import cv2
import mediapipe as mp
import pyautogui
import time
import math
import ctypes
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# NovaC - hand gesture computer control with a desktop control panel.
# Python 3.11 is recommended on Windows.

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

SCREEN_W, SCREEN_H = pyautogui.size()
MAX_HANDS = 2
FRAME_MARGIN = 80
PINCH_THRESHOLD = 0.045
CLICK_COOLDOWN = 0.45
VOLUME_MODE_HOLD = 0.8
VOLUME_REPEAT_DELAY = 0.35
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'novac_settings.json')

BG = "#0b1020"
PANEL = "#121a2e"
PANEL_ALT = "#18233b"
ACCENT = "#48d7c7"
TEXT = "#edf3ff"
MUTED = "#9aa8c7"
RED = "#ff657a"
GREEN = "#6ee7a8"


class NovaCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NovaC | Gesture Control")
        self.root.geometry("1180x760")
        self.root.minsize(980, 650)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.frame_queue = queue.Queue(maxsize=1)
        self.worker = None
        self.stop_event = threading.Event()
        self.config_lock = threading.Lock()
        self.config = {
            "mouse_enabled": True,
            "volume_enabled": True,
            "sensitivity": 5,
            "camera_index": 0,
        }
        self._load_settings()
        self.running = False
        self.photo = None
        self.status_var = tk.StringVar(value="Ready to start")
        self.mode_var = tk.StringVar(value="IDLE")
        self.hands_var = tk.StringVar(value="0")
        self.action_var = tk.StringVar(value="Waiting for camera")
        self.mouse_var = tk.BooleanVar(value=bool(self.config.get("mouse_enabled", True)))
        self.volume_var = tk.BooleanVar(value=bool(self.config.get("volume_enabled", True)))
        self.sensitivity_var = tk.IntVar(value=int(self.config.get("sensitivity", 5)))
        self.camera_index_var = tk.IntVar(value=int(self.config.get("camera_index", 0)))
        self.keyboard_preview_var = tk.StringVar(value="")
        self.caps_lock = False
        self.keyboard_window = None
        self.keyboard_target_hwnd = None
        self.keyboard_target_label = None

        self._style()
        self._build_ui()
        self._sync_config()
        self.root.after(30, self._poll_frames)

    def _load_settings(self):
        try:
            if os.path.isfile(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key in ("mouse_enabled", "volume_enabled", "sensitivity", "camera_index"):
                    if key in saved:
                        self.config[key] = saved[key]
        except (OSError, ValueError, TypeError):
            pass

    def _save_settings(self):
        try:
            self.config["camera_index"] = max(0, min(5, int(self.camera_index_var.get())))
            self.config["sensitivity"] = max(1, min(10, int(self.sensitivity_var.get())))
            self.config["mouse_enabled"] = bool(self.mouse_var.get())
            self.config["volume_enabled"] = bool(self.volume_var.get())
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self.status_var.set("Settings saved.")
        except Exception as exc:
            self.status_var.set(f"Could not save settings: {exc}")

    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Nova.Horizontal.TScale", background=PANEL, troughcolor=PANEL_ALT)
        style.configure("Nova.TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.map("Nova.TCheckbutton", background=[("active", PANEL)])
        style.configure("Nova.TButton", font=("Segoe UI Semibold", 10), padding=(14, 10))
        style.configure("Start.TButton", background=ACCENT, foreground="#07131d")
        style.map("Start.TButton", background=[("active", "#72f0df")])
        style.configure("Stop.TButton", background="#293650", foreground=TEXT)
        style.map("Stop.TButton", background=[("active", "#3b4b6c")])

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=26, pady=(20, 14))
        logo = tk.Frame(header, bg=ACCENT, width=48, height=48)
        logo.pack(side="left")
        logo.pack_propagate(False)
        tk.Label(logo, text="N", bg=ACCENT, fg="#07131d",
                 font=("Segoe UI Black", 24)).pack(expand=True)
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", padx=13)
        tk.Label(brand, text="NovaC", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(brand, text="GESTURE CONTROL CENTER", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.running_badge = tk.Label(header, text="●  SYSTEM IDLE", bg=PANEL_ALT, fg=MUTED,
                                      font=("Segoe UI", 9, "bold"), padx=13, pady=8)
        self.running_badge.pack(side="right", pady=5)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=26, pady=(0, 22))
        body.columnconfigure(0, weight=7)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        preview_card = tk.Frame(body, bg=PANEL, highlightbackground="#263450", highlightthickness=1)
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        preview_card.rowconfigure(1, weight=1)
        preview_card.columnconfigure(0, weight=1)
        tk.Label(preview_card, text="LIVE CAMERA", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 10))
        self.preview = tk.Label(preview_card, bg="#050914", fg=MUTED,
                                text="Camera preview will appear here\n\nPress  START TRACKING  to begin",
                                font=("Segoe UI", 12), justify="center")
        self.preview.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        preview_footer = tk.Frame(preview_card, bg=PANEL)
        preview_footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 15))
        tk.Label(preview_footer, text="Tip: keep your hand inside the camera frame.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(preview_footer, text="Q / ESC emergency exit in camera mode is replaced by Stop here",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")

        side = tk.Frame(body, bg=BG)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        controls = tk.Frame(side, bg=PANEL, highlightbackground="#263450", highlightthickness=1)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tk.Label(controls, text="CONTROLS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=18, pady=(16, 12))
        btn_row = tk.Frame(controls, bg=PANEL)
        btn_row.pack(fill="x", padx=16)
        self.start_btn = ttk.Button(btn_row, text="▶  Start tracking", style="Start.TButton",
                                    command=self.start_tracking)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.stop_btn = ttk.Button(btn_row, text="■  Stop", style="Stop.TButton",
                                   command=self.stop_tracking, state="disabled")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))
        keyboard_btn = ttk.Button(controls, text="⌨  Open floating keyboard",
                                  style="Stop.TButton", command=self.open_keyboard)
        keyboard_btn.pack(fill="x", padx=16, pady=(10, 0))
        media_row = tk.Frame(controls, bg=PANEL)
        media_row.pack(fill="x", padx=16, pady=(8, 0))
        for label, key in [("⏮ Previous", "prevtrack"), ("▶/Ⅱ Play/Pause", "playpause"), ("Next ⏭", "nexttrack")]:
            tk.Button(media_row, text=label, command=lambda k=key: self._media_key(k),
                      bg=PANEL_ALT, fg=TEXT, activebackground="#2b3d5e",
                      activeforeground=TEXT, relief="flat", padx=7, pady=6,
                      font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True, padx=2)
        tk.Frame(controls, bg="#263450", height=1).pack(fill="x", padx=18, pady=16)

        self._toggle_row(controls, "Virtual mouse + clicks", self.mouse_var,
                         "Move index finger; pinch thumb + index to left-click; thumb + middle to right-click.")
        self._toggle_row(controls, "Volume gestures", self.volume_var,
                         "Hold open palm to enter volume mode; make a fist to return to mouse mode.")
        tk.Label(controls, text="MOUSE SENSITIVITY", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(12, 2))
        sensitivity_row = tk.Frame(controls, bg=PANEL)
        sensitivity_row.pack(fill="x", padx=16, pady=(0, 16))
        self.sensitivity_label = tk.Label(sensitivity_row, text="5 / 10", bg=PANEL, fg=ACCENT,
                                          font=("Segoe UI Semibold", 9))
        self.sensitivity_label.pack(side="right")
        scale = ttk.Scale(sensitivity_row, from_=1, to=10, orient="horizontal",
                          command=self._on_sensitivity, style="Nova.Horizontal.TScale")
        scale.set(5)
        scale.pack(side="left", fill="x", expand=True, padx=(0, 12))
        camera_row = tk.Frame(controls, bg=PANEL)
        camera_row.pack(fill="x", padx=18, pady=(0, 14))
        tk.Label(camera_row, text="CAMERA INDEX", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Spinbox(camera_row, from_=0, to=5, width=4, textvariable=self.camera_index_var,
                   command=self._save_settings, bg=PANEL_ALT, fg=TEXT,
                   buttonbackground=PANEL_ALT, relief="flat").pack(side="right")
        tk.Button(camera_row, text="Save settings", command=self._save_settings,
                  bg=PANEL_ALT, fg=TEXT, activebackground="#2b3d5e",
                  activeforeground=TEXT, relief="flat", padx=8, pady=4,
                  font=("Segoe UI", 8)).pack(side="right", padx=8)

        status = tk.Frame(side, bg=PANEL, highlightbackground="#263450", highlightthickness=1)
        status.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        tk.Label(status, text="LIVE STATUS", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=18, pady=(15, 10))
        stats = tk.Frame(status, bg=PANEL)
        stats.pack(fill="x", padx=18)
        self._stat(stats, "CURRENT MODE", self.mode_var, 0)
        self._stat(stats, "HANDS DETECTED", self.hands_var, 1)
        self._stat(stats, "LAST ACTION", self.action_var, 2)
        tk.Label(status, textvariable=self.status_var, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9), wraplength=300, justify="left").pack(anchor="w", padx=18, pady=(10, 15))

        guide = tk.Frame(side, bg=PANEL, highlightbackground="#263450", highlightthickness=1)
        guide.grid(row=2, column=0, sticky="ew")
        tk.Label(guide, text="GESTURE QUICK GUIDE", bg=PANEL, fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=18, pady=(15, 9))
        for title, detail in [
            ("MOVE", "Raise index finger and move your hand."),
            ("LEFT CLICK", "Brief thumb + index fingertip pinch."),
            ("RIGHT CLICK", "Brief thumb + middle fingertip pinch."),
            ("VOLUME MODE", "Hold an open palm for about 0.8 seconds."),
            ("EXIT VOLUME MODE", "Make a fist."),
        ]:
            row = tk.Frame(guide, bg=PANEL)
            row.pack(fill="x", padx=18, pady=3)
            tk.Label(row, text=title, bg=PANEL, fg=ACCENT, width=13, anchor="w",
                     font=("Segoe UI Semibold", 8)).pack(side="left")
            tk.Label(row, text=detail, bg=PANEL, fg=MUTED, anchor="w", justify="left",
                     wraplength=220, font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)
        tk.Label(guide, text="Safety: PyAutoGUI stops if you move the cursor to the top-left corner.",
                 bg=PANEL, fg="#f5b96c", font=("Segoe UI", 8), wraplength=310,
                 justify="left").pack(anchor="w", padx=18, pady=(10, 14))

    def _toggle_row(self, parent, title, variable, description):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=18, pady=(0, 5))
        ttk.Checkbutton(row, text=title, variable=variable, style="Nova.TCheckbutton",
                        command=self._sync_config).pack(anchor="w")
        tk.Label(parent, text=description, bg=PANEL, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=330, justify="left").pack(anchor="w", padx=42, pady=(0, 8))

    def _stat(self, parent, label, variable, row):
        line = tk.Frame(parent, bg=PANEL)
        line.pack(fill="x", pady=4)
        tk.Label(line, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(line, textvariable=variable, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI Semibold", 9)).pack(side="right")

    def _sync_config(self):
        with self.config_lock:
            self.config["mouse_enabled"] = bool(self.mouse_var.get())
            self.config["volume_enabled"] = bool(self.volume_var.get())
        self._save_settings()

    def _on_sensitivity(self, value):
        val = int(float(value))
        self.sensitivity_label.config(text=f"{val} / 10")
        with self.config_lock:
            self.config["sensitivity"] = val
        self._save_settings()

    def _media_key(self, key):
        try:
            pyautogui.press(key)
            self.action_var.set({"prevtrack": "Previous track", "playpause": "Play/Pause",
                                 "nexttrack": "Next track"}.get(key, key))
        except Exception as exc:
            self.status_var.set(f"Media control error: {exc}")

    def start_tracking(self):
        if self.running:
            return
        self.stop_event.clear()
        self.worker = threading.Thread(target=self._camera_worker, daemon=True)
        self.running = True
        self.worker.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.running_badge.config(text="●  TRACKING ACTIVE", bg="#143c3a", fg=ACCENT)
        self.status_var.set("Starting camera…")

    def stop_tracking(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running_badge.config(text="●  STOPPING", bg=PANEL_ALT, fg=MUTED)
        self.status_var.set("Stopping camera…")
        self.root.after(100, self._finish_stop)

    def _finish_stop(self):
        if self.worker and self.worker.is_alive():
            self.root.after(100, self._finish_stop)
            return
        self.running = False
        self.worker = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.running_badge.config(text="●  SYSTEM IDLE", bg=PANEL_ALT, fg=MUTED)
        self.mode_var.set("IDLE")
        self.hands_var.set("0")
        self.action_var.set("Stopped")
        self.status_var.set("Tracking stopped. Press Start tracking when ready.")
        self.preview.config(image="", text="Camera preview stopped\n\nPress  START TRACKING  to begin")
        self.photo = None

    def _camera_worker(self):
        camera_index = max(0, min(5, int(self.camera_index_var.get())))
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self._put_frame(None, "ERROR: Could not open webcam. Close other camera apps and try again.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=MAX_HANDS,
            model_complexity=0,
            min_detection_confidence=0.65,
            min_tracking_confidence=0.6,
        )
        last_x, last_y = pyautogui.position()
        smooth_x, smooth_y = last_x, last_y
        last_click_time = 0
        last_volume_time = 0
        open_palm_start = None
        volume_mode = False
        pinch_start_time = None
        drag_active = False
        drag_candidate = False
        scroll_last_y = None
        last_scroll_time = 0
        action = "Ready"
        status = "Show your hand to the camera"
        try:
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    status = "Camera frame unavailable"
                    time.sleep(0.03)
                    continue
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)
                hand_count = len(result.multi_hand_landmarks) if result.multi_hand_landmarks else 0
                with self.config_lock:
                    cfg = dict(self.config)
                mouse_enabled = cfg["mouse_enabled"]
                volume_enabled = cfg["volume_enabled"]
                sensitivity = cfg["sensitivity"]

                cv2.rectangle(frame, (12, 12), (w - 12, 58), (18, 27, 48), -1)
                mode_label = "VOLUME MODE" if volume_mode else "MOUSE MODE"
                cv2.putText(frame, mode_label, (28, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                            (72, 215, 199) if volume_mode else (235, 243, 255), 2)

                if result.multi_hand_landmarks:
                    # Use the first detected hand for controls; draw all detected hands.
                    for landmarks in result.multi_hand_landmarks:
                        mp_draw.draw_landmarks(frame, landmarks, mp_hands.HAND_CONNECTIONS)
                    lm = result.multi_hand_landmarks[0].landmark
                    def point(index):
                        return (int(lm[index].x * w), int(lm[index].y * h))
                    thumb = point(4)
                    index_tip = point(8)
                    middle_tip = point(12)
                    ring_tip = point(16)
                    pinky_tip = point(20)
                    wrist = point(0)
                    index_pip = point(6)
                    middle_pip = point(10)
                    ring_pip = point(14)
                    pinky_pip = point(18)
                    thumb_index_gap = math.dist(lm[4].x_y if hasattr(lm[4], "x_y") else (lm[4].x, lm[4].y),
                                                 (lm[8].x, lm[8].y))
                    thumb_middle_gap = math.dist((lm[4].x, lm[4].y), (lm[12].x, lm[12].y))
                    fingers_up = [
                        lm[8].y < lm[6].y,
                        lm[12].y < lm[10].y,
                        lm[16].y < lm[14].y,
                        lm[20].y < lm[18].y,
                    ]
                    open_palm = all(fingers_up)
                    fist = not any(fingers_up)

                    if volume_enabled and not volume_mode:
                        if open_palm:
                            if open_palm_start is None:
                                open_palm_start = time.time()
                            elif time.time() - open_palm_start >= VOLUME_MODE_HOLD:
                                volume_mode = True
                                open_palm_start = None
                                action = "Volume mode on"
                        else:
                            open_palm_start = None
                    elif not volume_enabled:
                        volume_mode = False
                        open_palm_start = None

                    if volume_mode and fist:
                        volume_mode = False
                        action = "Mouse mode on"
                        last_volume_time = 0

                    if volume_mode and volume_enabled:
                        gap = thumb_index_gap
                        cv2.line(frame, thumb, index_tip, (72, 215, 199), 3)
                        cv2.circle(frame, thumb, 8, (72, 215, 199), -1)
                        cv2.circle(frame, index_tip, 8, (72, 215, 199), -1)
                        if time.time() - last_volume_time >= VOLUME_REPEAT_DELAY:
                            if gap < 0.075:
                                pyautogui.press("volumedown")
                                action = "Volume down"
                                last_volume_time = time.time()
                            elif gap > 0.22:
                                pyautogui.press("volumeup")
                                action = "Volume up"
                                last_volume_time = time.time()
                        status = "Volume mode: close fingers = down, spread fingers = up; fist exits."
                    else:
                        now = time.time()
                        # Map the useful central camera area to the full screen.
                        margin = 0.04
                        norm_x = (lm[8].x - margin) / (1.0 - 2.0 * margin)
                        norm_y = (lm[8].y - margin) / (1.0 - 2.0 * margin)
                        norm_x = max(0.0, min(1.0, norm_x))
                        norm_y = max(0.0, min(1.0, norm_y))
                        target_x = norm_x * (SCREEN_W - 1)
                        target_y = norm_y * (SCREEN_H - 1)
                        alpha = 0.25 + (sensitivity / 10.0) * 0.45
                        smooth_x = smooth_x + (target_x - smooth_x) * alpha
                        smooth_y = smooth_y + (target_y - smooth_y) * alpha

                        if mouse_enabled:
                            try:
                                pyautogui.moveTo(
                                    max(1, min(SCREEN_W - 2, int(smooth_x))),
                                    max(1, min(SCREEN_H - 2, int(smooth_y))),
                                    _pause=False
                                )
                            except pyautogui.FailSafeException:
                                status = "Emergency stop triggered (cursor reached top-left corner)."
                                self.stop_event.set()
                            except Exception as exc:
                                status = f"Mouse movement error: {exc}"

                            # Drag: hold thumb+index pinch for 0.35 seconds.
                            # A short pinch becomes a normal left click on release.
                            left_pinched = thumb_index_gap < PINCH_THRESHOLD
                            if left_pinched:
                                if pinch_start_time is None:
                                    pinch_start_time = now
                                    drag_candidate = True
                                elif drag_candidate and not drag_active and now - pinch_start_time >= 0.35:
                                    pyautogui.mouseDown()
                                    drag_active = True
                                    action = "Drag started"
                                if drag_active:
                                    action = "Dragging"
                            else:
                                if drag_active:
                                    pyautogui.mouseUp()
                                    action = "Drag released"
                                    drag_active = False
                                    drag_candidate = False
                                    last_click_time = now
                                elif drag_candidate and pinch_start_time is not None:
                                    if now - pinch_start_time < 0.35 and now - last_click_time > CLICK_COOLDOWN:
                                        pyautogui.click()
                                        action = "Left click"
                                        last_click_time = now
                                    drag_candidate = False
                                pinch_start_time = None

                            # Right click is a separate thumb + middle pinch.
                            if (thumb_middle_gap < PINCH_THRESHOLD
                                    and not left_pinched
                                    and now - last_click_time > CLICK_COOLDOWN
                                    and not drag_active):
                                pyautogui.rightClick()
                                action = "Right click"
                                last_click_time = now

                            # Scroll: raise index + middle fingers while ring + pinky stay down.
                            scrolling_pose = (
                                fingers_up[0] and fingers_up[1]
                                and not fingers_up[2] and not fingers_up[3]
                                and thumb_index_gap > PINCH_THRESHOLD * 1.4
                            )
                            if scrolling_pose:
                                current_y = (lm[8].y + lm[12].y) / 2
                                if scroll_last_y is not None and now - last_scroll_time >= 0.045:
                                    delta = scroll_last_y - current_y
                                    if abs(delta) > 0.008:
                                        amount = max(1, min(5, int(abs(delta) * 180)))
                                        pyautogui.scroll(amount if delta > 0 else -amount)
                                        action = "Scroll up" if delta > 0 else "Scroll down"
                                        last_scroll_time = now
                                scroll_last_y = current_y
                                status = "Scroll mode: raise index + middle fingers; move hand up/down."
                            else:
                                scroll_last_y = None
                                status = "Mouse mode: move index; pinch to click/hold to drag; two fingers to scroll."
                            cv2.circle(frame, index_tip, 9, (72, 215, 199), 2)
                            cv2.putText(frame, f"MOUSE: ON | sensitivity {sensitivity}/10",
                                        (28, 116), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (72, 215, 199), 2)
                            if drag_active:
                                cv2.putText(frame, "DRAGGING", (w - 180, 42),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (72, 215, 199), 2)
                        else:
                            # Release a held mouse button if the mouse feature is disabled mid-drag.
                            if drag_active:
                                pyautogui.mouseUp()
                            drag_active = False
                            drag_candidate = False
                            pinch_start_time = None
                            scroll_last_y = None
                            cv2.putText(frame, "MOUSE: OFF", (28, 116),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (150, 160, 180), 2)
                            status = "Mouse control is disabled in the panel."

                        if volume_enabled and not volume_mode:
                            status = status + " Open palm enters volume mode."
                    cv2.putText(frame, f"Hands: {hand_count}", (28, 88), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (235, 243, 255), 2)
                else:
                    open_palm_start = None
                    status = "No hand detected - show your hand clearly"
                    if volume_mode:
                        # Do not unexpectedly leave volume mode just because tracking briefly drops.
                        pass

                self._put_frame(frame, status, mode_label, hand_count, action)
        except pyautogui.FailSafeException:
            self._put_frame(None, "Emergency stop triggered: cursor reached the top-left corner.")
        except Exception as exc:
            self._put_frame(None, f"Tracking error: {exc}")
        finally:
            try:
                if drag_active:
                    pyautogui.mouseUp()
            except Exception:
                pass
            hands.close()
            cap.release()
            self._put_frame(None, "Camera stopped")

    def _put_frame(self, frame, status, mode=None, hand_count=0, action=""):
        try:
            while True:
                self.frame_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self.frame_queue.put_nowait((frame, status, mode, hand_count, action))
        except queue.Full:
            pass

    def _poll_frames(self):
        try:
            while True:
                frame, status, mode, hand_count, action = self.frame_queue.get_nowait()
                self.status_var.set(status)
                if mode:
                    self.mode_var.set(mode.replace(" MODE", ""))
                self.hands_var.set(str(hand_count))
                if action:
                    self.action_var.set(action)
                if frame is None:
                    if status.startswith("ERROR") or status.startswith("Tracking error") or status.startswith("Emergency"):
                        self.running_badge.config(text="●  ATTENTION", bg="#482330", fg=RED)
                        self.status_var.set(status)
                    continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame_rgb)
                box_w = max(320, self.preview.winfo_width())
                box_h = max(240, self.preview.winfo_height())
                image.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(image)
                self.preview.config(image=self.photo, text="")
        except queue.Empty:
            pass
        self.root.after(30, self._poll_frames)


    def open_keyboard(self):
        """Open an always-on-top virtual keyboard. Gesture clicks can press its keys."""
        if self.keyboard_window is not None and self.keyboard_window.winfo_exists():
            self.keyboard_window.deiconify()
            self.keyboard_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.keyboard_window = win
        win.title("NovaC | Floating Keyboard")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.geometry("920x510+180+380")
        win.protocol("WM_DELETE_WINDOW", self.close_keyboard)

        top = tk.Frame(win, bg=PANEL)
        top.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(top, text="NovaC Keyboard", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI Semibold", 13)).pack(side="left", padx=8, pady=8)
        tk.Button(top, text="Select typing window", command=self.select_keyboard_target,
                  bg=PANEL_ALT, fg=TEXT, activebackground="#2b3d5e",
                  activeforeground=TEXT, relief="flat", padx=10, pady=6,
                  font=("Segoe UI", 9)).pack(side="right", padx=5)
        tk.Button(top, text="×", command=self.close_keyboard,
                  bg="#482330", fg=TEXT, activebackground="#663044",
                  relief="flat", font=("Segoe UI", 12, "bold"), width=3).pack(side="right", padx=5)
        self.keyboard_target_label = tk.Label(
            win, text="Target: not selected — click Select typing window",
            bg=BG, fg=MUTED, font=("Segoe UI", 8)
        )
        self.keyboard_target_label.pack(anchor="w", padx=18, pady=(0, 5))
        preview_bar = tk.Frame(win, bg=PANEL_ALT)
        preview_bar.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(preview_bar, text="TYPING PREVIEW", bg=PANEL_ALT, fg=ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=8, pady=6)
        tk.Label(preview_bar, textvariable=self.keyboard_preview_var, bg=PANEL_ALT, fg=TEXT,
                 font=("Consolas", 10), anchor="w").pack(side="left", fill="x", expand=True, padx=4, pady=6)

        keys_area = tk.Frame(win, bg=BG)
        keys_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.keyboard_layout = tk.StringVar(value="letters")
        layout_bar = tk.Frame(keys_area, bg=BG)
        layout_bar.pack(fill="x", pady=(0, 4))
        for label, value in [("ABC", "letters"), ("Symbols", "symbols"), ("Number pad", "numpad")]:
            tk.Button(layout_bar, text=label, command=lambda v=value: self._render_keyboard_layout(v),
                      bg=PANEL_ALT, fg=TEXT, activebackground="#35665f",
                      relief="flat", padx=12, pady=5, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.caps_lock = False
        self.caps_button = tk.Button(layout_bar, text="Caps Lock: OFF", command=self._toggle_caps,
                                     bg=PANEL_ALT, fg=TEXT, activebackground="#35665f",
                                     relief="flat", padx=12, pady=5, font=("Segoe UI", 9))
        self.caps_button.pack(side="right")
        self.keyboard_keys_frame = tk.Frame(keys_area, bg=BG)
        self.keyboard_keys_frame.pack(fill="both", expand=True)
        self._render_keyboard_layout("letters")

        footer = tk.Label(win,
            text="Point the cursor at a key and pinch to press it. Select the destination app first.",
            bg=BG, fg=MUTED, font=("Segoe UI", 8))
        footer.pack(anchor="w", padx=18, pady=(0, 8))
        win.lift()

    def _toggle_caps(self):
        self.caps_lock = not self.caps_lock
        if self.caps_button and self.caps_button.winfo_exists():
            self.caps_button.config(
                text=f"Caps Lock: {'ON' if self.caps_lock else 'OFF'}",
                bg="#20534f" if self.caps_lock else PANEL_ALT
            )

    def _render_keyboard_layout(self, layout):
        self.keyboard_layout.set(layout)
        for child in self.keyboard_keys_frame.winfo_children():
            child.destroy()
        if layout == "letters":
            rows = [
                [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"),
                 ("6", "6"), ("7", "7"), ("8", "8"), ("9", "9"), ("0", "0"),
                 ("⌫", "BACKSPACE")],
                [(c.upper(), c) for c in "qwertyuiop"],
                [(c.upper(), c) for c in "asdfghjkl"] + [("↵", "ENTER")],
                [("Tab", "TAB"), ("⇧", "SHIFT")] + [(c.upper(), c) for c in "zxcvbnm"] + [(",", ","), (".", ".")],
                [("= / +", "="), ("- / _", "-"), ("@ ", "@"), ("Space", "SPACE"),
                 ("' ", "'"), ("←", "LEFT"), ("→", "RIGHT")]
            ]
        elif layout == "symbols":
            rows = [
                [("!", "!"), ("@", "@"), ("#", "#"), ("$", "$"), ("%", "%"),
                 ("^", "^"), ("&", "&"), ("*", "*"), ("(", "("), (")", ")")],
                [("_", "_"), ("+", "+"), ("{", "{"), ("}", "}"), ("|", "|"),
                 (":", ":"), ('"', '"'), ("<", "<"), (">", ">"), ("?", "?")],
                [("~", "~"), ("`", "`"), ("[", "["), ("]", "]"), ("\\\\", "\\\\"),
                 (";", ";"), ("'", "'"), (",", ","), (".", "."), ("/", "/")],
                [("Space", "SPACE"), ("⌫", "BACKSPACE"), ("↵", "ENTER")]
            ]
        else:
            rows = [
                [("7", "7"), ("8", "8"), ("9", "9")],
                [("4", "4"), ("5", "5"), ("6", "6")],
                [("1", "1"), ("2", "2"), ("3", "3")],
                [("0", "0"), (".", "."), ("↵", "ENTER"), ("⌫", "BACKSPACE")]
            ]
        for row_keys in rows:
            row_frame = tk.Frame(self.keyboard_keys_frame, bg=BG)
            row_frame.pack(fill="x", pady=2, expand=True)
            for label, value in row_keys:
                wide = value in ("BACKSPACE", "ENTER", "SHIFT", "TAB", "SPACE", "LEFT", "RIGHT")
                button = tk.Button(
                    row_frame, text=label, command=lambda v=value: self._keyboard_press(v),
                    bg="#26334a" if not wide else "#20534f", fg=TEXT,
                    activebackground="#35665f", activeforeground="#ffffff",
                    relief="flat", bd=0, font=("Segoe UI Semibold", 10),
                    padx=7, pady=7, takefocus=False
                )
                button.pack(side="left", fill="both", expand=True, padx=2)

    def select_keyboard_target(self):
        """Hide the keyboard briefly so the user can focus the destination application."""
        win = self.keyboard_window
        if win is None or not win.winfo_exists():
            return
        win.withdraw()
        self.status_var.set("Select the app/text field you want to type into. Capturing in 3 seconds…")
        self.root.after(3000, self._capture_keyboard_target)

    def _capture_keyboard_target(self):
        # Capture the currently foreground Windows window after the keyboard is hidden.
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                self.keyboard_target_hwnd = hwnd
                title_buf = ctypes.create_unicode_buffer(512)
                ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, 512)
                title = title_buf.value.strip() or "Selected application"
                if self.keyboard_target_label and self.keyboard_target_label.winfo_exists():
                    self.keyboard_target_label.config(text=f"Target: {title[:55]}", fg=ACCENT)
                self.status_var.set(f"Typing target selected: {title[:80]}")
        except Exception as exc:
            self.status_var.set(f"Could not select typing target: {exc}")
        if self.keyboard_window is not None and self.keyboard_window.winfo_exists():
            self.keyboard_window.deiconify()
            self.keyboard_window.lift()
            self.keyboard_window.attributes("-topmost", True)

    def _keyboard_press(self, key):
        """Send a key to the selected application, then keep NovaC keyboard visible."""
        try:
            if key == "SHIFT":
                # Toggle one-shot capitalization for the next letter.
                self._shift_once = not getattr(self, "_shift_once", False)
                if self.keyboard_target_label and self.keyboard_target_label.winfo_exists():
                    self.keyboard_target_label.config(
                        text=("Target selected • SHIFT on" if self._shift_once else "Target selected"),
                        fg=ACCENT
                    )
                return
            if self.keyboard_target_hwnd:
                ctypes.windll.user32.SetForegroundWindow(self.keyboard_target_hwnd)
                time.sleep(0.04)
            if key == "BACKSPACE":
                pyautogui.press("backspace")
            elif key == "ENTER":
                pyautogui.press("enter")
            elif key == "TAB":
                pyautogui.press("tab")
            elif key == "SPACE":
                pyautogui.press("space")
            elif key == "LEFT":
                pyautogui.press("left")
            elif key == "RIGHT":
                pyautogui.press("right")
            else:
                char = key
                if len(char) == 1 and char.isalpha():
                    shift_once = getattr(self, "_shift_once", False)
                    if self.caps_lock ^ shift_once:
                        char = char.upper()
                    self._shift_once = False
                pyautogui.write(char, interval=0)
            if key == "BACKSPACE":
                self.keyboard_preview_var.set(self.keyboard_preview_var.get()[:-1])
            elif key == "SPACE":
                self.keyboard_preview_var.set((self.keyboard_preview_var.get() + " ")[-80:])
            elif key == "ENTER":
                self.keyboard_preview_var.set((self.keyboard_preview_var.get() + "\\n")[-80:])
            elif key not in ("TAB", "LEFT", "RIGHT", "SHIFT") and len(key) == 1:
                preview_char = key.upper() if (key.isalpha() and (getattr(self, "caps_lock", False) ^ getattr(self, "_shift_once", False))) else key
                self.keyboard_preview_var.set((self.keyboard_preview_var.get() + preview_char)[-80:])
            if self.keyboard_window is not None and self.keyboard_window.winfo_exists():
                self.keyboard_window.lift()
                self.keyboard_window.attributes("-topmost", True)
        except Exception as exc:
            self.status_var.set(f"Keyboard input error: {exc}")

    def close_keyboard(self):
        if self.keyboard_window is not None and self.keyboard_window.winfo_exists():
            self.keyboard_window.destroy()
        self.keyboard_window = None
        self.keyboard_target_label = None

    def on_close(self):
        self.close_keyboard()
        self.stop_event.set()
        self.root.after(100, self._close_when_stopped)

    def _close_when_stopped(self):
        if self.worker and self.worker.is_alive():
            self.root.after(100, self._close_when_stopped)
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NovaCApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
