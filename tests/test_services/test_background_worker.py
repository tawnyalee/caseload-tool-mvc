import queue
import threading

import pytest

from src.services.background_worker import BackgroundWorker, UiDispatcher


def _make_worker():
    """A worker whose callbacks land in a queue the test can wait on (no Tk)."""
    delivered = queue.Queue()
    worker = BackgroundWorker(dispatch=lambda fn, value: delivered.put((fn, value)), thread_setup=lambda: None)
    return worker, delivered


def _next(delivered):
    fn, value = delivered.get(timeout=5)
    fn(value)
    return value


def test_work_runs_on_the_background_thread_and_result_is_delivered():
    worker, delivered = _make_worker()
    seen = {}

    def work():
        seen["thread"] = threading.current_thread().name
        return 42

    worker.submit(work, on_done=lambda r: seen.setdefault("done", r), on_error=lambda e: None)
    _next(delivered)

    assert seen == {"thread": "BackgroundWorker", "done": 42}
    worker.stop()


def test_an_exception_goes_to_on_error_not_on_done():
    worker, delivered = _make_worker()
    seen = {}

    def work():
        raise RuntimeError("Outlook did not respond")

    worker.submit(work, on_done=lambda r: seen.setdefault("done", r), on_error=lambda e: seen.setdefault("error", str(e)))
    _next(delivered)

    assert seen == {"error": "Outlook did not respond"}
    worker.stop()


def test_every_job_runs_on_the_same_single_thread():
    # Outlook connections only work on the thread that made them.
    worker, delivered = _make_worker()
    threads = []
    for _ in range(3):
        worker.submit(lambda: threads.append(threading.get_ident()), on_done=lambda r: None, on_error=lambda e: None)
    for _ in range(3):
        _next(delivered)

    assert len(set(threads)) == 1
    assert threads[0] != threading.get_ident()
    worker.stop()


def test_busy_while_a_job_is_running_and_clear_after():
    worker, delivered = _make_worker()
    release = threading.Event()
    started = threading.Event()

    def work():
        started.set()
        release.wait(5)

    worker.submit(work, on_done=lambda r: None, on_error=lambda e: None)
    started.wait(5)
    assert worker.busy
    release.set()
    _next(delivered)
    assert not worker.busy
    worker.stop()


class _FakeRoot:
    """Stands in for Tk's root: after() just records the scheduled poll."""
    def __init__(self):
        self.scheduled = []

    def after(self, ms, fn):
        self.scheduled.append(fn)


def test_dispatcher_runs_calls_from_other_threads_on_the_polling_thread():
    root = _FakeRoot()
    dispatcher = UiDispatcher(root)
    ran_on = []

    t = threading.Thread(target=lambda: dispatcher.call_soon(lambda x: ran_on.append((x, threading.get_ident())), "hi"))
    t.start()
    t.join()
    assert ran_on == []  # nothing runs until the UI thread polls

    root.scheduled.pop(0)()  # simulate Tk's after() firing on this (UI) thread

    assert ran_on == [("hi", threading.get_ident())]
    assert len(root.scheduled) == 1  # it re-schedules itself


def test_dispatcher_keeps_going_after_a_failing_call(capsys):
    root = _FakeRoot()
    dispatcher = UiDispatcher(root)
    ran = []
    dispatcher.call_soon(lambda: 1 / 0)
    dispatcher.call_soon(lambda: ran.append("second"))

    root.scheduled.pop(0)()

    assert ran == ["second"]
    assert len(root.scheduled) == 1
