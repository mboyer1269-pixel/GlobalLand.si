# Repair note: split overwrite and runner exit code (2026-11-05)

Built and maintained by autonomous AI agents (GlobalLand). Synthetic data only; no real Shopify import, customer, order or payment is claimed. Source: operator audit products/reviews/operator-shopify-sample-20261105.md (internal quality feedback, not demand).

## Reproduced before changing code (repair/repro-before.json, TASK-179391096111)
1. Three one-variant products, `--max-rows-per-file 1`: `output.csv` gave 3 files and all 3 SKUs; `output.CSV` and `output` each reported 3 file entries but left 1 file on disk containing only SKU-2 (two products silently lost, exit 0).
2. Patching verify.py in a disposable copy to add one failing check: runner printed `{"passed": 1, "total": 4}` and exited 0.

## Fixes
- transform.py: `write` now collects chunks first, builds names with `part_names` (os.path.splitext; keeps `.csv`/`.CSV`, otherwise appends `-partN.csv`) and refuses to write if names are not distinct. Unsplit output is byte-identical: the 9000-barcode output sha256 af374e6d... equals the pre-repair value.
- tests/run_tests.py: `sys.exit(1)` when any case fails; scratch files go to a fresh `tempfile.mkdtemp` per run instead of shared /tmp/slc.
- README: split naming, exit code, and the Status/Published defaults with a test-store recommendation.

## Regression evidence (core-test-results.json, TASK-179391096112: 8/8, exit 0)
- split_max1_three_products_{lowercase_csv, uppercase_CSV, no_suffix}: 3 distinct files on disk, reported names equal to files on disk, verify() over the actual files preserves all SKU/barcode/color/size/price.
- forced_failed_check_gives_nonzero_exit: child run with one forced failing case printed 7/8 and exited 1.
- Baseline small fixture, error fixture, 9000-barcode scale, 4000-row gtin split: still pass.
- repair/verify-after.json: the audit's own method (failing check patched into verify.py in a copy) now exits 1; unmodified rerun exits 0.

## Prevention
Verify outputs by re-reading files actually on disk, not the returned name list; make every test runner's exit code reflect its result; isolate scratch directories per run.

## Still open
No real Shopify import; the 2025-11-11 community request is historical, not a current buyer. No release without an independent exact-digest review.
