"""Auto-update via GitHub Releases.

On startup and then every hour (packaged builds only) this checks the repo's
latest GitHub Release in the background; the tray can also ask right away. If a newer version is published, it downloads the signed
installer and hands the path back; the app then offers a one-click install
(runs the installer silently and relaunches). No servers, keys, or Pages to
manage - releases are produced by CI on a tag.

Every failure here is swallowed: an update check must never crash or block.
"""

import os
import sys
import json
import time
import threading
import subprocess
import urllib.request

from . import config
from .models import logline
from . import __version__

REPO = "crymetr/crysence"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_UA = "CrySence-updater"
CHECK_EVERY = 3600      # seconds; unauthenticated API allows 60/hour per IP
_lock = threading.Lock()
_announced = None       # version already handed to on_ready


def _ver(s):
    parts = []
    for p in str(s).lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def _is_newer(remote, local):
    return bool(remote) and _ver(remote) > _ver(local)


def _run(on_ready):
    """Returns "newer", "latest" or "failed". on_ready fires once per version."""
    global _announced
    if not getattr(sys, "frozen", False):
        return "latest"
    if not _lock.acquire(blocking=False):
        return "busy"       # a check is already running
    try:
        req = urllib.request.Request(
            API_URL, headers={"User-Agent": _UA,
                              "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        tag = (data.get("tag_name") or "").lstrip("v")
        if not _is_newer(tag, __version__):
            return "latest"
        if tag == _announced:
            return "newer"
        asset = next(
            (a for a in data.get("assets", [])
             if a["name"].lower().startswith("crysence-setup")
             and a["name"].lower().endswith(".exe")), None)
        if not asset:
            return "latest"     # release still building (no installer yet)

        updir = os.path.join(config.DATA, "updates")
        os.makedirs(updir, exist_ok=True)
        dest = os.path.join(updir, asset["name"])
        if not (os.path.exists(dest)
                and os.path.getsize(dest) == asset.get("size")):
            dl = urllib.request.Request(
                asset["browser_download_url"], headers={"User-Agent": _UA})
            tmp = dest + ".part"
            with urllib.request.urlopen(dl, timeout=120) as resp, \
                    open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
            os.replace(tmp, dest)
        logline(f"update {tag} downloaded")
        _announced = tag
        on_ready(tag, dest)
        return "newer"
    except Exception as e:
        logline("update check failed: " + repr(e))
        return "failed"
    finally:
        _lock.release()


def check_in_background(on_ready):
    """Check now, then every CHECK_EVERY seconds, for the life of the app."""
    def loop():
        while True:
            _run(on_ready)
            time.sleep(CHECK_EVERY)
    threading.Thread(target=loop, daemon=True).start()


def check_now(on_ready, on_done):
    """Tray "Check for updates": one check, result string to on_done."""
    threading.Thread(target=lambda: on_done(_run(on_ready)),
                     daemon=True).start()


def apply(installer_path):
    """Run the downloaded installer silently. The caller must then exit the
    process for real (the installer can't replace files we still hold); the
    installer replaces the app and relaunches it into the tray."""
    if getattr(sys, "frozen", False):
        # PyInstaller points the DLL search path at _internal; don't let the
        # installer inherit that.
        try:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass
    log = os.path.join(config.DATA, "updates", "setup.log")
    logline("launching installer " + installer_path)
    subprocess.Popen(
        [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
         "/LOG=" + log],
        close_fds=True,
        creationflags=(subprocess.DETACHED_PROCESS
                       | subprocess.CREATE_NEW_PROCESS_GROUP))
