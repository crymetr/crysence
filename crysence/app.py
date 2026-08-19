"""Tray application entry point: engine + modern window + first-run wizard."""

import sys
import time
import ctypes
import threading

import customtkinter as ctk
import pystray
from pystray import Menu, MenuItem
from PIL import Image, ImageDraw

from . import ui  # noqa: F401  (sets appearance mode)
from . import updater
from .engine import Engine
from .gui import MainWindow
from .cover import Cover
from .wizard import Wizard
from .models import logline

_ICON_COLORS = {"idle": (120, 120, 120), "guard": (45, 212, 191),
                "paused": (224, 163, 46), "alert": (229, 72, 77),
                "enroll": (91, 141, 239)}
_MUTEX_NAME = "CrySence-singleton-5DA096C7-0D55-4077-B2E5-FFAAF55E246D"


def make_icon(state):
    img = Image.new("RGB", (64, 64), (22, 24, 29))
    d = ImageDraw.Draw(img)
    d.ellipse((12, 12, 52, 52), fill=_ICON_COLORS.get(state, (120, 120, 120)))
    return img


def _acquire_single_instance():
    """Named mutex; returns the handle (keep it alive) or None if already up."""
    k32 = ctypes.windll.kernel32
    handle = k32.CreateMutexW(None, False, _MUTEX_NAME)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def main():
    lock = _acquire_single_instance()
    if lock is None:
        logline("another instance is already running - exiting")
        ctypes.windll.user32.MessageBoxW(
            0, "CrySence is already running (see the system tray).",
            "CrySence", 0x40)
        return

    root = ctk.CTk()
    root.withdraw()
    engine = Engine()
    cover = Cover(root)
    state = {"wizard": None}

    def ui_call(fn):
        root.after(0, fn)

    def run_wizard():
        if state["wizard"] and state["wizard"].top.winfo_exists():
            state["wizard"].top.lift()
            return
        state["wizard"] = Wizard(root, engine, on_wizard_done)

    window = MainWindow(root, engine, on_run_wizard=run_wizard)

    def on_wizard_done(started):
        state["wizard"] = None
        if "--hidden" not in sys.argv:
            window.show()

    def set_icon(s):
        try:
            icon.icon = make_icon(s)
        except Exception:
            pass

    # Engine runs on its own thread; hop to the main thread for the tray update.
    engine.on_state = lambda s: ui_call(lambda: set_icon(s))
    engine.on_cover = lambda showing: root.after(
        0, (cover.show if showing else cover.hide))

    def reassert_icon():
        # Idempotent re-assert: an update issued before the tray window existed
        # would otherwise be lost, leaving the icon color stale.
        set_icon(engine.state)
        root.after(3000, reassert_icon)

    def toggle_guard():
        if not engine.guarding and engine.owner_feats is None:
            ui_call(run_wizard)
            return
        engine.guarding = not engine.guarding
        engine.last_seen = time.time()
        engine.save()
        logline("guarding " + ("started" if engine.guarding else "stopped")
                + " (tray)")

    icon = pystray.Icon(
        "CrySence", make_icon("idle"), "CrySence",
        menu=Menu(
            MenuItem("Guarding", lambda i, it: toggle_guard(),
                     checked=lambda it: engine.guarding),
            MenuItem("Pause", lambda i, it: setattr(
                engine, "manual_pause", not engine.manual_pause),
                     checked=lambda it: engine.manual_pause),
            MenuItem("Open window", lambda i, it: ui_call(window.show),
                     default=True),
            MenuItem("Setup wizard", lambda i, it: ui_call(run_wizard)),
            MenuItem("Quit", lambda i, it: (engine.stop(), i.stop(),
                                            ui_call(root.destroy))),
        ))
    engine.start()
    threading.Thread(target=icon.run, daemon=True).start()
    root.after(1500, reassert_icon)
    logline("app started")
    updater.check_in_background()  # signed auto-update (frozen builds only)

    if not engine.cfg["settings"].get("configured"):
        root.after(400, run_wizard)
    elif "--hidden" not in sys.argv:
        root.after(300, window.show)

    root.mainloop()


if __name__ == "__main__":
    main()
