# Interac and private orders — implementation plan

Approved design: `output/globalland-interac-orders-design.md` in the development workspace, approved explicitly 2026-11-07. No new market or platform requirement. No bank API claimed. Native execution with focused independent review; separate core register work may be delegated to keep browser configuration moving.

## Tasks

1. Add `scripts/orders.py` private SQLite register and `tests/test_orders.py`.
   Host-generated opaque IDs, immutable order terms/case association, separate unverified claims, founder-attested deposits, explicit allocation and Treasury posting. Exact replay idempotence, contradictory replay rejection. Bank transfer identity independent of order. Safe read-only aggregate projection, unavailable on corrupt/missing storage. No bank secrets, no public customer content. Run focused tests RED then GREEN.
2. Add `scripts/orders_admin.py` admin-only commands for private local JSON input, register/status/claim/confirm/allocate/post. No personal data in command-line arguments/output. Require explicit founder attestation. Use host locking and private paths. Funding untouched. No spending API. Test invalid inputs, authorization and error output.
3. Add deterministic financial notice hold in `mail.py` before responder/continuity and before send, with tests. Provider notices remain untrusted and cannot authorize payment; customer questions about payment must still be processed. Default notice-domain matching is only a hold, never authentication.
4. Expose aggregate `order_payments` context in controller and capability readiness. Keep existing commercial observations unverified. Add order route to case context only when enabled/configured; no global permission to accept binding commitments. Tests for unavailable/disabled/private projection and synthetic data exclusion.
5. Document operator workflow and limits in `docs/INTERAC-COMMANDES.md`. Include exact commands and draft/ready/accepted distinctions. Validate simulated full order → claim → founder attestation → allocation → Treasury once, restart replay, malformed evidence and mismatch.
6. Fresh independent whole-diff review, fix material issues, run CI and open a reviewable PR. Merge/deployment are separate from implementation approval; do not silently activate production cash or send a payment request.

## Review focus

- Reusing one bank transfer under a different order or reference normalization.
- Crash between Treasury credit and marking register posted; replay must repair only.
- Email authenticity/model text confused with financial authority.
- Privacy leaks through projections, errors, command line, cross-customer case context.
- Missing/corrupt ledger represented as zero demand or a ready payment route.
- Partial/excess/wrong-currency payments, fake fixtures, HALTED/EXTINCT Treasury states.

## Execution ledger

- Setup: clean existing isolated worktree reused on `codex/interac-orders-20261107`, based on origin/main. PR37 already merged. Existing main CI green; full local WSL suite previously caused host OOM, so focused portable tests and hosted CI will be used.
- Ruling: bank registration remains a separate observed UI fact; no automatic activation from this design or an email. No change to initial funding contract.
- Task 1: private register implemented by orders_register; focused RED/GREEN, replay/crash/corruption/overflow cases covered.
- Tasks 2–4: admin boundary, authenticated case context, director aggregates and protective financial notice hold implemented. Mail prompt regression observed RED on Linux and GREEN after integration.
- Validation: 39 order/admin/context/end-to-end tests and 70 existing Treasury/mail plus notice-hold tests pass on Linux in an isolated temporary directory. No active install or data touched. Windows checks are supplemental, not proof of POSIX permissions.
- Ruling: order creation/acceptance is administrative in this first increment; no silent new contract authority. Agents receive only accepted-order instructions and state for their authenticated conversation. Cost: this is not autonomous checkout yet; documented explicitly in operator guide/capabilities.
- Ruling: administrative route identity cannot change by simple reconfiguration, preventing the same account acquiring a new deduplication namespace. A future account migration requires explicit reconciliation.
