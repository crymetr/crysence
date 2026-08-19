"""Tray application entry point: engine + modern window + first-run wizard."""

import sys
import time
import socket
import threading

import customtkinter as ctk
import pystray
from pystray import Menu, MenuItem
from PIL import Image, ImageDraw

from . import ui  # noqa: F401  (sets appearance mode)
from .engine import Engine
from .gui import MainWindow
from .cover import Cover
from .wizard import Wizard
from .models import logline

_ICON_COLORS = {"idle": (120, 120, 120), "guard": (45, 212, 191),
                "paused": (224, 163, 46), "alert": (229, 72, 77),
                "enroll": (91, 141, 239)}


def make_icon(state):
    img = Image.new("RGB", (64, 64), (22, 24, 29))
    d = ImageDraw.Draw(img)
    d.ellipse((12, 12, 52, 52), fill=_ICON_COLORS.get(state, (120, 120, 120)))
    return img


def _single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 50573))
        s.listen(1)
        return s
    except OSError:
        return None


def main():
    lock = _single_instance()
    if lock is None:
        logline("another instance is already running - exiting")
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

    def on_state(s):
        try:
            icon.icon = make_icon(s)
        except Exception:
            pass

    def on_cover(showing):
        root.after(0, (cover.show if showing else cover.hide))
    engine.on_cover = on_cover

    icon = pystray.Icon(
        "CrySence", make_icon("idle"), "CrySence",
        menu=Menu(
            MenuItem("Guarding", lambda i, it: _toggle_guard(engine),
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
    engine.on_state = on_state
    engine.start()
    threading.Thread(target=icon.run, daemon=True).start()
    logline("app started")

    if not engine.cfg["settings"].get("configured"):
        root.after(400, run_wizard)          # first run -> setup wizard
    elif "--hidden" not in sys.argv:
        root.after(300, window.show)

    root.mainloop()


def _toggle_guard(engine):
    engine.guarding = not engine.guarding
    engine.last_seen = time.time()
    engine.save()
    logline("guarding " + ("started" if engine.guarding else "stopped")
            + " (tray)")


if __name__ == "__main__":
    main()
