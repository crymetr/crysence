"""Frozen-app entry point (used by PyInstaller)."""

import multiprocessing

if __name__ == "__main__":
    # The camera runs in a child process (camproc); in the frozen exe the
    # child re-launches CrySence.exe and must branch off here, before the UI
    # (and its single-instance check) is even imported.
    multiprocessing.freeze_support()
    from crysence.app import main
    main()
