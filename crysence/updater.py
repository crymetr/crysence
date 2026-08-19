"""Signed auto-update via tufup (The Update Framework).

On startup (frozen builds only) this checks a signed update repository hosted on
GitHub Pages. If a newer, properly-signed version is available it is downloaded
and applied on the next restart. Trust is anchored by the bundled root.json;
the private signing keys never ship - they stay with the maintainer.

Any failure here (offline, host down, bad metadata) is swallowed: updates must
never crash or block the app.
"""

import os
import sys
import shutil
import threading
from pathlib import Path

from . import config
from .models import logline
from . import __version__

APP_NAME = "CrySence"
METADATA_BASE_URL = "https://saitaskar.github.io/crysence/metadata/"
TARGET_BASE_URL = "https://saitaskar.github.io/crysence/targets/"


def _run():
    if not getattr(sys, "frozen", False):
        return  # only the packaged app updates itself
    try:
        from tufup.client import Client
    except Exception:
        return

    install_dir = Path(sys.executable).parent
    metadata_dir = Path(config.DATA) / "metadata"
    target_dir = Path(config.DATA) / "targets"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Seed the trust anchor (bundled, public) on first run.
    trusted = metadata_dir / "root.json"
    seed = Path(config.resource_dir()) / "root.json"
    if not trusted.exists():
        if not seed.exists():
            return
        shutil.copy(seed, trusted)

    try:
        client = Client(
            app_name=APP_NAME, app_install_dir=install_dir,
            current_version=__version__, metadata_dir=metadata_dir,
            metadata_base_url=METADATA_BASE_URL, target_dir=target_dir,
            target_base_url=TARGET_BASE_URL)
        new = client.check_for_updates()
        if new:
            logline(f"update available: {new}")
            # Downloads and stages the swap; it applies when the app exits.
            client.download_and_apply_update(skip_confirmation=True)
    except Exception as e:
        logline("update check failed: " + repr(e))


def check_in_background():
    threading.Thread(target=_run, daemon=True).start()
