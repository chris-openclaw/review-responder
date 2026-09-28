"""
Shared helpers for Review Responder.

Handles three things every script needs to get right:
  - Reading the OAuth app credentials from environment variables
    (never from files, never printed)
  - Validating client IDs so they can't be used to write outside clients/
  - Writing files that hold credentials or review data with owner-only
    permissions (0600) inside owner-only directories (0700)
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.resolve()
CLIENTS_DIR = SKILL_DIR / "clients"
PENDING_DIR = SKILL_DIR / "pending"
LOG_FILE = SKILL_DIR / "review_log.json"

SCOPES = ["https://www.googleapis.com/auth/business.manage"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

ENV_CLIENT_ID = "GBP_OAUTH_CLIENT_ID"
ENV_CLIENT_SECRET = "GBP_OAUTH_CLIENT_SECRET"

# Lowercase letters, digits, hyphens. Must start with a letter or digit.
CLIENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def validate_client_id(client_id: str) -> str:
    """Return the client ID if it's a safe slug, otherwise exit."""
    client_id = (client_id or "").strip()
    if not CLIENT_ID_RE.fullmatch(client_id):
        print(
            f"Error: invalid client ID {client_id!r}. Use lowercase letters, "
            "digits and hyphens only (for example: joes-pizza)."
        )
        sys.exit(1)
    return client_id


def is_valid_client_id(client_id: str) -> bool:
    return bool(CLIENT_ID_RE.fullmatch((client_id or "").strip()))


def get_oauth_app_credentials() -> "tuple[str, str]":
    """Read the Google OAuth app credentials from the environment."""
    client_id = os.environ.get(ENV_CLIENT_ID, "").strip()
    client_secret = os.environ.get(ENV_CLIENT_SECRET, "").strip()
    if not client_id or not client_secret:
        print(
            f"Error: set {ENV_CLIENT_ID} and {ENV_CLIENT_SECRET} in the "
            "environment. See SETUP.md, step 3."
        )
        sys.exit(1)
    return client_id, client_secret


def ensure_private_dir(path: Path) -> Path:
    """Create a directory readable only by the current user."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def write_private_json(path: Path, data: dict) -> None:
    """Atomically write JSON with 0600 permissions."""
    ensure_private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)
