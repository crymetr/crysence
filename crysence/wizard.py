"""First-run setup wizard (customtkinter). Walks through camera, face
enrollment, lock mode and (optional) alerts, then arms the guard."""

import customtkinter as ctk

from . import models, ui
from .models import logline


class Wizard:
    def __init__(self, root, engine, on_done):
        self.eng = engine
        self.on_done = on_done
        self.i = 0
        self.show_preview = False
        self.preview_img = None
        self.alert_fields = {}

        self.top = ctk.CTkToplevel(root)
        self.top.title("CrySence setup")
        self.top.geometry("560x740")
        self.top.configure(fg_color=ui.BG)
        self.top.protocol("WM_DELETE_WINDOW", self._skip)
        self.top.after(200, self.top.lift)

        # Nav bar is pinned to the bottom FIRST so a tall step (with a camera
        # preview) can never push the Back/Next buttons off-screen.
        nav = ctk.CTkFrame(self.top, fg_color="transparent")
        nav.pack(side="bottom", fill="x", padx=24, pady=(0, 18))

        self.body = ctk.CTkFrame(self.top, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True, padx=24, pady=18)
        self.back_btn = ctk.CTkButton(nav, text="Back", width=90,
                                      fg_color=ui.CARD, hover_color="#2A2E37",
                                      command=self._back)
        self.back_btn.pack(side="left")
        self.next_btn = ctk.CTkButton(nav, text="Next", width=120,
                                      fg_color=ui.ACCENT,
                                      hover_color=ui.ACCENT_HOVER,
                                      text_color="#0B0E10", command=self._next)
        self.next_btn.pack(side="right")

        self.steps = [self._welcome, self._camera, self._enroll, self._mode,
                      self._alerts, self._finish]
        self._render()
        self._tick()

    # ---- helpers --------------------------------------------------------
    def _clear(self):
        self.show_preview = False
        for w in self.body.winfo_children():
            w.destroy()

    def _title(self, text, sub=""):
        ctk.CTkLabel(self.body, text=text, font=("Segoe UI", 22, "bold"),
                     text_color=ui.ACCENT).pack(anchor="w", pady=(4, 2))
        if sub:
            ctk.CTkLabel(self.body, text=sub, justify="left", anchor="w",
                         text_color="#B4B8C0", wraplength=560).pack(
                             anchor="w", pady=(0, 12))

    def _preview_widget(self):
        self.preview = ctk.CTkLabel(self.body, text="", fg_color=ui.CARD,
                                    corner_radius=12)
        self.preview.pack(pady=10)
        self.show_preview = True

    def _render(self):
        self._clear()
        self.steps[self.i]()
        self.back_btn.configure(state="normal" if self.i > 0 else "disabled")
        self.next_btn.configure(
            text="Finish" if self.i == len(self.steps) - 1 else "Next")

    def _back(self):
        if self.i > 0:
            self.i -= 1
            self._render()

    def _next(self):
        if self.i == len(self.steps) - 1:
            self._commit()
            return
        # gate: must enroll before leaving the enroll step
        if self.steps[self.i] == self._enroll and self.eng.owner_feats is None:
            self.status_lbl.configure(text="Please enroll your face first.")
            return
        if self.steps[self.i] == self._alerts:
            self._save_alerts()
        self.i += 1
        self._render()

    def _skip(self):
        # closing the wizard just hides it; settings stay unconfigured
        if self.eng.mode == "enroll":
            self.eng.mode = "idle"  # don't keep enrolling whoever is in frame
        self.top.destroy()
        self.on_done(started=False)

    # ---- steps ----------------------------------------------------------
    def _welcome(self):
        self._title(
            "Welcome to CrySence",
            "CrySence locks your PC when you step away and recognizes you to "
            "come back. Everything runs locally on this machine. This quick "
            "setup takes about a minute.")
        ctk.CTkLabel(self.body, text="You'll pick a camera, enroll your face, "
                     "choose how it locks, and optionally set up alerts.",
                     justify="left", anchor="w", text_color="#B4B8C0",
                     wraplength=560).pack(anchor="w")

    def _camera(self):
        self._title("Pick your camera",
                    "Choose the camera that shows your face below.")
        cams = models.probe_cameras()
        vals = [f"Camera {i}" for i in cams] or ["-"]
        menu = ctk.CTkOptionMenu(
            self.body, values=vals, command=self._pick_cam, fg_color=ui.CARD,
            button_color=ui.ACCENT, button_hover_color=ui.ACCENT_HOVER,
            dropdown_fg_color=ui.CARD)
        if cams:
            idx = self.eng.cam_index if self.eng.cam_index in cams else cams[0]
            self.eng.cam_index = idx
            menu.set(f"Camera {idx}")
        menu.pack(anchor="w")
        self._preview_widget()

    def _pick_cam(self, val):
        if val.startswith("Camera"):
            self.eng.request_cam(int(val.split()[-1]))

    def _enroll(self):
        self._title(
            "Enroll your face",
            "Look at the camera and turn your head slowly (a little left, "
            "right, up, down; glasses on/off). It captures 20 samples.")
        self._preview_widget()
        self.status_lbl = ctk.CTkLabel(self.body, text="", text_color=ui.ACCENT)
        self.status_lbl.pack(pady=6)
        ctk.CTkButton(self.body, text="Start enrollment", fg_color=ui.ACCENT,
                      hover_color=ui.ACCENT_HOVER, text_color="#0B0E10",
                      command=self.eng.start_enroll).pack()
        if self.eng.owner_feats is not None:
            self.status_lbl.configure(text="Face already enrolled. You can "
                                      "re-enroll or continue.")

    def _mode(self):
        self._title(
            "How should it lock?",
            "Layered: a soft dim first (auto-unlocks when it sees you), then a "
            "real Windows lock if a stranger gets close or you're gone a while. "
            "Windows only: skip the soft stage, lock straight away.")
        self.mode_seg = ctk.CTkSegmentedButton(
            self.body, values=["Layered (recommended)", "Windows only"],
            selected_color=ui.ACCENT, selected_hover_color=ui.ACCENT_HOVER)
        self.mode_seg.set("Layered (recommended)"
                          if self.eng.lock_mode == "layered" else "Windows only")
        self.mode_seg.pack(anchor="w", pady=8)
        self.mode_seg.configure(command=self._pick_mode)

    def _pick_mode(self, _v):
        self.eng.lock_mode = ("layered" if self.mode_seg.get().startswith(
            "Layered") else "screen")

    def _alerts(self):
        self._title(
            "Alerts (optional)",
            "When an unknown face is caught, CrySence always shows a Windows "
            "toast and saves a photo locally. To also get notified when you're "
            "away, pick a channel. You can skip this.")
        self.channel = ctk.CTkOptionMenu(
            self.body, values=["None", "ntfy (phone push)", "Email (SMTP)",
                               "Telegram", "Resend"], command=self._alert_form,
            fg_color=ui.CARD, button_color=ui.ACCENT,
            button_hover_color=ui.ACCENT_HOVER, dropdown_fg_color=ui.CARD)
        self.channel.pack(anchor="w")
        self.form = ctk.CTkFrame(self.body, fg_color="transparent")
        self.form.pack(fill="x", pady=10)
        self._alert_form(self._current_channel_label())

    def _current_channel_label(self):
        n = self.eng.cfg["notifications"]
        if n["ntfy"]["enabled"]:
            return "ntfy (phone push)"
        if n["smtp"]["enabled"]:
            return "Email (SMTP)"
        if n["telegram"]["enabled"]:
            return "Telegram"
        if n["resend"]["enabled"]:
            return "Resend"
        return "None"

    def _alert_form(self, choice):
        for w in self.form.winfo_children():
            w.destroy()
        self.alert_fields = {}
        self.channel.set(choice)
        specs = {
            "ntfy (phone push)": [("server", "Server", "https://ntfy.sh"),
                                  ("topic", "Topic (pick something unguessable)",
                                   "")],
            "Email (SMTP)": [("host", "SMTP host", "smtp.gmail.com"),
                             ("port", "Port", "587"),
                             ("user", "Username / email", ""),
                             ("password", "Password / app password", "*"),
                             ("to", "Send alerts to", "")],
            "Telegram": [("bot_token", "Bot token", ""),
                         ("chat_id", "Chat id", "")],
            "Resend": [("api_key", "API key", ""),
                       ("from", "From (verified domain)", ""),
                       ("to", "Send alerts to", "")],
        }
        if choice not in specs:
            ctk.CTkLabel(self.form, text="No alerts beyond the Windows toast.",
                         text_color="#B4B8C0").pack(anchor="w")
            return
        key = {"ntfy (phone push)": "ntfy", "Email (SMTP)": "smtp",
               "Telegram": "telegram", "Resend": "resend"}[choice]
        cur = self.eng.cfg["notifications"][key]
        for field, label, default in specs[choice]:
            ctk.CTkLabel(self.form, text=label, anchor="w").pack(
                anchor="w", pady=(6, 0))
            e = ctk.CTkEntry(self.form, width=420,
                             show="*" if default == "*" else "")
            val = cur.get(field) or (default if default != "*" else "")
            e.insert(0, str(val))
            e.pack(anchor="w")
            self.alert_fields[field] = e

    def _save_alerts(self):
        choice = self.channel.get()
        n = self.eng.cfg["notifications"]
        for k in ("ntfy", "smtp", "telegram", "resend"):
            n[k]["enabled"] = False
        key = {"ntfy (phone push)": "ntfy", "Email (SMTP)": "smtp",
               "Telegram": "telegram", "Resend": "resend"}.get(choice)
        if key:
            for field, e in self.alert_fields.items():
                v = e.get().strip()
                n[key][field] = int(v) if field == "port" and v.isdigit() else v
            if key == "smtp" and not n[key].get("from"):
                n[key]["from"] = n[key].get("user", "")
            n[key]["enabled"] = True
            logline(f"alerts configured: {key}")

    def _finish(self):
        self._title(
            "You're all set",
            "CrySence will run in the tray. Right-click the tray icon any time "
            "to pause, open this window, or quit. Guarding starts when you "
            "click Finish.")
        ctk.CTkLabel(self.body, text="Tip: to auto-start at login, use the "
                     "installer's shortcut (coming soon) or drop a shortcut in "
                     "shell:startup.", justify="left", anchor="w",
                     text_color="#B4B8C0", wraplength=560).pack(anchor="w")

    def _commit(self):
        self.eng.cfg["settings"]["configured"] = True
        self.eng.guarding = True
        import time
        self.eng.last_seen = time.time()
        self.eng.save()
        logline("wizard finished, guarding on")
        self.top.destroy()
        self.on_done(started=True)

    # ---- preview loop ---------------------------------------------------
    def _tick(self):
        if not self.top.winfo_exists():
            return
        if self.show_preview and self.eng.latest_frame is not None:
            disp = ui.annotate(self.eng.latest_frame, self.eng.latest_scored,
                               self.eng.threshold, self.eng.min_frac)
            self.preview_img = ui.frame_to_image(disp, width=420)
            try:
                self.preview.configure(image=self.preview_img)
            except Exception:
                pass
        if hasattr(self, "status_lbl") and self.steps[self.i] == self._enroll:
            try:
                self.status_lbl.configure(text=self.eng.status)
            except Exception:
                pass
        self.top.after(90, self._tick)
