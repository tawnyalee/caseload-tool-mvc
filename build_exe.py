# build_exe.py
"""Builds the app and zips it, ready to copy to another computer:

    python build_exe.py                  -> dist/CaseloadTool.zip (to share)
    python build_exe.py --with-my-data   -> dist/CaseloadTool-with-my-data.zip

--with-my-data also packs YOUR groups, actions, templates, saved batches
and test-mode setting (from %LOCALAPPDATA%/CaseloadTool) into the zip; the
app copies them into place on its first launch on the new computer
(app_paths.install_starter_data). Moving to your work laptop is then:
copy the one zip, Extract All, run CaseloadTool.exe. Keep that zip to
yourself - it's your setup, not a blank copy for colleagues.

The zip holds the whole dist/CaseloadTool folder (the .exe needs the
files next to it). Professors don't need Python installed.

Decisions behind this (developer's calls, 2026-10-22):
  - One FOLDER, not a single .exe: starts faster (a one-file .exe unpacks
    itself on every launch) and is less likely to trip antivirus.
  - No browser bundled: the app drives the Microsoft Edge already on
    every Windows machine (see src/services/browser_launch.py). Only
    Playwright's small driver is bundled (Playwright's own PyInstaller
    hook does that automatically).
  - Per-user data lives in %LOCALAPPDATA%\\CaseloadTool, never in this
    folder (see src/services/app_paths.py), so replacing the folder with
    a newer build never touches anyone's groups/actions/templates.

PyInstaller is a developer-only tool (pip install pyinstaller).
"""
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

from src.services import app_paths
from src.services.guide_markdown import to_html_document

ROOT = Path(__file__).resolve().parent
APP_NAME = "CaseloadTool"


def _build_version() -> str:
    """e.g. "ebee7cc built 2026-10-28" - the git commit (plus "-dirty" when
    there are uncommitted changes) and the build date."""
    import subprocess
    from datetime import date

    try:
        commit = subprocess.run(
            ["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
    except OSError:
        commit = "unknown"
    return f"{commit} built {date.today().isoformat()}"


def main() -> None:
    # Start clean so a file removed from the project doesn't linger in the build.
    for leftover in (ROOT / "build", ROOT / "dist" / APP_NAME):
        shutil.rmtree(leftover, ignore_errors=True)

    # Which build this is, for the diagnostics log's startup line
    # (src/services/diagnostics.py reads it via app_paths.resource_path).
    version_file = ROOT / "build" / "version.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(_build_version(), encoding="utf-8")

    PyInstaller.__main__.run([
        str(ROOT / "main.py"),
        "--name", APP_NAME,
        "--onedir",
        "--windowed",  # no black console window behind the app
        "--noconfirm",
        # Read-only files the app ships with (found via app_paths.resource_path).
        "--add-data", f"{ROOT / 'src' / 'assets' / 'quill'};src/assets/quill",
        "--add-data", f"{ROOT / 'docs' / 'professor_guide.md'};docs",  # the in-app Help screen
        "--add-data", f"{version_file};.",
        # CustomTkinter's themes/fonts and the time-zone database are data
        # files, not code - make sure they're included.
        "--collect-data", "customtkinter",
        "--collect-data", "tzdata",
        # Modules only imported inside functions (so PyInstaller's scan can
        # miss them): Outlook automation and the Salesforce/Mongoose browser.
        "--hidden-import", "win32com.client",
        "--hidden-import", "pythoncom",
        "--hidden-import", "playwright.sync_api",
        # Developer/test-only packages - keep them out of the build.
        "--exclude-module", "pytest",
        "--exclude-module", "simple_salesforce",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ])

    # The printable handout, next to the .exe where professors will see it
    # (same source as the in-app Help screen - see guide_markdown.py).
    guide = (ROOT / "docs" / "professor_guide.md").read_text(encoding="utf-8")
    handout = ROOT / "dist" / APP_NAME / "Professor Guide.html"
    handout.write_text(to_html_document(guide), encoding="utf-8")

    app_folder = ROOT / "dist" / APP_NAME
    zip_name = APP_NAME
    if "--with-my-data" in sys.argv:
        starter = app_folder / app_paths.STARTER_DATA_FOLDER
        starter.mkdir()
        packed = []
        for name in app_paths.STARTER_FILES:
            source = app_paths.data_dir() / name
            if source.is_file():
                shutil.copy2(source, starter / name)
                packed.append(name)
        zip_name = f"{APP_NAME}-with-my-data"
        print(f"\nPacked your data: {', '.join(packed) or 'nothing found'}")
        if "test_mode.json" not in packed:
            print("WARNING: no test_mode.json - this copy will start LIVE (real emails) on the new computer.")

    for old_zip in (ROOT / "dist").glob(f"{APP_NAME}*.zip"):
        old_zip.unlink()
    zip_path = shutil.make_archive(str(ROOT / "dist" / zip_name), "zip", root_dir=ROOT / "dist", base_dir=APP_NAME)

    print(f"\nBuilt: {app_folder / (APP_NAME + '.exe')}")
    print(f"Guide: {handout}")
    print(f"Zip:   {zip_path}")


if __name__ == "__main__":
    main()
