from datetime import datetime

from src.services.activity_logger import ActivityLogger


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
