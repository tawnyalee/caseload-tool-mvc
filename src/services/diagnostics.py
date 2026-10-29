# src/services/diagnostics.py
"""A second, student-free log for working out what went wrong after the fact
(developer's ask, 2026-10-28).

The daily activity log names students, so it's deleted after one day
(FERPA). That's too short to look into a problem a professor reports later.
This log gets a copy of every activity-log line, plus the full error report
(traceback) for every failure, each labeled:

  - "Outside problem": something outside the app the professor can fix or
    retry - Outlook closed, a login expired, a page that didn't load, a
    student not found in Mongoose.
  - "App error": anything else, i.e. most likely a bug in the app.

Every line is scrubbed BEFORE it's written: names and IDs of the students in
the current roster, plus anything shaped like an email address, phone
number, long ID number or Salesforce Contact Id. That makes it safe to keep
for KEEP_DAYS days and to send to whoever supports the app. Files live in
logs/diagnostics/YYYY-MM-DD.log.
"""
import logging
import platform
import re
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

KEEP_DAYS = 14
OUTSIDE_PROBLEM = "Outside problem"
APP_ERROR = "App error"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_CONTACT_ID = re.compile(r"\b003[A-Za-z0-9]{12,15}\b")
_PHONE = re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")
_LONG_NUMBER = re.compile(r"\b\d{6,}\b")


def classify(exc: BaseException) -> str:
    """Outside problem vs app error. The app's own adapters report outside
    problems (Outlook closed, login expired, page timeouts, Mongoose misses)
    as RuntimeError or OS/connection errors with a plain message; anything
    else - a TypeError, KeyError, AttributeError... - means the code itself
    went wrong."""
    if isinstance(exc, (NotImplementedError, RecursionError)):
        return APP_ERROR
    if isinstance(exc, (RuntimeError, OSError, TimeoutError, ConnectionError)):
        return OUTSIDE_PROBLEM
    module = type(exc).__module__ or ""
    if module.startswith(("playwright", "pywintypes")) or type(exc).__name__ == "com_error":
        return OUTSIDE_PROBLEM
    return APP_ERROR


def app_version() -> str:
    """The build's version.txt (written by build_exe.py) in the .exe; the
    git commit when running from source. Best-effort."""
    from src.services import app_paths

    try:
        stamp = app_paths.resource_path("version.txt")
        if stamp.exists():
            return stamp.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    try:
        import subprocess

        root = Path(__file__).resolve().parent.parent.parent
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"], cwd=root, capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"source {out.stdout.strip()}"
    except Exception:
        pass
    return "unknown"


class Diagnostics:
    def __init__(self, folder, keep_days: int = KEEP_DAYS, today: Optional[date] = None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.keep_days = keep_days
        self._terms: List[str] = []
        self._pattern: Optional[re.Pattern] = None
        self.purge_old(today)

        self._logger = logging.getLogger(f"diagnostics.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._handler = None
        self._handler_date = None

    def purge_old(self, today: Optional[date] = None) -> int:
        cutoff = (today or date.today()) - timedelta(days=self.keep_days)
        removed = 0
        for path in self.folder.glob("*.log"):
            try:
                if date.fromisoformat(path.stem) < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except ValueError:
                continue
        return removed

    # --- scrubbing ---------------------------------------------------------

    def set_roster(self, students: Iterable) -> None:
        """Remembers the current roster's names and IDs so they're scrubbed.
        Called after every roster load."""
        terms = set()
        for s in students:
            for value in (
                getattr(s, "full_name", ""), getattr(s, "first_name", ""), getattr(s, "last_name", ""),
                getattr(s, "salesforce_id", ""), getattr(s, "texting_contact_id", ""),
                getattr(s, "email", ""), getattr(s, "phone", ""),
            ):
                value = (value or "").strip()
                if len(value) >= 2:
                    terms.add(value)
        # Longest first, so "Jane Doe" is replaced whole before "Jane". Case-
        # sensitive: names appear as the roster spells them, and ignoring case
        # would also blank out ordinary words like "will" or "may".
        self._terms = sorted(terms, key=len, reverse=True)
        self._pattern = (
            re.compile("|".join(rf"(?<!\w){re.escape(t)}(?!\w)" for t in self._terms))
            if self._terms else None
        )

    def scrub(self, text: str) -> str:
        if self._pattern is not None:
            text = self._pattern.sub("[student]", text)
        text = _EMAIL.sub("[email]", text)
        text = _CONTACT_ID.sub("[contact-id]", text)
        text = _PHONE.sub("[phone]", text)
        return _LONG_NUMBER.sub("[number]", text)

    # --- writing -----------------------------------------------------------

    def _write(self, message: str) -> None:
        today = datetime.now().date()
        if today != self._handler_date:
            if self._handler:
                self._logger.removeHandler(self._handler)
                self._handler.close()
            self._handler = logging.FileHandler(self.folder / f"{today.isoformat()}.log", encoding="utf-8")
            self._handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            self._logger.addHandler(self._handler)
            self._handler_date = today
        self._logger.info(self.scrub(message))

    def line(self, message: str) -> None:
        try:
            self._write(message)
        except Exception:
            pass  # diagnostics must never break the app

    def error(self, message: str, exc: BaseException) -> None:
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        self.line(f"[{classify(exc).upper()}] {message}\n{details.rstrip()}")

    def header(self, test_mode: bool) -> None:
        self.line(
            "=== App started === "
            f"version: {app_version()} | "
            f"{'packaged .exe' if getattr(sys, 'frozen', False) else 'from source'} | "
            f"Windows {platform.version()} | Python {platform.python_version()} | "
            f"test mode: {'ON' if test_mode else 'off'}"
        )
