import sys

import pytest

from src.services import keep_awake as ka


def test_asks_for_awake_with_the_screen_on_then_releases():
    calls = []
    with ka.keep_awake(set_state=lambda flags: calls.append(flags) or 1) as accepted:
        assert accepted is True
        assert calls == [ka.ES_CONTINUOUS | ka.ES_SYSTEM_REQUIRED | ka.ES_DISPLAY_REQUIRED]
    assert calls[-1] == ka.ES_CONTINUOUS  # back to normal settings


def test_releases_even_when_the_run_fails():
    calls = []
    with pytest.raises(RuntimeError):
        with ka.keep_awake(set_state=lambda flags: calls.append(flags) or 1):
            raise RuntimeError("a student failed badly")
    assert calls[-1] == ka.RELEASE


def test_a_refused_or_broken_request_never_stops_a_run():
    with ka.keep_awake(set_state=lambda flags: 0) as accepted:
        assert accepted is False

    def broken(flags):
        raise OSError("no such call")

    with ka.keep_awake(set_state=broken) as accepted:
        assert accepted is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_the_real_windows_call_accepts_the_request():
    with ka.keep_awake() as accepted:
        assert accepted is True
