#!/usr/bin/env python3
"""
Google Business Profile Review Manager for OpenClaw
----------------------------------------------------
Fetches unanswered reviews, tracks drafts through an explicit approval
step, and posts a reply only after that approval has been recorded.

Usage:
  python3 gbp_reviews.py check   --client <client_id>
  python3 gbp_reviews.py pending
  python3 gbp_reviews.py draft   --client <client_id> --review <review_id> --text "Draft reply"
  python3 gbp_reviews.py approve --client <client_id> --review <review_id> --via telegram [--text "Edited reply"]
  python3 gbp_reviews.py skip    --client <client_id> --review <review_id>
  python3 gbp_reviews.py reply   --client <client_id> --review <review_id>

Posting rules (enforced by this script, not just by the instructions):
  - `reply` only works for a review that `check` saved to pending/
  - `reply` only works after `approve` has recorded an approval
  - `reply` posts the exact text that was approved; it takes no text argument

Network calls:
  - https://oauth2.googleapis.com/token        (refresh the access token)
  - https://mybusiness.googleapis.com/v4/...   (list reviews, post a reply)
  Nothing else.

Credentials:
  - GBP_OAUTH_CLIENT_ID / GBP_OAUTH_CLIENT_SECRET come from the environment
  - Each client's refresh token lives in clients/<client_id>.json (mode 0600)
  - Credentials are never printed or written anywhere else

Requires:
  pip install google-auth requests
"""

import argparse
import os
import re
import stat
import sys
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError:
    print("Missing dependencies. Run:")
    print("  pip install google-auth requests")
    sys.exit(1)

from rr_common import (
    CLIENTS_DIR,
    LOG_FILE,
    PENDING_DIR,
    SCOPES,
    TOKEN_URI,
    get_oauth_app_credentials,
    read_json,
    validate_client_id,
    write_private_json,
)

GBP_API = "https://mybusiness.googleapis.com/v4"
REVIEW_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
MAX_REPLY_BYTES = 4096  # Google's limit for a review reply
REQUEST_TIMEOUT = 30
APPROVAL_CHANNELS = ("telegram", "email", "webhook", "chat")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_review_id(review_id: str) -> str:
    if not REVIEW_ID_RE.fullmatch(review_id or ""):
        print(f"Error: invalid review ID {review_id!r}.")
        sys.exit(1)
    return review_id


def validate_reply_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        print("Error: reply text is empty.")
        sys.exit(1)
    if len(text.encode("utf-8")) > MAX_REPLY_BYTES:
        print(f"Error: reply is longer than Google's {MAX_REPLY_BYTES}-byte limit.")
        sys.exit(1)
    return text


# --- Client config ---------------------------------------------------------

def load_client_config(client_id: str) -> dict:
    """Load clients/<client_id>.json and tighten its permissions if needed."""
    config_path = CLIENTS_DIR / f"{client_id}.json"
    if not config_path.exists():
        print(f"Error: no config for client '{client_id}'. See SETUP.md, per-client onboarding.")
        sys.exit(1)

    mode = stat.S_IMODE(config_path.stat().st_mode)
    if mode & 0o077:
        os.chmod(config_path, 0o600)
        print(f"Note: tightened permissions on clients/{client_id}.json to 600.")

    config = read_json(config_path, {})
    for field in ("account_id", "location_id", "refresh_token"):
        value = config.get(field, "")
        if not value or value == "NEEDS_LOOKUP":
            print(f"Error: '{field}' is missing in clients/{client_id}.json.")
            sys.exit(1)
    if "oauth_client_secret" in config:
        print(
            f"Warning: clients/{client_id}.json still contains oauth_client_secret. "
            "It is no longer used; delete that line (see SETUP.md, 'Upgrading from 2.0')."
        )
    return config


def get_access_token(config: dict) -> str:
    """Exchange the client's refresh token for a short-lived access token."""
    app_id, app_secret = get_oauth_app_credentials()
    creds = Credentials(
        token=None,
        refresh_token=config["refresh_token"],
        client_id=app_id,
        client_secret=app_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds.token


def location_path(config: dict) -> str:
    account = str(config["account_id"]).removeprefix("accounts/")
    location = str(config["location_id"]).removeprefix("locations/")
    return f"accounts/{account}/locations/{location}"


# --- Local state -----------------------------------------------------------

def load_review_log() -> dict:
    return read_json(LOG_FILE, {})


def save_review_log(log: dict):
    write_private_json(LOG_FILE, log)


def pending_path(client_id: str, review_id: str):
    return PENDING_DIR / f"{client_id}_{review_id}.json"


def load_pending(client_id: str, review_id: str) -> dict:
    path = pending_path(client_id, review_id)
    data = read_json(path)
    if data is None:
        print(
            f"Error: no pending review {review_id} for client '{client_id}'. "
            "Only reviews found by `check` can be drafted, approved or replied to."
        )
        sys.exit(1)
    return data


def update_log(review_id: str, **fields):
    log = load_review_log()
    if review_id in log:
        log[review_id].update(fields)
        save_review_log(log)


# --- Commands --------------------------------------------------------------

def check_reviews(client_id: str):
    """Fetch unanswered reviews and save new ones to pending/."""
    config = load_client_config(client_id)
    token = get_access_token(config)

    url = f"{GBP_API}/{location_path(config)}/reviews"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"pageSize": 50, "orderBy": "updateTime desc"}

    resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        print(f"Google API error ({resp.status_code}) while listing reviews for '{client_id}'.")
        sys.exit(1)

    reviews = resp.json().get("reviews", [])
    log = load_review_log()
    new_count = 0

    for review in reviews:
        review_id = review.get("reviewId", "")
        if not REVIEW_ID_RE.fullmatch(review_id):
            continue
        if review.get("reviewReply") is not None or review_id in log:
            continue

        name = review.get("reviewer", {}).get("displayName", "A customer")
        star = review.get("starRating", "UNKNOWN")
        comment = review.get("comment", "(no comment)")

        path = pending_path(client_id, review_id)
        write_private_json(path, {
            "client_id": client_id,
            "review_id": review_id,
            "reviewer_name": name,
            "star_rating": star,
            "comment": comment,
            "create_time": review.get("createTime", ""),
            "saved_at": now(),
            "status": "pending_draft",
            "draft_text": None,
            "approved_text": None,
            "approved_at": None,
            "approved_via": None,
        })
        log[review_id] = {"client_id": client_id, "first_seen": now(), "status": "pending_draft"}
        new_count += 1

        print(f"\n--- NEW REVIEW ({client_id}) ---")
        print(f"Review ID: {review_id}")
        print(f"From: {name}")
        print(f"Rating: {star}")
        print(f"Comment: {comment}")

    save_review_log(log)
    if new_count == 0:
        print(f"No new unanswered reviews for client '{client_id}'.")
    else:
        print(f"\nFound {new_count} new unanswered review(s) for client '{client_id}'.")


def save_draft(client_id: str, review_id: str, text: str):
    """Store the agent's draft. Drafting never makes anything postable."""
    data = load_pending(client_id, review_id)
    if data.get("status") == "approved":
        print("This review is already approved. Run `skip` and `check` again to start over.")
        sys.exit(1)
    data["draft_text"] = validate_reply_text(text)
    data["status"] = "awaiting_approval"
    data["drafted_at"] = now()
    write_private_json(pending_path(client_id, review_id), data)
    update_log(review_id, status="awaiting_approval")
    print(f"Draft saved for review {review_id}. Send it to the operator for approval.")


def approve(client_id: str, review_id: str, via: str, text: Optional[str]):
    """Record the operator's approval, with either the draft or their edited text."""
    data = load_pending(client_id, review_id)
    if text is not None:
        final = validate_reply_text(text)
        decision = "edited"
    elif data.get("draft_text"):
        final = data["draft_text"]
        decision = "approved_as_is"
    else:
        print("Error: there is no saved draft to approve. Save one with `draft`, or pass --text.")
        sys.exit(1)

    data.update({
        "status": "approved",
        "approved_text": final,
        "approved_at": now(),
        "approved_via": via,
        "decision": decision,
    })
    write_private_json(pending_path(client_id, review_id), data)
    update_log(review_id, status="approved", approved_via=via)
    print(f"Approval recorded for review {review_id} ({decision}, via {via}).")


def skip(client_id: str, review_id: str):
    path = pending_path(client_id, review_id)
    load_pending(client_id, review_id)
    path.unlink()
    update_log(review_id, status="skipped", skipped_at=now())
    print(f"Review {review_id} skipped. No reply will be posted.")


def post_reply(client_id: str, review_id: str):
    """Post the approved text. Refuses anything that hasn't been approved."""
    data = load_pending(client_id, review_id)
    if data.get("status") != "approved" or not data.get("approved_text"):
        print(
            f"Refusing to post: review {review_id} has no recorded approval "
            f"(status: {data.get('status')}). Run `approve` after the operator says OK."
        )
        sys.exit(1)

    reply_text = validate_reply_text(data["approved_text"])
    config = load_client_config(client_id)
    token = get_access_token(config)

    url = f"{GBP_API}/{location_path(config)}/reviews/{review_id}/reply"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, json={"comment": reply_text}, timeout=REQUEST_TIMEOUT)

    if resp.status_code in (200, 201):
        update_log(review_id, status="replied", replied_at=now(), approved_via=data.get("approved_via"))
        pending_path(client_id, review_id).unlink(missing_ok=True)
        print(f"Reply posted to review {review_id}.")
    else:
        print(f"Failed to post reply ({resp.status_code}). The approval is kept; you can retry `reply`.")
        sys.exit(1)


def list_pending():
    files = sorted(PENDING_DIR.glob("*.json")) if PENDING_DIR.exists() else []
    if not files:
        print("No pending reviews.")
        return
    print(f"Found {len(files)} pending review(s):\n")
    for f in files:
        data = read_json(f, {})
        print(f"  Client: {data.get('client_id')}")
        print(f"  Review: {data.get('review_id')}")
        print(f"  Status: {data.get('status', 'pending_draft')}")
        print(f"  From: {data.get('reviewer_name')} ({data.get('star_rating')})")
        print(f"  Comment: {str(data.get('comment', ''))[:120]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Google Business Profile Review Manager")
    sub = parser.add_subparsers(dest="command")

    def client_and_review(p):
        p.add_argument("--client", required=True, help="Client ID (e.g. joes-pizza)")
        p.add_argument("--review", required=True, help="Review ID")

    p = sub.add_parser("check", help="Fetch new unanswered reviews into pending/")
    p.add_argument("--client", required=True, help="Client ID (e.g. joes-pizza)")

    sub.add_parser("pending", help="List pending reviews and their status")

    p = sub.add_parser("draft", help="Save a draft reply (does not approve or post)")
    client_and_review(p)
    p.add_argument("--text", required=True, help="Draft reply text")

    p = sub.add_parser("approve", help="Record the operator's approval")
    client_and_review(p)
    p.add_argument("--via", required=True, choices=APPROVAL_CHANNELS,
                   help="Channel the operator approved through")
    p.add_argument("--text", help="Operator's edited text (omit to approve the saved draft)")

    p = sub.add_parser("skip", help="Drop a pending review without replying")
    client_and_review(p)

    p = sub.add_parser("reply", help="Post the approved reply to Google")
    client_and_review(p)

    args = parser.parse_args()

    if args.command == "pending":
        list_pending()
        return
    if args.command is None:
        parser.print_help()
        return

    client_id = validate_client_id(args.client)
    if args.command == "check":
        check_reviews(client_id)
        return

    review_id = validate_review_id(args.review)
    if args.command == "draft":
        save_draft(client_id, review_id, args.text)
    elif args.command == "approve":
        approve(client_id, review_id, args.via, args.text)
    elif args.command == "skip":
        skip(client_id, review_id)
    elif args.command == "reply":
        post_reply(client_id, review_id)


if __name__ == "__main__":
    main()
