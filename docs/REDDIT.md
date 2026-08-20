# Reddit launch draft

Post to a friendly sub first: **r/coolgithubprojects**, **r/opensource**, or
**r/Python** (Show & Tell). Save r/privacy and r/windows for after it has a demo
and a few users.

> **Sub note:** the draft below is the "project + privacy" pitch — good for
> r/opensource, r/Python, r/coolgithubprojects. **r/vibecoding is different:**
> their rules ban a bare link (rule 3 — must be "here's the project, here's how I
> built it") and their dev-tool approval flow (rule 2) is for vibe-coding
> startups/tools, not a free end-user app like this, so CrySence posts as a
> *project*, not a *tool submission*. Use the **build-story version at the bottom
> of this file** for r/vibecoding.

---

## Title (r/coolgithubprojects format)

`[Python] CrySence - a webcam presence lock for Windows that recognizes you (open source, 100% local)`

Alt title for r/opensource / r/Python:

`CrySence: my webcam presence-lock that knows me from everyone else - locks when I leave, lets me back in by face, all local`

---

## Body

I work in an open office and wanted my screen to stay private without me having
to think about it — and honestly because I kept walking away and forgetting to
lock the PC (Windows Hello is disabled on this machine and never behaved the way
I wanted anyway). Idle-timer locks don't help: they fire while you're reading and
stay open while you're gone. So I built a lock that works on **presence** instead.

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

---

## r/vibecoding version (build story — rule 3 compliant)

**Title:**

`I vibe-coded a webcam presence lock that knows me from everyone else — locks when I leave, lets me back in by face, 100% local`

**Body:**

I work in an open office and kept walking away without locking my PC (Windows
Hello is disabled here and never worked the way I wanted), and I wanted my screen
private by default without thinking about it. Idle-timer locks are useless for
that — they fire while you're reading and stay open while you're gone. So I built
a lock that works on *presence* instead, with Claude Code over a few evenings.
It's ~1k lines of Python and it's open source.

**What it does:** the webcam tells *me* apart from everyone else (OpenCV YuNet
detection + SFace recognition, local ONNX models). Walk away → the screen dims;
it lifts itself the moment it sees me, no password. Gone a while or a stranger
leans in → a real Windows lock + a photo + an alert. On a Teams/Zoom call it
releases the camera and pauses automatically.

**How I built it (the interesting bits):**

- **Recognition** is just two ONNX models wired through OpenCV — detect faces
  with YuNet, embed with SFace, cosine-compare to one enrolled embedding. The
  hard part wasn't the ML, it was **threshold tuning**: too strict and it locks
  in your face when you glance at the keyboard, too loose and a coworker passes.
  I added a "keyboard-glance is still you" grace window and a strictness slider
  instead of pretending one number fits every webcam.
- **Meeting-aware pause** was fiddly — I watch for another process grabbing the
  camera/mic and hand it over, then reclaim it on hang-up, without treating a
  mid-call *mute* as "call ended."
- **Best bug:** it kept false-locking at random. Turned out Windows USB power
  management sleeps the webcam when idle; the dropout read as "you left." Fix
  was distinguishing "no face" from "no camera."
- **Packaging** with a coding agent was the surprise time-sink: PyInstaller +
  a per-user Inno installer + a GitHub Actions release + self-update from GitHub
  Releases. Getting an unsigned per-user app to update itself cleanly took
  longer than the recognition engine did.

**Honest limits** (in the README too): the soft cover is privacy, not security —
Ctrl+Alt+Del still kills any user-mode app. And there's no liveness yet, so a
printed photo could fool recognition. It's a convenience + privacy tool, not
defense against a prepared attacker.

Repo (MIT): https://github.com/saitaskar/crysence — happy to talk through any of
the above, especially how others handle recognition thresholds across different
webcams.
