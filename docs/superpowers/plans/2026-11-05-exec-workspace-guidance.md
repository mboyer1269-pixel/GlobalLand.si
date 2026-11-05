# EXEC workspace recovery — implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, one fresh whole-branch review.

**Goal:** Help agents recover from observed missing-directory failures without silently changing their programs or execution environment.

**Architecture:** Keep disposable workspaces and selected inputs unchanged. Add a bounded, fixed explanatory hint to missing-file execution errors; document the same lifecycle in the public controller tool guide and protocol. No directory creation, retry, new permission or paid dependency.

**Tech Stack:** Existing Node executor, Python controller, Node/Python tests.

**Spec:** Audit execution reliability and shared development mandate. Production tasks TASK-179390958111 and TASK-179390958113 failed writing the same nested output folder in separate EXEC calls. Intervening corrections succeeded. This confirms an ergonomics gap, not an unavailable executor or lost published artifact. The founder's goal authorizes reversible implementation choices; no additional strategy or platform is imposed.

## Constraints and decisions

- Preserve result status, artifact collection, no automatic retries and the 8,000-character failure-output limit.
- Hint only for missing-file diagnostics; do not characterize unrelated failures as filesystem problems.
- Private fulfillment must not be told to supply public `inputs`; explicitly qualify public re-selection advice.
- Automatic output-parent creation was considered and rejected: existing programs may themselves create those directories and depend on their initial absence.
- Keep the exact installed release checkout immutable for deployment/graph evidence. Work in a separate branch/worktree; PR31 remains separate and reviewed.

## Task 1 — actionable lifecycle contract

Files: scripts/executor.js, scripts/controller.py, queue/PROTOCOL.md, tests/executor.test.js, tests/test_docker_smoke.py.

- [x] Add a regression executing a program that writes a nested output without mkdir; assert FAILED/no publication, original error and lifecycle recovery hint. Observe RED first.
- [x] Add fixed bounded hint only for missing-file failures, keep directory creation the program's responsibility.
- [x] Add public controller/protocol guidance: selected inputs only, no implicit prior work or output directories, include published prior inputs to reuse them. Private path unchanged.
- [x] Add actual Docker recovery coverage: empty selection, missing parent produces clear failure, corrected new task creates parent and publishes one validated artifact.
- [x] Run Node, Python and relevant Docker coverage, inspect exact results; one fresh review, fix important findings once if any, prepare PR with limits and evidence.

Review focus: failure-output bounds, misleading diagnostics, private/public input distinction, preservation of successful programs and no synthesized artifact.
