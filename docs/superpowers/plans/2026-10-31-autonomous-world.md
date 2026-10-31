# Autonomous world Implementation Plan

Goal: replace AUDIT-only capability with a persistent autonomous-world core, broad sandbox tools and delegated budget.
Spec: ../specs/2026-10-31-autonomous-world-design.md
Stack: Python 3.12 sqlite3/stdlib, Node 22, Docker Compose, Git.

Global constraints: initial capital 5000 CAD cents; no overdraft or personal top-up; no per-action CEO veto; retain Oria separation and private credentials. Existing v2 VPS continues until reviewed upgrade. No actual paid call in development.

1. Treasury: scripts/treasury.py, tests/test_treasury.py. SQLite durable exact-cent reservations, receipts, settlements, GLC accounts, funding readiness and irreversible extinction. Tests first.
2. World: scripts/world.py, tests/test_world.py. Separate SQLite world tables with roster/missions/messages/leases/events; no invented monetary effects. Tests first.
3. Executor/broker: scripts/tools.py, task schema and supervisor dispatch. Broad EXEC argv, public FETCH, safe artifact collection, world operations and readiness. No repository code on host. Tests first, real Git publication.
4. Controller: durable observation/outbox integration for external Grok and configured installed controller, explicit missing-configuration status. No unpaid model claim; no external paid calls without treasury/provider capabilities.
5. Upgrade/config/governance: update all authoritative rules to CEO mandate, retain historic ledger, deterministic fixtures, isolated control installer upgrade with rollback and bounded sandbox configuration.
6. Verification: full tests, syntax/Compose checks, fresh read-only review, address confirmed findings, publish PR. Actual controller and custody setup are explicit external dependencies.

Review focus: concurrent funds reservations; unknown external outcomes; task crash plus lost push; sandbox output symlinks/secrets; terminal death with pending assets.
