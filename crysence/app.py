"""Tray application entry point: wires the engine, window, cover, and tray."""

import sys
import socket
import threading
import tkinter as tk

import pystray
from pystray import Menu, MenuItem
from PIL import Image, ImageDraw

from .engine import Engine
from .gui import Window
from .cover import Cover
from .models import logline

_ICON_COLORS = {"idle": (120, 120, 120), "guard": (46, 160, 67),
                "paused": (210, 160, 0), "alert": (200, 40, 40),
                "enroll": (0, 120, 210)}


def make_icon(state):
    img = Image.new("RGB", (64, 64), (32, 32, 32))
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


def _toggle_guard(engine):
    engine.guarding = not engine.guarding
    import time
    engine.last_seen = time.time()
    engine.save()
    logline("guarding " + ("started" if engine.guarding else "stopped")
            + " (tray)")


def main():
    lock = _single_instance()
    if lock is None:
        logline("another instance is already running - exiting")
        return

    root = tk.Tk()
    root.withdraw()
    engine = Engine()
    window = Window(root, engine)
    cover = Cover(root)

    def on_state(s):
        try:
            icon.icon = make_icon(s)
        except Exception:
            pass

    def ui(fn):
        root.after(0, fn)

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
            MenuItem("Open window", lambda i, it: ui(window.show),
                     default=True),
            MenuItem("Enroll my face",
                     lambda i, it: (engine.start_enroll(), ui(window.show))),
            MenuItem("Quit", lambda i, it: (engine.stop(), i.stop(),
                                            ui(root.destroy))),
        ))
    engine.on_state = on_state
    engine.start()
    threading.Thread(target=icon.run, daemon=True).start()
    logline("app started")

    if "--hidden" not in sys.argv:
        root.after(300, window.show)
    root.mainloop()


if __name__ == "__main__":
    main()
