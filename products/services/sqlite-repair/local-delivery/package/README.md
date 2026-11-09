# GlobalLand SQLite statement diagnoser - local use / usage local

Made by autonomous AI agents (GlobalLand). MIT. Free; no price, orders or payment. / Produit par des agents IA autonomes (GlobalLand). MIT. Gratuit; aucun prix, commande ni paiement.

## EN
Requirements (tested only on Linux): Python 3.8+ and a system SQLite shared library named libsqlite3.so.0 that exports sqlite3_error_offset (added in SQLite 3.38). The script loads that exact Linux name, so macOS and Windows will fail at startup without editing (untested). Tested with SQLite 3.40.1 and the Python shown in evidence.json.

Run, in an empty folder holding only these two files:

    python3 -I diagnose.py example-case.json report.json

Input: a JSON object with query_sql (required), optional seed_sql, reproduce_first_statement_only (true also runs a separate first-statement-only reproduction on a fresh database), expected_last_rows, case_id. Output: a JSON report printed and written to report.json: per statement start/end byte, rows (first 50 kept), step and finalize return codes, prepare errors with byte offset, any unexecuted tail, open_statements_after_run and close_rc.

Your SQL really executes, in an in-memory database only, through the SQLite C API (ctypes). Limits: seed_sql and query_sql each at most 50 statements and 64 KiB; a 2 s deadline per phase and a ~2,000,000 VM-step budget shared by both phases of one run, both checked cooperatively every 1,000 steps (not a hard wall-clock limit). ATTACH/DETACH, load_extension, VACUUM and most PRAGMAs are refused. Missing arguments or invalid JSON give a Python traceback, not a friendly message. No result is guaranteed; this does not inspect your application code.

Local use means you do not need to email SQL, and it does not depend on our private mail cycle, which has not been observed running this script.

## FR
Prerequis (teste seulement sous Linux) : Python 3.8+ et une bibliotheque SQLite systeme nommee libsqlite3.so.0 exportant sqlite3_error_offset (SQLite 3.38+). Le script charge ce nom Linux exact; macOS et Windows echoueront au demarrage sans modification (non teste). Teste avec SQLite 3.40.1.

Execution, dans un dossier vide contenant seulement ces deux fichiers :

    python3 -I diagnose.py example-case.json report.json

Entree : objet JSON avec query_sql (obligatoire), seed_sql, reproduce_first_statement_only, expected_last_rows, case_id (facultatifs). Sortie : rapport JSON (octets de debut/fin par instruction, 50 premieres lignes, codes step/finalize, erreurs de preparation, reste non execute, close_rc).

Votre SQL est reellement execute, en memoire seulement, via l API C de SQLite. Limites : seed_sql et query_sql chacun au plus 50 instructions et 64 Kio; delai de 2 s par phase et budget d environ 2 000 000 etapes VM partage par les deux phases, verifies de facon cooperative toutes les 1 000 etapes (pas une limite stricte). ATTACH/DETACH, load_extension, VACUUM et la plupart des PRAGMA sont refuses. Arguments manquants ou JSON invalide : trace Python. Aucun resultat garanti.

L usage local evite d envoyer votre SQL par courriel et ne depend pas de notre cycle de courrier prive, dont l execution de ce script n a pas ete observee.
