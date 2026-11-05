# Private Commercial Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver an evidence-qualified private mail observation to the next director decision, with operational activity and financial results kept separate.
**Architecture:** Reuse existing private READY and mail journals. Interpret within the existing model call and project only validated counts and existing public IDs; no second service or classifier.
**Tech Stack:** Python stdlib, existing unittest and subscription controller.
**Spec:** `docs/superpowers/specs/2026-11-04-commercial-feedback-design.md`.

## Global Constraints

- No change to market freedom, financial authority, Treasury, GLC, public action schemas, external routing or permissions.
- No extra model call, paid dependency, external communication, VPS or account mutation during local implementation.
- Private content and all source IDs remain private; public fields and map keys use fixed enums/validated public experiment IDs only.
- Interpreted observations are unverified; synthetic tests and automated mail cannot become external-demand or financial evidence.
- Existing/disabled workflows remain compatible; malformed optional observation never invalidates an otherwise valid reply.
- Root owns Git staging and commits; implementer edits only the listed files and writes a report.

## Review Focus

- Crash between immutable READY and send journal: reuse interpretation without another model call or send.
- Untrusted message-derived experiment ID or quoted private data: no public leakage or host-provenance upgrade.
- Reclassification/replayed source: counts reflect current interpretation without creating a fresh market signal.
- Scan corruption/limits: partial/unavailable is explicit, not zero demand; previous progress baseline is not corrupted.
- Legacy valid replies and disabled configuration: no regression or extra classification access.

### Task 1: Private feedback and independent progress axes

**Files:** Create `scripts/commercial.py`, `tests/test_commercial.py`, `docs/COMMERCIAL-FEEDBACK.md`; modify `scripts/mail.py`, `scripts/mail_agent.py`, `scripts/private_work.py`, `scripts/controller.py`, `scripts/tools.py`, `scripts/progress.py` and focused existing tests in `tests/test_mail.py`, `tests/test_mail_agent.py`, `tests/test_private_work.py`, `tests/test_progress.py`, `tests/test_capability_context.py`. Avoid unrelated refactors.

**Interfaces:** Implement `commercial.settings(config)` for disabled/valid/invalid private configuration; `commercial.allowed_experiments(root)` deriving bounded identifiers only from existing public work/world/status.json missions and products/sites directories; `commercial.normalize_observation(raw, message, allowed_experiments, host_origin, provider)` producing a private validated record; `commercial.project(root, config)` producing safe projection; `commercial.progress_snapshot(root, config)` returning private stable source identities for tracking plus availability. Internal shapes are implementer-owned, but they must meet the exact spec and be documented. No public arbitrary observation-write tool.

**Global constraints for this task:** All constraints and exact schema/limits in the spec apply. No additional calls, no money mutation, preserve valid replies, disabled default. New optional raw observation has exact schema and enums from spec. `agentmail.commercial.enabled` activates classification and projection. Exact private synthetic sender matches exclude tests; unknown source never becomes verified customer. Experiment attribution is inferred or unassigned, never trusted merely because model chose it. Read spec first.

- [ ] **Step 1: Write failing acceptance tests.** Exercise grounded PRICE_QUESTION/REJECTION and malformed quote/enum/key, private sentinel leakage in actual Controller.tick prompt, disabled/legacy compatibility, known synthetic sender overriding model ORDINARY, bogus experiment IDs, repeated source, revised category, unavailable/partial projection, and technical mission completion without revenue. Include full mocked Mailbox -> durable journal -> Controller.tick -> captured planner prompt path; do not mock the new observation/projection functions.
- [ ] **Step 2: Run the new focused tests and record RED output.** Use WSL with `PYTHONPATH=scripts:tests python3 -m unittest test_commercial -v`; missing functionality must be the reason, not an import/setup error unrelated to the feature.
- [ ] **Step 3: Implement storage and interpretation.** Reuse READY write and existing mail journal writes/locks. Maintain normalized observation separately from reply text. Preserve it in ACCEPTED/IGNORED/UNKNOWN and pre-send retries. No classifier retry on invalid observation. Protect source identity and single-record idempotency; do not add a second database. Exact incoming evidence must have been visible to the model. Guard symlinks/hardlinks/size and fixed errors.
- [ ] **Step 4: Integrate public view and independent tracking.** Controller.context must include commercial projection with clear interpretation disclaimer. Capability view exposes state only, never private config. Keep existing activity counters; add durable turns without new interpreted feedback and turns without verified revenue, baseline migration and unknown handling. Freshness uses distinct private source identity, not changing category counts; remember all sources, including previously unknown ones, to prevent reinterpretation resetting the counter. Persist once per successful turn. No new forced-market prompt or loss of prior stall detection. Revenue source remains treasury.revenue_cents; no claim of profit.
- [ ] **Step 5: Run focused tests until GREEN and regressions.** Run test_commercial, test_private_work, test_private_guide, test_mail, test_mail_agent, test_capability_context, test_progress via WSL unittest. If failures expose pre-existing environment constraints, report precisely; do not weaken assertions. Root runs complete suite after review.
- [ ] **Step 6: Document and self-review.** Describe enablement, schema, counts semantics, no-customer-proof disclaimer, synthetic setup before live tests, migration, private paths, bounds and next-step limitations. Include one illustrative fictional event that is never called a sale. Report exact files, RED/GREEN evidence, unresolved concerns and proposed follow-up. No Git staging or commits by implementer; root commits this coherent increment for independent review.

## Following validation

Root requests independent spec/code review, fixes findings, runs full appropriate checks and prepares a draft PR. A controlled real-model exercise may be run only with explicit synthetic provenance and within existing authorized private test scope; its result must be separate from deterministic tests and actual market outcomes. Deployment/merge state is reported truthfully. Remaining goal milestones stay open.
