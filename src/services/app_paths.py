# src/services/app_paths.py
"""The one place that knows where the app keeps its files.

Per-user data - what a professor creates or the app writes while running
(groups, actions, templates, saved batches, the Mongoose Contact-Id map,
the test-mode switch, daily logs and failure screenshots) - lives in

    %LOCALAPPDATA%\\CaseloadTool\\

(e.g. C:\\Users\\<you>\\AppData\\Local\\CaseloadTool). Not inside the app's own
folder: a packaged .exe usually can't write next to itself (Program Files
is read-only for normal users), and keeping data separate means
reinstalling or updating the app never touches it. Moved here 2026-10-22;
migrate_legacy_data() copies files from their old in-repo locations once.

CASELOAD_DATA_DIR overrides the location - the test suite points it at a
temporary folder (tests/conftest.py), so tests never touch real data.

Read-only files that ship WITH the app (the template editor's assets)
are found with resource_path(), which also works inside a PyInstaller
build.
"""
import os
import shutil
import sys
from pathlib import Path
from typing import List

APP_NAME = "CaseloadTool"
DATA_DIR_ENV_VAR = "CASELOAD_DATA_DIR"

# The repo root when running from source; the bundle folder inside a build.
_SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    """Created on first use."""
    override = os.environ.get(DATA_DIR_ENV_VAR)
    if override:
        path = Path(override)
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        path = Path(local_appdata) / APP_NAME if local_appdata else Path.home() / f".{APP_NAME.lower()}"
        _warn_if_store_python_would_hide_it(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


_warned = False


def _warn_if_store_python_would_hide_it(path: Path) -> None:
    """Microsoft Store Python silently redirects NEW folders under AppData
    into its own private package folder, so data created there is invisible
    to everything else - including the packaged .exe (found on the dev
    machine 2026-10-22). If the folder already exists in the real location,
    Store Python writes there directly, so the fix is to create it once
    from outside Python. Only matters when running from source."""
    global _warned
    if _warned or path.exists() or "WindowsApps" not in sys.executable:
        return
    _warned = True
    print(
        f"WARNING: Microsoft Store Python will hide {path} inside its own private folder.\n"
        f"Create it once from PowerShell, then restart:  New-Item -ItemType Directory \"{path}\"",
        file=sys.stderr,
    )


def groups_file() -> Path:
    return data_dir() / "groups.json"


def actions_file() -> Path:
    return data_dir() / "actions.json"


def templates_file() -> Path:
    return data_dir() / "templates.json"


def saved_batches_file() -> Path:
    return data_dir() / "saved_batches.json"


def mongoose_contact_ids_file() -> Path:
    return data_dir() / "mongoose_contact_ids.json"


def test_mode_file() -> Path:
    return data_dir() / "test_mode.json"


def browser_profile_dir() -> Path:
    """The app's own Edge profile, used only for the login windows, so
    PingID and WGU sign-in recognize the device on later launches."""
    return data_dir() / "edge-profile"


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshots_dir() -> Path:
    return logs_dir() / "screenshots"


def resource_path(relative: str) -> Path:
    """A read-only file shipped with the app, e.g. "src/assets/quill".
    PyInstaller unpacks bundled files under sys._MEIPASS; from source it's
    the repo root."""
    base = Path(getattr(sys, "_MEIPASS", _SOURCE_ROOT))
    return base / relative


# Where each file lived before 2026-10-22 (relative to the repo root).
# Logs aren't carried over - they're deleted daily anyway.
_LEGACY_LOCATIONS = {
    "groups.json": "src/data/groups.json",
    "actions.json": "src/data/actions.json",
    "saved_batches.json": "src/data/saved_batches.json",
    "mongoose_contact_ids.json": "src/data/mongoose_contact_ids.json",
    "templates.json": "data/templates.json",
    "test_mode.json": "data/test_mode.json",
}


def migrate_legacy_data(legacy_root: Path = _SOURCE_ROOT) -> List[str]:
    """Copies each file from its old in-repo location into data_dir(), but
    only if it isn't there yet - so it runs once in practice, and never
    overwrites anything. Originals are left in place (copied, not moved).
    Returns the names copied. Does nothing in a packaged build (there's no
    old location to copy from)."""
    if getattr(sys, "frozen", False):
        return []
    copied = []
    for name, old_relative in _LEGACY_LOCATIONS.items():
        old, new = Path(legacy_root) / old_relative, data_dir() / name
        if old.is_file() and not new.exists():
            shutil.copy2(old, new)
            copied.append(name)
    return copied


# Files a "with my data" build carries in a starter_data folder next to the
# .exe (python build_exe.py --with-my-data). Setup and the test-mode switch
# only - never logs or derived data.
STARTER_DATA_FOLDER = "starter_data"
STARTER_FILES = ("groups.json", "actions.json", "templates.json", "saved_batches.json", "test_mode.json")


def install_starter_data(starter_folder: Path = None) -> List[str]:
    """First launch of a "with my data" build on a new computer: copies the
    bundled starter_data files into data_dir(), only those not there yet -
    so it never overwrites what's already on this computer. Lets moving to
    another machine be "copy one zip, extract, run" (developer's ask,
    2026-10-27) instead of finding the hidden AppData folder by hand.
    test_mode.json comes along, so a fresh install starts in test mode
    instead of live. Returns the names copied."""
    if starter_folder is None:
        if not getattr(sys, "frozen", False):
            return []
        starter_folder = Path(sys.executable).parent / STARTER_DATA_FOLDER
    starter_folder = Path(starter_folder)
    if not starter_folder.is_dir():
        return []
    copied = []
    for name in STARTER_FILES:
        source, target = starter_folder / name, data_dir() / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)
            copied.append(name)
    return copied
