# Operator development audit — catalogue sample

Scope: independent offline review of the agent-selected sample at commit `1b120d42fb8c505c4054fe30b0d64cf0428b0454`. Synthetic fixtures only. This note does not approve deployment, contact a prospect, accept a paid order or verify any revenue.

The existing four tests were rerun in an isolated copy and all passed, including the 9,000-barcode case. Additional checks found two concrete defects that should be resolved before proposing this sample as a usable deliverable.

## 1. Split output names can silently overwrite earlier products

`transform.write` constructs split names with `out.replace('.csv', '-partN.csv')`. With a filename lacking lowercase `.csv`, every chunk has the same destination.

Reproduction: three distinct one-variant products, split limit 1. `output.csv` produces three distinct files and preserves all three variants. `output` and `output.CSV` each report three output entries but create only one file containing the final variant. Earlier chunks are overwritten without a reported transformation error.

Expected repair: either produce distinct safe names for supported filename forms or reject unsupported forms before any write. Add regression coverage asserting distinct paths and complete identifier preservation across actual files. Do not merely count entries in the returned filename list.

## 2. Product test runner returns success despite failed checks

In a disposable copy only, the final `verify` return was preceded by `chk['intentional_audit_failure'] = False`. Rerunning `tests/run_tests.py` reported **1 passed / 4 total** but returned process exit code **0**. The unmodified baseline reports 4/4 and exit 0.

Expected repair: nonzero process exit when any case fails; confirm by a deliberate failing assertion/check and restore the verifier afterwards. Isolate scratch files per run instead of relying on shared `/tmp/slc` to keep reruns independent.

## Commercial and import evidence still open

The public request retained in the repository is dated 2025-11-11. It is a historical problem statement, not proof that the author still needs this work or would buy it. Current availability of that request could not be established through the development web tool. No contact has been made.

The [official Shopify CSV documentation](https://help.shopify.com/en/manual/products/import-export/using-csv), checked on 2026-11-05, says omitted product Status defaults to active; online-store publication also has a true default. The sample omits these fields. Before recommending an import, explicitly address preview/draft behavior and the consequences for an existing store; an offline shape verifier does not prove a safe live import. No live-store change is authorized by this note.

Agents retain the choice to correct, narrow or abandon this experiment according to the observed results. Any further release still needs its existing independent review. A developer-authored audit note is neither customer feedback nor new market demand.
