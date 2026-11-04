# Commercial channel audit — 4 November 2026

## Outcome

The [welfare brief](https://globalland-welfare-tender-brief.global-land.workers.dev/) is publicly reachable. The installed publisher verified the served index hash at 22:47 UTC and returned `DONE` / `ONLINE_VERIFIED`; the durable journal was `PUBLISHED`. Public receipt: `queue/done/TASK-179383242177.result.json`.

This is an informational expression-of-interest experiment selected by the agents. It accepts neither orders nor payment. It does not establish customer demand, revenue or a required strategy for GlobalLand.

## Confirmed defects repaired before publication

The operator helper omitted the required `created_at` and `estimated_cost_cad` fields, could exit successfully after failed/unverified publication, and created a new task on each invocation. Recovery could also lose the transient pending-Git marker and report completion too early.

The archived operation in `ops/publish_welfare_brief.py` now validates its envelope, retains one immutable request per reviewed digest, checks the durable Git-publication journal on replay and reports success only after verified publication and receipt. It refuses mismatched requests and content changes. The prior host copy was backed up before replacement.

The helper retains both Codex and Claude as content authors. A same-provider runtime review was not used as independent approval. The founder's instruction to audit the presented page and advance was recorded through the existing founder-review route for this exact digest. The record explicitly distinguishes delegated authorization from the founder personally performing technical tests. No review policy was disabled.

## Verification evidence

- Six offline regression tests pass, using the real envelope validator and a simulated durable executor. They cover valid submission, repeated invocation without another effect, failure exit status, pending receipt recovery, authorship/review rejection and request mismatch.
- Twenty existing site tests pass under Linux. Saved-source hash, source quote, authorized contact address and visible page/evidence consistency were checked. This was not a fresh retrieval of the procurement notice.
- Site digest: `af0b1e99a1d3c24095c313fbd438d8bf854bc1b34c8abeb29ce3db5eccee116e`.
- Served index SHA256: `70718e8c49ac20a31d48ba4ea9d5aafbbc552561ba9809d10814a7c75aee668c`.
- Real helper re-entry at 22:51 UTC reused `TASK-179383242177`, returned `DONE` / `ONLINE_VERIFIED`, and found its Git receipt already published. This verifies replay, not a second deployment or a fresh health probe.
- The browser displayed the public page, bilingual contact link and source limitations after publication.

## Substantive controlled email test

A separate authorized AgentMail test inbox sent a request at 22:47 UTC asking for a useful synthesis of the published notice. GlobalLand's subscribed Codex model replied at 22:55 UTC. The operator read the reply in the recipient's thread: buyer and two services, both deadlines with UTC, the six-year/2031 discrepancy, three questions for the buyer, official links, source age and explicit lack of fresh verification were present. The response identified itself as an AI agent and a controlled test.

The API journal recorded `ACCEPTED`. Recipient receipt was separately verified in the AgentMail UI; these are distinct evidence. A subsequent manual mail cycle and the 23:00 scheduled cycle left one incoming test and one outgoing reply, in the same thread, addressed only to the fixture inbox. Detailed identifiers, message content and proof remain private on the host.

**Qualification:** AgentMail initially classified this known test as spam, excluding it from the normal incoming API listing. The operator removed only that message's spam label, then the normal mail cycle handled it. No filter, token permission or Armor policy was weakened. This test therefore required intervention before processing. It covers internal AgentMail transport, not Gmail/Outlook deliverability or unattended handling of every legitimate inbound message. It is not a client, order, sale or proof of financial settlement.

## Remaining gaps, in priority order

1. **Private inquiry-to-delivery execution.** The correspondence model currently answers from public context without tools. It cannot create a private case, execute customer work or attach a new deliverable. Add a private, durable request/result path with thread association and replay protection before claiming this workflow works. Keep customer content out of public WORLD/Git projections. Let agents choose the work and strategy.
2. **Inbound visibility and uncertain sends.** Legitimate messages classified as spam can remain unseen by the restricted normal listing. Define an observable review path without automatically replying to spam/blocked content. `UNKNOWN` sends still need operator reconciliation rather than automatic resending.
3. **Reviewer provenance for administrator-authored artifacts.** Runtime authorship receipts do not cover every administrator Git edit. This publication helper conservatively includes both known providers, but general provenance across these paths remains an improvement; this audit does not claim to fix it globally.
4. **Time-sensitive content.** Retire or revise this page after 4 December 2026 at 17:00 UTC. No automatic expiration job exists yet.
5. **Collection.** Finance adapter absent; treasury `UNFUNDED`. No paid order, bank integration, deposit or revenue is established by these checks.

Cloudflare and AgentMail credentials were present, enabled and owner-only at the final read-only configuration check. Apify remained disabled. Installed controller revision stayed `45669825ab06296306af2bd412cb2eda9333032e`; this audit changes the operator helper and records evidence, not the production controller release. The credential installer's interrupted-write recovery was not exercised; the completed installation passed its access checks.

The operator sent these public-safe observations to DIRECTOR through the durable WORLD channel, receipt `TASK-179383335188` (`DONE`, `PUBLISHED`). The update asks the agents to reconcile stale blockers and choose their next useful action. It does not mark a business mission complete or claim they have already acted on the update.
