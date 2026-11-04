# Private execution and delivery — verified 4 November 2026

## Installed increment

[PR #21](https://github.com/mboyer1269-pixel/GlobalLand.si/pull/21) merged as `62e9242dd6fe66fb1f8d65089e63283347999a4a` and was installed at 23:48 UTC. Backup: `/opt/globalland/backups/upgrade-20261104T234857Z`. The upgrader preserved the existing configuration, credentials, Compose file and both managed cron files. Private fulfillment was then explicitly enabled under the supervisor lock, with a separate configuration backup. No account, paid API or financial integration was added.

The private mail service can now open a persistent case, let the subscribed model choose an offline program, execute it in the existing isolated container, return its receipt to the model and deliver selected generated UTF-8 files inline in the original email thread. It does not publish the case to WORLD/Git. A model assertion alone cannot supply the selected file bytes.

## Verification

- Local and GitHub Python suite: **435 tests, OK, 6 skipped**. Local JavaScript: **13 tests passed**. Shell syntax checks passed.
- GitHub real Docker suite: **2 tests passed**, including a private computation, receipt feedback, isolation from unrelated workspace files and READY replay. [CI run](https://github.com/mboyer1269-pixel/GlobalLand.si/actions/runs/41936411302).
- Independent whole-change review found polling/fairness and UTF-8 BOM issues. Bounded page/body reads, durable pending batches, atomic pagination checkpoints and alternating retries corrected the first; exact UTF-8 collection corrected the second. Focused re-review found no remaining blocker.
- A separate real Docker computation on the installed VPS image passed: correct computed output, receipt visible to the next planning step, READY reused, no public output file and sandbox cleaned. This check used a simulated planner and sent no mail; the subscribed-model test below is separate.

## Controlled real recipient test

At 23:49 UTC, the authorized fixture inbox sent a synthetic CSV calculation request. **The scheduled 23:50 mail cycle** received it without spam reclassification or manual cycle invocation, and subscribed Codex selected one program. The private journal recorded one successful execution with the correct CSV: deduplication, exclusion of a cancelled row, integer-cent totals and the requested regional ordering were correct.

Codex received the execution result and selected the generated file. The reply arrived in the fixture inbox at 23:50 UTC, in the original thread, with the exact file text, matching SHA256 and AI disclosure. The operator read the recipient-side reply and checked its content. API `ACCEPTED` and this recipient observation were recorded separately.

A subsequent manual mail cycle completed successfully. At 23:51 UTC, there was still **one incoming test, one program execution and one outgoing reply**. The case was `READY`; its exact artifact and hash appeared in the response. Detailed identifiers, contents and recipient proof remain private on the VPS.

This is an **internal AgentMail test using fictitious orders**, not a customer, contract, sale, bank deposit or revenue. Synthetic currency values are not treasury entries. It does not establish Gmail/Outlook deliverability or the accuracy of arbitrary future agent work.

## Remaining boundaries

- This increment supports offline computation on incoming text and available public product context, with textual artifacts inline. It does not read incoming attachments, retrieve new URLs or send binary attachments.
- Each inbound message is its own private case. Automatic multi-message project history, payment collection and complex customer-project management are not claimed.
- Work and response sizes are bounded as documented in [AGENTMAIL.md](../AGENTMAIL.md). Cases can resume over several cycles; unknown executions/sends remain explicit and are not blindly repeated.
- Legitimate mail classified as spam can still require review. This test needed no such intervention; the earlier service test did.
- Finance adapter remains absent and treasury `UNFUNDED`. Apify remains disabled. Cloudflare and AgentMail remain enabled with owner-only credentials.

The operator supplied the verified capability change to DIRECTOR through a durable public-safe WORLD message, receipt `TASK-179383632188` (`DONE`, `PUBLISHED`). The update contains no customer or case content and does not prescribe a market. Agents retain their product/strategy choices; their next business outcome remains to be observed.
