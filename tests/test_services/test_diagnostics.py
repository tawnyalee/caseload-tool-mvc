from datetime import date, timedelta

from src.models.student import Student
from src.services.activity_logger import ActivityLogger
from src.services.diagnostics import APP_ERROR, OUTSIDE_PROBLEM, Diagnostics, classify


def _jane():
    return Student(
        salesforce_id="000562489", first_name="Jane", last_name="Doe", email="jdoe12@wgu.edu",
        phone="(555) 201-3344", texting_contact_id="0033x000038KA8HAAW",
    )


def _today_text(diag):
    return (diag.folder / f"{date.today().isoformat()}.log").read_text(encoding="utf-8")


def test_roster_students_never_reach_the_diagnostics_log(tmp_path):
    diag = Diagnostics(tmp_path)
    diag.set_roster([_jane()])

    diag.line("[PROCESSING] Jane Doe (ID: 000562489) <jdoe12@wgu.edu> 555-201-3344 id 0033x000038KA8HAAW; Hi Jane")

    text = _today_text(diag)
    for secret in ("Jane", "Doe", "000562489", "jdoe12", "201-3344", "0033x000038KA8HAAW"):
        assert secret not in text
    assert "[PROCESSING] [student] (ID: [student])" in text


def test_shapes_are_scrubbed_even_for_people_not_on_the_roster(tmp_path):
    diag = Diagnostics(tmp_path)
    diag.line("mail someone@example.com, call 801.555.0199, id 0031a000004XyZ9AAB, number 12345678")
    text = _today_text(diag)
    assert "[email]" in text and "[phone]" in text and "[contact-id]" in text and "[number]" in text
    assert "someone" not in text and "12345678" not in text


def test_ordinary_words_dates_and_course_codes_are_left_alone(tmp_path):
    diag = Diagnostics(tmp_path)
    diag.set_roster([Student(salesforce_id="S1", first_name="Will", last_name="May", email="w@x.test")])
    diag.line("Texts to them will be skipped on 2026-10-28 for D424, may retry at 10:15")
    assert "Texts to them will be skipped on 2026-10-28 for D424, may retry at 10:15" in _today_text(diag)


def test_errors_get_the_full_report_and_a_label(tmp_path):
    diag = Diagnostics(tmp_path)
    try:
        {}["missing"]
    except KeyError as exc:
        diag.error("[EMAIL FAILED] something", exc)
    text = _today_text(diag)
    assert "[APP ERROR] [EMAIL FAILED] something" in text
    assert "Traceback (most recent call last)" in text and "KeyError" in text


def test_outside_problems_and_app_errors_are_told_apart():
    assert classify(RuntimeError("Outlook isn't open")) == OUTSIDE_PROBLEM
    assert classify(TimeoutError()) == OUTSIDE_PROBLEM
    assert classify(ConnectionError()) == OUTSIDE_PROBLEM
    assert classify(KeyError("x")) == APP_ERROR
    assert classify(AttributeError("x")) == APP_ERROR
    assert classify(NotImplementedError()) == APP_ERROR


def test_files_older_than_14_days_are_deleted_at_startup(tmp_path):
    today = date(2026, 10, 28)
    for days_ago in (0, 14, 15, 30):
        (tmp_path / f"{(today - timedelta(days=days_ago)).isoformat()}.log").write_text("x")
    (tmp_path / "notes.txt").write_text("not ours")

    Diagnostics(tmp_path, today=today)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-14.log", "2026-10-28.log", "notes.txt"]


def test_startup_header_names_the_version_and_test_mode(tmp_path):
    diag = Diagnostics(tmp_path)
    diag.header(test_mode=True)
    text = _today_text(diag)
    assert "=== App started === version:" in text and "test mode: ON" in text and "Windows" in text


def test_activity_log_keeps_names_while_the_diagnostics_copy_drops_them(tmp_path):
    diag = Diagnostics(tmp_path / "diagnostics")
    diag.set_roster([_jane()])
    logger = ActivityLogger(log_dir=str(tmp_path / "logs"), diagnostics=diag)

    logger.log("[EMAIL] Sent to Jane Doe <jdoe12@wgu.edu>")
    logger.log_failure("[TEXT FAILED] Jane Doe: Outlook isn't open", RuntimeError("Outlook isn't open"))

    activity = (tmp_path / "logs" / f"{date.today().isoformat()}.log").read_text(encoding="utf-8")
    assert "Jane Doe" in activity and "[TEXT FAILED] Jane Doe" in activity
    diagnostics = _today_text(diag)
    assert "Jane" not in diagnostics
    assert "[EMAIL] Sent to [student] <[student]>" in diagnostics
    assert "[OUTSIDE PROBLEM] [TEXT FAILED] [student]: Outlook isn't open" in diagnostics
