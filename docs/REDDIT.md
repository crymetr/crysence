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

I work in an open office. I wanted my screen to stay private without me having to
think about it, and honestly because I kept getting up and forgetting to lock my
PC. (Windows Hello is turned off on this machine and never worked the way I wanted
anyway.)

Normal auto-lock timers don't really fix this. They lock while you're sitting
there reading, and they stay open for a while after you walk off. So I made a lock
that watches whether you're actually there instead.

It uses the webcam to tell me apart from everyone else. Two small models run
locally (OpenCV YuNet to find faces, SFace to recognize them), nothing goes to
the cloud:

- You walk away and the screen dims (a soft cover). It lifts itself the second it
  sees your face again. No password.
- If you're gone a while, or a stranger leans in toward the screen, it does a
  real Windows lock, snaps a photo, and pings you.
- If you hop on a Teams or Zoom call, it hands the camera over and pauses on its
  own, then comes back after.

**Privacy:** everything stays on your machine. No cloud, no account, no tracking.
The only times it touches the internet are one update check to GitHub and
whatever alert you set up yourself (email, phone push, and so on), and you can
read those parts in the source. Your face is saved as a bunch of numbers, not a
photo. Don't want to trust a program that watches your camera? Run it straight
from the source code, it's about 1,000 lines of Python.

**Being honest about the limits:** the soft cover is for privacy, not real
security. Anyone can still hit Ctrl+Alt+Del and close it, no normal app can stop
that. The real Windows lock is the solid one. There's also no "is this a real
live face" check yet, so a good printed photo of you could trick it for now. Think
of it as a convenience and privacy tool, not something that stops a determined
attacker. All of this is in the README too.

Repo (MIT): https://github.com/saitaskar/crysence

It's early and I'd love feedback, especially on the recognition strictness and any
weird edge cases. What would you want it to do?

---

## Tips
- Reply to early comments fast; Reddit rewards an active OP.
- Expect "unsigned exe" pushback — point them at run-from-source.
- Expect "photo can beat it" — agree, it's in the README, liveness is next.
- A demo GIF in the post itself roughly doubles engagement. Record it first.

---

## r/vibecoding version (build story — rule 3 compliant)

**Title:**

`I vibe-coded a webcam presence lock that knows me from everyone else. Locks when I leave, lets me back in by face, 100% local`

**Body:**

I kept getting up in an open office and forgetting to lock my PC (Windows Hello is
off here and never worked right). Auto-lock timers don't help: they lock while
you're reading and stay open after you leave. So I built one that locks based on
whether you're actually there, with Claude Code over a few evenings. ~1,000 lines
of Python, open source.

**What it does:** the webcam recognizes me (two local models: YuNet finds the
face, SFace matches it). Walk away and the screen dims, then lifts itself the
moment it sees me, no password. Gone longer, or a stranger leans in, and it
hard-locks Windows and snaps a photo. It also pauses itself during Teams/Zoom
calls.

**The parts that were actually work:**

- **Tuning the strictness, not the ML.** Too strict locks in your face when you
  look at the keyboard; too loose lets a coworker count as you. Ended up with a
  "glancing down is still you" grace window and a slider.
- **Pausing during calls:** hand the camera to whatever app grabbed it, take it
  back when the call ends, don't treat a mute as "call over."
- **Best bug:** random locks. Windows was sleeping the webcam to save power, and
  the dropout looked like "nobody's there." Had to tell "no face" apart from
  "no camera."
- **Packaging** (installer, per-user, silent self-update from GitHub) took longer
  than the face recognition did.

**Limits** (also in the README): the soft cover is privacy, not security,
Ctrl+Alt+Del still closes it. And no live-face check yet, so a printed photo can
fool it.

Repo (MIT): https://github.com/saitaskar/crysence. Happy to get into any of it.
