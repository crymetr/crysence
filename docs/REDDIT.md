# Reddit launch draft

Post to a friendly sub first: **r/coolgithubprojects**, **r/opensource**, or
**r/Python** (Show & Tell). Save r/privacy and r/windows for after it has a demo
and a few users.

---

## Title (r/coolgithubprojects format)

`[Python] CrySence - a webcam presence lock for Windows that recognizes you (open source, 100% local)`

Alt title for r/opensource / r/Python:

`CrySence: my webcam presence-lock that knows me from everyone else - locks when I leave, lets me back in by face, all local`

---

## Body

I got tired of idle-timer screen locks (they fire while you're reading and stay
open while you're gone), so I built a lock that works on **presence** instead.

It uses the webcam to tell **me** apart from everyone else (OpenCV YuNet + SFace,
local ONNX models):

- Walk away → the screen dims (soft cover); it lifts itself the moment it sees
  me again, no password.
- Gone a while, or a stranger leans toward the screen → a real Windows lock, and
  it snaps a photo + alerts me.
- On a Teams/Zoom call it releases the camera and pauses automatically.

**Privacy:** it's all local. No cloud, no account, no telemetry — the only
network calls are one GitHub update check and whatever alert channel you set up
yourself, and you can read every one of them in the source. Your face is stored
as a numeric embedding, not images. Don't trust a binary that watches your
camera? Run it from source, it's ~1k lines of Python.

**Honest limitations:** the soft cover is privacy, not security (Ctrl+Alt+Del
still works — nothing user-mode can block that). And there's no liveness yet, so
a good printed photo could fool recognition. It's a convenience + privacy tool,
not defense against a prepared attacker. Both are called out in the README.

Repo (MIT): https://github.com/saitaskar/crysence

It's early and I'd love feedback, especially on the recognition thresholds and
edge cases. What would you want it to do?

---

## Tips
- Reply to early comments fast; Reddit rewards an active OP.
- Expect "unsigned exe" pushback — point them at run-from-source.
- Expect "photo can beat it" — agree, it's in the README, liveness is next.
- A demo GIF in the post itself roughly doubles engagement. Record it first.
