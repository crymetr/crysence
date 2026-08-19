"""Build the frozen CrySence app with PyInstaller (used locally and in CI)."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = ";" if os.name == "nt" else ":"
DATA = os.path.join("crysence", "data")

ARGS = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
    "--name", "CrySence",
    "--collect-data", "customtkinter",
    "--collect-submodules", "winotify",
    "--hidden-import", "pystray._win32",
    "--add-data", f"{os.path.join(DATA, 'face_detection_yunet_2023mar.onnx')}{SEP}.",
    "--add-data", f"{os.path.join(DATA, 'face_recognition_sface_2021dec.onnx')}{SEP}.",
    "main.py",
]

if __name__ == "__main__":
    raise SystemExit(subprocess.call(ARGS, cwd=ROOT))
