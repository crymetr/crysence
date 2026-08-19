"""Full-screen privacy cover + a keyboard hook that swallows escape hotkeys.

The cover is NOT a real OS lock (it can be killed via Ctrl+Alt+Del -> Task
Manager, which cannot be blocked). It is strong privacy from a passer-by; for
real security the engine escalates to a Windows lock.
"""

import time
import ctypes
from ctypes import wintypes
import tkinter as tk

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                             wintypes.WPARAM, wintypes.LPARAM)


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC,
                                      wintypes.HINSTANCE, wintypes.DWORD]
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int,
                                   wintypes.WPARAM, wintypes.LPARAM]
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class KeyBlocker:
    """Blocks Win keys, Alt+Tab/Esc/F4, Ctrl+Esc, Ctrl+Shift+Esc while active.
    Ctrl+Alt+Del cannot be blocked. Install from the Tk main thread."""

    def __init__(self):
        self.hook = None
        self._proc = _HOOKPROC(self._cb)

    def _cb(self, nCode, wParam, lParam):
        if nCode == 0 and wParam in (0x100, 0x104):
            vk = ctypes.cast(
                lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents.vkCode
            alt = wParam == 0x104
            ctrl = _user32.GetAsyncKeyState(0x11) & 0x8000
            if (vk in (0x5B, 0x5C) or (alt and vk in (0x09, 0x1B, 0x73))
                    or (ctrl and vk == 0x1B)):
                return 1
        return _user32.CallNextHookEx(None, nCode, wParam, lParam)

    def install(self):
        if not self.hook:
            self.hook = _user32.SetWindowsHookExW(
                13, self._proc, _kernel32.GetModuleHandleW(None), 0)

    def remove(self):
        if self.hook:
            _user32.UnhookWindowsHookEx(self.hook)
            self.hook = None


class Cover:
    def __init__(self, root):
        self.root = root
        self.win = None
        self.blocker = KeyBlocker()

    def show(self):
        if self.win is not None:
            return
        u = _user32
        x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        w, h = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(bg="black")
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(win, text="Locked", fg="#777", bg="black",
                 font=("Segoe UI", 34, "bold")).place(relx=0.5, rely=0.42,
                                                       anchor="center")
        tk.Label(win, text="Look at the camera to unlock", fg="#555",
                 bg="black", font=("Segoe UI", 15)).place(relx=0.5, rely=0.5,
                                                          anchor="center")
        self.clock = tk.Label(win, fg="#444", bg="black",
                              font=("Segoe UI", 13))
        self.clock.place(relx=0.5, rely=0.56, anchor="center")
        self.win = win
        try:
            win.focus_force()
            win.grab_set()
        except Exception:
            pass
        self.blocker.install()
        self._keep()

    def _keep(self):
        if self.win is not None:
            try:
                self.win.lift()
                self.win.attributes("-topmost", True)
                self.clock.config(text=time.strftime("%H:%M:%S"))
            except Exception:
                pass
            self.root.after(1000, self._keep)

    def hide(self):
        self.blocker.remove()
        if self.win is not None:
            try:
                self.win.grab_release()
            except Exception:
                pass
            self.win.destroy()
            self.win = None
