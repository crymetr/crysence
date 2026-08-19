# CrySence

Webcam presence lock for Windows that knows **you** from everyone else. It locks
when you leave, dims when someone's hovering, and captures + alerts you if an
unknown face gets close to your screen. It steps aside automatically for video
calls. Everything runs **locally** — no cloud, no account, no telemetry.

> Not a real product yet — early, works, and being hardened toward a clean
> release. Contributions and issues welcome.

## What it does

- **Knows your face.** Enroll once; it tells you apart from anyone else
  (OpenCV YuNet detection + SFace recognition, both local ONNX models).
- **Layered locking:**
  - *Soft cover* — when you step away or someone lingers nearby, a full-screen
    cover drops and lifts itself the moment it recognizes you again (no
    password). While it's up it blocks the common escape hotkeys.
  - *Hard lock* — a stranger close to your screen, or a long absence, triggers a
    real Windows lock.
- **Intruder capture + alert.** An unknown face close to your screen is
  photographed and clipped locally, and an alert is sent through whatever
  channels you enabled (Windows toast + optional email / push).
- **Meeting-aware.** When another app uses your microphone or webcam (Teams,
  Zoom, a browser call), CrySence releases the camera and pauses, then resumes
  when the call ends. Muting mid-call won't yank the camera back.
- **Keyboard-glance safe.** Looking down at your keyboard reads as "still you,"
  so it won't lock in your face.

## Privacy

CrySence is built to be trustworthy:

- **100% local.** Face models, matching, and captures never leave your machine.
- **No telemetry, no account, no network calls** — except the alert channels
  *you* explicitly configure.
- **Your face** is stored only as a numeric embedding (`owner_face.npy`), not as
  images.
- **No secrets in this repo.** All configuration and credentials live under
  `%LOCALAPPDATA%\CrySence\config.json`, which is never committed.
- Captured intruder photos/clips stay in `%LOCALAPPDATA%\CrySence\captures\`.

**Honest limit:** the soft cover is privacy, not security — it can be killed via
Ctrl+Alt+Del → Task Manager (which no user app can block). The *hard* Windows
lock is the real thing.

## Install (from source, for now)

```
python -m pip install opencv-python-headless numpy pillow winotify pystray
python -m crysence
```

A tray icon appears. Right-click → **Open window** → pick your camera →
**Enroll my face** → **Start guarding**. Close the window; it keeps running in
the tray.

(A signed installer with auto-update is on the roadmap — see below.)

## Alerts

Windows toast is always on. For alerts that reach you when you're away from the
PC, enable one or more channels in `%LOCALAPPDATA%\CrySence\config.json`
(copy the shape from [`config.example.json`](config.example.json)):

- **SMTP email** — works with any provider. For Gmail, create an
  [App Password](https://support.google.com/accounts/answer/185833) (a normal
  password won't work) and use `smtp.gmail.com` / port `587`.
- **ntfy** — the simplest: pick an unguessable topic, install the
  [ntfy app](https://ntfy.sh/) on your phone, subscribe to that topic. No
  account needed; self-hostable.
- **Telegram** — create a bot via @BotFather, put its token and your chat id in.
- **Resend** — if you already have a verified domain and API key.

Only fill in what you use; leave the rest `"enabled": false`. Nothing is sent
anywhere you didn't set up.

## Settings (tune in the window, saved to `config.json`)

| Setting | Meaning | Default |
|---|---|---|
| Soft dim after (s) | Seconds not present before a soft cover | 15 |
| Recognize | Match score to count as "you" (raise to be stricter) | 0.50 |
| Stranger close (hard lock) | How big a stranger's face means "at your screen" | 0.30 |
| Layered | Soft cover first, then hard lock (off = Windows lock only) | on |

## Roadmap

- [ ] Modern themed GUI + first-run setup wizard
- [ ] Signed auto-update (tufup) + Inno Setup installer (per-user, no admin)
- [ ] GitHub Actions release pipeline

## Credits

Face models from the [OpenCV Zoo](https://github.com/opencv/opencv_zoo):
YuNet (detection) and SFace (recognition).

## License

MIT — see [LICENSE](LICENSE).
