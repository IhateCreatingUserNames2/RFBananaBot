import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import pyautogui
import win32gui
import win32process
import numpy as np
import cv2
from PIL import ImageGrab
import ctypes

# Map named keys to virtual key codes
KEY_MAPPING = {
    '0': 0x30,
    '1': 0x31,
    '2': 0x32,
    '3': 0x33,
    '4': 0x34,
    '5': 0x35,
    '6': 0x36,
    '7': 0x37,
    '8': 0x38,
    '9': 0x39,
    'SPACE': 0x20,
}

# Define the structures needed for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]


def press_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(wVk=hexKeyCode, wScan=0, dwFlags=0, time=0, dwExtraInfo=ctypes.pointer(extra))
    x = Input(type=ctypes.c_ulong(1), ii=ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


def release_key(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(wVk=hexKeyCode, wScan=0, dwFlags=2, time=0, dwExtraInfo=ctypes.pointer(extra))
    x = Input(type=ctypes.c_ulong(1), ii=ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


class SimpleGameBot:
    def __init__(self, hp_region, key_delays):
        self.hp_region = hp_region  # The region where the HP bar is located (left, top, width, height)
        self.key_delays = key_delays
        self.is_running = False
        self.next_press_times = [0] * len(key_delays)

    def capture_hp_bar(self):
        # Ensure coordinates are correctly ordered
        left, top, width, height = self.hp_region
        right = left + width
        bottom = top + height
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame

    def is_mob_dead(self, frame):
        # Check if the HP bar has any red component left
        red_threshold = np.array([0, 0, 150])
        mask = cv2.inRange(frame, red_threshold, np.array([50, 50, 255]))
        red_pixels = np.sum(mask == 255)
        return red_pixels == 0  # No red pixels means the mob is dead

    def target_mob(self):
        pyautogui.press('tab')

    def hit_mob(self):
        current_time = time.time()
        for i, (selected, key, delay) in enumerate(self.key_delays):
            if selected.get() and key.get() != "None" and current_time >= self.next_press_times[i]:
                press_key(KEY_MAPPING[key.get()])
                time.sleep(0.05)
                release_key(KEY_MAPPING[key.get()])
                self.next_press_times[i] = current_time + delay.get()

    def start_bot(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run_bot)
        self.thread.start()

    def stop_bot(self):
        self.is_running = False
        if hasattr(self, 'thread'):
            self.thread.join()

    def run_bot(self):
        while self.is_running:
            self.target_mob()
            time.sleep(0.5)  # Adjust as needed

            while not self.is_mob_dead(self.capture_hp_bar()):
                self.hit_mob()
                time.sleep(0.1)  # Adjust as needed

            time.sleep(0.5)  # Adjust as needed


class RegionSelector:
    def __init__(self, root):
        self.root = root
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.selection_window = tk.Toplevel(root)
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes("-alpha", 0.3)
        self.selection_window.configure(background='black')
        self.canvas = tk.Canvas(self.selection_window, cursor="cross", bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.region = None

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red",
                                                 width=2)

    def on_mouse_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.region = (
            min(self.start_x, end_x), min(self.start_y, end_y), max(self.start_x, end_x), max(self.start_y, end_y))
        self.selection_window.destroy()

    def get_region(self):
        self.selection_window.wait_window()
        if self.region:
            left, top, right, bottom = self.region
            return (left, top, right - left, bottom - top)
        return None


class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Bot")

        self.windows = []
        self.hp_region = None
        self.bot = None
        self.key_delays = [(tk.BooleanVar(), tk.StringVar(value="None"), tk.DoubleVar(value=0)) for _ in range(9)]

        self.create_widgets()
        self.update_window_list()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="10 10 10 10")
        frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(frame, text="Window:").grid(column=1, row=1, sticky=tk.W)
        self.window_var = tk.StringVar()
        self.window_menu = ttk.Combobox(frame, textvariable=self.window_var)
        self.window_menu.grid(column=2, row=1, sticky=(tk.W, tk.E))

        self.add_button = ttk.Button(frame, text="Select HP Bar Area", command=self.select_hp_area)
        self.add_button.grid(column=3, row=1, sticky=tk.W)

        ttk.Label(frame, text="Select").grid(column=0, row=2, sticky=tk.W)
        ttk.Label(frame, text="Key").grid(column=1, row=2, sticky=tk.W)
        ttk.Label(frame, text="Delay (s)").grid(column=2, row=2, sticky=tk.W)

        for i, (selected, key_var, delay_var) in enumerate(self.key_delays):
            ttk.Checkbutton(frame, variable=selected).grid(column=0, row=3 + i, sticky=(tk.W, tk.E))
            ttk.Combobox(frame, textvariable=key_var, values=[str(n) for n in range(10)] + ["SPACE", "None"]).grid(column=1, row=3 + i, sticky=(tk.W, tk.E))
            ttk.Entry(frame, textvariable=delay_var).grid(column=2, row=3 + i, sticky=(tk.W, tk.E))

        self.start_button = ttk.Button(frame, text="Start", command=self.start_bot)
        self.start_button.grid(column=1, row=12, sticky=tk.W)

        self.stop_button = ttk.Button(frame, text="Stop", command=self.stop_bot)
        self.stop_button.grid(column=2, row=12, sticky=tk.W)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=5)

    def update_window_list(self):
        windows = []

        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append(f"{title} (PID: {pid})")

        win32gui.EnumWindows(enum_handler, None)
        self.window_menu['values'] = windows

    def select_hp_area(self):
        selector = RegionSelector(self.root)
        self.hp_region = selector.get_region()
        if self.hp_region:
            messagebox.showinfo("Region Selected", f"Region selected: {self.hp_region}")
        else:
            messagebox.showwarning("Selection Error", "Failed to select region.")

    def start_bot(self):
        if not self.hp_region:
            messagebox.showwarning("Error", "Please select the HP bar area first.")
            return
        window_info = self.window_var.get()
        if not window_info:
            messagebox.showwarning("Error", "Please select a game window.")
            return

        key_delays = [(selected, key, delay) for selected, key, delay in self.key_delays]
        self.bot = SimpleGameBot(self.hp_region, key_delays)
        self.bot.start_bot()

    def stop_bot(self):
        if self.bot:
            self.bot.stop_bot()


if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()
