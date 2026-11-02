# Workspace working directory — 2026-10-31

At installed commit 17a573487d86682666e8a1c7a306fcdbb843a717, the instrumented VPS attempt returned model exit 0, 6,656 stdout bytes and 13,988 stderr bytes. Its next exception originated at supervisor.safe_path line 48, called by tools.validate_envelope line 41 and controller.tick line 226. This identifies EXEC cwd validation after a successful model invocation/decision decoding. The native schema was accepted in this invocation. No task batch was persisted or published. The exact generated cwd value was not captured; the trace alone does not establish its spelling. The Python RuntimeWarnings appeared during temporary frame tracing, not during an ordinary installed think command.

The provider schema previously allowed any cwd string without explaining which root to select, while the task envelope requires relative paths. A real Controller.tick regression reproduces the same unsafe-path failure using the conventional workspace-root aliases `.` and `/workspace`.

The model boundary now removes only the exact root aliases empty string, `.`, `./`, `/workspace` and `/workspace/`, producing the same task as cwd absent/null. The executor already defaults that task to its fixed /workspace container root. All other paths retain the unchanged task-envelope validation; no realpath expansion, prefix stripping, traversal repair or host-path access is introduced. Relative subdirectories retain their original meaning and must exist at execution. The schema field description and model tool guide explain this contract. The installed generated schema matches the Python schema.

Verification:

- Before implementation, the new root-alias test failed at the same Controller.tick → validate_envelope → safe_path boundary with `unsafe path`.
- After implementation, all three new tests pass. They exercise five canonical root spellings through real task validation/durable outbox creation, preserve null/relative cwd semantics, and reject eleven absolute/traversing/malformed paths without a partial outbox batch. Only subscription authentication/model transport are replaced by test fixtures.
- Full Python suite: 128 total, 127 passed, 1 optional Docker smoke skipped locally. Node runtime: 8 passed; executor: 2 passed. Total 137 passed, 1 skipped.
- Python compilation and git diff checks passed.

Limits: these local tests do not demonstrate a productive cycle on the VPS, validate a generated product, or move/verify funds. Retry one normal think followed by queue on the exact reviewed commit, then inspect its actual tasks/results/products before enabling recurring think. Existing accounts/images/configuration are preserved; no rebuild or login is required for this code-only change. Gemini and financial custody remain unconnected.

Rollback: retain the upgrade backup and previous installed release. Pause only GlobalLand cron, acquire its shared lock, and preserve current state/outboxes/financial journals before repointing control to the saved release. Never restore an old financial balance or replay an uncertain payment. Existing INSTALL.md describes the full procedure.
