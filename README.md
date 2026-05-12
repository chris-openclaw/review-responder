# Review Responder

An [OpenClaw](https://openclaw.ai) skill that monitors Google Business Profile reviews, drafts professional responses, and routes them to a configurable approval channel before posting.

Built for consultants and agencies managing reviews across multiple client locations and industries.

**Current version: 2.0.0**

## What's new in 2.0.0

- **Configurable script paths and channels** via a single `review-responder.config.json` file
- **Channel-agnostic approval flow**: Telegram, email, webhook, or in-thread chat
- **Industry compliance profiles**: medical (HIPAA-safe), legal, restaurant, retail, and general
- **Operator pattern learning**: logs approval decisions per client and surfaces patterns (e.g., "you usually shorten 5-star replies for this client")
- **Per-client overrides** for industry, approval channel, and tone notes

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## How It Works

1. On each scheduled check, OpenClaw enumerates configured clients and looks for new unanswered reviews
2. For each new review, the agent applies the client's industry profile and drafts a tone-matched response
3. The draft is sent to the configured approval channel (Telegram, email, webhook, or chat)
4. The operator replies "OK" to post it, sends edits to revise it, or "skip" to ignore it
5. Decisions are logged so the agent can learn the operator's preferences over time

No reviews are ever posted without explicit operator approval.

## What's Included

- `SKILL.md` — Agent behavior instructions (configuration, approval flow, industry profiles, pattern learning)
- `HEARTBEAT.md` — Periodic check instructions for OpenClaw's heartbeat system
- `gbp_reviews.py` — Main script for checking reviews and posting replies
- `get_client_token.py` — One-time OAuth helper for onboarding clients locally
- `oauth_server.py` — Web-based OAuth flow for remote client onboarding
- `clients/_template.json` — Config template for adding new clients
- `SETUP.md` — Full setup and per-client onboarding guide

## Quick Start

1. Set up a Google Cloud project with the Business Profile API enabled (details in `SETUP.md`)
2. Install dependencies: `pip install google-auth google-auth-oauthlib requests`
3. Copy the `review-responder` folder into your OpenClaw workspace
4. Create `review-responder.config.json` from the template in `SKILL.md`
5. Register the skill in your `openclaw.json`
6. Onboard your first client using `get_client_token.py` or `oauth_server.py`
7. Wire up the scheduled check and you're live

See `SETUP.md` for the full walkthrough.

## Requirements

- Python 3 with `google-auth`, `google-auth-oauthlib`, `requests`
- Flask (only if using the web-based OAuth onboarding server)
- A Google Cloud project with OAuth 2.0 credentials
- One approval channel configured: Telegram, email (SMTP), webhook endpoint, or in-thread chat
