"""Camera access in a child process.

DirectShow can wedge inside a native call when a webcam vanishes (its monitor
switched off, USB unplugged): VideoCapture() or read() blocks forever and leaks
memory on every retry. Nothing in-process can cancel that. So the camera lives
in a small worker process; every call has a timeout, and a worker that misses
it is killed and a fresh one is spawned on the next call. The app itself never
touches cv2.VideoCapture.
"""

import multiprocessing as mp

from .models import logline

READY_TIMEOUT = 30      # worker start (imports cv2)
OPEN_TIMEOUT = 10
READ_TIMEOUT = 5
PROBE_TIMEOUT = 25
RECYCLE_FAILS = 30      # failed opens before a fresh worker (DShow leaks)


def _worker(conn):
    """Child process: owns at most one open camera, serves commands."""
    import os
    os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
    os.environ.setdefault("OPENCV_VIDEOIO_DEBUG", "0")
    import cv2
    from . import models

    cap = None

    def close():
        nonlocal cap
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
            cap = None

    conn.send("ready")
    try:
        while True:
            cmd = conn.recv()
            op = cmd[0]
            if op == "read":
                try:
                    ok, frame = cap.read() if cap is not None else (False,
                                                                     None)
                except Exception:
                    ok, frame = False, None
                conn.send((bool(ok), frame if ok else None))
            elif op == "open":
                close()
                try:
                    c = cv2.VideoCapture(cmd[1], cv2.CAP_DSHOW)
                    if c.isOpened():
                        cap = c
                    else:
                        c.release()
                except Exception:
                    pass
                conn.send(cap is not None)
            elif op == "release":
                close()
                conn.send(True)
            elif op == "probe":
                close()
                conn.send(models.probe_cameras())
            else:
                break
    except (EOFError, OSError):
        pass            # parent gone
    finally:
        close()


class _Timeout(Exception):
    pass


class CamWorker:
    """Parent side. Use from ONE thread (the engine thread)."""

    def __init__(self):
        self.proc = None
        self.conn = None
        self.open_fails = 0

    def _spawn(self):
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        proc = ctx.Process(target=_worker, args=(child,), daemon=True,
                           name="crysence-camera")
        proc.start()
        child.close()
        self.proc, self.conn = proc, parent
        try:
            if self._recv(READY_TIMEOUT) != "ready":
                raise _Timeout()
        except Exception:
            self.kill("worker did not start")
            raise _Timeout()

    def _recv(self, timeout):
        if not self.conn.poll(timeout):
            raise _Timeout()
        return self.conn.recv()

    def kill(self, why=""):
        if why:
            logline("camera worker restarted: " + why)
        proc, conn = self.proc, self.conn
        self.proc = self.conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if proc is not None:
            try:
                proc.kill()
                proc.join(2)
            except Exception:
                pass

    def call(self, cmd, timeout, default):
        """Send cmd, wait for the answer; on timeout/crash kill the worker and
        return default. Never blocks longer than start + timeout."""
        try:
            if self.proc is None or not self.proc.is_alive():
                if self.proc is not None:
                    self.kill("worker died")
                self._spawn()
            self.conn.send(cmd)
            return self._recv(timeout)
        except _Timeout:
            self.kill(f"'{cmd[0]}' hung >{timeout}s")
        except (EOFError, OSError, BrokenPipeError) as e:
            self.kill(f"'{cmd[0]}' failed: {e!r}")
        return default

    # ---- VideoCapture-ish API -------------------------------------------
    def open(self, index):
        """Returns a Capture on success, else None."""
        if self.call(("open", index), OPEN_TIMEOUT, False):
            self.open_fails = 0
            return Capture(self)
        self.open_fails += 1
        if self.open_fails >= RECYCLE_FAILS and self.proc is not None:
            self.open_fails = 0
            self.kill()     # quietly shed whatever DShow leaked
        return None

    def probe(self):
        return self.call(("probe",), PROBE_TIMEOUT, [])

    def stop(self):
        if self.proc is not None:
            try:
                self.conn.send(("quit",))
            except Exception:
                pass
            self.kill()


class Capture:
    """Handle to the camera currently open in the worker."""

    def __init__(self, worker):
        self.w = worker
        self.proc = worker.proc     # stale once the worker is replaced

    def _live(self):
        return self.w.proc is not None and self.w.proc is self.proc

    def isOpened(self):
        return self._live()

    def read(self):
        if not self._live():
            return False, None
        return self.w.call(("read",), READ_TIMEOUT, (False, None))

    def release(self):
        if self._live():
            self.w.call(("release",), OPEN_TIMEOUT, True)
