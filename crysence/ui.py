"""Shared UI theme + helpers for the customtkinter windows."""

import cv2
import customtkinter as ctk
from PIL import Image

from . import models

# Brand palette (dark-first).
ACCENT = "#2DD4BF"          # teal
ACCENT_HOVER = "#25A99A"
BG = "#16181D"
CARD = "#1E2128"
STATE_COLORS = {"idle": "#8A8F98", "guard": "#2DD4BF", "paused": "#E0A32E",
                "alert": "#E5484D", "enroll": "#5B8DEF"}

PREVIEW_W = 560

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def frame_to_image(frame, width=PREVIEW_W):
    h, w = frame.shape[:2]
    scale = width / w
    size = (width, int(h * scale))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb).resize(size)
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)


def annotate(frame, scored, threshold, min_frac):
    """Draw recognition boxes on a copy of the frame (BGR)."""
    disp = frame.copy()
    hard_frac = min_frac
    soft_frac = min_frac * models.SOFT_NEAR_RATIO
    margin = models.INTRUDER_MARGIN
    h, w = disp.shape[:2]
    for f, best in scored:
        x, y, fw, fh = f[:4].astype(int)
        frac = fw / w
        if best >= threshold:
            color, tag = (77, 212, 45), f"you {best:.2f}"
        elif best >= threshold - margin:
            color, tag = (220, 220, 0), f"maybe you {best:.2f}"
        elif frac >= hard_frac:
            color, tag = (77, 72, 229), f"CLOSE {best:.2f}"
        elif frac >= soft_frac:
            color, tag = (46, 163, 224), f"nearby {best:.2f}"
        else:
            color, tag = (150, 150, 150), f"far {best:.2f}"
        cv2.rectangle(disp, (x, y), (x + fw, y + fh), color, 2)
        cv2.putText(disp, tag, (x, max(y - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return disp
