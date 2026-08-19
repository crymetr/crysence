"""Modern main window (customtkinter): dashboard + live preview + settings."""

import time
import customtkinter as ctk

from . import models, ui
from .models import logline


class MainWindow:
    def __init__(self, root, engine, on_run_wizard=None):
        self.root = root
        self.eng = engine
        self.on_run_wizard = on_run_wizard
        self.visible = False
        self._img = None

        root.title("CrySence")
        root.geometry("620x820")
        root.configure(fg_color=ui.BG)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        self.scan()
        self._refresh()

    # ---- layout ---------------------------------------------------------
    def _build(self):
        head = ctk.CTkFrame(self.root, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(head, text="CrySence", font=("Segoe UI", 24, "bold"),
                     text_color=ui.ACCENT).pack(side="left")
        self.pill = ctk.CTkLabel(head, text="  idle  ", corner_radius=12,
                                 fg_color=ui.STATE_COLORS["idle"], height=26,
                                 text_color="#101216",
                                 font=("Segoe UI", 12, "bold"))
        self.pill.pack(side="right")

        cam = ctk.CTkFrame(self.root, fg_color="transparent")
        cam.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(cam, text="Camera").pack(side="left", padx=(0, 8))
        self.cam_menu = ctk.CTkOptionMenu(cam, values=["-"], width=140,
                                          command=self.on_cam,
                                          fg_color=ui.CARD,
                                          button_color=ui.CARD)
        self.cam_menu.pack(side="left")
        ctk.CTkButton(cam, text="Rescan", width=70, command=self.scan,
                      fg_color=ui.CARD, hover_color="#2A2E37").pack(
                          side="left", padx=8)

        self.preview = ctk.CTkLabel(self.root, text="", fg_color=ui.CARD,
                                    corner_radius=12)
        self.preview.pack(padx=18, pady=8)

        self.guard_btn = ctk.CTkButton(
            self.root, text="Start guarding", height=44,
            font=("Segoe UI", 15, "bold"), command=self.toggle_guard,
            fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
            text_color="#0B0E10")
        self.guard_btn.pack(fill="x", padx=18, pady=(4, 6))

        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=2)
        for txt, cmd in (("Enroll face", self.eng.start_enroll),
                         ("Pause", self.toggle_pause),
                         ("Setup wizard", self._wizard)):
            ctk.CTkButton(row, text=txt, command=cmd, fg_color=ui.CARD,
                          hover_color="#2A2E37").pack(
                              side="left", expand=True, fill="x", padx=3)

        card = ctk.CTkFrame(self.root, fg_color=ui.CARD, corner_radius=12)
        card.pack(fill="x", padx=18, pady=10)
        self.grace = self._slider(card, "Soft dim after (s)", 5, 120,
                                  self.eng.grace, "{:.0f}")
        self.thr = self._slider(card, "Recognize (strictness)", 0.30, 0.75,
                                self.eng.threshold, "{:.2f}")
        self.minf = self._slider(card, "Stranger 'close' -> hard lock", 0.15,
                                 0.60, self.eng.min_frac, "{:.2f}")

        modes = ctk.CTkFrame(card, fg_color="transparent")
        modes.pack(fill="x", padx=14, pady=(2, 10))
        ctk.CTkLabel(modes, text="Lock mode").pack(side="left")
        self.mode = ctk.CTkSegmentedButton(
            modes, values=["Layered", "Windows only"],
            command=self.apply_mode, selected_color=ui.ACCENT,
            selected_hover_color=ui.ACCENT_HOVER)
        self.mode.set("Layered" if self.eng.lock_mode == "layered"
                      else "Windows only")
        self.mode.pack(side="right")

        self.alerts_lbl = ctk.CTkLabel(self.root, text="", text_color="#8A8F98",
                                       font=("Segoe UI", 12))
        self.alerts_lbl.pack(pady=(0, 12))

    def _slider(self, parent, label, lo, hi, value, fmt):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(f, text=label, anchor="w").pack(side="left")
        val = ctk.CTkLabel(f, text=fmt.format(value), width=42,
                           text_color=ui.ACCENT)
        val.pack(side="right")
        s = ctk.CTkSlider(parent, from_=lo, to=hi, progress_color=ui.ACCENT,
                          button_color=ui.ACCENT, button_hover_color=ui.ACCENT,
                          command=lambda _v: self.apply())
        s.set(value)
        s.pack(fill="x", padx=14, pady=(2, 2))
        s._val_lbl, s._fmt = val, fmt
        return s

    # ---- actions --------------------------------------------------------
    def apply(self):
        self.eng.grace = float(self.grace.get())
        self.eng.threshold = float(self.thr.get())
        self.eng.min_frac = float(self.minf.get())
        for s in (self.grace, self.thr, self.minf):
            s._val_lbl.configure(text=s._fmt.format(s.get()))
        self.eng.save()

    def apply_mode(self, _v=None):
        self.eng.lock_mode = ("layered" if self.mode.get() == "Layered"
                              else "screen")
        self.eng.save()
        logline("lock_mode = " + self.eng.lock_mode)

    def scan(self):
        cams = models.probe_cameras()
        vals = [f"Camera {i}" for i in cams] or ["-"]
        self.cam_menu.configure(values=vals)
        if cams:
            idx = self.eng.cam_index if self.eng.cam_index in cams else cams[0]
            self.eng.cam_index = idx
            self.cam_menu.set(f"Camera {idx}")

    def on_cam(self, val):
        if val.startswith("Camera"):
            self.eng.cam_index = int(val.split()[-1])
            self.eng.release_cam()
            self.eng.save()

    def toggle_guard(self):
        if self.eng.owner_feats is None:
            self._wizard()
            return
        self.eng.guarding = not self.eng.guarding
        self.eng.last_seen = time.time()
        self.eng.save()
        logline("guarding " + ("started" if self.eng.guarding else "stopped"))

    def toggle_pause(self):
        self.eng.manual_pause = not self.eng.manual_pause

    def _wizard(self):
        if self.on_run_wizard:
            self.on_run_wizard()

    def show(self):
        self.visible = True
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        self.visible = False
        self.root.withdraw()

    # ---- refresh loop ---------------------------------------------------
    def _refresh(self):
        st = self.eng.state
        self.pill.configure(text=f"  {self.eng.status}  ",
                            fg_color=ui.STATE_COLORS.get(st, "#8A8F98"))
        self.guard_btn.configure(
            text="Stop guarding" if self.eng.guarding else "Start guarding",
            fg_color=(ui.STATE_COLORS["alert"] if self.eng.guarding
                      else ui.ACCENT))
        notif = self.eng.cfg["notifications"]
        on = [k for k in ("smtp", "ntfy", "telegram", "resend")
              if notif.get(k, {}).get("enabled")]
        self.alerts_lbl.configure(
            text="alerts: toast" + (" + " + ", ".join(on) if on else
                                    "  (add channels in the wizard)"))
        if self.visible and self.eng.latest_frame is not None:
            disp = ui.annotate(self.eng.latest_frame, self.eng.latest_scored,
                               self.eng.threshold, self.eng.min_frac)
            self._img = ui.frame_to_image(disp)
            self.preview.configure(image=self._img)
        self.root.after(100, self._refresh)
