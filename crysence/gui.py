"""Modern main window (customtkinter): dashboard + live preview + settings."""

import time
import customtkinter as ctk

from . import config, models, ui
from .models import logline

MUTED = "#8A8F98"
PREVIEW_W = 400


class MainWindow:
    def __init__(self, root, engine, on_run_wizard=None):
        self.root = root
        self.eng = engine
        self.on_run_wizard = on_run_wizard
        self.visible = False
        self._img = None

        root.title("CrySence")
        root.geometry("560x788")
        root.minsize(520, 720)
        root.configure(fg_color=ui.BG)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        self.scan()
        self._refresh()

    # ---- layout ---------------------------------------------------------
    def _build(self):
        head = ctk.CTkFrame(self.root, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(20, 6))
        title = ctk.CTkFrame(head, fg_color="transparent")
        title.pack(side="left")
        ctk.CTkLabel(title, text="CrySence", font=("Segoe UI", 25, "bold"),
                     text_color=ui.ACCENT).pack(anchor="w")
        ctk.CTkLabel(title, text="presence lock", font=("Segoe UI", 12),
                     text_color=MUTED).pack(anchor="w")
        self.pill = ctk.CTkLabel(head, text="  idle  ", corner_radius=13,
                                 fg_color=ui.STATE_COLORS["idle"], height=28,
                                 text_color="#0B0E10",
                                 font=("Segoe UI", 12, "bold"))
        self.pill.pack(side="right", pady=6)

        cam = ctk.CTkFrame(self.root, fg_color="transparent")
        cam.pack(fill="x", padx=22, pady=(4, 2))
        ctk.CTkLabel(cam, text="Camera", text_color=MUTED).pack(
            side="left", padx=(0, 8))
        self.cam_menu = ctk.CTkOptionMenu(
            cam, values=["-"], width=150, command=self.on_cam,
            fg_color=ui.CARD, button_color=ui.ACCENT,
            button_hover_color=ui.ACCENT_HOVER, dropdown_fg_color=ui.CARD,
            text_color="#E6E8EC")
        self.cam_menu.pack(side="left")
        ctk.CTkButton(cam, text="Rescan", width=76, command=self.scan,
                      corner_radius=9, fg_color=ui.CARD,
                      hover_color="#2A2E37").pack(side="left", padx=8)

        self.preview = ctk.CTkLabel(self.root, text="camera preview",
                                    text_color=MUTED, fg_color=ui.CARD,
                                    corner_radius=14, width=PREVIEW_W,
                                    height=int(PREVIEW_W * 3 / 4))
        self.preview.pack(padx=22, pady=10)

        self.guard_btn = ctk.CTkButton(
            self.root, text="Start guarding", height=46, corner_radius=12,
            font=("Segoe UI", 15, "bold"), command=self.toggle_guard,
            fg_color=ui.ACCENT, hover_color=ui.ACCENT_HOVER,
            text_color="#0B0E10")
        self.guard_btn.pack(fill="x", padx=22, pady=(2, 8))

        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=2)
        for txt, cmd in (("Enroll face", self.eng.start_enroll),
                         ("Pause", self.toggle_pause),
                         ("Unlock password", self.password_dialog),
                         ("Setup wizard", self._wizard)):
            ctk.CTkButton(row, text=txt, command=cmd, corner_radius=9,
                          fg_color=ui.CARD, hover_color="#2A2E37").pack(
                              side="left", expand=True, fill="x", padx=3)

        card = ctk.CTkFrame(self.root, fg_color=ui.CARD, corner_radius=14)
        card.pack(fill="x", padx=22, pady=12)
        ctk.CTkLabel(card, text="SETTINGS", font=("Segoe UI", 11, "bold"),
                     text_color=MUTED).pack(anchor="w", padx=16, pady=(12, 0))
        self.grace = self._slider(card, "Soft dim after (s)", 5, 120,
                                  self.eng.grace, "{:.0f}")
        self.thr = self._slider(card, "Recognize (strictness)", 0.30, 0.75,
                                self.eng.threshold, "{:.2f}")
        self.minf = self._slider(card, "Stranger 'close' -> hard lock", 0.15,
                                 0.60, self.eng.min_frac, "{:.2f}")

        modes = ctk.CTkFrame(card, fg_color="transparent")
        modes.pack(fill="x", padx=16, pady=(6, 14))
        ctk.CTkLabel(modes, text="Lock mode", text_color=MUTED).pack(
            side="left")
        self.mode = ctk.CTkSegmentedButton(
            modes, values=["Layered", "Windows only"], command=self.apply_mode,
            selected_color=ui.ACCENT, selected_hover_color=ui.ACCENT_HOVER,
            unselected_color="#2A2E37", text_color="#E6E8EC")
        self.mode.set("Layered" if self.eng.lock_mode == "layered"
                      else "Windows only")
        self.mode.pack(side="right")

        self.alerts_lbl = ctk.CTkLabel(self.root, text="", text_color=MUTED,
                                       font=("Segoe UI", 12))
        self.alerts_lbl.pack(pady=(0, 14))

    def _slider(self, parent, label, lo, hi, value, fmt):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(f, text=label, anchor="w").pack(side="left")
        val = ctk.CTkLabel(f, text=fmt.format(value), width=42,
                           text_color=ui.ACCENT, font=("Segoe UI", 13, "bold"))
        val.pack(side="right")
        s = ctk.CTkSlider(parent, from_=lo, to=hi, progress_color=ui.ACCENT,
                          button_color=ui.ACCENT, button_hover_color=ui.ACCENT,
                          command=lambda _v: self.apply())
        s.set(value)
        s.pack(fill="x", padx=16, pady=(2, 2))
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
        # Probe on a worker thread; opening DirectShow devices can take seconds
        # and must not block the Tk mainloop (a stalled pump makes Windows drop
        # the cover's keyboard hook).
        import threading

        def work():
            cams = models.probe_cameras()
            self.root.after(0, lambda: self._apply_cams(cams))
        threading.Thread(target=work, daemon=True).start()

    def _apply_cams(self, cams):
        vals = [f"Camera {i}" for i in cams] or ["-"]
        self.cam_menu.configure(values=vals)
        if cams:
            idx = self.eng.cam_index if self.eng.cam_index in cams else cams[0]
            self.eng.cam_index = idx
            self.cam_menu.set(f"Camera {idx}")

    def on_cam(self, val):
        if val.startswith("Camera"):
            self.eng.request_cam(int(val.split()[-1]))
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

    def password_dialog(self):
        """Set/clear the emergency password for the cover's hidden hotkey."""
        top = ctk.CTkToplevel(self.root)
        top.title("Emergency unlock")
        top.geometry("400x330")
        top.configure(fg_color=ui.BG)
        top.transient(self.root)
        top.after(50, top.grab_set)
        has = bool(self.eng.cfg["settings"].get("unlock_pw"))
        ctk.CTkLabel(
            top, justify="left", wraplength=350, text=(
                "On the black cover, press Ctrl+Alt+Shift+U and type this "
                "password to unlock without the camera. 3 wrong tries go to "
                "the Windows lock. With no password, the hotkey goes straight "
                "to the Windows lock.")).pack(padx=22, pady=(18, 8))
        status = ctk.CTkLabel(top, text="Password is set" if has
                              else "No password set", text_color=MUTED)
        status.pack()
        e1 = ctk.CTkEntry(top, show="•", placeholder_text="New password")
        e2 = ctk.CTkEntry(top, show="•", placeholder_text="Repeat")
        e1.pack(fill="x", padx=22, pady=(10, 4))
        e2.pack(fill="x", padx=22, pady=4)

        def save():
            a, b = e1.get(), e2.get()
            if len(a) < 4:
                status.configure(text="Use at least 4 characters",
                                 text_color=ui.STATE_COLORS["alert"])
                return
            if a != b:
                status.configure(text="Passwords don't match",
                                 text_color=ui.STATE_COLORS["alert"])
                return
            self.eng.cfg["settings"]["unlock_pw"] = config.hash_password(a)
            self.eng.save()
            logline("emergency unlock password set")
            top.destroy()

        def clear():
            self.eng.cfg["settings"]["unlock_pw"] = None
            self.eng.save()
            logline("emergency unlock password cleared")
            top.destroy()

        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(12, 16))
        ctk.CTkButton(row, text="Save", command=save, fg_color=ui.ACCENT,
                      hover_color=ui.ACCENT_HOVER, text_color="#0B0E10").pack(
                          side="left", expand=True, fill="x", padx=3)
        ctk.CTkButton(row, text="Remove", command=clear, fg_color=ui.CARD,
                      hover_color="#2A2E37",
                      state="normal" if has else "disabled").pack(
                          side="left", expand=True, fill="x", padx=3)
        e1.focus_set()

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
                            fg_color=ui.STATE_COLORS.get(st, MUTED))
        self.guard_btn.configure(
            text="Stop guarding" if self.eng.guarding else "Start guarding",
            fg_color=(ui.STATE_COLORS["alert"] if self.eng.guarding
                      else ui.ACCENT))
        notif = self.eng.cfg["notifications"]
        on = [k for k in ("smtp", "ntfy", "telegram", "resend")
              if notif.get(k, {}).get("enabled")]
        self.alerts_lbl.configure(
            text="alerts: toast" + (" + " + ", ".join(on) if on else
                                    "  ·  add channels in the wizard"))
        if self.visible and self.eng.latest_frame is not None:
            disp = ui.annotate(self.eng.latest_frame, self.eng.latest_scored,
                               self.eng.threshold, self.eng.min_frac)
            self._img = ui.frame_to_image(disp, width=PREVIEW_W)
            self.preview.configure(image=self._img, text="")
        self.root.after(100, self._refresh)
