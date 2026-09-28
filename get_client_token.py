#!/usr/bin/env python3
"""
One-time Google authorization for a new client, run on the operator's own
computer (the client signs in on that computer, or screen-shares).

Usage:
  python3 get_client_token.py --client joes-pizza

What it does:
  1. Opens a browser so the client can sign in with the Google account that
     owns their Business Profile and grant "manage Business Profile" access.
     The redirect goes to a temporary server on localhost only.
  2. Saves the resulting refresh token straight into clients/<client>.json
     with owner-only permissions (0600). The token is never printed.
  3. Looks up the client's account and location IDs and fills them in when
     there is exactly one of each; otherwise it lists them so you can choose.

Network calls:
  - accounts.google.com / oauth2.googleapis.com         (sign-in and token exchange)
  - mybusinessaccountmanagement.googleapis.com           (list accounts)
  - mybusinessbusinessinformation.googleapis.com         (list locations)

Before running:
  export GBP_OAUTH_CLIENT_ID=...     # Desktop-app OAuth client (SETUP.md, step 2)
  export GBP_OAUTH_CLIENT_SECRET=...
  pip install google-auth-oauthlib requests
"""

import argparse
import sys
from datetime import datetime, timezone

try:
    import requests
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install google-auth-oauthlib requests")
    sys.exit(1)

from rr_common import (
    CLIENTS_DIR,
    SCOPES,
    TOKEN_URI,
    get_oauth_app_credentials,
    read_json,
    validate_client_id,
    write_private_json,
)

TIMEOUT = 30


def lookup_ids(access_token: str):
    """Return [(account_name, account_title, [(location_name, title), ...]), ...]."""
    headers = {"Authorization": f"Bearer {access_token}"}
    out = []
    resp = requests.get(
        "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
        headers=headers, timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        print(f"Could not list accounts ({resp.status_code}). Fill in account_id and location_id by hand.")
        return out
    for acct in resp.json().get("accounts", []):
        name = acct.get("name", "")
        lresp = requests.get(
            f"https://mybusinessbusinessinformation.googleapis.com/v1/{name}/locations",
            headers=headers, params={"readMask": "name,title", "pageSize": 100}, timeout=TIMEOUT,
        )
        locs = []
        if lresp.status_code == 200:
            locs = [(l.get("name", ""), l.get("title", "")) for l in lresp.json().get("locations", [])]
        out.append((name, acct.get("accountName", ""), locs))
    return out


def main():
    parser = argparse.ArgumentParser(description="Authorize a new Review Responder client")
    parser.add_argument("--client", required=True, help="Client ID to save under (e.g. joes-pizza)")
    parser.add_argument("--business-name", help="Display name (defaults to the client ID)")
    args = parser.parse_args()

    client_id = validate_client_id(args.client)
    app_id, app_secret = get_oauth_app_credentials()

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": app_id,
                "client_secret": app_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": TOKEN_URI,
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )

    print("Opening a browser for Google sign-in.")
    print("The client should sign in with the Google account that owns their Business Profile.\n")
    creds = flow.run_local_server(host="localhost", bind_addr="127.0.0.1", port=0, open_browser=True)

    if not creds.refresh_token:
        print(
            "No refresh token was returned. The client may have authorized this app before.\n"
            "Have them remove it at https://myaccount.google.com/permissions and run this again."
        )
        sys.exit(1)

    config_path = CLIENTS_DIR / f"{client_id}.json"
    config = read_json(config_path, {}) or {}
    config.pop("oauth_client_id", None)
    config.pop("oauth_client_secret", None)
    config.setdefault("client_id", client_id)
    config.setdefault("business_name", args.business_name or client_id)
    config.setdefault("account_id", "NEEDS_LOOKUP")
    config.setdefault("location_id", "NEEDS_LOOKUP")
    config.setdefault("industry", "general")
    config.setdefault("tone_notes", "")
    config["refresh_token"] = creds.refresh_token
    config["authorized_at"] = datetime.now(timezone.utc).isoformat()

    found = lookup_ids(creds.token)
    all_locs = [(a, l) for a, _, locs in found for l in locs]
    if len(all_locs) == 1:
        acct, (loc, title) = all_locs[0]
        config["account_id"] = acct
        config["location_id"] = loc
        print(f"Found one location: {title} ({loc}). Saved it to the config.")
    elif all_locs:
        print("This Google account manages several locations. Put the right pair in the config:")
        for acct, title, locs in found:
            print(f"  account_id: {acct}  ({title})")
            for loc, ltitle in locs:
                print(f"      location_id: {loc}  ({ltitle})")

    write_private_json(config_path, config)
    print(f"\nAuthorization saved to clients/{client_id}.json (permissions 600).")
    print("The refresh token is stored there and is not shown here.")
    print(f"Test it with: python3 gbp_reviews.py check --client {client_id}")


if __name__ == "__main__":
    main()
