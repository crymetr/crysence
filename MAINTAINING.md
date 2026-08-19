# Maintaining CrySence

## Signing keys (read this first)

`tools/tuf_init.py` created `keystore/` with the private update-signing keys
(root / targets / snapshot / timestamp). These are the root of update trust.

- **Back up `keystore/` somewhere safe and offline. Never commit or lose it.**
  Losing the root key means you can never ship a trusted update again (clients
  would have to reinstall from a fresh download).
- `keystore/` and `tufrepo/` are gitignored. Only the **public** trust anchor
  `crysence/data/root.json` and `.tufup-repo-config` are committed.

## Cutting a release

1. Bump `__version__` in `crysence/__init__.py` and the version in
   `installer/crysence.iss`.
2. Tag it: `git tag vX.Y.Z && git push origin vX.Y.Z`.
   GitHub Actions builds `CrySence-Setup-X.Y.Z.exe` (Inno) and a portable zip
   and attaches them to the GitHub Release. Users can install from there.

## Enabling signed auto-update (tufup)

The app checks `https://saitaskar.github.io/crysence/` for signed updates. To
publish one after a build:

1. Build: `python tools/build.py` (produces `dist/CrySence`).
2. Add + sign the bundle: `python tools/tuf_release.py X.Y.Z`
   (needs the restored `keystore/`).
3. Publish `tufrepo/` to GitHub Pages so `metadata/` and `targets/` are served
   at the site root (a `gh-pages` branch, or `docs/` on `main`, whichever you
   configure in the repo's Pages settings).

Clients running a build that bundles `root.json` (v0.2.0+) will then pick up the
new version on next launch and apply it on restart. The very first tufup-served
version must itself bundle `root.json` and the updater (already wired in
`crysence/updater.py`).

> Note: target bundles are large (~110 MB full; subsequent versions are patches
> if `binary_diff` is enabled). GitHub Pages serves them, but watch bandwidth.
