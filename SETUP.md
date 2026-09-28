# Review Responder: Setup Guide

## One-Time Setup (Your VPS)

### 1. Install Python Dependencies
Python 3.9 or newer.
```bash
pip install google-auth google-auth-oauthlib requests
```
Add `flask` only if you plan to use the optional onboarding server (see Remote Onboarding below).

### 2. Create a Google Cloud Project
1. Go to https://console.cloud.google.com
2. Create a new project (e.g., "Review Responder")
3. Enable the **Google My Business API**, the **My Business Account Management API** and the **My Business Business Information API**
4. Go to **Credentials** > **Create Credentials** > **OAuth 2.0 Client ID**
5. Choose the application type based on how you'll onboard clients. Use one OAuth client for everything, because each client's refresh token only works with the OAuth client that issued it.
   - **Desktop app**: you'll run `get_client_token.py` with the client present or screen-sharing (recommended)
   - **Web application**: you'll use the optional `oauth_server.py`. Add `https://<your-domain>/auth/callback` as an authorized redirect URI.
6. Keep the **Client ID** and **Client Secret** for the next step. Don't put them in any file inside the skill folder.

### 3. Set Your Credentials as Environment Variables
The scripts read your OAuth app credentials from the environment only:
```bash
export GBP_OAUTH_CLIENT_ID="1234-abc.apps.googleusercontent.com"
export GBP_OAUTH_CLIENT_SECRET="your-client-secret"
```
Put these wherever OpenClaw gets its environment on your VPS (for example your service's environment file or OpenClaw's secrets settings), not in a file that's committed or shared. If you use a plain env file, lock it down: `chmod 600 <file>`.

### 4. Copy Files to Your OpenClaw Workspace
```bash
cp -r review-responder ~/.openclaw/workspace/review-responder
chmod 700 ~/.openclaw/workspace/review-responder/clients
```

### 5. Register the Skill
Add the skill to your OpenClaw config (openclaw.json):
```json
{
  "skills": {
    "entries": {
      "review-responder": {
        "path": "~/.openclaw/workspace/review-responder/SKILL.md"
      }
    }
  }
}
```

### 6. Wire Up the Heartbeat
Append the review check instructions to your HEARTBEAT.md, or reference `review-responder/HEARTBEAT.md` in your heartbeat config. If your HEARTBEAT.md was written for version 2.0, update any `reply ... --reply "..."` command to the draft → approve → reply flow in SKILL.md. The heartbeat should only run `check` and `draft`; it must never run `approve` or `reply`.

### 7. Set Heartbeat Interval
In openclaw.json, set the heartbeat to run every 1-2 hours:
```json
{
  "agent": {
    "heartbeat": { "every": "60m" }
  }
}
```

---

## Per-Client Onboarding

### Step 1: Authorize the Client
Run this on your own computer with the client present (or screen-sharing):
```bash
python3 get_client_token.py --client joes-pizza --business-name "Joe's Pizza"
```
This will:
1. Open a browser so the client can sign in with the Google account that owns their Business Profile and approve access
2. Save their refresh token directly to `clients/joes-pizza.json` with owner-only permissions (the token is never printed)
3. Look up their account and location IDs, and fill them in automatically if they have exactly one location

If you ran this on your laptop, copy the file to the VPS securely (`scp`), then delete the local copy.

### Step 2: Check Their Account and Location IDs
If the client manages several locations, the script lists them. Open `clients/joes-pizza.json` and set `account_id` and `location_id` to the right pair.

### Step 3: Fill In Their Details
Edit the non-secret fields in `clients/joes-pizza.json`:
```json
{
  "client_id": "joes-pizza",
  "business_name": "Joe's Pizza",
  "account_id": "accounts/123456789",
  "location_id": "locations/987654321",
  "industry": "restaurant",
  "tone_notes": "Family pizza place, casual and friendly tone",
  "refresh_token": "(filled in by get_client_token.py; leave as is)"
}
```
Client IDs must be lowercase letters, digits and hyphens.

### Step 4: Test It
```bash
python3 gbp_reviews.py check --client joes-pizza
```
If it returns reviews (or "No new unanswered reviews"), you're good.

---

## Remote Onboarding (Optional)

Use `oauth_server.py` only when you can't be with the client. It's a small web server that walks them through Google's authorization and saves their token. **Start it when you need it and let it shut down afterward.** It stops itself after 60 minutes by default.

It needs a **Web application** OAuth client (step 2) and HTTPS. The simplest setup on a VPS is a domain pointed at the server plus [Caddy](https://caddyserver.com), which gets certificates automatically:

```
# /etc/caddy/Caddyfile
reviews.example.com {
    reverse_proxy 127.0.0.1:5050
}
```

Then:
```bash
pip install flask
export GBP_PUBLIC_URL="https://reviews.example.com"
export GBP_ONBOARD_TOKEN="$(openssl rand -hex 24)"
python3 oauth_server.py
```

Send the client:
```
https://reviews.example.com/auth/start?client=joes-pizza&token=<your GBP_ONBOARD_TOKEN>
```

Safety features:
- Refuses to start with a plain `http://` URL (except `localhost` for testing)
- Listens only on 127.0.0.1, so it's reachable only through your HTTPS proxy
- Rejects any link without the correct `GBP_ONBOARD_TOKEN`
- Rejects client names that aren't simple slugs
- Verifies the OAuth state on the callback
- Never shows tokens, secrets or file paths to the visitor

Pick a new `GBP_ONBOARD_TOKEN` each time you onboard someone.

---

## Security

These files give access to your clients' Google Business Profiles. Treat them like passwords.

- **Permissions.** The scripts write `clients/`, `pending/` and `review_log.json` as owner-only (folders 700, files 600) and fix a client file's permissions if they're too open. Run OpenClaw as a dedicated user, not root.
- **Version control.** Never commit `clients/`, `pending/` or `review_log.json`. The included `.gitignore` excludes them.
- **Backups.** If you back up the skill folder, encrypt the backup or exclude `clients/`. A lost token can be reissued; a leaked one has to be revoked.
- **Revoking access.** To cut off a client, delete `clients/<client>.json` and have them remove the app at https://myaccount.google.com/permissions. To cut off everyone, delete or rotate the OAuth client secret in Google Cloud Console.
- **If a token leaks.** Revoke it as above, re-run onboarding for that client, and check their Business Profile for replies you didn't approve.
- **Approvals.** Only you, through your configured channel, can approve a reply. `gbp_reviews.py reply` refuses to post a review without a recorded approval.

---

## Upgrading from 2.0

1. Set `GBP_OAUTH_CLIENT_ID` and `GBP_OAUTH_CLIENT_SECRET` (step 3). Use the same OAuth client as before so existing refresh tokens keep working.
2. Remove `oauth_client_id` and `oauth_client_secret` from every `clients/*.json` file. The scripts warn until you do.
3. `chmod 700 clients pending && chmod 600 clients/*.json pending/*.json review_log.json`
4. Update your HEARTBEAT.md as described in step 6. The old `reply --reply "text"` form no longer exists.
5. Reviews already in `pending/` from 2.0 need a `draft` and `approve` before they can be posted.

---

## Folder Structure
```
review-responder/
  gbp_reviews.py          # Main script: check, draft, approve, skip, reply, pending
  get_client_token.py     # Client onboarding on your own computer
  oauth_server.py         # Optional remote onboarding server
  rr_common.py            # Shared helpers (credentials, permissions, validation)
  SKILL.md                # Agent behavior instructions
  HEARTBEAT.md            # Periodic check instructions
  SETUP.md                # This file
  .gitignore              # Keeps credentials and review data out of git
  review_log.json         # Auto-generated: review status history (600)
  clients/                # (700)
    _template.json        # Config template (no secrets)
    joes-pizza.json       # A client's config and refresh token (600)
  pending/                # (700)
    joes-pizza_abc123.json  # Review awaiting draft/approval (600)
```
