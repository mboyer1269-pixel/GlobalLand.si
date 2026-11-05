# Economic Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the director and STATUS one truthful read-only economic view of known cash movements, commitments, receivables and unknown costs.

**Architecture:** Extend the existing Treasury with one consistent read transaction; a small economic projection combines its safe aggregates and existing receivables. Preserve the existing authoritative snapshot and financial actions. No new ledger or money integration.

**Tech Stack:** Python3.12+ standard library, SQLite, existing unittest fixtures.

**Spec:** `docs/superpowers/specs/2026-11-05-economic-context.md`.

## Global Constraints

- Python3.12+ standard library only; no network, schema/balance migration, verifier invocation, new payment capability or authority change.
- Reading this view is not a prerequisite for free useful work. Root owns Git; code readiness, deployment and economic outcomes stay separate.
- Preserve the existing authoritative snapshot and stop behavior; no silent zero on unreadable optional history.
- Cash, commitments, receivables, gross known credits, authoritative net revenue and unknown profit are different facts. Existing founder-provided VPS/model subscriptions are outside50CAD; no invented period/allocation.
- No raw account, receipt, request, digest, operation/payment reference or free-form exception in director/STATUS context.

## Review Focus

1. Internally consistent but incomplete legacy history must remain UNKNOWN, not COMPLETE.
2. Actual settled debit differs from reserved maximum; holds and released reservations are not realized spending.
3. Reversal flooring/order and attested credits must not produce invented net revenue by recomputation.
4. Optional history/receivable corruption must not fabricate zero or mutate authoritative balances.
5. Both consumers use a coherent same-read snapshot/context and preserve privacy and stop guards.

## Task1: Shared read-only economic projection

**Files:** Modify `scripts/treasury.py` (read-only economic_snapshot), `scripts/controller.py` (prepare_context), `scripts/tools.py` (STATUS), `scripts/payouts.py` (optional validated entries input only); create `scripts/economic.py`, `tests/test_economic.py`; extend only directly affected Treasury/controller/STATUS tests if needed. Add a short explanation in an existing relevant operational doc or README, without rewriting the mandate or unrelated sections.

**Interfaces:** `Treasury.economic_snapshot()->{snapshot,journal,commitments}`; `economic.project(root,bank)->{snapshot,context}`. Exact semantics and fields are in the spec. No additional read layer or materialized ledger. Tests may use actual temporary SQLite databases and fake verifiers only for fixture admission; projection itself never calls a verifier. Existing simple test doubles remain usable with explicit unavailable economic fields.

- [ ] Step1: Read Treasury._view/_evidence/settle/release/reverse, current payout projection, director preparation and STATUS. Confirm source action/status names and canonical receipt hashing; no broader audit.
- [ ] Step2: Write failing tests for the five exact acceptance scenarios in the spec. Cover admitted5000funding+1000revenue-250spend+50refund-100reversal =5700cash; HELD200/UNKNOWN300 leaves5200available; grossknownrevenue1000 versus authoritative net900. USD2340receivable never changes CAD.
- [ ] Step3: Run `python -m unittest discover -s tests -p test_economic.py -v` and record actual missing-interface RED. POSIX consumer integration runs on root's Linux fixture; do not shim fcntl or claim skipped integration passed.
- [ ] Step4: Implement consistent read-only Treasury snapshot/aggregate/coverage, then minimal safe economic projection. Use explicit fixed-state/null failure fields. Validate event identities,digests,kind/action and bounded amounts, sum lifetime amounts in Python. Preserve authoritative errors; no initializer/migration/write/finance invocation from the projection.
- [ ] Step5: Add exact reuse in director and STATUS, preserving all other payloads/stop checks and existing snapshot-only doubles with unavailable details. Add privacy sentinels and consistent-read integration tests. Keep treasury-only protection unchanged.
- [ ] Step6: Run focused economic/Treasury/payout/controller/tool tests. Assert SQLite tables unchanged, replay totals stable, partial settlement and released/cancelled cases, reversal-order authority, maturity/floor and both stop states, legacy mismatch/corruption, and missing optional data. Verify no raw private markers in either consumer.
- [ ] Step7: Root runs appropriate full Linux/CI checks and independent review on a frozen diff. Worker reports commands/output, limitations and changedfiles without staging. Root alone commits and prepares a separate PR after its dependency is stable; no deployment here.

## Binding preflight resolutions

Follow the spec preflight clarifications: one strict optional invoice read with missing/invalid UNAVAILABLE versus existing empty zero; reuse receivables via entries without reload. SQLite consistency excludes the independently persisted invoice ledger, which may lag settlement. Extend the existing optional-data/consistency acceptance cases accordingly; no payout-write repair.

## Dependency and isolation

Prepared on separate branch codex/economic-context frome4edb465 while PR26 final review runs. Before implementation, root must bring in any PR26 final correction and record the final base. Baseline at e4edb465 passed exact-treeCI530Python7skip+Node/Docker/shell/products; do not rerun unchanged baseline. PR26 integration choice remains separate. Native worktree creation previously rejected this nested repository sourceRoot; Git fallback from its normal checkout preserves the frozen event branch. This plan only prepares the next increment, not a claim that economic context is implemented.
