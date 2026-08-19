"""One-time: initialize the tufup update repository and signing keys.

Produces:
  keystore/   - PRIVATE signing keys (gitignored; BACK THESE UP, never lose or
                commit them - they are the root of update trust).
  tufrepo/    - the update repository (metadata/ + targets/) to publish to
                GitHub Pages.
  crysence/data/root.json - the PUBLIC trust anchor bundled into the app.

Run once, after building dist/CrySence:
    python tools/tuf_init.py
"""

import shutil
from pathlib import Path

from tufup.repo import Repository

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "keystore"
REPO = ROOT / "tufrepo"
BUNDLE = ROOT / "dist" / "CrySence"
VERSION = "0.1.0"


def main():
    if not (BUNDLE / "CrySence.exe").exists():
        raise SystemExit(f"Build first: {BUNDLE}\\CrySence.exe not found "
                         "(run python tools/build.py).")
    repo = Repository(app_name="CrySence", repo_dir=REPO, keys_dir=KEYS)
    repo.initialize()
    repo.add_bundle(new_bundle_dir=BUNDLE, new_version=VERSION)
    repo.publish_changes(private_key_dirs=[KEYS])

    meta = REPO / "metadata"
    root = meta / "root.json"
    if not root.exists():
        cands = sorted(meta.glob("*.root.json"))
        if cands:
            root = cands[-1]
    dest = ROOT / "crysence" / "data" / "root.json"
    shutil.copy(root, dest)
    print("initialized. trust anchor ->", dest)
    print("BACK UP the keystore/ directory. Publish tufrepo/ to GitHub Pages.")


if __name__ == "__main__":
    main()
