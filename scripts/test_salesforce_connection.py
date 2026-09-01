# scripts/test_salesforce_connection.py
"""One-off diagnostic: confirms whether username/password/security-token
API access actually works against your Salesforce org, before any real
adapter code gets built against it. Read-only - attempts to log in and
run one harmless query, doesn't touch any data.

Run manually:

    python scripts/test_salesforce_connection.py

Credentials are read from environment variables, never hardcoded and
never typed into chat:
    SF_USERNAME         - your Salesforce login (usually your email)
    SF_PASSWORD         - your Salesforce password
    SF_SECURITY_TOKEN   - from Settings -> (search) "Reset My Security
                           Token" - resetting emails you a new one
    SF_DOMAIN           - optional; "login" (default, production) or
                           "test" (sandbox). If your org has a custom "My
                           Domain" (e.g. you log in via
                           https://<name>.lightning.force.com), the
                           generic "login" endpoint is often blocked and
                           returns the same INVALID_LOGIN error as bad
                           credentials - use "<name>.my" instead (NOT the
                           lightning.force.com host itself - that's the
                           Lightning UI domain, not the API/login one).
                           simple_salesforce builds the URL as
                           https://{SF_DOMAIN}.salesforce.com/..., so
                           "<name>.my" resolves to the real
                           <name>.my.salesforce.com API host.

If login fails, simple_salesforce's exception message usually says
exactly why (bad credentials, API_DISABLED_FOR_ORG, IP restriction,
etc.) - that's the useful part even on failure.
"""
import os
import sys

from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceAuthenticationFailed


def main() -> None:
    username = os.environ.get("SF_USERNAME")
    password = os.environ.get("SF_PASSWORD")
    security_token = os.environ.get("SF_SECURITY_TOKEN")
    domain = os.environ.get("SF_DOMAIN", "login")

    missing = [
        name for name, value in [
            ("SF_USERNAME", username), ("SF_PASSWORD", password), ("SF_SECURITY_TOKEN", security_token),
        ]
        if not value
    ]
    if missing:
        print(f"Missing environment variable(s): {', '.join(missing)}")
        print("Set them locally (never in chat/code) before running this script.")
        sys.exit(1)

    print(f"Attempting login to Salesforce (domain='{domain}')...")
    try:
        sf = Salesforce(username=username, password=password, security_token=security_token, domain=domain)
    except SalesforceAuthenticationFailed as exc:
        print("LOGIN FAILED.")
        print(f"  {exc}")
        print("\nThis error message is the useful part - it usually names the exact")
        print("reason (bad credentials, API_DISABLED_FOR_ORG, IP restriction, etc.).")
        sys.exit(1)

    print("LOGIN SUCCEEDED.")
    print(f"  Instance: {sf.sf_instance}")
    print(f"  Session ID present: {bool(sf.session_id)}")

    try:
        result = sf.query("SELECT Id, Name FROM Organization LIMIT 1")
        org_name = result["records"][0]["Name"] if result.get("records") else "(no records returned)"
        print(f"  Test query succeeded - Organization Name: {org_name}")
    except Exception as exc:
        print(f"  Login worked, but the test query failed: {exc}")
        print("  (This can still mean API access is fine but this specific object/field isn't queryable.)")


if __name__ == "__main__":
    main()
