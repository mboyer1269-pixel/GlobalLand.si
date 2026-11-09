# Commercial proposal: bilingual GCC trivia batch (prepared 2026-11-09, autonomous AI agents, GlobalLand)

Status tracking: opportunity=OBSERVED | offer=DRAFTED, NOT SENT | buyer response=NONE | accepted order=NONE | delivered artifact=NONE (sample only) | verified external receipt=NONE.

## 1. Dated source request
- r/forhire post "[Hiring] Arabic-English Trivia Writer & Content Organizer for Trivia Game", by /u/CodingKiller, updated 2026-11-08T14:33:16Z.
- URL: https://www.reddit.com/r/forhire/comments/1xqzs02/hiring_arabicenglish_trivia_writer_content/
- Evidence: products/services/first-receipt/raw/forhire-new.rss (FETCH TASK-179424244312), extract forhire-hiring-extract.json (TASK-179424244313/314).
- Quoted: "start with a small paid batch"; "Budget: US$50-75 per batch of 100 completed questions"; "a reliable source link for each question"; "Organizing questions by category and difficulty in Google Sheets/Excel, following a provided template"; "To apply, please send me a DM".

## 2. Why this buyer may pay
Explicit paid trial with a stated budget and an offline, file-based deliverable (spreadsheet). Unlike earlier leads, no live system access is needed. This is a stated willingness to pay a contractor, not evidence they will accept AI-produced work.

## 3. How the buyer can be reached
Only by Reddit DM or comment. Agents have no Reddit account (blocker NO-COMMUNITY-ANSWER-ACCOUNT covers community accounts). Operator action: send the message in section 8 once, from a founder-approved, AI-disclosed account. No bulk contact.

## 4. Scoped deliverable
Trial batch of 100 questions (or the buyer's smaller trial size) in the buyer's template: question/answer in English and Arabic, category, difficulty, one source URL per question; duplicates removed. Answers fact-checked against the fetched source text before delivery; questions failing the check are dropped and replaced.

## 5. Tested capability
Sample: trivia-sample/sample-v3.csv, 8 rows (5 Easy, 3 Medium), EN/AR, one English Wikipedia source link per row. Verification method (verification-v2.json, TASK-179424390111): each answer's evidence terms were checked for presence in the saved intro of the linked Wikipedia article; this is a term-presence check against the source intro, not a full reading of the source. Independent AI QA (independent-qa.json) found all 8 facts supported and flagged Arabic wording in rows 3 and 8; v3 corrects only those two Arabic questions. Limits: all Arabic is AI-drafted and not native-reviewed; the sample is mostly encyclopedic, so Gulf pop culture and entertainment, which the buyer emphasizes, is our weakest and least demonstrated area; no 100-question batch has been produced yet.

## 6. Price and time (hypothesis)
USD 60 per 100 questions, inside the buyer's range. Turnaround is not evidenced (no 100-question run yet; source checks use bounded fetches per turn). Non-binding estimate: a few days after receiving the template; ask the buyer's timeline first.

## 7. Payment compatibility (main blocker for a receipt by 2026-11-11T04:59Z)
The existing Interac CAD route needs a Canadian bank account; the buyer's location is unknown and the budget is in USD, so Interac is probably incompatible. A USD/international route (e.g. PayPal) would need operator setup; agents have none. Order creation and acceptance stay operator-only (SERVICE-PAYMENT-COLLECTION). Realistic assessment: a verified receipt by the deadline is unlikely, even if the buyer replies.

## 8. Ready-to-send message (operator, Reddit DM)
Hi! Saw your trivia-writer post (Nov 8). Disclosure first: I am an AI-agent team (GlobalLand), not a single human writer. A free 8-question EN/AR sample is attached (CSV in your columns, or I can match your template), each row with a source link. Each answer was checked against the linked source intro, and we drop any question we cannot verify that way. Limits: our Arabic is AI-drafted and has not been reviewed by a native speaker, and Gulf pop culture is our weakest area, so we would expect your editor to review it. If AI-produced work is acceptable, we could do a 100-question trial at USD 60, with payment only after you accept the batch. What timeline do you need? Our non-binding estimate is a few days after receiving your template. Which payment methods can you use? If AI work is not what you want, no problem, and thanks.

## Other leads rejected in the same feed (2026-11-09)
Plex/router config (live home-network access), security code review (repository access), Montreal phone calls (phone and in-person French), video/game roles (out of scope).
