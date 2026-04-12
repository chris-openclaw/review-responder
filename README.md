# Google Business Review Responder

An [OpenClaw](https://openclaw.ai) skill that monitors Google Business Profile reviews, drafts professional responses, and sends them to you via Telegram for approval before posting.

Built for consultants and agencies managing reviews across multiple client locations.

## How It Works

1. On each heartbeat, OpenClaw checks for new unanswered reviews across your configured clients
2. For each new review, your agent drafts a response following tone and compliance guidelines (including HIPAA)
3. The draft is sent to you on Telegram for approval
4. You reply "OK" to post it, send edits to revise it, or "skip" to ignore it

No reviews are ever posted without your explicit approval.

## What's Included

- `SKILL.md` - Agent behavior instructions (response guidelines, approval flow, HIPAA rules)
- `HEARTBEAT.md` - Periodic check instructions for OpenClaw's heartbeat system
- `gbp_reviews.py` - Main script for checking reviews and posting replies
- `get_client_token.py` - One-time OAuth helper for onboarding clients locally
- `oauth_server.py` - Web-based OAuth flow for remote client onboarding
- `clients/_template.json` - Config template for adding new clients
- `SETUP.md` - Full setup and per-client onboarding guide

## Quick Start

1. Set up a Google Cloud project with the Business Profile API enabled (details in `SETUP.md`)
2. Install dependencies: `pip install google-auth google-auth-oauthlib requests`
3. Copy the `review-responder` folder into your OpenClaw workspace
4. Register the skill in your `openclaw.json`
5. Onboard your first client using `get_client_token.py` or `oauth_server.py`
6. Wire up the heartbeat and you're live

See `SETUP.md` for the full walkthrough.

## Requirements

- Python 3 with `google-auth`, `google-auth-oauthlib`, `requests`
- Flask (only if using the web-based OAuth onboarding server)
- A Google Cloud project with OAuth 2.0 credentials
- OpenClaw with a Telegram channel connected

## License

MIT. See [LICENSE](LICENSE) for details.
