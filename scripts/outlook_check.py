# scripts/outlook_check.py
"""One-off, run-by-hand diagnostic for the work laptop: answers every open
question about Outlook before the real OutlookEmailSender is built, in one
visit. Run it on the machine that has Outlook Classic:

    pip install pywin32
    python scripts/outlook_check.py

Deliberately standalone (imports nothing from src/), so it works before
the rest of the app is set up on that machine.

It only READS, except for one optional step at the end that sends a test
email to YOUR OWN address, and only after you type "y". It never touches
student data. Copy the whole printed report back into the chat.

What it checks:
  1. pywin32 is installed (the library the app uses to drive Outlook)
  2. Outlook Classic answers automation (the "New Outlook" can't)
  3. Which mailboxes/accounts are set up, and which one is the default
  4. Which signatures exist, their file encoding, and whether they
     contain images (images need extra handling when sending)
  5. Any IT policy settings that control Outlook's "a program is trying
     to send email" security prompt
  6. (Optional) A real test send to yourself with a chosen signature, to
     see whether that prompt appears and how the signature looks
"""
import os
import re
import sys
import threading
import time
import winreg
from pathlib import Path

DIVIDER = "-" * 70


def section(title: str) -> None:
    print(f"\n{DIVIDER}\n{title}\n{DIVIDER}")


def check_pywin32():
    section("1. pywin32")
    try:
        import win32com.client  # noqa: F401 - imported to prove it's available
        import pywintypes  # noqa: F401
    except ImportError:
        print("NOT INSTALLED. Run:  pip install pywin32   then run this script again.")
        return None
    print("OK - pywin32 is installed.")
    import win32com.client
    return win32com.client


def connect_to_outlook(win32com_client):
    section("2. Outlook Classic automation")
    print("Connecting to the Outlook that's already open...")
    # Connecting can block forever with no error if Outlook has a window open
    # that needs a human - e.g. the first-run "Welcome to Microsoft Outlook"
    # setup on a machine where Outlook is installed but never set up (this
    # actually happened on the dev machine). It can't be timed out safely,
    # so instead explain what's going on if it's taking too long.
    hint = threading.Timer(20, lambda: print(
        "\n...still waiting on Outlook. Look for an Outlook window asking for\n"
        "something (a 'Welcome' / account setup screen, a profile picker, or a\n"
        "security prompt). Finish or close it, or press Ctrl+C to stop.",
        flush=True,
    ))
    hint.daemon = True
    hint.start()
    try:
        # GetActiveObject, not Dispatch: Dispatch would START Outlook if it
        # isn't open - invisibly, with no window (this happened once and
        # left a hidden Outlook running for two days).
        outlook = win32com_client.GetActiveObject("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
    except Exception as exc:
        hint.cancel()
        print(f"FAILED to connect: {exc}")
        print("First: is Outlook open? Open it, let it finish loading, then rerun this.")
        print("Other causes: Outlook Classic isn't installed (the 'New Outlook'")
        print("has no automation support), or IT has blocked automation.")
        print("If you're on New Outlook, check for a 'New Outlook' toggle at the")
        print("top right of Outlook and switch it off, then rerun.")
        return None, None
    hint.cancel()
    print(f"OK - connected. Outlook version: {outlook.Version}")
    return outlook, namespace


def list_accounts(namespace):
    section("3. Accounts / mailboxes")
    accounts = []
    try:
        for i in range(1, namespace.Accounts.Count + 1):
            account = namespace.Accounts.Item(i)
            accounts.append(account)
            print(f"  [{i}] {account.DisplayName}  <{account.SmtpAddress}>")
    except Exception as exc:
        print(f"Couldn't list accounts: {exc}")
    if not accounts:
        print("  (none found)")
    try:
        default_store = namespace.DefaultStore.DisplayName
        print(f"Default mailbox: {default_store}")
    except Exception as exc:
        print(f"Couldn't read default mailbox: {exc}")
    if len(accounts) > 1:
        print("NOTE: more than one account - the app will need to know which to send from.")
    return accounts


def _read_signature_html(path: Path):
    """Outlook usually saves signature .htm files as Windows-1252 with a
    <meta charset> tag; some are UTF-8. Returns (text, encoding_used)."""
    raw = path.read_bytes()
    match = re.search(rb'charset="?([\w-]+)', raw[:2000], re.IGNORECASE)
    candidates = ([match.group(1).decode("ascii")] if match else []) + ["utf-8", "cp1252"]
    for encoding in candidates:
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("cp1252", errors="replace"), "cp1252 (with replacements)"


def list_signatures():
    section("4. Signatures")
    appdata = os.environ.get("APPDATA")
    folder = Path(appdata) / "Microsoft" / "Signatures" if appdata else None
    if not folder or not folder.is_dir():
        print(f"No signatures folder found at {folder}")
        return []
    print(f"Folder: {folder}")
    found = []
    for htm in sorted(folder.glob("*.htm")):
        html, encoding = _read_signature_html(htm)
        image_refs = re.findall(r'src="([^"]+)"', html, re.IGNORECASE)
        files_dir = folder / f"{htm.stem}_files"
        print(f"  - {htm.stem}")
        print(f"      encoding: {encoding}, size: {len(html)} chars")
        print(f"      images referenced: {len(image_refs)}"
              + (f" (e.g. {image_refs[0]})" if image_refs else ""))
        print(f"      '{files_dir.name}' folder exists: {files_dir.is_dir()}")
        found.append((htm.stem, html, image_refs))
    if not found:
        print("  (no .htm signatures found)")
    return found


def check_security_policy():
    section("5. Programmatic-access (security prompt) policy")
    print("Values found (none found = Outlook's default: no prompt while")
    print("antivirus is active and up to date):")
    locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Policies\Microsoft\Office\16.0\Outlook\Security"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Office\16.0\Outlook\Security"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Office\16.0\Outlook\Security"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Office\16.0\Outlook\Security"),
    ]
    interesting = {"ObjectModelGuard", "PromptOOMSend", "AdminSecurityMode", "PromptOOMAddressBookAccess"}
    any_found = False
    for hive, key_path in locations:
        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            with winreg.OpenKey(hive, key_path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    if name in interesting:
                        print(f"  {hive_name}\\{key_path}\\{name} = {value}")
                        any_found = True
                    i += 1
        except OSError:
            continue  # key doesn't exist - normal
    if not any_found:
        print("  (none)")
    print("Reference: ObjectModelGuard 0 = warn only if antivirus is inactive,")
    print("1 = always warn, 2 = never warn. PromptOOMSend 0 = prompt user,")
    print("1 = auto-deny (sending would fail), 2 = auto-approve.")


def optional_test_send(outlook, accounts, signatures):
    section("6. Optional test send (to yourself only)")
    if not accounts:
        print("Skipped - no accounts found.")
        return
    to_address = accounts[0].SmtpAddress
    answer = input(f"Send ONE test email to your own address ({to_address})? [y/N]: ").strip().lower()
    if answer != "y":
        print("Skipped.")
        return

    signature_html = ""
    if signatures:
        print("Signatures:")
        for i, (name, _, _) in enumerate(signatures, start=1):
            print(f"  [{i}] {name}")
        choice = input("Pick a signature number to append (Enter for none): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(signatures):
            name, signature_html, image_refs = signatures[int(choice) - 1]
            print(f"Using signature '{name}'.")
            if image_refs:
                print("NOTE: this signature has images. This test appends the HTML as-is,")
                print("so images will probably show as broken - that's expected, and is")
                print("exactly what this test is meant to reveal.")

    body = (
        "<p>This is a test email from the caseload tool's scripts/outlook_check.py.</p>"
        "<p>If you can read this, automated sending through Outlook works.</p>"
        "<p><b>Bold</b>, <i>italic</i>, and a <a href='https://www.wgu.edu'>link</a>.</p>"
    )
    try:
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to_address
        mail.Subject = "Caseload tool - Outlook test"
        mail.HTMLBody = body + signature_html
        mail.SendUsingAccount = accounts[0]
        print("Sending... (if Outlook shows a security prompt, note what it says")
        print("and whether you had to click Allow - that's important to report)")
        started = time.monotonic()
        mail.Send()
        print(f"Send() returned after {time.monotonic() - started:.1f}s with no error.")
        print("Check your inbox (it may sit in Outbox briefly), and report:")
        print("  - did it arrive?  - did a security prompt appear?")
        print("  - does the signature look right (fonts, images, links)?")
    except Exception as exc:
        print(f"Send FAILED: {exc}")


def main() -> None:
    # Print each line immediately, so if Outlook hangs the report so far is
    # still visible (and the 20s hint above actually shows up).
    sys.stdout.reconfigure(line_buffering=True)
    print("Caseload tool - Outlook check")
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    win32com_client = check_pywin32()
    if win32com_client is None:
        return
    outlook, namespace = connect_to_outlook(win32com_client)
    accounts = list_accounts(namespace) if namespace is not None else []
    signatures = list_signatures()
    check_security_policy()
    if outlook is not None:
        optional_test_send(outlook, accounts, signatures)
    section("Done - copy everything above into the chat.")


if __name__ == "__main__":
    main()
