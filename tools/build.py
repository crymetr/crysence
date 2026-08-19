"""Build the frozen CrySence app with PyInstaller (used locally and in CI)."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if os.name == "nt" else ":"
DATA = os.path.join("crysence", "data")

ROOT_JSON = os.path.join(DATA, "root.json")            # relative (cwd == ROOT)
ROOT_JSON_ABS = os.path.join(ROOT, DATA, "root.json")  # for the existence check

ARGS = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
    "--name", "CrySence",
    "--collect-data", "customtkinter",
    "--collect-submodules", "winotify",
    "--hidden-import", "pystray._win32",
    # auto-update stack
    "--collect-all", "tuf",
    "--collect-all", "securesystemslib",
    "--collect-all", "tufup",
    "--add-data", f"{os.path.join(DATA, 'face_detection_yunet_2023mar.onnx')}{SEP}.",
    "--add-data", f"{os.path.join(DATA, 'face_recognition_sface_2021dec.onnx')}{SEP}.",
]

# The update trust anchor (present only after tools/tuf_init.py has run).
if os.path.exists(ROOT_JSON_ABS):
    ARGS += ["--add-data", f"{ROOT_JSON}{SEP}."]

ARGS.append("main.py")

if __name__ == "__main__":
    raise SystemExit(subprocess.call(ARGS, cwd=ROOT))
