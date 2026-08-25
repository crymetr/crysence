"""Auto-update via GitHub Releases.

On startup (packaged builds only) this checks the repo's latest GitHub Release
in the background. If a newer version is published, it downloads the signed
installer and hands the path back; the app then offers a one-click install
(runs the installer silently and relaunches). No servers, keys, or Pages to
manage - releases are produced by CI on a tag.

Every failure here is swallowed: an update check must never crash or block.
"""

import os
import sys
import json
import threading
import subprocess
import urllib.request

from . import config
from .models import logline
from . import __version__

REPO = "crymetr/crysence"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_UA = "CrySence-updater"


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
    if not getattr(sys, "frozen", False):
        return
    try:
        req = urllib.request.Request(
            API_URL, headers={"User-Agent": _UA,
                              "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        tag = (data.get("tag_name") or "").lstrip("v")
        if not _is_newer(tag, __version__):
            return
        asset = next(
            (a for a in data.get("assets", [])
             if a["name"].lower().startswith("crysence-setup")
             and a["name"].lower().endswith(".exe")), None)
        if not asset:
            return

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
        on_ready(tag, dest)
    except Exception as e:
        logline("update check failed: " + repr(e))


def check_in_background(on_ready):
    threading.Thread(target=_run, args=(on_ready,), daemon=True).start()


def apply(installer_path):
    """Run the downloaded installer silently. The installer closes the running
    app, replaces it, and relaunches into the tray."""
    subprocess.Popen(
        [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True)
