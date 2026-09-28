#!/usr/bin/env python3
"""
OPTIONAL: web-based onboarding for clients you can't sit with in person.

Most operators should use get_client_token.py instead. Use this only when a
client needs to authorize remotely, and shut it down as soon as they're done.

What it does:
  - Runs a small Flask web server with two routes: /auth/start and /auth/callback
  - Sends the client to Google to grant "manage Business Profile" access
  - Saves the resulting refresh token to clients/<client>.json (mode 0600)

Safety rules built in:
  - Refuses to start unless GBP_PUBLIC_URL is https:// (plain http is allowed
    only for localhost testing)
  - Listens on 127.0.0.1 by default; put it behind an HTTPS reverse proxy
    (e.g. Caddy) or an SSH tunnel rather than exposing the port
  - Every onboarding link must carry the secret GBP_ONBOARD_TOKEN
  - Client IDs must be simple slugs, so nothing can be written outside clients/
  - OAuth state is verified on the callback
  - Shuts itself down after GBP_ONBOARD_MAX_MINUTES (default 60)
  - Never displays or logs tokens, secrets or file paths

Environment:
  GBP_OAUTH_CLIENT_ID, GBP_OAUTH_CLIENT_SECRET   Web-application OAuth client
  GBP_PUBLIC_URL        e.g. https://reviews.example.com
  GBP_ONBOARD_TOKEN     long random string, e.g. `openssl rand -hex 24`
  GBP_BIND_HOST         default 127.0.0.1
  GBP_BIND_PORT         default 5050
  GBP_ONBOARD_MAX_MINUTES  default 60

Usage:
  python3 oauth_server.py
  Send the client: https://reviews.example.com/auth/start?client=joes-pizza&token=<GBP_ONBOARD_TOKEN>

Requires:
  pip install flask google-auth-oauthlib requests
"""

import hmac
import html
import os
import secrets
import sys
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    from flask import Flask, redirect, request, session
    from google_auth_oauthlib.flow import Flow
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install flask google-auth-oauthlib requests")
    sys.exit(1)

from get_client_token import lookup_ids
from rr_common import (
    CLIENTS_DIR,
    SCOPES,
    TOKEN_URI,
    get_oauth_app_credentials,
    is_valid_client_id,
    read_json,
    write_private_json,
)

REDIRECT_PATH = "/auth/callback"


def load_settings():
    public_url = os.environ.get("GBP_PUBLIC_URL", "").strip().rstrip("/")
    onboard_token = os.environ.get("GBP_ONBOARD_TOKEN", "").strip()
    parsed = urlparse(public_url)
    local = parsed.hostname in ("localhost", "127.0.0.1")

    if not public_url or parsed.scheme not in ("http", "https"):
        sys.exit("Error: set GBP_PUBLIC_URL, e.g. https://reviews.example.com")
    if parsed.scheme != "https" and not local:
        sys.exit("Error: GBP_PUBLIC_URL must use https:// (plain http is only allowed for localhost).")
    if len(onboard_token) < 24:
        sys.exit("Error: set GBP_ONBOARD_TOKEN to a random string of at least 24 characters "
                 "(for example: openssl rand -hex 24).")
    if local and parsed.scheme == "http":
        # Only permitted for a server reachable solely from this machine.
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    return {
        "public_url": public_url,
        "https": parsed.scheme == "https",
        "onboard_token": onboard_token,
        "host": os.environ.get("GBP_BIND_HOST", "127.0.0.1"),
        "port": int(os.environ.get("GBP_BIND_PORT", "5050")),
        "max_minutes": int(os.environ.get("GBP_ONBOARD_MAX_MINUTES", "60")),
    }


SETTINGS = load_settings()
APP_ID, APP_SECRET = get_oauth_app_credentials()
REDIRECT_URI = f"{SETTINGS['public_url']}{REDIRECT_PATH}"

app = Flask(__name__)
app.secret_key = secrets.token_bytes(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SETTINGS["https"],
)


def get_flow(state=None):
    return Flow.from_client_config(
        {
            "web": {
                "client_id": APP_ID,
                "client_secret": APP_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": TOKEN_URI,
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state,
    )


def page(title: str, body: str, status: int = 200):
    return (f"<!doctype html><title>{html.escape(title)}</title>"
            f"<h2>{html.escape(title)}</h2><p>{body}</p>"), status


@app.route("/")
def index():
    return page("Review Responder", "Use the authorization link you were sent.")


@app.route("/auth/start")
def auth_start():
    token = request.args.get("token", "")
    if not hmac.compare_digest(token.encode(), SETTINGS["onboard_token"].encode()):
        return page("Link not valid", "Ask for a new authorization link.", 403)

    client_id = request.args.get("client", "").strip()
    if not is_valid_client_id(client_id):
        return page("Link not valid", "The client name in this link isn't valid.", 400)

    flow = get_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session.clear()
    session["client_id"] = client_id
    session["oauth_state"] = state
    # PKCE: the verifier must survive to the callback's token exchange.
    session["code_verifier"] = getattr(flow, "code_verifier", None)
    return redirect(auth_url)


@app.route(REDIRECT_PATH)
def auth_callback():
    client_id = session.pop("client_id", None)
    state = session.pop("oauth_state", None)
    code_verifier = session.pop("code_verifier", None)
    if not client_id or not state or request.args.get("state") != state:
        return page("Session expired", "Please open your authorization link again.", 400)
    if "error" in request.args:
        return page("Authorization cancelled", "No access was granted. You can close this window.", 400)

    # Rebuild the callback URL from the configured public URL so this works
    # correctly behind an HTTPS reverse proxy.
    authorization_response = f"{REDIRECT_URI}?{request.query_string.decode()}"
    flow = get_flow(state=state)
    if code_verifier:
        flow.code_verifier = code_verifier
    try:
        flow.fetch_token(authorization_response=authorization_response)
    except Exception:
        return page("Authorization failed", "Please try your link again.", 400)

    creds = flow.credentials
    if not creds.refresh_token:
        return page(
            "One more step",
            "Google didn't issue a long-term token, usually because this app was authorized before. "
            'Remove it at <a href="https://myaccount.google.com/permissions">Google Account permissions</a>, '
            "then open your link again.",
            400,
        )

    config_path = CLIENTS_DIR / f"{client_id}.json"
    config = read_json(config_path, {}) or {}
    config.pop("oauth_client_id", None)
    config.pop("oauth_client_secret", None)
    config.setdefault("client_id", client_id)
    config.setdefault("business_name", client_id)
    config.setdefault("account_id", "NEEDS_LOOKUP")
    config.setdefault("location_id", "NEEDS_LOOKUP")
    config.setdefault("industry", "general")
    config.setdefault("tone_notes", "")
    config["refresh_token"] = creds.refresh_token
    config["authorized_at"] = datetime.now(timezone.utc).isoformat()

    found = lookup_ids(creds.token)
    all_locs = [(a, loc) for a, _, locs in found for loc, _t in locs]
    if len(all_locs) == 1:
        config["account_id"], config["location_id"] = all_locs[0]

    write_private_json(config_path, config)
    print(f"[{config['authorized_at']}] Authorized client '{client_id}'.")
    return page("All set", "Thanks! Access was granted successfully. You can close this window.")


def shutdown_later(minutes: int):
    def stop():
        print(f"Onboarding window of {minutes} minutes has ended. Shutting down.")
        os._exit(0)
    t = threading.Timer(minutes * 60, stop)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    shutdown_later(SETTINGS["max_minutes"])
    print(f"Onboarding server listening on {SETTINGS['host']}:{SETTINGS['port']}")
    print(f"Public URL: {SETTINGS['public_url']}")
    print(f"Client link format: {SETTINGS['public_url']}/auth/start?client=<client-id>&token=<GBP_ONBOARD_TOKEN>")
    print(f"This server stops automatically in {SETTINGS['max_minutes']} minutes.")
    app.run(host=SETTINGS["host"], port=SETTINGS["port"])
