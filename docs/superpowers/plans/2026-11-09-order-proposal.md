# Order Proposal Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task; the parent agent coordinates the final independent review.

**Goal:** Make saved customer demand usable as an immutable product proposal, administrative order, and private payment instruction artifact.

**Architecture:** A small `order_proposals.py` module validates saved continuity evidence and product terms, persists immutable private snapshots, and reuses the existing register/context. `orders_admin.py` exposes three root-only actions; mail and bank protocols are unchanged.

**Tech Stack:** Python standard library, SQLite through existing OrderRegister, unittest, Linux temporary directories.

**Spec:** `docs/superpowers/specs/2026-11-09-order-proposal-design.md`.

## Global Constraints

- Only administrative acceptance; no bank writes, messages, deployment, model metadata, or new service dependency.
- Reusable product identity/version; bounded MANUAL_ARTIFACT evidence <=1 MiB; agents retain product/niche/price choice.
- Source and acceptance must reference distinct saved authenticated READY cases with matching conversation bindings.
- Private storage only; replay preserves one order; changed immutable evidence fails closed.

## Review Focus

Wrong buyer/thread/inbox; changed proposal replay; altered or stale product evidence; reused acceptance across orders; public/linked/private output path violations. Each is covered by the tests below.

### Task 1: Administrative proposal lifecycle

**Files:** create `scripts/order_proposals.py`, `tests/test_order_proposals.py`; modify `scripts/orders_admin.py`; document `docs/order-proposals.md`.

**Interfaces:** module `propose(root, data)`, `accept(root, data)`, `instructions(root, data)` return sanitized record identifiers/status. Inputs use existing completion reference `{version,case_key,ready_digest}`. Existing `OrderRegister.create_order/accept_order`, `continuity.load_ready`, and `order_context.for_message` retain their contracts.

- [x] Write tests exercising real saved READY cases and existing ledger through CLI: draft creation, exact replay, revision/changed terms, separate acceptance, matching binding, private instructions, no Treasury initialization.
- [x] Run `python -m unittest tests.test_order_proposals -v`; observe failure because CLI lacks `propose`, before implementing.
- [x] Implement strict schemas, host-derived identity/digest, actual artifact validation, immutable private snapshots, explicit acceptance and private instruction export.
- [x] Run focused tests to GREEN; add failure-first tests for malformed inputs, path privacy, false acceptance, source reuse, crash/retry and payment suppression.
- [ ] Run order/mail/continuity integration suites, then project Python unittest discovery and Node checks used by CI, all offline with temporary storage. Record actual results and limitations.
- [x] Write operational JSON examples and local verification record; hand diff to parent for independent review. No push/merge/deploy by this implementer.

## Execution ledger

Base `c17e7d765082690ea0b48b702c292335164a0e7e`; new branch `codex/order-proposal-20261109`. Existing isolated checkout reused as requested. Ruling: use the operator-only importer, not responder metadata capture; this is the smallest authorized operational increment and leaves model contract authority unchanged. Pre-flight: all new actions consume existing continuity/register interfaces; no shared protocol changes.

Ruling: per parent review, product evidence uses binary-safe `MANUAL_ARTIFACT`, not an inline UTF-8 eligibility restriction. Retained existing 1 MiB per-product evidence bound; larger executable delivery is not implemented.

Review findings fixed with failing regressions: re-authorize saved cases using current host configuration and exclude synthetic/automatic sources; replace hardlink publication with serialized atomic replacement and directory fsync; allow exact administrator order selection without changing the ten-order default mail view. Separate reviewer confirmed no blocking finding after these fixes. Root coordinates commit/publication.

Targeted Linux run: 119 tests passed, including 19 bridge tests and existing order/mail/continuity/private-work suites. Linux Node 22.23.4: runtime 8/8, executor 7/7, city JavaScript syntax check passed. Native Windows Python is not a supported verification environment for existing `fcntl` imports; native Node symlink tests failed with EPERM, superseded by the successful Linux Node run. Full Python suite is rerunning with corrected Node PATH; results tracked in the local verification report, not inferred here.
