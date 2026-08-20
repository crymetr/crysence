"""The guard engine: owns the camera and all detection / escalation logic.
Runs on its own thread, independent of any window."""

import os
import time
import threading

import cv2
import numpy as np

from . import config, models, notify
from .models import logline

DETECT_EVERY = 0.4
ENROLL_SAMPLES = 20


def _num(v, default):
    """Coerce a config value to float, falling back on garbage/None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _blank(frame):
    """A near-black frame means the webcam is asleep / powered down (common with
    USB power management on laptops), not that the user is absent."""
    try:
        return float(frame.mean()) < 8.0
    except Exception:
        return False


class Engine(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_evt = threading.Event()
        self.cfg = config.load_config()
        s = self.cfg["settings"]

        self.cap = None
        self.cam_index = s.get("cam_index")
        self.detector = None
        self.det_size = None
        self.recognizer = models.make_recognizer()
        self.owner_feats = self._load_owner()

        self.grace = _num(s.get("grace"), 15.0)
        self.threshold = _num(s.get("threshold"), 0.50)
        self.min_frac = _num(s.get("min_frac"), 0.30)
        self.guarding = bool(s.get("guarding", False))
        self.lock_mode = ("screen" if s.get("lock_mode") == "screen"
                          else "layered")

        self.manual_pause = False
        self.meeting_paused = False
        self.free_since = 0.0
        self.covered = False
        self.known_streak = 0
        self.mode = "idle"
        self.enroll_feats = []
        self.latest_frame = None
        self.latest_scored = []
        self.status = "starting"
        self.state = "idle"
        self.on_state = None
        self.on_cover = None

        self.last_detect = 0.0
        self.last_seen = time.time()
        self.last_known = 0.0
        self.unknown_streak = 0
        self.close_streak = 0       # consecutive frames a stranger is "close"
        self._cam_dirty = False     # UI requested a camera switch

    def _load_owner(self):
        if not os.path.exists(config.OWNER_PATH):
            return None
        try:
            return np.load(config.OWNER_PATH)
        except Exception as e:
            logline("owner_face load failed (corrupt?): " + repr(e))
            return None

    def _save_owner(self, feats):
        arr = np.array(feats, dtype=np.float32)
        tmp = config.OWNER_PATH + ".tmp.npy"
        np.save(tmp, arr)
        os.replace(tmp, config.OWNER_PATH)

    def request_cam(self, idx):
        """Called from the UI thread: switch camera without touching the
        device here (the engine thread releases/reopens on its next cycle)."""
        self.cam_index = idx
        self._cam_dirty = True

    # ---- persistence ----------------------------------------------------
    def save(self):
        self.cfg["settings"].update({
            "cam_index": self.cam_index, "grace": self.grace,
            "threshold": self.threshold, "min_frac": self.min_frac,
            "guarding": self.guarding, "lock_mode": self.lock_mode})
        config.save_config(self.cfg)

    # ---- helpers --------------------------------------------------------
    def set_state(self, s):
        if s != self.state:
            self.state = s
            if self.on_state:
                self.on_state(s)

    def release_cam(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def open_cam(self):
        self.release_cam()
        if self.cam_index is None:
            cams = models.probe_cameras()
            self.cam_index = cams[0] if cams else None
        if self.cam_index is None:
            return False
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        self.det_size = None
        return self.cap.isOpened()

    def ensure_detector(self, w, h):
        if self.det_size != (w, h):
            self.detector = models.make_detector((w, h))
            self.detector.setInputSize((w, h))
            self.det_size = (w, h)

    def score_face(self, frame, f):
        aligned = self.recognizer.alignCrop(frame, f)
        feat = self.recognizer.feature(aligned)
        best = max(
            self.recognizer.match(feat, ref.reshape(1, -1),
                                  cv2.FaceRecognizerSF_FR_COSINE)
            for ref in self.owner_feats)
        return feat, best

    def start_enroll(self):
        self.enroll_feats = []
        self.mode = "enroll"

    # ---- main loop ------------------------------------------------------
    def run(self):
        while not self.stop_evt.is_set():
            try:
                self._cycle()
            except Exception as e:
                logline("engine error: " + repr(e))
                self.stop_evt.wait(1.0)
        self.release_cam()

    def _detect(self, frame):
        _, faces = self.detector.detect(frame)
        scored = []
        if faces is not None and self.owner_feats is not None:
            for f in faces:
                _, best = self.score_face(frame, f)
                scored.append((f, float(best)))
        self.latest_scored = scored
        return faces, scored

    def _drop_cover(self):
        """Lift the soft cover without treating it as a recognition."""
        if self.covered:
            self.covered = False
            self.known_streak = 0
            if self.on_cover:
                self.on_cover(False)

    def _cycle(self):
        now = time.time()

        # Apply a pending camera switch here, on the engine thread, so the UI
        # never releases the device while we're inside cap.read().
        if self._cam_dirty:
            self._cam_dirty = False
            self.release_cam()

        # Anything that should stop us guarding also drops a soft cover.
        interrupted = (self.manual_pause or not self.guarding
                       or models.mic_in_use()
                       or models.camera_in_use_by_others())
        if self.covered and interrupted:
            self._drop_cover()

        if self.covered:
            if self.cap is None and not self.open_cam():
                self.last_seen = now
                self.stop_evt.wait(0.5)
                return
            ok, frame = self.cap.read()
            if not ok or _blank(frame):
                # camera asleep: keep the cover, but don't let it hard-lock
                self.last_seen = now
                self.stop_evt.wait(0.5)
                return
            self.latest_frame = frame
            h, w = frame.shape[:2]
            self.ensure_detector(w, h)
            if now - self.last_detect >= DETECT_EVERY:
                self.last_detect = now
                _, scored = self._detect(frame)
                self._guard_step(frame, scored, now, w)
            self.stop_evt.wait(0.03)
            return

        if self.manual_pause:
            self.release_cam()
            self.set_state("paused")
            self.status = "paused (manual)"
            self.last_seen = now
            self.meeting_paused = False
            self.free_since = 0.0
            self.stop_evt.wait(1.0)
            return

        if models.mic_in_use() or models.camera_in_use_by_others():
            self.meeting_paused = True
            self.free_since = 0.0
        elif self.meeting_paused:
            if self.free_since == 0.0:
                self.free_since = now
            elif now - self.free_since >= models.RESUME_HYSTERESIS:
                self.meeting_paused = False
                self.free_since = 0.0
                logline("meeting over, resuming")
        if self.meeting_paused:
            self.release_cam()
            self.set_state("paused")
            self.status = "paused - meeting (mic/camera in use)"
            self.last_seen = now
            self.stop_evt.wait(1.0)
            return

        if self.cap is None and not self.open_cam():
            self.last_seen = now  # freeze absence: no camera != user away
            self.set_state("paused")
            self.status = "camera unavailable"
            self.stop_evt.wait(1.0)
            return

        ok, frame = self.cap.read()
        if not ok or _blank(frame):
            # Webcam asleep / powered down (USB power management), not absence.
            # Freeze the absence timer so it can't false-lock.
            if not ok:
                self.release_cam()
            self.last_seen = now
            self.set_state("paused")
            self.status = "camera unavailable (asleep?)"
            self.stop_evt.wait(1.0)
            return

        self.latest_frame = frame
        h, w = frame.shape[:2]
        self.ensure_detector(w, h)
        if now - self.last_detect >= DETECT_EVERY:
            self.last_detect = now
            faces, scored = self._detect(frame)
            if self.mode == "enroll":
                self._enroll_step(frame, faces)
            elif self.guarding:
                self._guard_step(frame, scored, now, w)
            else:
                self.set_state("idle")
                self.status = "idle (not guarding)"
        self.stop_evt.wait(0.03)

    def _enroll_step(self, frame, faces):
        if faces is None or len(faces) == 0:
            self.status = (f"enroll: show your face "
                           f"({len(self.enroll_feats)}/{ENROLL_SAMPLES})")
            self.set_state("enroll")
            return
        f = max(faces, key=lambda a: a[2] * a[3])
        aligned = self.recognizer.alignCrop(frame, f)
        feat = self.recognizer.feature(aligned)
        self.enroll_feats.append(feat[0].copy())
        self.set_state("enroll")
        self.status = f"enroll: {len(self.enroll_feats)}/{ENROLL_SAMPLES}"
        if len(self.enroll_feats) >= ENROLL_SAMPLES:
            self._save_owner(self.enroll_feats)
            self.owner_feats = self._load_owner()
            self.mode = "idle"
            self.status = "enroll done - face saved"
            logline("enrolled owner face")

    def _guard_step(self, frame, scored, now, w):
        thr, margin = self.threshold, models.INTRUDER_MARGIN
        hard_frac = self.min_frac
        soft_frac = self.min_frac * models.SOFT_NEAR_RATIO
        known = maybe_you = False
        su_frac = 0.0
        for f, best in scored:
            if best >= thr:
                known = True
            elif best >= thr - margin:
                maybe_you = True
            else:
                su_frac = max(su_frac, f[2] / w)

        if known:
            self.last_known = now
        # "maybe you" only counts as present if you were confidently seen
        # recently (e.g. a keyboard glance). A look-alike who is never confidently
        # matched will NOT keep the session alive forever.
        present = known or (maybe_you
                            and now - self.last_known < models.MAYBE_GRACE)
        if present:
            self.last_seen = now
        absence = now - self.last_seen

        stranger_ok = known or (now - self.last_known > models.OWNER_GRACE)
        # Hysteresis: a stranger must persist several frames before we act, so a
        # single false-positive detection can't hard-lock the machine.
        if stranger_ok and su_frac >= soft_frac:
            self.close_streak += 1
        else:
            self.close_streak = 0
        confirmed = self.close_streak >= models.CONSEC_UNKNOWN
        stranger_close = confirmed and su_frac >= hard_frac
        stranger_near = confirmed and su_frac >= soft_frac
        layered = self.lock_mode == "layered"

        if self.covered:
            if stranger_close:
                logline(f"HARD from cover: stranger close ({su_frac:.2f})")
                self._hard_lock("intruder", frame.copy(), from_cover=True)
            elif absence >= models.HARD_ABSENCE:
                logline(f"HARD from cover: away {absence:.0f}s")
                self._hard_lock("absence", frame.copy(), from_cover=True)
            elif known:
                self.known_streak += 1
                if self.known_streak >= 2:
                    self._uncover(now)
                else:
                    self.status = "soft cover - recognizing you..."
            else:
                self.known_streak = 0
                self.status = f"soft cover (away {absence:.0f}s)"
                self.set_state("alert")
            return

        if stranger_close:
            logline(f"HARD: stranger close ({su_frac:.2f}) known={known}")
            self._hard_lock("intruder", frame.copy())
            return

        if not present and (absence >= self.grace or stranger_near):
            reason = "intruder" if stranger_near else "absence"
            if layered:
                self._soft_cover(now, reason, su_frac)
            else:
                self._hard_lock(reason, frame.copy())
            return

        self.set_state("guard")
        self.status = ("guarding - present" if present
                       else f"guarding - away {absence:.0f}s")

    def _soft_cover(self, now, reason, su_frac):
        self.covered = True
        self.known_streak = 0
        self.set_state("alert")
        self.status = "soft cover"
        if self.on_cover:
            self.on_cover(True)
        logline(f"SOFT cover ({reason}, stranger={su_frac:.2f})")

    def _uncover(self, now):
        self.covered = False
        self.known_streak = 0
        if self.on_cover:
            self.on_cover(False)
        self.last_seen = now
        self.last_known = now
        self.set_state("guard")
        self.status = "guarding - present"
        logline("owner recognized - soft cover lifted")

    def _hard_lock(self, reason, frame, from_cover=False):
        # Lock FIRST - the screen must be secured before we spend any time on
        # evidence, and it must happen even if capture below raises.
        self.set_state("alert")
        self.status = "LOCKED (Windows)"
        try:
            models.lock_workstation()
        finally:
            if from_cover:
                self.covered = False
                if self.on_cover:
                    self.on_cover(False)

        # Now that the desktop is locked, capture the intruder (camera is still
        # held) and send alerts. Failures here never leave the screen unlocked.
        if reason == "intruder":
            try:
                self._capture_intruder(frame)
            except Exception as e:
                logline("capture failed: " + repr(e))

        self.release_cam()
        self.close_streak = 0
        end = time.time() + models.COOLDOWN_AFTER_LOCK
        while time.time() < end and not self.stop_evt.is_set():
            self.stop_evt.wait(0.5)
        self.last_seen = time.time()
        self.unknown_streak = 0

    def _capture_intruder(self, frame):
        os.makedirs(config.CAPTURES_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        photo = os.path.join(config.CAPTURES_DIR, f"intruder_{stamp}.jpg")
        clip = os.path.join(config.CAPTURES_DIR, f"intruder_{stamp}.mp4")
        cv2.imwrite(photo, frame)
        h, w = frame.shape[:2]
        writer = cv2.VideoWriter(clip, cv2.VideoWriter_fourcc(*"mp4v"),
                                 12, (w, h))
        end = time.time() + models.CLIP_SECONDS
        while time.time() < end:
            cap = self.cap
            if cap is None:
                break
            ok, f2 = cap.read()
            if ok:
                writer.write(f2)
        writer.release()
        when = time.strftime("%Y-%m-%d %H:%M:%S")
        notify.send(self.cfg["notifications"],
                    "CrySence: unknown face at your PC",
                    f"An unknown face was close to your screen at {when}. "
                    f"The PC was locked. Video clip: {clip}", photo)

    def stop(self):
        self.stop_evt.set()
