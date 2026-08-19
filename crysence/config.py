"""Paths and persistent config for CrySence.

Nothing here is machine-specific. User data (config, enrolled face, captures,
log) lives under %LOCALAPPDATA%\\CrySence so the repo and the installed program
directory stay clean and read-only. No secrets are ever written into the source
tree.
"""

import os
import sys
import json
import copy

APP_NAME = "CrySence"


def data_dir():
    """Per-user writable directory for config, enrollment, captures, logs."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def resource_dir():
    """Read-only bundled resources (the ONNX models)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


DATA = data_dir()
CONFIG_PATH = os.path.join(DATA, "config.json")
OWNER_PATH = os.path.join(DATA, "owner_face.npy")
CAPTURES_DIR = os.path.join(DATA, "captures")
LOG_PATH = os.path.join(DATA, "crysence.log")

DET_MODEL = os.path.join(resource_dir(), "face_detection_yunet_2023mar.onnx")
REC_MODEL = os.path.join(resource_dir(), "face_recognition_sface_2021dec.onnx")

DEFAULT_CONFIG = {
    "settings": {
        "cam_index": None,
        "grace": 15.0,            # seconds not present before a soft cover
        "threshold": 0.50,        # face match to count as "you"
        "min_frac": 0.30,         # stranger face size that means "close" (hard)
        "guarding": False,
        "lock_mode": "layered",   # "layered" | "screen"
    },
    "notifications": {
        # Windows toast: no config, on by default.
        "toast": True,
        # Everything below is off until the user fills it in. No defaults point
        # at any real account or server.
        "smtp": {"enabled": False, "host": "", "port": 587, "tls": True,
                 "user": "", "password": "", "from": "", "to": ""},
        "ntfy": {"enabled": False, "server": "https://ntfy.sh",
                 "topic": "", "token": ""},
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "resend": {"enabled": False, "api_key": "", "from": "", "to": ""},
    },
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return _merge(DEFAULT_CONFIG, json.load(fh))
    except Exception:
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        pass
