# Reliable VPS Implementation Plan

Goal: implement the ten requirements approved in the user's Go, without deployment or paid calls.
Architecture: immutable host control plane (Python stdlib), private Git checkout outside containers, ephemeral offline Node 22 worker with read-only trusted code. Durable host journal records running/completed tasks before publication. Only AUDIT is exposed; AGENT_CODE stays disabled even with a signature.

1. Tests first: reject shell strings, unknown types, negative/nonfinite costs, path and symlink inputs; prove explicit audit succeeds and signatures bind exact bytes.
2. Trusted Node modules: strict task parser, atomic JSON, reconciled cent-based ledger and UTC idempotent tick with journal derived from ledger.
3. Host supervisor: one shared flock, sanitized archive export excluding Git, isolated container, durable task artifacts, interrupted-task quarantine, allowlisted publication, fail-closed secret check, push-before-pull retry.
4. Installer and wrappers: install reviewed control files outside checkout; no unattended updates; valid Compose, non-root worker, no network, resource limits, no secrets. Root-only administration.
5. Documentation and CI: replace unsafe operational claims; reproducible pinned installation, smoke test, backup/rollback and paid-agent limitations.
6. Run all tests and syntax/config checks; fresh independent read-only review; fix confirmed findings; open PR on current base.

Review focus: crash between action and journal save; successful commit followed by failed push; malicious Git attributes/symlinks; secret in result metadata; repeated UTC tick after downtime.

Ruling: a crash during action is marked INTERRUPTED, never automatically retried. Exactly-once arbitrary external side effects are not claimed.
Ruling: only AUDIT is initially registered. Product execution and paid agents require a separately reviewed extension.
