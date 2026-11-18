# src/services/keep_awake.py
"""Keeps the laptop awake, with its screen on, while a run is going
(developer, 2026-11-18).

Why the screen too: on a Modern Standby laptop (the developer's is one),
turning the screen off already puts Windows into a standby that freezes
desktop programs. A live run stalled 40 minutes on one student that way:
IT's 15-minute screensaver locked the laptop, the lock screen turned the
screen off a minute later, and the run froze with no error. Every step
gives up after about 2 minutes, so a stall with no timeout means frozen,
not stuck.

SetThreadExecutionState is the standard Windows call that presentation
and video apps use. The request belongs to the calling thread and lasts
until it's reset, so `keep_awake()` is used on the thread doing the run
(the BackgroundWorker). It can't stop IT's screensaver from coming on, and
an IT power policy may still override it; `powercfg /requests` during a
run shows whether Windows sees the request. Outside Windows it does
nothing, and it never raises: a run must never fail over this.
"""
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

KEEP_AWAKE = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
RELEASE = ES_CONTINUOUS


def _windows_call() -> Optional[Callable[[int], int]]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        return ctypes.windll.kernel32.SetThreadExecutionState
    except Exception:
        return None


@contextmanager
def keep_awake(set_state: Optional[Callable[[int], int]] = None) -> Iterator[bool]:
    """While inside, Windows keeps this computer awake with the screen on.
    Yields whether Windows accepted the request. `set_state` is for tests."""
    call = set_state if set_state is not None else _windows_call()
    accepted = False
    if call is not None:
        try:
            accepted = bool(call(KEEP_AWAKE))  # 0 means it was refused
        except Exception:
            accepted = False
    try:
        yield accepted
    finally:
        if call is not None:
            try:
                call(RELEASE)
            except Exception:
                pass
