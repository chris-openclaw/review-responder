# Changelog

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this skill adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] — 2026-09-28

Security release addressing ClawHub security audit findings. Upgrading from 2.0.x requires a few manual steps; see "Upgrading from 2.0" in SETUP.md.

### Security
- **Approval gate is now enforced in code.** Posting is a three-step flow (`draft` → `approve` → `reply`). `gbp_reviews.py reply` refuses to post unless an approval has been recorded for that exact review, and posts only the approved text. It no longer accepts reply text as an argument.
- **OAuth app credentials moved to environment variables** (`GBP_OAUTH_CLIENT_ID`, `GBP_OAUTH_CLIENT_SECRET`). They are no longer stored in per-client files or edited into scripts.
- **Credential and review files are written owner-only** (files 0600, folders 0700) via atomic writes. Existing client files with looser permissions are tightened automatically on load.
- **Refresh tokens are never printed.** `get_client_token.py` writes the token directly to the client's config file.
- **Client and review IDs are validated** (lowercase slugs / safe characters), so no input can write files outside `clients/` or `pending/`.
- **Onboarding server hardened.** `oauth_server.py` now refuses plain `http://` (except localhost), listens on 127.0.0.1 by default for use behind an HTTPS reverse proxy, requires a secret `GBP_ONBOARD_TOKEN` in every link, verifies OAuth state, HTML-escapes output, no longer reveals file paths, and shuts itself down after 60 minutes. `OAUTHLIB_INSECURE_TRANSPORT` is no longer set for public servers.
- **Prompt-injection guidance.** SKILL.md and HEARTBEAT.md now treat review content as untrusted data and accept approvals only from the operator's configured channel.
- API requests now use timeouts, and error output no longer echoes raw API response bodies.

### Added
- `draft`, `approve`, and `skip` commands in `gbp_reviews.py`; `pending` now shows each review's status
- `rr_common.py` shared helper module (credentials, permissions, validation)
- `get_client_token.py --client` and `--business-name` options, plus automatic account and location ID lookup
- **Scope and Permissions** section in SKILL.md listing every command, network destination, and file the skill touches
- `metadata.openclaw` declarations for required binaries, environment variables, and config paths
- **Security** and **Upgrading from 2.0** sections in SETUP.md, including HTTPS setup with Caddy
- `.gitignore` excluding `clients/`, `pending/`, `review_log.json`, and approval-pattern data
- Secret-free `clients/_template.json`

### Changed
- **BREAKING**: `gbp_reviews.py reply` no longer takes `--reply "text"`. Use `draft`, `approve`, then `reply`.
- **BREAKING**: `oauth_client_id` and `oauth_client_secret` in client config files are no longer read. Set the environment variables instead.
- **BREAKING**: `get_client_token.py` now requires `--client`, and `oauth_server.py` requires `GBP_PUBLIC_URL` and `GBP_ONBOARD_TOKEN`.
- HEARTBEAT.md now uses the configured approval channel instead of assuming Telegram, and the heartbeat is limited to `check`, `draft`, and `pending`
- `description` frontmatter now discloses local token storage, outbound approval messages, public posting, and the optional onboarding server
- Minimum Python version is now 3.9

### Fixed
- Google API URLs were built as `accounts/accounts/...` when `account_id` or `location_id` included its prefix, as the setup guide instructed
- `oauth_server.py` could fail the token exchange on current `google-auth-oauthlib` releases because the PKCE code verifier wasn't carried from the start of sign-in to the callback
- The remote onboarding server wrote the client name from the URL straight into a file path

## [2.0.1] — 2026-06-08

### Added
- **Privacy and Data Handling** section in SKILL.md describing the real network surface (Google Business Profile API v4, Google OAuth token endpoint, configured approval channel), credential storage (operator-owned OAuth credentials per client in `clients_dir`), and hard guardrails (no auto-posting, no PHI in public replies, no credential leakage, no bulk export)
- **Permissions and Privacy** section in README.md so operators see the full network surface, credential storage posture, hard guardrails, and the compliance scope (HIPAA-aware drafting, NOT a HIPAA-certified workflow) before installing

### Changed
- Reworded the `medical` industry profile from "HIPAA-safe" to "HIPAA-aware drafting" to accurately describe the constraint (avoids PHI in public reply text) without implying a regulatory certification this skill cannot provide. CHANGELOG references to "HIPAA-safe" updated in the 2.0.0 entry's description of this profile for consistency
- Narrowed the activation triggers in the `description` frontmatter to require an explicit configured-client workflow (named client, named reviewer, specific approval/post action), with a "do NOT trigger" guardrail for casual review chat, review-writing requests, and marketing-strategy questions
- Unquoted the `version` field in frontmatter (matches updated ClawHub CLI semver requirements)

## [2.0.0] — 2026-05-12

### Added
- Configuration file (`review-responder.config.json`) for centralizing script paths, clients directory, approval channel, default industry, and memory file location
- Per-client configuration overrides for industry, approval channel, and tone notes
- Channel-agnostic approval flow with four supported channels: Telegram, email, webhook, and in-thread chat
- Industry compliance profiles for medical (HIPAA-safe), legal, restaurant, retail, and general business types
- Operator pattern learning layer that logs each approval decision (approved-as-is, edited with diff summary, skipped) per client and surfaces patterns over time
- Periodic insight surfacing to the operator (e.g., "you usually shorten 5-star replies for this client by ~10 words")

### Changed
- **BREAKING**: Hardcoded script paths (`~/review-responder/gbp_reviews.py`) replaced with a configurable `script_path` field
- **BREAKING**: Telegram is no longer the assumed approval channel; `approval_channel` must be set explicitly in config
- HIPAA section promoted from a sub-block under Response Guidelines into a top-level `Industry Compliance Profiles` section with peer profiles for other industries
- SKILL.md now has proper YAML frontmatter (`name`, `version`, `description`, `metadata.openclaw.emoji`)

### Removed
- MIT LICENSE file (license now managed at the ClawHub platform level)

## [1.0.0] — 2026-03-27

### Added
- Initial release
- Scheduled review checks across multiple Google Business Profile clients
- Tone-matched response drafting by star rating (5, 4, 3, 1-2)
- Telegram-based approval flow with OK/edit/skip operator commands
- HIPAA-aware response guidance for medical clients
- Per-client config files for multi-client agency use
- OAuth onboarding helpers (`get_client_token.py`, `oauth_server.py`)
