# Recording the demo (for the README / Reddit post)

The strongest asset is a short **screen recording** (not a webcam recording) so
the focus is the app: the cover dropping and lifting, the tray, the alert. A
screen capture also keeps your face incidental (small preview box) instead of
front-and-center.

## The clip (aim for 20-30s)

1. **Guarding** — dashboard open, status pill green "guarding - present".
2. **Walk away** — step out of the camera's view. After ~15s the black **soft
   cover** drops ("Locked - look at the camera").
3. **Come back** — lean back in; the cover lifts itself, no password. (This is
   the money shot.)
4. **Stranger** — have a second person lean toward the screen (or hold up a
   different face). Preview shows red **UNKNOWN**, then a **Windows lock** +
   toast alert fires.

Set "Soft dim after" to ~5s in the window first so the demo isn't slow.

## Keeping it faceless (optional, matches your opsec)

Pick one:
- **Angle the webcam** so your face isn't in frame for the away/return beats (the
  cover + tray are the story, not your face).
- **Blur the preview box** in post — record normally, then blur just that region:
  ```
  ffmpeg -i raw.mp4 -filter_complex "[0:v]crop=<w>:<h>:<x>:<y>,boxblur=20[b];[0:v][b]overlay=<x>:<y>" -c:a copy demo.mp4
  ```
  (`<w>:<h>:<x>:<y>` = the preview rectangle on your screen.)
- Or just accept a small preview; it's tasteful and shows the tool actually
  recognizing a face.

## Capture

Windows Game Bar (`Win+G` → record) or OBS, primary monitor, then trim.

## Convert to an optimized GIF (palette method = crisp + small)

```
ffmpeg -i demo.mp4 -vf "fps=12,scale=900:-1:flags=lanczos,palettegen" -y docs/palette.png
ffmpeg -i demo.mp4 -i docs/palette.png -filter_complex "fps=12,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse" -y docs/demo.gif
```
Keep `docs/demo.gif` under ~8 MB so it renders inline on GitHub. Then uncomment
the `![demo](docs/demo.gif)` line in the README.

## Screenshots to grab (faceless)

Save as PNG under `docs/` and drop them into the README:
- `wizard.png` — the setup wizard (welcome or lock-mode step, no camera).
- `dashboard.png` — the main window (cover the lens or use the "away" state so
  there's no face; the teal UI is the point).
- `cover.png` — the full-screen "Locked - look at the camera" cover.
- `tray.png` — the tray menu (Guarding / Pause / Install update / Quit).
