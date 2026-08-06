from src.services.outlook_signature_provider import (
    FakeOutlookSignatureProvider,
    LocalOutlookSignatureProvider,
)


def test_fake_provider_returns_default_names():
    provider = FakeOutlookSignatureProvider()
    assert provider.get_signature_names() == ["Default Outlook Signature", "Custom Signature 1"]


def test_fake_provider_returns_configured_names():
    provider = FakeOutlookSignatureProvider(names=["Work", "Personal"])
    assert provider.get_signature_names() == ["Work", "Personal"]


def test_local_provider_returns_empty_list_when_folder_missing(tmp_path):
    missing = tmp_path / "does_not_exist"
    provider = LocalOutlookSignatureProvider(folder_path=str(missing))
    assert provider.get_signature_names() == []


def test_local_provider_lists_and_dedupes_signature_names(tmp_path):
    (tmp_path / "Default.htm").write_text("<html></html>")
    (tmp_path / "Default.rtf").write_text("rtf")
    (tmp_path / "Default.txt").write_text("txt")
    (tmp_path / "Personal.htm").write_text("<html></html>")
    (tmp_path / "notes.png").write_text("not a signature file")

    provider = LocalOutlookSignatureProvider(folder_path=str(tmp_path))

    assert provider.get_signature_names() == ["Default", "Personal"]
