# src/services/background_worker.py
"""Runs slow work (sending, writing notes, loading the roster) off the UI
thread, so the window keeps responding during a run.

Two pieces:

  - UiDispatcher: Tk widgets may only be touched from the main (UI)
    thread. Background code calls dispatcher.call_soon(fn, ...) instead of
    touching the UI; the main thread picks those calls up every 50 ms.
    queue.Queue is thread-safe, so this is the one safe hand-off point.

  - BackgroundWorker: ONE long-lived background thread that runs jobs one
    at a time. One thread (not a new one per run) on purpose: Outlook's
    COM automation must be set up per thread (CoInitialize) and an
    Outlook connection only works on the thread that created it -
    OutlookEmailSender keeps its connection between sends, so every send
    has to happen on the same thread.
"""
import queue
import threading
from typing import Any, Callable, Optional


class UiDispatcher:
    POLL_MS = 50

    def __init__(self, root):
        self._root = root
        self._calls: "queue.Queue[tuple]" = queue.Queue()
        self._root.after(self.POLL_MS, self._drain)

    def call_soon(self, fn: Callable, *args) -> None:
        """Safe from any thread: runs fn(*args) on the UI thread shortly."""
        self._calls.put((fn, args))

    def _drain(self) -> None:
        while True:
            try:
                fn, args = self._calls.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception as exc:  # one bad UI update must not stop the pump
                print(f"[UiDispatcher] {exc!r}")
        self._root.after(self.POLL_MS, self._drain)


def _init_com_for_this_thread() -> None:
    try:
        import pythoncom  # part of pywin32
        pythoncom.CoInitialize()
    except ImportError:
        pass  # not on Windows / no pywin32 - nothing COM-based will run anyway


class BackgroundWorker:
    def __init__(self, dispatch: Callable[..., None], thread_setup: Callable[[], None] = _init_com_for_this_thread):
        """`dispatch` delivers the finished/failed callbacks - normally
        UiDispatcher.call_soon, so they run on the UI thread."""
        self._dispatch = dispatch
        self._jobs: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._busy = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(thread_setup,), name="BackgroundWorker", daemon=True)
        self._thread.start()

    @property
    def busy(self) -> bool:
        return self._busy.is_set()

    def submit(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Queues `work` for the background thread. Exactly one of on_done
        (with work's return value) or on_error (with the exception) is then
        delivered through `dispatch`."""
        self._busy.set()
        self._jobs.put((work, on_done, on_error))

    def stop(self) -> None:
        self._jobs.put(None)

    def _loop(self, thread_setup: Callable[[], None]) -> None:
        thread_setup()
        while True:
            job = self._jobs.get()
            if job is None:
                return
            work, on_done, on_error = job
            try:
                result = work()
            except BaseException as exc:
                self._finish(on_error, exc)
            else:
                self._finish(on_done, result)

    def _finish(self, callback: Callable, value: Any) -> None:
        if self._jobs.empty():
            self._busy.clear()
        self._dispatch(callback, value)
