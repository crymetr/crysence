"""Face models, camera/mic device detection, and small OS helpers."""

import os
import time
import ctypes
import winreg

# Silence OpenCV console noise (must be set before cv2 is imported).
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
os.environ.setdefault("OPENCV_VIDEOIO_DEBUG", "0")

import cv2  # noqa: E402

from . import config  # noqa: E402

user32 = ctypes.windll.user32

# Tuning that isn't per-user (kept here, documented).
INTRUDER_MARGIN = 0.15    # score between (threshold-margin) and threshold is
                          # "maybe you" (a bad angle) and never triggers.
OWNER_GRACE = 10          # seconds; a recent confident sighting suppresses a
                          # self-lock from a single bad-angle frame.
CONSEC_UNKNOWN = 3
CLIP_SECONDS = 5
COOLDOWN_AFTER_LOCK = 12
RESUME_HYSTERESIS = 4     # mic AND camera free this long before resuming.
HARD_ABSENCE = 300        # soft cover -> hard lock after this long away.
SOFT_NEAR_RATIO = 0.6     # "nearby" size = min_frac * this.
DET_SCORE = 0.6

# Processes whose device use is NOT treated as a meeting (just ourselves).
_DEVICE_IGNORE = ("crysence", "python", "pythonw")
_CONSENT = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager"
            r"\ConsentStore")


def logline(msg):
    try:
        p = config.LOG_PATH
        if os.path.exists(p) and os.path.getsize(p) > 1_000_000:
            with open(p, encoding="utf-8") as fh:
                tail = fh.readlines()[-300:]
            with open(p, "w", encoding="utf-8") as fh:
                fh.writelines(tail)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def make_detector(size):
    return cv2.FaceDetectorYN.create(config.DET_MODEL, "", size, DET_SCORE,
                                     0.3, 5000)


def make_recognizer():
    return cv2.FaceRecognizerSF.create(config.REC_MODEL, "")


def lock_workstation():
    user32.LockWorkStation()


def _device_in_use(device):
    """True if a non-ignored app currently holds the given device
    ('microphone' or 'webcam') per the Windows ConsentStore."""
    base = _CONSENT + "\\" + device

    def scan(path):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return False
        try:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                if any(w in name.lower() for w in _DEVICE_IGNORE):
                    continue
                try:
                    sk = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                        path + "\\" + name)
                except OSError:
                    continue
                try:
                    start, _ = winreg.QueryValueEx(sk, "LastUsedTimeStart")
                    stop, _ = winreg.QueryValueEx(sk, "LastUsedTimeStop")
                    if start and stop == 0:
                        return True
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(sk)
        finally:
            winreg.CloseKey(key)
        return False
    return scan(base) or scan(base + r"\NonPackaged")


def mic_in_use():
    return _device_in_use("microphone")


def camera_in_use_by_others():
    return _device_in_use("webcam")


def probe_cameras(max_probe=4):
    found = []
    for i in range(max_probe):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                found.append(i)
        cap.release()
    return found
