# Changelog

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this skill adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
