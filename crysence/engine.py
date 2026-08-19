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
        self.owner_feats = (np.load(config.OWNER_PATH)
                            if os.path.exists(config.OWNER_PATH) else None)

        self.grace = float(s.get("grace", 15))
        self.threshold = float(s.get("threshold", 0.5))
        self.min_frac = float(s.get("min_frac", 0.30))
        self.guarding = bool(s.get("guarding", False))
        self.lock_mode = s.get("lock_mode", "layered")

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

    def _cycle(self):
        now = time.time()

        if self.covered:
            if self.cap is None and not self.open_cam():
                self.stop_evt.wait(0.5)
                return
            ok, frame = self.cap.read()
            if not ok:
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
            self.status = "no camera / camera busy"
            self.stop_evt.wait(1.0)
            return

        ok, frame = self.cap.read()
        if not ok:
            self.release_cam()
            self.status = "camera busy"
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
            np.save(config.OWNER_PATH, np.array(self.enroll_feats,
                                                dtype=np.float32))
            self.owner_feats = np.load(config.OWNER_PATH)
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
        present = known or maybe_you
        if present:
            self.last_seen = now
        absence = now - self.last_seen

        stranger_ok = known or (now - self.last_known > models.OWNER_GRACE)
        stranger_close = stranger_ok and su_frac >= hard_frac
        stranger_near = stranger_ok and su_frac >= soft_frac
        layered = self.lock_mode == "layered"

        if self.covered:
            if stranger_close:
                logline(f"HARD from cover: stranger close ({su_frac:.2f})")
                self._hard_lock("intruder", frame.copy(), from_cover=True)
            elif absence >= models.HARD_ABSENCE:
                logline(f"HARD from cover: away {absence:.0f}s")
                self._hard_lock("absence", frame.copy(), from_cover=True)
            elif present and not stranger_near:
                self.known_streak = self.known_streak + 1 if known else 0
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
        self.set_state("alert")
        if from_cover:
            self.covered = False
            if self.on_cover:
                self.on_cover(False)

        if reason == "intruder":
            os.makedirs(config.CAPTURES_DIR, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            photo = os.path.join(config.CAPTURES_DIR, f"intruder_{stamp}.jpg")
            clip = os.path.join(config.CAPTURES_DIR, f"intruder_{stamp}.mp4")
            cv2.imwrite(photo, frame)
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(clip, cv2.VideoWriter_fourcc(*"mp4v"),
                                     12, (w, h))
            end = time.time() + models.CLIP_SECONDS
            while time.time() < end and self.cap is not None:
                ok, f2 = self.cap.read()
                if ok:
                    writer.write(f2)
            writer.release()
            when = time.strftime("%Y-%m-%d %H:%M:%S")
            notify.send(self.cfg["notifications"],
                        "CrySence: unknown face at your PC",
                        f"An unknown face was close to your screen at {when}. "
                        f"The PC was locked. Video clip: {clip}", photo)

        self.status = "LOCKED (Windows)"
        models.lock_workstation()
        self.release_cam()
        end = time.time() + models.COOLDOWN_AFTER_LOCK
        while time.time() < end and not self.stop_evt.is_set():
            self.stop_evt.wait(0.5)
        self.last_seen = time.time()
        self.unknown_streak = 0

    def stop(self):
        self.stop_evt.set()
