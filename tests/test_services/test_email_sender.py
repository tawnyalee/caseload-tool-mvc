import pytest

from src.services.email_sender import FakeEmailSender


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
