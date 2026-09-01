from unittest.mock import MagicMock, patch

import pytest

from src.services.email_sender import FakeEmailSender, SmtpEmailSender


def test_fake_email_sender_records_sent_email():
    sender = FakeEmailSender()
    sender.send(to_email="jane@example.test", subject="Hi", body="<b>Hello</b>", signature="Sig")

    assert len(sender.sent) == 1
    assert sender.sent[0] == {
        "to": "jane@example.test",
        "subject": "Hi",
        "body": "<b>Hello</b>",
        "signature": "Sig",
    }


def test_fake_email_sender_raises_for_configured_failure():
    sender = FakeEmailSender(fail_for={"broken@example.test"})

    with pytest.raises(RuntimeError):
        sender.send(to_email="broken@example.test", subject="Hi", body="body")

    assert sender.sent == []


def test_fake_email_sender_unaffected_addresses_still_succeed():
    sender = FakeEmailSender(fail_for={"broken@example.test"})
    sender.send(to_email="fine@example.test", subject="Hi", body="body")

    assert len(sender.sent) == 1


def test_smtp_email_sender_requires_env_vars(monkeypatch):
    monkeypatch.delenv("TEST_SMTP_EMAIL", raising=False)
    monkeypatch.delenv("TEST_SMTP_APP_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        SmtpEmailSender()


def test_smtp_email_sender_reads_credentials_from_env(monkeypatch):
    monkeypatch.setenv("TEST_SMTP_EMAIL", "tester@gmail.com")
    monkeypatch.setenv("TEST_SMTP_APP_PASSWORD", "app-password-123")

    sender = SmtpEmailSender()

    assert sender.sender_email == "tester@gmail.com"
    assert sender.app_password == "app-password-123"


@patch("src.services.email_sender.smtplib.SMTP")
def test_smtp_email_sender_send_logs_in_and_sends_the_right_message(mock_smtp_class, monkeypatch):
    monkeypatch.setenv("TEST_SMTP_EMAIL", "tester@gmail.com")
    monkeypatch.setenv("TEST_SMTP_APP_PASSWORD", "app-password-123")
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    sender = SmtpEmailSender()
    sender.send(to_email="student@example.test", subject="Welcome", body="<b>Hi there</b>", signature="Ignored")

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("tester@gmail.com", "app-password-123")

    args, _ = mock_server.sendmail.call_args
    from_addr, to_addrs, raw_message = args
    assert from_addr == "tester@gmail.com"
    assert to_addrs == ["student@example.test"]
    assert "Welcome" in raw_message
    assert "Hi there" in raw_message


@patch("src.services.email_sender.smtplib.SMTP")
def test_smtp_email_sender_lets_smtp_errors_propagate(mock_smtp_class, monkeypatch):
    monkeypatch.setenv("TEST_SMTP_EMAIL", "tester@gmail.com")
    monkeypatch.setenv("TEST_SMTP_APP_PASSWORD", "app-password-123")
    mock_server = MagicMock()
    mock_server.login.side_effect = RuntimeError("bad credentials")
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    sender = SmtpEmailSender()
    with pytest.raises(RuntimeError):
        sender.send(to_email="student@example.test", subject="Hi", body="body")
