# Skill: Google Business Review Responder

## Description
Automatically monitors Google Business Profile reviews for clients, drafts professional responses, and sends them via Telegram for approval before posting.

## Trigger
This skill activates during heartbeat checks and when the operator replies to a review approval message.

---

## Review Check Flow (Heartbeat)

1. Run the review check script for each configured client:
   ```
   python3 ~/review-responder/gbp_reviews.py check --client <client_id>
   ```
2. For each new unanswered review found, draft a response following the Response Guidelines below.
3. Send the draft to the operator via Telegram in this format:

```
📝 New Review for [Business Name]

⭐ [star_rating] from [reviewer_name]
💬 "[review comment]"

My draft reply:
"[your drafted response]"

Reply OK to post, or send your edits.
(Review ID: [review_id] | Client: [client_id])
```

4. Do NOT post the reply automatically. Wait for operator approval.

---

## Approval Flow (Chat)

When the operator replies to a review draft:

- **"OK"** or **"post it"** or **"send it"** or **"approved"**: Post the draft as-is using:
  ```
  python3 ~/review-responder/gbp_reviews.py reply --client <client_id> --review <review_id> --reply "the approved response"
  ```
  Confirm once posted: "Done -- reply posted for [reviewer_name]'s review."

- **Edited text**: If the operator sends replacement text (anything that isn't a simple approval), use their text as the reply instead. Confirm before posting: "Got it -- posting your version now."

- **"Skip"** or **"ignore"**: Do not reply to that review. Remove it from pending.

---

## Response Guidelines

### Tone Principles
- Warm, professional, and human -- not corporate or robotic
- Specific to what the reviewer said (never generic "thanks for your review!")
- Concise: 2-4 sentences max
- Match the energy of the review without being over the top

### By Star Rating

**5 Stars:**
- Thank them warmly and reference something specific they mentioned
- Reinforce what they loved ("We're glad [specific thing] made a difference")
- End with a light invitation to return or share with others
- Keep it brief -- don't overdo it on a great review

**4 Stars:**
- Thank them and acknowledge specific positives
- If they mentioned something that could improve, acknowledge it gracefully without being defensive
- Show you're listening: "We appreciate the feedback on [topic] and are always looking to improve"

**3 Stars:**
- Thank them for taking the time
- Acknowledge both the positives and the concern
- Show genuine interest in making it right: "We'd love the chance to do better next time"
- Optionally invite them to reach out directly

**1-2 Stars:**
- Lead with empathy, not defensiveness: "We're sorry to hear this wasn't the experience you deserved"
- Acknowledge the specific issue without making excuses
- Offer a path forward: invite them to contact the business directly
- Keep it short and dignified -- do not argue or over-explain
- Never blame the reviewer or question their experience

### HIPAA Compliance (CRITICAL)
- NEVER reference or confirm any medical conditions, diagnoses, treatments, medications, or health details -- even if the reviewer mentioned them in their review
- NEVER confirm or deny that someone is or was a patient
- Keep responses general: "your experience," "your visit," "your care" -- not "your diagnosis" or "your treatment"
- If a reviewer shares health details in their review, do NOT reference those specifics in the reply. Respond to the sentiment and experience only.
- When inviting someone to follow up, use "please contact our office" -- never suggest discussing their "case" or "medical records"
- This applies to ALL star ratings, positive and negative

### Things to Avoid
- Generic filler: "We value all our customers" / "Your feedback is important to us"
- Mentioning the star rating directly: "Thanks for the 5 stars!"
- Being defensive about negative reviews
- Making promises the business can't keep
- Using the reviewer's full name unless they used it in their review
- Emojis (unless the business brand is very casual and the operator approves it)
- Referencing any health information, even if the patient shared it publicly (HIPAA)

---

## Checking Pending Reviews

To see what's waiting for approval:
```
python3 ~/review-responder/gbp_reviews.py pending
```

---

## Dependencies
- Python 3 with: google-auth, google-auth-oauthlib, requests
- Client config files in `~/review-responder/clients/`
- Telegram channel connected for approval messages
