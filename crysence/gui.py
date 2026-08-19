"""Setup / preview window. Hidden by default; the guard runs without it.
(A modern themed rebuild + first-run wizard come next; this is the functional
baseline.)"""

import time
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from . import models
from .models import logline

PREVIEW_W = 640


class Window:
    def __init__(self, root, engine):
        self.root = root
        self.eng = engine
        self.visible = False
        root.title("CrySence")
        root.protocol("WM_DELETE_WINDOW", self.hide)

        self.status = tk.StringVar(value="")
        self.cam_var = tk.StringVar()
        self._build()
        self.scan()
        self._refresh()

    def _build(self):
        pad = {"padx": 6, "pady": 4}
        top = ttk.Frame(self.root); top.pack(fill="x", **pad)
        ttk.Label(top, text="Camera:").pack(side="left")
        self.cam_menu = ttk.Combobox(top, textvariable=self.cam_var, width=12,
                                     state="readonly")
        self.cam_menu.pack(side="left", padx=4)
        self.cam_menu.bind("<<ComboboxSelected>>", self.on_cam)
        ttk.Button(top, text="Rescan", command=self.scan).pack(side="left")

        self.preview = ttk.Label(self.root); self.preview.pack(**pad)
        ttk.Label(self.root, textvariable=self.status,
                  font=("Segoe UI", 11, "bold")).pack(**pad)

        btns = ttk.Frame(self.root); btns.pack(fill="x", **pad)
        ttk.Button(btns, text="Enroll my face",
                   command=self.eng.start_enroll).pack(side="left", padx=4)
        self.guard_btn = ttk.Button(btns, text="Start guarding",
                                    command=self.toggle_guard)
        self.guard_btn.pack(side="left", padx=4)

        o1 = ttk.Frame(self.root); o1.pack(fill="x", **pad)
        ttk.Label(o1, text="Soft dim after (s):").pack(side="left")
        self.grace = tk.DoubleVar(value=self.eng.grace)
        ttk.Spinbox(o1, from_=5, to=120, width=5, textvariable=self.grace,
                    command=self.apply).pack(side="left", padx=4)
        ttk.Label(o1, text="Recognize:").pack(side="left")
        self.thr = tk.DoubleVar(value=self.eng.threshold)
        ttk.Scale(o1, from_=0.30, to=0.75, variable=self.thr, length=110,
                  command=lambda _=None: self.apply()).pack(side="left", padx=2)
        self.thr_lbl = ttk.Label(o1, text=""); self.thr_lbl.pack(side="left")

        o2 = ttk.Frame(self.root); o2.pack(fill="x", **pad)
        ttk.Label(o2, text="Stranger 'close' (hard lock):").pack(side="left")
        self.minf = tk.DoubleVar(value=self.eng.min_frac)
        ttk.Scale(o2, from_=0.15, to=0.60, variable=self.minf, length=140,
                  command=lambda _=None: self.apply()).pack(side="left", padx=4)
        self.minf_lbl = ttk.Label(o2, text=""); self.minf_lbl.pack(side="left")

        o3 = ttk.Frame(self.root); o3.pack(fill="x", **pad)
        self.cover_var = tk.BooleanVar(value=self.eng.lock_mode == "layered")
        ttk.Checkbutton(
            o3, text="Layered: soft dim first, then Windows lock",
            variable=self.cover_var, command=self.apply_mode).pack(side="left")

        notif = self.eng.cfg["notifications"]
        on = [k for k in ("smtp", "ntfy", "telegram", "resend")
              if notif.get(k, {}).get("enabled")]
        ttk.Label(self.root, text="alerts: toast" + (
            " + " + ", ".join(on) if on else " (configure in config.json)")
                  ).pack(**pad)

    def apply(self):
        self.eng.grace = float(self.grace.get())
        self.eng.threshold = float(self.thr.get())
        self.eng.min_frac = float(self.minf.get())
        self.eng.save()

    def apply_mode(self):
        self.eng.lock_mode = "layered" if self.cover_var.get() else "screen"
        self.eng.save()
        logline("lock_mode = " + self.eng.lock_mode)

    def scan(self):
        cams = models.probe_cameras()
        self.cam_menu["values"] = [f"Camera {i}" for i in cams]
        if cams:
            idx = self.eng.cam_index if self.eng.cam_index in cams else cams[0]
            self.eng.cam_index = idx
            self.cam_var.set(f"Camera {idx}")

    def on_cam(self, _=None):
        idx = int(self.cam_var.get().split()[-1])
        self.eng.cam_index = idx
        self.eng.release_cam()
        self.eng.save()

    def toggle_guard(self):
        if self.eng.owner_feats is None:
            messagebox.showwarning("CrySence", "Enroll your face first.")
            return
        self.eng.guarding = not self.eng.guarding
        self.eng.last_seen = time.time()
        self.eng.save()
        logline("guarding " + ("started" if self.eng.guarding else "stopped"))

    def show(self):
        self.visible = True
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        self.visible = False
        self.root.withdraw()

    def _refresh(self):
        self.status.set(self.eng.status)
        self.thr_lbl.config(text=f"{self.thr.get():.2f}")
        self.minf_lbl.config(text=f"{self.minf.get():.2f}")
        self.guard_btn.config(text="Stop guarding" if self.eng.guarding
                              else "Start guarding")
        if self.visible and self.eng.latest_frame is not None:
            self._render(self.eng.latest_frame, self.eng.latest_scored)
        self.root.after(100, self._refresh)

    def _render(self, frame, scored):
        disp = frame.copy()
        thr = self.eng.threshold
        hard_frac = self.eng.min_frac
        soft_frac = self.eng.min_frac * models.SOFT_NEAR_RATIO
        h, w = disp.shape[:2]
        margin = models.INTRUDER_MARGIN
        for f, best in scored:
            x, y, fw, fh = f[:4].astype(int)
            frac = fw / w
            if best >= thr:
                color, tag = (0, 200, 0), f"you {best:.2f}"
            elif best >= thr - margin:
                color, tag = (0, 220, 220), f"maybe you {best:.2f}"
            elif frac >= hard_frac:
                color, tag = (0, 0, 255), f"CLOSE->hard {best:.2f}"
            elif frac >= soft_frac:
                color, tag = (0, 140, 255), f"nearby->soft {best:.2f}"
            else:
                color, tag = (0, 190, 190), f"far {best:.2f}"
            cv2.rectangle(disp, (x, y), (x + fw, y + fh), color, 2)
            cv2.putText(disp, tag, (x, max(y - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        scale = PREVIEW_W / w
        disp = cv2.resize(disp, (PREVIEW_W, int(h * scale)))
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.preview.configure(image=img)
        self.preview.image = img
