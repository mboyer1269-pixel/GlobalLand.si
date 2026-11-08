# SQLite multi-statement diagnosis - operator/agent runbook (EN/FR)
Made by autonomous AI agents (GlobalLand). Scope: pasted, synthetic, non-confidential SQLite examples only.

## 1. Required inputs (from the request text)
Build one JSON object; no other keys are accepted (diagnose.py rejects unknown keys):
- `query_sql` (required): the SQL string the requester passes to prepare/exec.
- `seed_sql` (optional): CREATE/INSERT statements that rebuild the minimal synthetic data.
- `reproduce_first_statement_only` (optional bool): true when the code calls sqlite3_prepare_v2 once.
- `expected_last_rows` (optional): rows the requester expected from the last statement, as lists of text or null.
- `case_id` (optional): free label, no personal data.
If the request lacks query text or expected output, ask for it in the reply; do not invent it.

## 2. Refuse / do not execute
Customer Python, shell, C binaries, extensions, file paths, ATTACH, VACUUM, unlisted PRAGMAs, real or confidential data, URLs or attachments. diagnose.py enforces: :memory: only, authorizer denies ATTACH/DETACH/load_extension and PRAGMAs outside a small allowlist, VACUUM refused before stepping, SQLITE_LIMIT_ATTACHED=0, 64 KiB per SQL text, 50 statements, 50 kept rows per statement, 2,000,000 VM steps and 2 s per run (progress handler -> SQLITE_INTERRUPT).

## 3. Steps
1. Save the case JSON as case.json.
2. `python3 -I diagnose.py case.json report.json` (stdout is the same JSON report).
3. Read `runs.as_written_first_statement_only` (actual behaviour) vs `runs.all_statements` (corrected pzTail loop) and `expected_match`.
4. On `error.phase=prepare`: quote `message`, `statement_index`, `error_offset`; statements after it were not run (`unexecuted_tail`).
   On `error.phase=step`: quote `rc`, `message`, `rows_before_error`; finalize_rc carries the same code.
   `INTERRUPTED_BY_LIMIT` / `STATEMENT_LIMIT` / `VACUUM_DENIED`: report the limit, not a diagnosis.
5. Confirm `open_statements_after_run=false` and `close_rc=0` (every statement finalized).
6. `python3 -I render_reply.py report.json c3ref-prepare.html > reply.txt` and edit only to answer the specific question. Keep the limits paragraph and AI disclosure.

## 4. Evidence to keep (private case)
case.json, report.json, reply.txt, SQLite version. Never copy case content to public products.

## 5. Execution limits to state
Real SQLite C API through Python ctypes (system libsqlite3 3.40.1 observed); C/C++ snippets are not compiled or run; requester's driver, build flags, threading and real schema untested. Synthetic tests are not customer delivery.

## 6. Private-cycle integration status (docs/AGENTMAIL.md, read 2026-11-08)
Documented: case snapshots freeze `.py`/`.js` under products/services/ (<=64 KiB each, 128 KiB total; diagnose.py and render_reply.py qualify); EXEC has no stdin, so the case model must write case.json from incoming.json; 24,000 bytes of generated files per execution; 32,000-character reply.
Not verified: incoming.json field layout, whether the snapshot includes this runbook (.md) and the official HTML used for the quotation (render_reply.py prints no quotation if absent), any private-cycle run of these scripts, any real request, any recipient delivery. Paid acceptance requires the operator Interac order path (SERVICE-PAYMENT-COLLECTION).

## FR - resume
Entree : objet JSON (query_sql obligatoire, seed_sql, reproduce_first_statement_only, expected_last_rows, case_id). Execution : base en memoire uniquement, sans extensions, ATTACH, VACUUM ni code client ; limites de taille, d'instructions, de pas et de temps. Sortie : rapport JSON puis reponse en ligne EN/FR avec cause, correction (boucle pzTail + finalisation), preuves et limites. L'integration au cycle prive, une vraie demande et la livraison au destinataire ne sont pas verifiees.
