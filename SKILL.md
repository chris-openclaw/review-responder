---
name: review-responder
version: 2.0.0
description: "Use this skill when monitoring or responding to Google Business Profile reviews. Key triggers: 'check reviews,' 'new review came in,' 'draft a reply,' 'respond to that review,' 'approve the draft,' 'post the reply,' 'review approval,' 'Google review,' 'business profile review,' 'reply to a 5-star,' 'how do I handle a bad review,' 'HIPAA-safe review reply,' 'medical practice reviews,' or referencing a specific reviewer by name. Covers: scheduled review checks across multiple clients, tone-matched response drafting by star rating, channel-agnostic approval flow (Telegram, email, web dashboard, or in-thread chat), industry compliance profiles (medical/HIPAA, legal, restaurant, retail), and operator-pattern learning."
metadata:
  openclaw:
    emoji: ⭐
---

# Review Responder

Automatically monitors Google Business Profile reviews across one or more client accounts, drafts professional responses tuned to star rating and industry, and routes drafts to a configurable approval channel before posting. Designed for agencies and consultants managing reviews on behalf of clients.

## Trigger

This skill activates during scheduled review checks (heartbeat) and when an operator responds to a pending review approval message.

---

## Configuration

All paths and channels are read from a single config file: `review-responder.config.json` in the skill's data directory. If it doesn't exist, create one from this template on first run:

```json
{
  "script_path": "~/review-responder/gbp_reviews.py",
  "clients_dir": "~/review-responder/clients/",
  "approval_channel": "telegram",
  "telegram_chat_id": "",
  "email_recipient": "",
  "webhook_url": "",
  "default_industry": "general",
  "memory_file": "approval-patterns.json"
}
```

### Configuration fields

- **script_path**: Absolute path to the `gbp_reviews.py` CLI. Defaults to `~/review-responder/gbp_reviews.py` but can live anywhere.
- **clients_dir**: Directory containing per-client config files. Each client gets its own subdirectory or JSON entry.
- **approval_channel**: One of `telegram`, `email`, `webhook`, or `chat`. Determines where draft replies are sent for approval. See Approval Channels below.
- **default_industry**: Industry profile applied when a client doesn't specify one. See Industry Compliance Profiles below.
- **memory_file**: Where to log approval patterns for the learning layer.

### Per-client overrides

Each client in `clients_dir` can override `industry`, `approval_channel`, and `tone_notes` (free-text guidance specific to that business). Example client config:

```json
{
  "client_id": "smithdental",
  "business_name": "Smith Family Dental",
  "industry": "medical",
  "approval_channel": "email",
  "email_recipient": "office@smithdental.com",
  "tone_notes": "Dr. Smith is warm but understated. Avoid exclamation points."
}
```

---

## Review Check Flow (Heartbeat)

1. Load `review-responder.config.json` and enumerate all clients in `clients_dir`.
2. For each client, run:
   ```
   python3 {script_path} check --client {client_id}
   ```
3. For each new unanswered review:
   - Apply the client's industry profile (or `default_industry` if none specified)
   - Draft a response following the Response Guidelines and the industry profile's constraints
   - Cross-reference against the approval-patterns memory file for operator-specific adjustments (e.g., if the operator consistently shortens 5-star replies for this client, default to shorter)
4. Route the draft to the operator via the configured `approval_channel` (see below).
5. Do NOT post the reply automatically. Wait for operator approval.

---

## Approval Channels

The approval message format stays consistent across channels; only the delivery method changes.

### Standard approval message

```
📝 New Review for [Business Name]

⭐ [star_rating] from [reviewer_name]
💬 "[review comment]"

My draft reply:
"[your drafted response]"

Reply OK to post, or send your edits.
(Review ID: [review_id] | Client: [client_id])
```

### Telegram (`approval_channel: telegram`)
Send the message to the configured `telegram_chat_id`. The operator replies in the Telegram thread.

### Email (`approval_channel: email`)
Send the message as a plain-text email to `email_recipient`. Subject line: `Review approval needed — [Business Name]`. The operator replies to the email; treat the reply body as the approval response.

### Webhook (`approval_channel: webhook`)
POST a JSON payload to `webhook_url` containing the review draft and metadata. Useful for custom dashboards or Slack relays. Expected response: `{ "decision": "approve" | "edit" | "skip", "edited_text": "..." }`.

### Chat (`approval_channel: chat`)
Surface the draft directly in the current chat session. Use this mode when the operator is actively interacting with the skill rather than receiving async notifications.

---

## Approval Flow

When the operator responds to a draft (via any channel):

- **"OK"**, **"post it"**, **"send it"**, **"approved"**: Post the draft as-is:
  ```
  python3 {script_path} reply --client {client_id} --review {review_id} --reply "{approved response}"
  ```
  Confirm once posted: "Done — reply posted for [reviewer_name]'s review."
  Log to the memory file as `approved_as_is`.

- **Edited text**: Treat any reply that isn't a recognized approval/skip keyword as replacement text. Confirm before posting: "Got it — posting your version now." Log the edit to the memory file with a diff summary (length delta, key word changes) so the learning layer can pick up patterns.

- **"Skip"**, **"ignore"**, **"don't reply"**: Do not reply to that review. Remove it from pending. Log as `skipped`.

---

## Response Guidelines

### Tone principles
- Warm, professional, and human — not corporate or robotic
- Specific to what the reviewer said (never generic "thanks for your review!")
- Concise: 2-4 sentences max
- Match the energy of the review without being over the top
- Layer in any `tone_notes` from the client config

### By star rating

**5 stars**
- Thank them warmly and reference something specific they mentioned
- Reinforce what they loved ("We're glad [specific thing] made a difference")
- End with a light invitation to return or share with others
- Keep it brief; don't overdo it on a great review

**4 stars**
- Thank them and acknowledge specific positives
- If they mentioned something that could improve, acknowledge it gracefully without being defensive
- Show you're listening: "We appreciate the feedback on [topic] and are always looking to improve"

**3 stars**
- Thank them for taking the time
- Acknowledge both the positives and the concern
- Show genuine interest in making it right: "We'd love the chance to do better next time"
- Optionally invite them to reach out directly

**1-2 stars**
- Lead with empathy, not defensiveness: "We're sorry to hear this wasn't the experience you deserved"
- Acknowledge the specific issue without making excuses
- Offer a path forward: invite them to contact the business directly
- Keep it short and dignified; do not argue or over-explain
- Never blame the reviewer or question their experience

---

## Industry Compliance Profiles

Industry profiles enforce constraints and tone defaults appropriate to specific business types. Apply the profile from the client config (or `default_industry`) on every draft.

### `medical` (HIPAA-safe)

**Hard rules** (never violate, regardless of star rating):
- NEVER reference or confirm any medical conditions, diagnoses, treatments, medications, procedures, or health details, even if the reviewer mentioned them publicly
- NEVER confirm or deny that someone is or was a patient
- Keep responses general: "your experience," "your visit," "your care" — not "your diagnosis" or "your treatment"
- If the reviewer shared health details, respond to the sentiment and experience only
- When inviting follow-up, use "please contact our office" — never suggest discussing their "case" or "medical records"

**Tone defaults**: professional, reassuring, brief.

### `legal`

**Hard rules**:
- Never confirm or discuss case details, legal advice, or attorney-client relationships
- Never speculate about outcomes or imply guarantees
- Avoid language that could be interpreted as a new attorney-client communication
- For dissatisfied reviewers, direct them to the firm's office line rather than offering legal commentary

**Tone defaults**: measured, professional, no flourishes.

### `restaurant`

**Hard rules**: none specific, but stay grounded.

**Tone defaults**: warmer and more conversational than medical/legal. Food-specific callouts welcome ("glad the carbonara hit"). For complaints, offer a direct contact for the manager.

### `retail`

**Hard rules**:
- Don't speculate about specific products or stock issues you can't verify
- For return/refund disputes, direct to customer service, not public dialogue

**Tone defaults**: friendly, helpful, solution-oriented.

### `general`

No industry-specific constraints. Fall back to base Tone Principles and By Star Rating guidance.

---

## Approval Pattern Learning

Log each approval interaction to the memory file (`memory_file` in config). Use the log to surface patterns and adjust future drafts.

### What to log per review

```json
{
  "client_id": "smithdental",
  "review_id": "abc123",
  "stars": 5,
  "draft": "Thank you, Maria...",
  "decision": "edited",
  "final": "Thanks Maria...",
  "length_delta_words": -8,
  "timestamp": "2026-03-20T14:22:00Z"
}
```

### How to apply patterns

Before drafting any new reply, scan the log for the same client and look for trends across the last 10-20 interactions:

- If `length_delta_words` is consistently negative for a given star rating, default to shorter drafts for that client at that rating
- If certain words/phrases are routinely stripped (e.g., "incredibly", "truly"), avoid them on future drafts for that client
- If the operator consistently skips 1-star reviews from anonymous reviewers, surface that as a default rather than drafting one

Surface insights to the operator periodically (e.g., once a week or on the 20th interaction): "I've noticed you usually shorten 5-star replies for Smith Dental by about 10 words. Want me to default to shorter going forward?"

---

## Checking Pending Reviews

To see what's waiting for approval:
```
python3 {script_path} pending
```

---

## Things to Avoid

- Generic filler: "We value all our customers," "Your feedback is important to us"
- Mentioning the star rating directly: "Thanks for the 5 stars!"
- Being defensive about negative reviews
- Making promises the business can't keep
- Using the reviewer's full name unless they used it in their review
- Emojis (unless the business brand is very casual and the operator approves it)
- Violating the active industry profile's hard rules under any circumstance

---

## Dependencies

- Python 3 with: `google-auth`, `google-auth-oauthlib`, `requests`
- Client config files in the directory specified by `clients_dir`
- For Telegram: a Telegram channel/chat configured and a working bot token
- For email: SMTP credentials or a relay
- For webhook: an HTTPS endpoint that accepts POST and returns the decision JSON
