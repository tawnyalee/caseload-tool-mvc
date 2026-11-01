from datetime import datetime, timezone

from unittest.mock import MagicMock

import pytest

from src.models.student import Student
from src.services import mongoose_text_sender as mts
from src.services.mongoose_compose import NoMongooseMatch
from src.services.text_sender import TextSkipped


def _student(**overrides):
    fields = dict(salesforce_id="S1", first_name="Jane", last_name="Doe", email="j@example.test",
                  course_code="D424", timezone="CST", texting_contact_id="003AAA")
    fields.update(overrides)
    return Student(**fields)


class _NoBrowser(mts.MongooseTextSender):
    """Skips the real browser; records what would have been typed."""

    def __init__(self, mode, compose_error=None):
        super().__init__(mode)
        self.composed = []
        self.compose_error = compose_error
        self.reviewed = False

    def ensure_ready(self):
        pass

    def _go_home(self):
        pass

    def _wait_for_review(self, student):
        self.reviewed = True


@pytest.fixture
def fake_compose(monkeypatch):
    calls = []

    def compose(page, text, commit=False, say=None):
        if getattr(compose, "error", None):
            raise compose.error
        calls.append((text, commit))

    monkeypatch.setattr(mts, "compose_scheduled_text", compose)
    compose.calls = calls
    return compose


@pytest.mark.parametrize("overrides, reason", [
    ({"texting_contact_id": ""}, "No texting ID"),
    ({"course_code": ""}, "No course code"),
    ({"timezone": ""}, "No usable time zone"),
])
def test_students_it_cant_place_are_skipped_not_guessed(fake_compose, overrides, reason):
    with pytest.raises(TextSkipped, match=reason):
        _NoBrowser(mts.REVIEW).send(_student(**overrides), "Hi", "Name")
    assert fake_compose.calls == []


def test_dry_run_fills_it_in_but_never_schedules(fake_compose):
    what = _NoBrowser(mts.DRY_RUN).send(_student(), "Hi Jane", "Task 4")
    text, commit = fake_compose.calls[0]
    assert commit is False
    assert (text.course_code, text.contact_id, text.body, text.message_name) == ("D424", "003AAA", "Hi Jane", "Task 4")
    assert what.startswith("TEST MODE - filled in for") and "not scheduled" in what


def test_review_mode_waits_for_the_professor(fake_compose):
    sender = _NoBrowser(mts.REVIEW)
    sender.send(_student(), "Hi", "Name")
    assert fake_compose.calls[0][1] is False
    assert sender.reviewed


def test_automatic_mode_clicks_schedule(fake_compose):
    what = _NoBrowser(mts.AUTOMATIC).send(_student(), "Hi", "Name")
    assert fake_compose.calls[0][1] is True
    assert what.startswith("Scheduled for")


def test_no_match_in_the_department_is_a_skip(fake_compose):
    fake_compose.error = NoMongooseMatch("Not found in this Mongoose department")
    with pytest.raises(TextSkipped, match=r"Not found.*\(D424\)"):
        _NoBrowser(mts.REVIEW).send(_student(), "Hi", "Name")


def test_the_time_typed_into_mongoose_is_the_same_moment_as_the_students_time():
    student_time = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
    entry = mts.mongoose_entry_time(student_time)
    assert entry == student_time and entry.tzinfo is not None


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        mts.MongooseTextSender("sometimes")


def _open_sender(page):
    sender = mts.MongooseTextSender(mode=mts.REVIEW)
    sender._page = page
    return sender


def test_review_brings_mongoose_forward_and_says_its_waiting_on_you():
    page = MagicMock()
    sender = _open_sender(page)
    sender.on_waiting = MagicMock()

    sender._wait_for_review(_student())

    page.bring_to_front.assert_called_once()
    assert "click Schedule or Cancel" in sender.on_waiting.call_args[0][0]


def test_an_open_window_is_reused_between_runs():
    page = MagicMock()
    page.is_closed.return_value = False
    sender = _open_sender(page)

    sender.ensure_ready()
    sender.finish()

    assert sender._page is page
    page.goto.assert_not_called()


def test_a_window_the_professor_closed_is_opened_again(monkeypatch):
    closed_page, new_page = MagicMock(), MagicMock()
    closed_page.is_closed.return_value = True
    context = MagicMock(pages=[new_page])
    monkeypatch.setattr(mts, "acquire_playwright", MagicMock())
    monkeypatch.setattr(mts, "release_playwright", MagicMock())
    monkeypatch.setattr(mts, "launch_login_context", lambda *_a, **_k: context)
    sender = _open_sender(closed_page)

    sender.ensure_ready()

    assert sender._page is new_page
    new_page.goto.assert_called_once_with(mts.MONGOOSE_URL)


def test_closing_keeps_mongooses_sign_in(monkeypatch):
    clear = MagicMock()
    monkeypatch.setattr(mts, "clear_cached_pages", clear)
    context = MagicMock()
    sender = _open_sender(MagicMock())
    sender._context = context

    sender.close()

    clear.assert_called_once_with(context, mts.MONGOOSE_URL, keep_local_storage=True)
    context.close.assert_called_once()
    assert sender._page is None
