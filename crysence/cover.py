"""Full-screen privacy cover + a keyboard hook that swallows escape hotkeys.

The cover is NOT a real OS lock (it can be killed via Ctrl+Alt+Del -> Task
Manager, which cannot be blocked). It is strong privacy from a passer-by; for
real security the engine escalates to a Windows lock.

Two ways out besides your face:
- Camera lost (webcam unplugged, or its monitor switched off): after
  CAM_LOST_LOCK seconds the cover hands over to the Windows lock screen, so the
  PC is never stuck behind a black screen nobody can lift.
- Hidden hotkey Ctrl+Alt+Shift+U: asks for the emergency-unlock password (set in
  the main window). With no password set it goes straight to the Windows lock.
"""

import time
import ctypes
import threading
from ctypes import wintypes
import tkinter as tk

from . import config, models
from .models import logline

CAM_LOST_LOCK = 6       # seconds without a camera frame before Windows lock
MAX_PW_TRIES = 3        # wrong passwords before Windows lock
HOTKEY_VK = 0x55        # 'U' (with Ctrl+Alt+Shift)

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
_user32.GetKeyState.argtypes = [ctypes.c_int]
_user32.GetKeyState.restype = ctypes.c_short
_user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
_user32.GetKeyboardLayout.restype = ctypes.c_void_p
_user32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT,
                                ctypes.POINTER(ctypes.c_ubyte),
                                wintypes.LPWSTR, ctypes.c_int, wintypes.UINT,
                                ctypes.c_void_p]
_user32.ToUnicodeEx.restype = ctypes.c_int
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE

# Left/right-specific modifier VKs as the low-level hook reports them.
_SHIFT = (0xA0, 0xA1)
_CTRL = (0xA2, 0xA3)
_ALT = (0xA4, 0xA5)


class KeyBlocker:
    """While active, swallows ALL keyboard input so keystrokes can't leak to the
    app focused underneath the cover (e.g. a password typed by reflex). Only
    Ctrl+Alt+Del still works - Windows handles it below any user-mode hook, so
    there is always an escape. Install from the Tk main thread.

    Eaten keys never reach the OS key state, so modifiers are tracked here and
    each key-down is handed to on_key(vk, scan, mods)."""

    def __init__(self, on_key=None):
        self.hook = None
        self.on_key = on_key
        self.mods = set()
        self._proc = _HOOKPROC(self._cb)

    def _cb(self, nCode, wParam, lParam):
        # 0x100/0x101 = key down/up, 0x104/0x105 = syskey down/up
        if nCode == 0 and wParam in (0x100, 0x101, 0x104, 0x105):
            try:
                kb = ctypes.cast(lParam,
                                 ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                vk, down = kb.vkCode, wParam in (0x100, 0x104)
                if vk in _SHIFT + _CTRL + _ALT:
                    (self.mods.add if down else self.mods.discard)(vk)
                elif down and self.on_key:
                    self.on_key(vk, kb.scanCode, frozenset(self.mods))
            except Exception:
                pass
            return 1  # eat every key event while the cover is up
        return _user32.CallNextHookEx(None, nCode, wParam, lParam)

    def install(self):
        if not self.hook:
            self.mods.clear()
            self.hook = _user32.SetWindowsHookExW(
                13, self._proc, _kernel32.GetModuleHandleW(None), 0)

    def remove(self):
        if self.hook:
            _user32.UnhookWindowsHookEx(self.hook)
            self.hook = None


def _key_char(vk, scan, mods):
    """Translate a key-down to text with the user's keyboard layout, using our
    own modifier state (the OS never saw the eaten modifiers)."""
    state = (ctypes.c_ubyte * 256)()
    if mods & set(_SHIFT):
        state[0x10] = 0x80
    if mods & set(_CTRL):
        state[0x11] = 0x80
    if mods & set(_ALT):
        state[0x12] = 0x80
    if 0xA5 in mods:          # AltGr = LCtrl + RAlt
        state[0x11] = state[0x12] = 0x80
    if _user32.GetKeyState(0x14) & 1:
        state[0x14] = 0x01    # Caps Lock toggled
    buf = ctypes.create_unicode_buffer(8)
    n = _user32.ToUnicodeEx(vk, scan, state, buf, 8, 0x4,
                            _user32.GetKeyboardLayout(0))
    return buf.value[:n] if n > 0 else ""


class Cover:
    def __init__(self, root, engine):
        self.root = root
        self.eng = engine
        self.win = None
        self.blocker = KeyBlocker(self._on_key)
        self.geom = None
        self.pw_mode = False
        self.pw_buf = []
        self.pw_fails = 0
        self.checking = False

    def _metrics(self):
        u = _user32
        return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
                u.GetSystemMetrics(78), u.GetSystemMetrics(79))

    def show(self):
        if self.win is not None:
            return
        x, y, w, h = self.geom = self._metrics()
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
        self.pw_lbl = tk.Label(win, text="", fg="#AAA", bg="black",
                               font=("Segoe UI", 16))
        self.pw_lbl.place(relx=0.5, rely=0.66, anchor="center")
        self.win = win
        self.pw_mode = False
        self.pw_buf = []
        self.pw_fails = 0
        try:
            win.focus_force()
            win.grab_set()
        except Exception:
            pass
        self.blocker.install()
        self._keep()

    def _keep(self):
        if self.win is None:
            return
        # Camera gone while covered: hand over to the Windows lock screen
        # rather than leave a black screen only a face could lift.
        if time.time() - self.eng.last_frame_ts >= CAM_LOST_LOCK:
            logline(f"camera lost under cover ({CAM_LOST_LOCK}s) "
                    "-> Windows lock")
            self._windows_lock("camera lost -> Windows lock")
            return
        try:
            g = self._metrics()
            if g != self.geom:    # monitor added/removed/woke up
                self.geom = g
                x, y, w, h = g
                self.win.geometry(f"{w}x{h}+{x}+{y}")
            self.win.lift()
            self.win.attributes("-topmost", True)
            self.clock.config(text=time.strftime("%H:%M:%S"))
        except Exception:
            pass
        self.root.after(1000, self._keep)

    # ---- emergency unlock -------------------------------------------------
    def _on_key(self, vk, scan, mods):
        """Runs inside the hook callback: keep it quick, defer UI work."""
        if not self.pw_mode:
            if (vk == HOTKEY_VK and mods & set(_CTRL) and mods & set(_ALT)
                    and mods & set(_SHIFT)):
                self.root.after(0, self._hotkey)
            return
        if self.checking:
            return
        if vk == 0x0D:                                   # Enter
            self.root.after(0, self._verify)
        elif vk == 0x1B:                                 # Esc
            self.pw_mode = False
            self.pw_buf = []
            self.root.after(0, self._draw_pw)
        elif vk == 0x08:                                 # Backspace
            if self.pw_buf:
                self.pw_buf.pop()
            self.root.after(0, self._draw_pw)
        else:
            ch = _key_char(vk, scan, mods)
            if ch and ch.isprintable() and len(self.pw_buf) < 128:
                self.pw_buf.append(ch)
                self.root.after(0, self._draw_pw)

    def _hotkey(self):
        if self.win is None:
            return
        if not self.eng.cfg["settings"].get("unlock_pw"):
            logline("unlock hotkey, no password set -> Windows lock")
            self._windows_lock("hotkey -> Windows lock")
            return
        self.pw_mode = True
        self.pw_buf = []
        self._draw_pw()

    def _draw_pw(self, note=""):
        if self.win is None:
            return
        if not self.pw_mode:
            self.pw_lbl.config(text="")
            return
        dots = "•" * len(self.pw_buf)
        self.pw_lbl.config(text=f"Password: {dots or ' '}\n"
                                f"{note or 'Enter to unlock  ·  Esc to cancel'}")

    def _verify(self):
        if self.win is None or self.checking:
            return
        pw = "".join(self.pw_buf)
        self.pw_buf = []
        rec = self.eng.cfg["settings"].get("unlock_pw")
        self.checking = True
        self._draw_pw("checking...")

        # PBKDF2 off the Tk thread: a stalled pump makes Windows drop the hook.
        def work():
            ok = config.check_password(rec, pw)
            self.root.after(0, lambda: self._verified(ok))
        threading.Thread(target=work, daemon=True).start()

    def _verified(self, ok):
        self.checking = False
        if self.win is None:
            return
        if ok:
            logline("cover lifted with emergency password")
            self.eng.release_cover("unlocked with password")
            self.hide()
            return
        self.pw_fails += 1
        logline(f"emergency unlock: wrong password ({self.pw_fails})")
        if self.pw_fails >= MAX_PW_TRIES:
            self._windows_lock("wrong password -> Windows lock")
            return
        self._draw_pw(f"Wrong password ({MAX_PW_TRIES - self.pw_fails} "
                      "left)")

    def _windows_lock(self, why):
        # Lock first, then drop the cover: the desktop is never exposed.
        try:
            models.lock_workstation()
        finally:
            self.eng.release_cover(why)
            self.hide()

    def hide(self):
        self.blocker.remove()
        self.pw_mode = False
        self.pw_buf = []
        if self.win is not None:
            try:
                self.win.grab_release()
            except Exception:
                pass
            self.win.destroy()
            self.win = None
