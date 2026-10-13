import os
from datetime import date, datetime

from src.services.activity_logger import ActivityLogger, purge_old_logs


def test_log_writes_to_todays_file(tmp_path):
    logger = ActivityLogger(log_dir=str(tmp_path))
    logger.log("Test message")

    today = datetime.now().date().isoformat()
    log_file = tmp_path / f"{today}.log"

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test message" in content


def test_log_forwards_to_ui_callback(tmp_path):
    received = []
    logger = ActivityLogger(log_dir=str(tmp_path), ui_callback=received.append)

    logger.log("Group deleted: Test Group")

    assert len(received) == 1
    assert "Group deleted: Test Group" in received[0]


def test_log_without_callback_does_not_error(tmp_path):
    logger = ActivityLogger(log_dir=str(tmp_path))
    logger.log("No callback registered")  # should not raise


def test_multiple_log_calls_append_to_same_file(tmp_path):
    logger = ActivityLogger(log_dir=str(tmp_path))
    logger.log("First message")
    logger.log("Second message")

    today = datetime.now().date().isoformat()
    content = (tmp_path / f"{today}.log").read_text(encoding="utf-8")

    assert "First message" in content
    assert "Second message" in content


TODAY = date(2026, 10, 13)


def _set_mtime(path, day):
    stamp = datetime(day.year, day.month, day.day, 12).timestamp()
    os.utime(path, (stamp, stamp))


def test_purge_deletes_only_log_files_from_before_today(tmp_path):
    (tmp_path / "2026-08-05.log").write_text("old")
    (tmp_path / "2026-10-12.log").write_text("yesterday")
    (tmp_path / "2026-10-13.log").write_text("today")

    removed = purge_old_logs(tmp_path, tmp_path / "screenshots", today=TODAY)

    assert removed == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-13.log"]


def test_purge_deletes_only_screenshots_last_modified_before_today(tmp_path):
    shots = tmp_path / "screenshots"
    shots.mkdir()
    old, new = shots / "old.png", shots / "new.png"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    _set_mtime(old, date(2026, 10, 12))
    _set_mtime(new, TODAY)

    removed = purge_old_logs(tmp_path, shots, today=TODAY)

    assert removed == 1
    assert [p.name for p in shots.iterdir()] == ["new.png"]


def test_purge_leaves_files_it_does_not_recognize(tmp_path):
    (tmp_path / "notes.log").write_text("not dated")
    (tmp_path / "readme.txt").write_text("not a log")

    assert purge_old_logs(tmp_path, tmp_path / "screenshots", today=TODAY) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["notes.log", "readme.txt"]


def test_purge_handles_missing_folders(tmp_path):
    assert purge_old_logs(tmp_path / "nope", tmp_path / "nope2", today=TODAY) == 0
