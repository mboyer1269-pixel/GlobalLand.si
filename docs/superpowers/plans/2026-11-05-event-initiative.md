# Event-driven Initiative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume useful existing GlobalLand work from durable signals without replayed effects, invisible acknowledgments or wake loops.

**Architecture:** A private host event ledger admits the existing Supervisor's director/private-mail lanes under its shared lock. Frozen sanitized context and exact mailbox processing receipts prove which source revisions were consumed. Periodic paths remain recovery and continuation mechanisms; existing execution journals retain effect authority.

**Tech Stack:** Python 3.12 standard library, SQLite, existing Linux flock/cron, unittest, Node 22 regression checks.

**Spec:** `docs/superpowers/specs/2026-11-05-event-initiative.md` (read before implementation).

## Global Constraints

- Python 3.12+, standard library only; preserve Node 22 executor contracts.
- All productive admissions use `state/supervisor.lock` and installed control; never invoke another supervisor CLI while holding that lock.
- Events grant scheduling eligibility only; all existing agent, tool, financial, private-routing and independent-review authority remains unchanged.
- Preserve task no-replay, mail UNKNOWN, immutable READY, broker budgets, private case budgets and mailbox fairness.
- HALTED in either world or treasury defers production; EXTINCT in either permanently suppresses it. Preserve evidence and existing accounting/publication recovery.
- A discovery cursor, aggregate count or baseline is never proof that a model saw a source.
- Root alone stages, commits and installs; implementation workers leave a reviewable diff.

The founder already authorized the implementation and team method; hand this plan to root for execution, without asking for a new market or workflow approval. Base is `194ffb36ae7f40ba7a43fadb9dbc3f62e6cc854c`, branch `codex/event-initiative`.

## Review Focus

- Deleting a cursor source or restarting during historical baseline must not lose subsequent arrivals or invent ACKs; test `test_scan_cursor_deletion_and_baseline_restart`.
- A financial result stored under each legacy journal shape must never leak request/receipt data merely to make it visible; test `test_financial_legacy_shapes_are_status_only`.
- Accepted mail followed by callback failure must stay accepted and must not POST again; test `test_processed_callback_failure_cannot_downgrade_accepted`.
- A broker lease claim committed before its supervisor receipt must retain causal depth after restart; test `test_claim_effect_before_receipt_keeps_lineage`.
- A custom cron or failed atomic replacement must preserve the previous usable schedule/config; test `test_event_schedule_refuses_custom_and_rolls_back`.

---

## File responsibilities

| File | Responsibility |
|---|---|
| New `scripts/initiative.py` | Strict settings; source revision helpers; SQLite event/admission/lineage receipts; bounded reconciliation, selection and recovery bookkeeping. No model, Git, mailbox network or tool execution. |
| `scripts/controller.py:390–504` | Prepare one initial context+coverage; compatible tick callbacks; persist final-task lineage with its decision. Keep broker live reads separate from frozen ACK coverage. |
| `scripts/commercial.py:142–226`, `scripts/progress.py:155–197` | One shared bounded commercial read set for projection, coverage and progress. Priority keys without exposing them publicly. |
| `scripts/mail.py:388–575`, `scripts/mail_agent.py:142–160` | Exact host callback after durable per-source processing; unchanged fair selection, transport and aggregate status. |
| `scripts/supervisor.py:208–386` | Shared local admission before cycle network work; internal director lane; pre-effect lineage; recovery/ACK; complete stop guards. |
| `scripts/world.py:152–189` | Read-only operation-result lookup for recovering the exact lease claim already committed. No new WORLD action. |
| `scripts/start_autonomy.py:17–79`, `INSTALL.md` | Exact enabled/disabled managed schedules, same-file wake, backup/rollback and operational meaning. No deployment. |
| New `tests/test_initiative.py`, `tests/test_initiative_integration.py` | Pure ledger/source/coverage and existing-supervisor integration, using temporary storage and fakes. |
| Existing `tests/test_controller.py`, `tests/test_commercial.py`, `tests/test_mail.py`, `tests/test_private_mail_integration.py`, `tests/test_start_autonomy.py`, `tests/test_world.py` | Focused regressions in affected existing interfaces; reuse their fixtures. |

## Task 1: Durable event admission through the existing Supervisor

One coherent review gate: event persistence without exact coverage/recovery is unsafe to enable, so do not split scaffolding into separately shipped tasks. Implement in the steps below, keeping each step's focused tests runnable.

**Interfaces** (plain dictionaries; shapes are fixed by the spec):

- `initiative.settings(config: dict) -> dict`: strict enabled flag and validated defaults/ranges from the spec.
- `initiative.source_revision(kind: str, source: dict) -> tuple[str,str]`: validated key/version, independent of publication time/state; no untrusted path resolution.
- `initiative.Store(root, config: dict)`: host-only persistent ledger; derive policy with settings(config), retain the current inbox/commercial configuration for source validation, and never persist configuration credentials.
- `Store.reconcile(world: dict, *, now: int) -> None`: bounded local scans, baseline/cursors, canonical insertions and obsolete dispositions; no external calls.
- `Store.claim(mode: str, *, now: int, world_state: str, bank_state: str) -> dict | None`: transactional reservation returned with target, selected Event dictionaries, exact event IDs, cause and unique turn for director; modes `wake`, `think`, `mail`. Pass its selected events as prepare_context priority. Periodic eligibility may consume depth-limited sources. Stop/rate checks happen here.
- `Store.start(wake_id: str, *, prepared: dict | None, now: int) -> None`: persist STARTED, frozen context/coverage/digest (director only), and spacing before the first provider/private pass.
- `Store.bind_task(task: dict, *, turn: str | None, cause: dict, origin: str) -> None`: durable input-hash/validated-action lineage and claim intent before effects; no financial args in exported metadata.
- `World.operation_result(operation_id: str) -> dict | None`: read-only validated lookup of the exact stored operation result, returning no result when absent; never replay `apply` to infer a lease revision.
- `Store.processed(wake_id: str, receipt: dict) -> None`: consume only the matching private source revision after mailbox persistence.
- `Store.finish(wake_id: str, *, turn: str | None, now: int) -> None`: validates durable controller publication or private receipts, then ACKs only exact covered revisions.
- `Store.recover(*, now: int) -> list[dict]`: returns existing CLAIMED or decision-publication admissions to resume; marks director STARTED without decision INTERRUPTED/periodic-only; reconciles private terminal/successor state without sends. It never calls the model or starts a new root.
- `Controller.prepare_context(*, priority=()) -> dict`: `{context,assessment,coverage,excluded}`; `Controller.context() -> dict` remains compatible.
- `Controller.tick(now=None, *, prepared=None, before_plan=None) -> tuple[str,dict]`: pending decisions return unchanged; before_plan fires once only before first new provider invocation, not while returning a prior decision. Existing in-turn provider failover stays unchanged.
- `commercial.scan(root,config,*,priority=()) -> dict`; `commercial.project(root,config,*,scan=None) -> dict`; `commercial.progress_snapshot(root,config,*,scan=None) -> dict`; `progress.assess(root,world,bank,config,*,commercial_snapshot=None) -> dict` preserve old call forms.
- `Mailbox.cycle(self,responder,*,on_processed=None) -> dict`; `run_mail_cycle(root,config,*,on_processed=None) -> dict`; callback receives spec receipt, never mail content.
- `Supervisor.dispatch(mode,*,now=None) -> dict`: local entry under held supervisor lock. Keep `cycle(mode)` as a compatibility wrapper routed through admission; move existing productive body into an internal helper that cannot recursively dispatch or reacquire flock. Internal director path runs think then queue in the same process.

- [ ] **Step 1: Write failing coverage and privacy tests.** Add `test_frozen_context_ack_only_visible_revisions` with 23 queued results and 2,001 commercial sources: initial task summary count is 20, output length is at most 2,000, only exact visible versions are covered, and subsequent oldest-first batches cover the remainder despite newly arriving recent sources. Assert commercial scan count is one per prepared turn; mutate a source after preparation and assert the old manifest/prompt remain paired. Add `test_financial_legacy_shapes_are_status_only` for `request`, task-dict and queued-path shapes: SPEND/RECONCILE secret sentinels in arguments, output, receipts, gateway cursor and idempotency key are absent; only validated status/redaction survives. Include corrupt/redacted sources and multibyte output boundaries with explicit truncation.

- [ ] **Step 2: Run the coverage tests and observe the missing-contract failures.** Run `python3 -m unittest discover -s tests -p 'test_initiative.py' -v`; expected failures refer to missing initiative/prepare_context interfaces or wrong coverage, not fixture/import mistakes. Do not weaken the 20/2,000/2,000 limits to pass.

- [ ] **Step 3: Implement frozen context and shared reads.** Implement the specified commercial/progress optional arguments and `Controller.prepare_context`. Derive context and exact coverage from the same selected values. Prioritize oldest pending admitted keys within existing windows, retain safe status-only summaries and fixed exclusions, and preserve treasury aggregate behavior. Use current controller result-screening and commercial validation, including the financial legacy-shape fixes required for new coverage. Wire tick's prepared payload without changing decision schema or broker authority; broker recent-result reads remain live but cannot enlarge its initial ACK manifest.

- [ ] **Step 4: Run the focused coverage regression checks.** Run `python3 -m unittest discover -s tests -p 'test_initiative.py' -v`, then `python3 -m unittest discover -s tests -p 'test_commercial*.py' -v` and `python3 -m unittest discover -s tests -p 'test_progress*.py' -v`. Expected: all pass; old callers still return existing public shapes apart from explicit safe summary flags.

- [ ] **Step 5: Write failing event/admission/restart tests.** Add tests for canonical duplicate suppression and exact configuration ranges; `test_scan_cursor_deletion_and_baseline_restart`; one COMMERCIAL_SIGNAL excluding synthetic/automated/held/unknown sources; one QUEUED_RESULT excluding broker/STATUS/outbox writes; lease near-expiry/expired dedupe and replacement; `test_chain_depth_survives_restart_and_periodic_consumes_backlog` with default depth 1 and a configured higher value. Assert CLAIMED reuses its reservation, director STARTED with no decision never invokes a model again, and decision/push-before-ACK recovery reuses the same turn. Assert a returned older controller decision ACKs zero newly discovered events. Persisted rate accounting must survive restart and backward wall-clock movement must not enable rapid admissions.

- [ ] **Step 6: Run the new admission tests to verify failure.** Run `python3 -m unittest discover -s tests -p 'test_initiative.py' -v`; expected failure is the missing Store/admission behavior while Step 4 tests still pass.

- [ ] **Step 7: Implement the ledger and pre-effect lineage.** Implement the Store interfaces and spec schema/permissions with SQLite transactions. Default disabled; defaults are 60-second debounce, 300-second director/mail spacing, depth 1, batch 64, page 200 and lease notice 300. Save turn cause before broker use, task bindings before executor calls or queued publication, and claim intents before WORLD mutation. Resolve committed claim intents from World operation receipts; never invent lineage from public strings or mtime. Keep baseline, exclusion, coverage and acknowledgment states distinct. Wire only local callbacks/reconciliation, not a new executor.

- [ ] **Step 8: Write failing per-revision private-mail integration tests.** Add `test_private_pass_receipts_match_selected_revisions`: a due retry batch larger than max_messages_per_cycle plus fresh arrivals ACKs only actually processed old versions; new durable RETRY revisions retain their own retry_after. Held cases, zero-progress budget deferrals and failed journal saves produce no receipt. Add `test_processed_callback_failure_cannot_downgrade_accepted`: inject callback failure after ACCEPTED, rerun the cycle, assert state ACCEPTED and POST count exactly 1. Test STARTED→UNKNOWN, READY reuse and callback-loss recovery; no direct case-event sender is allowed.

- [ ] **Step 9: Run the new mailbox tests to verify failure.** Run `python3 -m unittest discover -s tests -p 'test_initiative_integration.py' -v`; expected failures identify callback/consumption contracts. Existing mailbox fairness must not be changed to make selection match event order.

- [ ] **Step 10: Implement private processing receipts and common admission.** Add the optional host callback to mailbox/mail_agent, isolated after durable handling so failure cannot enter the send uncertainty branch. Connect exact old/new revisions to Store.processed; reconcile obsolete terminal/successor sources without sends. Factor Supervisor dispatch before Git/finance, retaining existing recovery helpers and same-process think→queue. The wake lock is nonblocking; no nested CLI. Add both-world-and-bank stop checks to legacy mail/queue and event admission. Preserve existing global bank EXTINCT handling and accounting/publication recovery; never invoke production to test it.

- [ ] **Step 11: Add and run decisive supervisor fault tests.** `test_idle_and_busy_wake_make_no_external_calls` patches Git, finance, provider, mailbox transport and subprocess supervisor launch to fail if called. `test_periodic_and_wake_share_single_admission` interleaves callers under the shared lock. `test_claim_effect_before_receipt_keeps_lineage` commits WORLD claim then crashes before supervisor receipt. `test_broker_effect_before_decision_never_reinfers_wake` increments an effect counter then interrupts; restart must preserve counter 1 and mark uncertainty. Also inject source-write-before-insert, CLAIMED-before-STARTED, decision-before-publication, push-before-ACK and private ACCEPTED-before-callback failures. Test each stop state/store through old and new callers; assert zero productive calls but permitted existing recovery. Run `python3 -m unittest discover -s tests -p 'test_initiative*.py' -v` and `python3 -m unittest discover -s tests -p 'test_private*.py' -v`; all pass.

- [ ] **Step 12: Add scheduler tests and implement the existing-file schedule.** `test_event_schedule_refuses_custom_and_rolls_back` verifies exact old JOB→enabled schedule migration, repeated activation, disabled legacy schedule, 30-minute think + one-minute wake in the same `globalland-think`, preserved other cron/config files, and replacement/fsync failure behavior. Implement generation in `start_autonomy.py` from validated initiative settings; do not add a second cron filename/service. Update INSTALL.md with disabled default, tunables, source-discovery latency, uncertainty receipts and recovery semantics. Run `python3 -m unittest discover -s tests -p 'test_start_autonomy.py' -v` and `python3 -m unittest discover -s tests -p 'test_cron_pause.py' -v`; all pass.

- [ ] **Step 13: Run the complete authorized local verification once.** On Linux/WSL with the repository's Python environment: `python3 -m unittest discover -s tests -p 'test_*.py'`; `node tests/runtime.test.js`; `node tests/executor.test.js`; `bash -n scripts/cron_pause.sh`; `bash -n scripts/upgrade_vps.sh`. If the already-installed local Docker fixture is available, run `GLOBALLAND_DOCKER_SMOKE=1 python3 -m unittest discover -s tests -p 'test_docker_smoke.py'`; otherwise report that limitation without claiming real sandbox evidence. Expected: no regressions, explicit skip counts and no network/production side effects. Rerun only checks justified by subsequent fixes.

- [ ] **Step 14: Root review and commit gate.** Implementation worker reports changed files, focused/full test results and remaining limitations, with no staging. Root reviews a frozen diff against this spec, obtains independent review of coverage/crash/privacy/stop boundaries, and owns any commit (suggested title: `feat: resume autonomous work from durable events`). Fix material findings and rerun affected checks. Installation and controlled live evidence remain separate authorized root work, not completion claims from these unit tests.

Self-review: all four event kinds, exact coverage, private fairness, causal lineage, admission timing, crash dispositions, configurable bounds, legacy guards and schedule rollback map to Task 1. The five Review Focus cases have named tests in Steps 1, 5, 8, 11 and 12. No code scaffolding is a standalone deliverable.
