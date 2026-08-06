# src/services/outlook_signature_provider.py
"""Reads the end user's actual Outlook signature names off the local
machine. Outlook stores each signature as a set of files (.htm/.rtf/.txt,
plus an image folder) under %APPDATA%\\Microsoft\\Signatures\\ — this only
lists what's in that folder, it never talks to Outlook itself, so it works
today even though the real Outlook send adapter isn't built yet (see
CLAUDE.md). Only the signature *name* is read here; resolving a name to its
actual HTML content is left for whatever eventually sends the email.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

SIGNATURE_FILE_EXTENSIONS = (".htm", ".rtf", ".txt")


class OutlookSignatureProvider(ABC):
    @abstractmethod
    def get_signature_names(self) -> List[str]:
        """Returns the names of every signature currently available, sorted."""
        raise NotImplementedError


class LocalOutlookSignatureProvider(OutlookSignatureProvider):
    """Scans the local Outlook signatures folder. Returns an empty list if
    the folder doesn't exist (Outlook not installed/configured, or running
    on a non-Windows dev machine) rather than raising."""

    def __init__(self, folder_path: Optional[str] = None):
        if folder_path is not None:
            self.folder_path: Optional[Path] = Path(folder_path)
        else:
            appdata = os.environ.get("APPDATA")
            self.folder_path = Path(appdata) / "Microsoft" / "Signatures" if appdata else None

    def get_signature_names(self) -> List[str]:
        if not self.folder_path or not self.folder_path.is_dir():
            return []

        names = {
            f.stem for f in self.folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in SIGNATURE_FILE_EXTENSIONS
        }
        return sorted(names)


class FakeOutlookSignatureProvider(OutlookSignatureProvider):
    """Returns a fixed list of signature names for tests/dev, without
    touching the filesystem."""

    def __init__(self, names: Optional[List[str]] = None):
        self.names = names if names is not None else ["Default Outlook Signature", "Custom Signature 1"]

    def get_signature_names(self) -> List[str]:
        return list(self.names)


def get_signature_names_or_fallback(
    provider: Optional[OutlookSignatureProvider],
    fallback: str = "No Outlook signatures found",
) -> List[str]:
    """Shared by every place that needs signature names for a dropdown:
    falls back to a single explanatory option instead of an empty/missing
    combobox when no provider is wired up or no signatures are configured."""
    if provider:
        names = provider.get_signature_names()
        if names:
            return names
    return [fallback]
