"""Cut a new signed update: add the freshly built bundle and re-sign metadata.

Usage (after building dist/CrySence for the new version):
    python tools/tuf_release.py 0.2.0

Then publish the updated tufrepo/ (metadata/ + targets/) to GitHub Pages.
Requires the private keystore/ from tuf_init.py.
"""

import sys
from pathlib import Path

from tufup.repo import Repository

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "keystore"
REPO = ROOT / "tufrepo"
BUNDLE = ROOT / "dist" / "CrySence"


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python tools/tuf_release.py <version>")
    version = sys.argv[1].lstrip("v")
    if not (BUNDLE / "CrySence.exe").exists():
        raise SystemExit("Build first: python tools/build.py")
    if not KEYS.exists():
        raise SystemExit("No keystore/. Run tuf_init.py once (and restore your "
                         "backed-up keys).")
    repo = Repository.from_config()
    repo.add_bundle(new_bundle_dir=BUNDLE, new_version=version)
    repo.publish_changes(private_key_dirs=[KEYS])
    print(f"released {version}. Publish tufrepo/ to GitHub Pages.")


if __name__ == "__main__":
    main()
