# Source catalog verification — 2026-11-05

This increment addresses EXE-04. It is prepared for review, not installed by this report. Agents retain all public source history and choose which inputs each job needs. The 128 MiB bound applies to a job, not to the world's retained products.

## Verified code

An exact source archive was tested in an isolated Linux directory, outside the installed GlobalLand release. Archive SHA256: `95994cf01fcdaf3ca74569e373c484ae5b4a4e64311ea6964028f75efa2c818d`. Python 3.12.3, Node 22.23.4.

- Full Python suite: **671 tests, OK, 9 skipped** (4 subscription CLI contracts, 5 Docker cases).
- Node: 8 runtime and 5 executor tests passed. Shell syntax checks passed.
- Docker enabled separately: 3 general smoke tests, 8 private source tests and 9 catalog supervisor tests passed. These overlap the full suite; the five previously skipped Docker cases are covered, not additional independent counts.
- A real container used only a selected CSV despite a 19 MiB unrelated product history. No Git, host credentials or Docker socket was mounted. It produced the expected output and its disposable job was removed.
- Same-batch FETCH then EXEC sees the published source bytes. A failed push keeps the previous default catalog revision; replay publishes without repeating the effect.
- A 129 MiB legacy selection fails only that job with measured capacity feedback; the next empty-input job succeeds. Queue, lessons, publisher review, progress and private frozen-source consumers are covered.
- STATUS followed by a real Node legacy AUDIT in one lot retains the private Treasury projection. A false Git banking projection does not become authority.

## Growth observations

Temporary Git corpora, not production data: one tree walk enumerated 1,000 paths in 0.047 s and 10,000 in 0.294 s, with measured Python allocation peaks of 244–277 KiB. A two-file export of 32 MiB and 256 MiB took 0.092 s and 0.583 s respectively; each used eight Git processes, approximately 18 MiB observed reader/Git RSS and about 223 KiB traced Python allocations. The 256 MiB case uses a larger test-only export budget; ordinary EXEC remains 128 MiB. These are local benchmark observations, not service-level guarantees.

## Failures found and corrected

The first integrated run failed because an existing test imported an operations helper which inserted `/opt/globalland/control` into `sys.path`. It mixed installed old modules with the checkout under test. Test isolation now preloads checkout dependencies, restores the path and verifies full-suite discovery in a fresh process that forbids installed-control imports. The production helper is unchanged.

Independent review reproduced a missing Treasury projection after the first task erased the sparse work directory. Legacy staging now regenerates that projection from private Treasury. The regression failed before the correction and passed with the real Node worker afterward. No actionable P1/P2 remained in the reviewed code; full integration passed after these fixes.

The CI now runs the same private-source and catalog Docker checks explicitly after pulling its Node image. GitHub checks must be observed separately. No new paid service, live publication or banking integration is established by these tests.
