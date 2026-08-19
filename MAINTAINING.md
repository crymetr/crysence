# Maintaining CrySence

## Cutting a release (this is the whole flow)

1. Bump the version in **two** places:
   - `__version__` in `crysence/__init__.py`
   - `AppVersion` in `installer/crysence.iss`
2. Commit, then tag and push:
   ```
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```
3. GitHub Actions (`.github/workflows/release.yml`) builds the app, compiles the
   per-user Inno installer, packages a portable zip, and attaches both to the
   GitHub Release. Done.

## How auto-update works

Packaged builds check `https://api.github.com/repos/saitaskar/crysence/releases/latest`
on startup (background, non-blocking). If the latest tag is newer than the
running `__version__`, the app downloads the release's `CrySence-Setup-*.exe`
into `%LOCALAPPDATA%\CrySence\updates\`, shows a toast, and adds an
**Install update** item to the tray menu. Clicking it runs the installer
silently (`/VERYSILENT`); the installer closes the running app, replaces it, and
relaunches into the tray (`CloseApplications=yes` + a `WizardSilent` relaunch in
`installer/crysence.iss`).

No servers, keys, or GitHub Pages to manage - releasing is just a tag push, the
same as the installer flow above. Nothing about the update path needs secrets.
