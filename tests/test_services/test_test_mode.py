import pytest

from src.services.email_sender import FakeEmailSender
from src.services.test_mode import INVALID_REDIRECT, RedirectingEmailSender, load_redirect_email


# --- load_redirect_email ---

def test_no_file_means_test_mode_is_off(tmp_path):
    assert load_redirect_email(tmp_path / "test_mode.json") is None


def test_valid_file_returns_the_address(tmp_path):
    path = tmp_path / "test_mode.json"
    path.write_text('{"redirect_email": " me@example.test "}', encoding="utf-8")
    assert load_redirect_email(path) == "me@example.test"


@pytest.mark.parametrize("content", ["not json", "[]", '{"redirect_email": ""}', '{"redirect_email": "nope"}', "{}"])
def test_broken_file_keeps_test_mode_on_with_no_address(tmp_path, content):
    # The safe direction: a broken file must never silently mean "go live".
    path = tmp_path / "test_mode.json"
    path.write_text(content, encoding="utf-8")
    assert load_redirect_email(path) == INVALID_REDIRECT


# --- RedirectingEmailSender ---

def test_redirects_to_the_test_address_and_names_the_real_recipient():
    inner = FakeEmailSender()
    RedirectingEmailSender(inner, "me@example.test").send("jane@student.test", "Welcome", "<p>Hi Jane</p>", "Sig")

    [sent] = inner.sent
    assert sent["to"] == "me@example.test"
    assert sent["subject"] == "[TEST -> jane@student.test] Welcome"
    assert "would have been sent to <b>jane@student.test</b>" in sent["body"]
    assert sent["body"].endswith("<p>Hi Jane</p>")
    assert sent["signature"] == "Sig"


def test_student_with_no_email_still_fails_like_a_real_send():
    inner = FakeEmailSender()
    with pytest.raises(RuntimeError, match="no email address"):
        RedirectingEmailSender(inner, "me@example.test").send("", "S", "<p>Hi</p>")
    assert inner.sent == []


def test_no_valid_address_fails_instead_of_sending_anywhere():
    inner = FakeEmailSender()
    with pytest.raises(RuntimeError, match="TEST MODE is on"):
        RedirectingEmailSender(inner, INVALID_REDIRECT).send("jane@student.test", "S", "<p>Hi</p>")
    assert inner.sent == []


def test_recipient_address_is_html_escaped_in_the_banner():
    inner = FakeEmailSender()
    RedirectingEmailSender(inner, "me@example.test").send("<b>x</b>@y.test", "S", "")
    assert "&lt;b&gt;x&lt;/b&gt;@y.test" in inner.sent[0]["body"]


def test_redirecting_sender_passes_the_readiness_check_through():
    class NotReady(FakeEmailSender):
        def ensure_ready(self):
            raise RuntimeError("Outlook isn't open")
    with pytest.raises(RuntimeError, match="Outlook isn't open"):
        RedirectingEmailSender(NotReady(), "me@example.test").ensure_ready()
