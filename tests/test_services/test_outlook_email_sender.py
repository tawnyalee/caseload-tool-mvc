import pytest

from src.services.outlook_email_sender import (
    OutlookEmailSender,
    combine_body_and_signature,
    embed_local_images,
    read_signature_html,
)

SIGNATURE = '<html><head><style>p{color:red}</style></head><body lang=EN-US><p>Stay Magical,</p></body></html>'


class _FakeAttachment:
    def __init__(self, path):
        self.path = path
        self.properties = {}
        self.PropertyAccessor = self

    def SetProperty(self, name, value):
        self.properties[name] = value


class _FakeAttachments(list):
    def Add(self, path):
        attachment = _FakeAttachment(path)
        self.append(attachment)
        return attachment


class _FakeMail:
    def __init__(self):
        self.To = self.Subject = self.HTMLBody = None
        self.Attachments = _FakeAttachments()
        self.sent = False

    def Send(self):
        self.sent = True


class _FakeOutlook:
    def __init__(self, fail_first_create=False):
        self.mails = []
        self._fail_next = fail_first_create

    def CreateItem(self, item_type):
        assert item_type == 0
        if self._fail_next:
            self._fail_next = False
            raise OSError("The RPC server is unavailable.")
        mail = _FakeMail()
        self.mails.append(mail)
        return mail


def _make_sender(tmp_path, outlooks):
    """`outlooks` is a list - each (re)connect takes the next one, so tests
    can tell a reconnect apart from reusing the same connection."""
    return OutlookEmailSender(signatures_folder=tmp_path, outlook_factory=lambda: outlooks.pop(0))


# --- combine_body_and_signature ---

def test_message_goes_inside_the_signature_page_before_its_content():
    combined = combine_body_and_signature("<p>Hi</p>", SIGNATURE)
    assert combined.count("<html>") == 1
    assert combined.index("<body lang=EN-US>") < combined.index("<p>Hi</p>") < combined.index("Stay Magical")
    assert "<style>p{color:red}</style>" in combined  # signature keeps its own styles


def test_no_signature_leaves_the_body_unchanged():
    assert combine_body_and_signature("<p>Hi</p>", "") == "<p>Hi</p>"


def test_signature_fragment_without_a_body_tag_is_appended():
    assert combine_body_and_signature("<p>Hi</p>", "<p>Sig</p>") == "<p>Hi</p><br><p>Sig</p>"


# --- embed_local_images ---

def test_local_signature_image_becomes_a_cid_attachment(tmp_path):
    (tmp_path / "TLee_files").mkdir()
    logo = tmp_path / "TLee_files" / "image001.png"
    logo.write_bytes(b"png")
    html = '<img width=50 src="TLee_files/image001.png" alt="logo">'

    new_html, attachments = embed_local_images(html, tmp_path)

    assert new_html == '<img width=50 src="cid:sigimg1" alt="logo">'
    assert attachments == [(logo.resolve(), "sigimg1")]


def test_url_encoded_image_paths_are_found(tmp_path):
    (tmp_path / "TLee (me@x.com)_files").mkdir()
    (tmp_path / "TLee (me@x.com)_files" / "image001.png").write_bytes(b"png")

    new_html, attachments = embed_local_images('<img src="TLee%20(me@x.com)_files/image001.png">', tmp_path)

    assert new_html == '<img src="cid:sigimg1">'
    assert len(attachments) == 1


def test_web_data_and_missing_images_are_left_alone(tmp_path):
    html = ('<img src="https://wgu.edu/logo.png"><img src="cid:already">'
            '<img src="data:image/png;base64,AA"><img src="Missing_files/nope.png">')
    assert embed_local_images(html, tmp_path) == (html, [])


# --- read_signature_html ---

def test_reads_windows_1252_signature_as_declared(tmp_path):
    path = tmp_path / "Sig.htm"
    text = '<meta charset="windows-1252"><p>Café – Prof</p>'
    path.write_bytes(text.encode("cp1252"))
    assert read_signature_html(path) == text


# --- OutlookEmailSender.send ---

def test_send_builds_and_sends_one_mail_with_the_signature(tmp_path):
    (tmp_path / "TLee.htm").write_text(SIGNATURE, encoding="utf-8")
    outlook = _FakeOutlook()
    sender = _make_sender(tmp_path, [outlook])

    sender.send("jane@example.test", "Welcome", "<p>Hi Jane</p>", signature="TLee")

    [mail] = outlook.mails
    assert mail.sent
    assert (mail.To, mail.Subject) == ("jane@example.test", "Welcome")
    assert mail.HTMLBody.index("<p>Hi Jane</p>") < mail.HTMLBody.index("Stay Magical")


def test_send_attaches_signature_images_with_matching_content_ids(tmp_path):
    (tmp_path / "Logo_files").mkdir()
    (tmp_path / "Logo_files" / "image001.png").write_bytes(b"png")
    (tmp_path / "Logo.htm").write_text('<body><img src="Logo_files/image001.png"></body>', encoding="utf-8")
    outlook = _FakeOutlook()

    _make_sender(tmp_path, [outlook]).send("jane@example.test", "S", "<p>Hi</p>", signature="Logo")

    [mail] = outlook.mails
    [attachment] = mail.Attachments
    content_id = attachment.properties["http://schemas.microsoft.com/mapi/proptag/0x3712001F"]
    assert f'src="cid:{content_id}"' in mail.HTMLBody


def test_missing_signature_fails_loudly_and_sends_nothing(tmp_path):
    outlook = _FakeOutlook()
    sender = _make_sender(tmp_path, [outlook])

    with pytest.raises(RuntimeError, match="signature 'Gone' wasn't found"):
        sender.send("jane@example.test", "S", "<p>Hi</p>", signature="Gone")
    assert outlook.mails == []


def test_student_with_no_email_fails_without_contacting_outlook(tmp_path):
    outlooks = [_FakeOutlook()]
    with pytest.raises(RuntimeError, match="no email address"):
        _make_sender(tmp_path, outlooks).send("", "S", "<p>Hi</p>")
    assert len(outlooks) == 1  # never connected


def test_outlook_is_not_contacted_until_the_first_send(tmp_path):
    def explode():
        raise AssertionError("connected too early")
    OutlookEmailSender(signatures_folder=tmp_path, outlook_factory=explode)  # must not raise


def test_connection_is_reused_across_sends(tmp_path):
    outlook = _FakeOutlook()
    sender = _make_sender(tmp_path, [outlook])  # only one connection available
    sender.send("a@example.test", "S", "<p>1</p>")
    sender.send("b@example.test", "S", "<p>2</p>")
    assert [m.To for m in outlook.mails] == ["a@example.test", "b@example.test"]


def test_stale_connection_reconnects_once(tmp_path):
    stale, fresh = _FakeOutlook(fail_first_create=True), _FakeOutlook()
    sender = _make_sender(tmp_path, [stale, fresh])

    sender.send("jane@example.test", "S", "<p>Hi</p>")

    assert stale.mails == []
    assert [m.To for m in fresh.mails] == ["jane@example.test"]


# --- never starts Outlook: attach to an open one or fail clearly ------------

from unittest.mock import patch

from src.services.outlook_email_sender import OUTLOOK_NOT_OPEN_MESSAGE, _connect_to_outlook


def test_connects_only_to_an_already_open_outlook_never_starts_one():
    import win32com.client
    running = object()
    with patch.object(win32com.client, "GetActiveObject", return_value=running) as attach, \
         patch.object(win32com.client, "Dispatch") as start:
        assert _connect_to_outlook() is running
    attach.assert_called_once_with("Outlook.Application")
    start.assert_not_called()  # Dispatch would start a hidden Outlook


def test_outlook_not_open_gives_a_plain_message():
    import win32com.client
    with patch.object(win32com.client, "GetActiveObject", side_effect=Exception("Operation unavailable")),          patch("src.services.outlook_email_sender._new_outlook_is_running", return_value=False):
        with pytest.raises(RuntimeError, match="Outlook isn't open"):
            _connect_to_outlook()


def test_new_outlook_open_says_the_app_needs_classic():
    import win32com.client
    with patch.object(win32com.client, "GetActiveObject", side_effect=Exception("Operation unavailable")),          patch("src.services.outlook_email_sender._new_outlook_is_running", return_value=True):
        with pytest.raises(RuntimeError, match=r"New Outlook open, but this app needs Outlook \(classic\)"):
            _connect_to_outlook()


def test_ensure_ready_connects_once_and_reuses_it(tmp_path):
    outlook = _FakeOutlook()
    sender = _make_sender(tmp_path, [outlook])  # only one connection available
    sender.ensure_ready()
    sender.send("a@example.test", "S", "<p>1</p>")
    assert [m.To for m in outlook.mails] == ["a@example.test"]


def test_ensure_ready_raises_when_outlook_is_not_open(tmp_path):
    def not_open():
        raise RuntimeError(OUTLOOK_NOT_OPEN_MESSAGE)
    sender = OutlookEmailSender(signatures_folder=tmp_path, outlook_factory=not_open)
    with pytest.raises(RuntimeError, match="Outlook isn't open"):
        sender.ensure_ready()
