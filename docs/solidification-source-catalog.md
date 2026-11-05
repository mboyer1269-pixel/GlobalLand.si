# EXE-04: source catalog and selected job inputs

Design and implementation record, 2026-11-05. The interface below is implemented in this development branch; it is not yet deployed. VISION.md remains authoritative: agents choose activities and inputs; a resource bound applies to one operation, never to the number of products the world may retain. Existing Git history and product evidence remain intact. The following diagnosis describes the previous code; the implementation status is recorded at the end.

## Observed failure chain before this change

The current `Supervisor.refresh_work()` and `_cycle()` call `git archive HEAD` through the generic 20 MiB buffered command runner. `extract_archive()` buffers the tar, enumerates all members, then refuses an individual file above 1 MiB or total content above 16 MiB. Therefore an unrelated large repository file can prevent every cycle from reaching a task.

Removing that archive limit alone is insufficient. `Toolbox.run(EXEC)` copies all of `work/` into a job input directory. `executor.js` then copies all of that input into the writable 256 MiB `/workspace` tmpfs. A growing corpus eventually prevents even a tiny new job from starting. Streaming a whole archive bounds host RAM but still copies the complete corpus and consumes growing disk space and work on every cycle/job.

The broker currently lists the first 500 product paths with no cursor. Its read operation loads a whole file and then returns the first 64 KiB, with no offset. Thus some retained products or later portions of a file become inaccessible independently of the archive problem. The frozen checkout inspected here has 1,144 Git tree files, of which 407 are under `products/`; these counts describe the inspected revision, not runtime limits.

These observations come from source inspection, not a new load benchmark. Relevant functions: `supervisor.extract_archive`, `Supervisor.refresh_work`, `Supervisor._cycle`, `tools.Toolbox.run`, `executor.execute`, `broker.read_handlers`, `Controller.prepare`, `progress.capture`.

## Proposed host-only source interface

The private `source.git` remains the complete durable source, including history. Resolve an immutable revision once for each job/read session. Never mount Git, SSH credentials, private state or installed control into generated programs. A new installed module can expose:

- `list(revision, prefix, cursor, limit=100)` returns the revision, sorted entries `{path, size, oid}`, and `next_cursor`. Every eligible product must be reachable through repeated pages. Cursors bind the prefix and revision; a later publication cannot silently reorder an existing walk.
- `read(revision, path, offset=0, limit=65536)` returns `{revision, path, offset, content, next_offset, total_bytes}`. Decode UTF-8 at a documented byte boundary, or return a bounded base64 chunk for binary data. The next offset advances by the bytes actually returned. Never read the complete blob merely to return a small range.
- `export(revision, selected_paths, destination, job_budget)` materializes only selected files/directory prefixes, preserving exact relative paths. Return a manifest of revision, paths, blob IDs and sizes. Determine the selected size before extraction, then stream regular blobs into fresh files; bound memory, process output, timeout and destination capacity. No whole-repository tar buffer is needed.

Use Git's literal path handling (`--literal-pathspecs` or equivalent), NUL-separated tree records, and incremental readers for large listings/blobs. Do not interpolate paths into a shell or accept a path as an arbitrary Git revision expression. Validate every path component and Git mode. Reject traversal, absolute paths, `.git`, symlinks, submodules, special files and source/destination aliases. Export only eligible public source files, never private host paths. Reject a selected invalid file for that operation; an unrelated invalid/large path must not prevent a safe independent job.

The selection/manifest is pinned to one commit. Verify the exported blob against its expected object ID or content digest. Updates become visible only through an explicit newer revision; never combine entries from different revisions under one snapshot claim. If the broker successfully publishes during a turn, subsequent ordinary reads may default to the newer published revision; explicit paginated sessions retain their original revision. An uncommitted/pending outbox must be described as pending and handled through its host-owned overlay, never represented as a committed Git object.

## Consumers that must change together

| Current consumer | Needed source view |
| --- | --- |
| Supervisor queue cycle | Stream eligible `queue/inbox/` entries/tasks and materialize only a currently selected task. A large historical result or unrelated product cannot block queue enumeration. |
| Installed legacy worker/daily | Explicit minimal public inputs: validated `ledger.json`, `bank/status.json` and the selected legacy task where needed. Installed worker modules already come from `control/`; mutable repository scripts do not become trusted code. |
| Controller context/results | Bounded product catalog pages, selected public task/result fallbacks and `products/receipts/` lookups. Prefer existing private durable result envelopes. Expose continuation rather than pretending a truncated catalog is complete. |
| Controller lessons/playbooks | Export or read the documented playbook files explicitly. Inspect `lessons.playbooks()` before selecting them; a sparse tree must not silently erase this context. |
| Broker list/read | Use the paginated/ranged catalog interface; preserve publication/read-after-write semantics within a turn. |
| Progress measurement | Compare eligible Git tree path/blob IDs instead of reading and hashing every product body on each turn. Preserve the current distinction between research, receipts, new products and rewrites; pagination must not hide later new products. |
| Apify `load_source()` | Export just `products/actors/<actor>/` into an operation directory before existing size, secret and independent-review validation. Preserve source-digest identity. |
| Sites `load_site()` | Export just `products/sites/<site>/` before existing validation/review. Emergency offline action must still work without exporting missing source. |
| EXEC | Export the agent's selected inputs only, retaining their relative `/workspace/...` paths. Keep declared outputs and current output validation/provenance separate. |

Also audit any direct `work/` filesystem reader before making that directory sparse. A successful small queue cycle is not proof that publication, reviews, lessons, progress and old task classification remain complete.

## EXEC and backward compatibility

Add optional `inputs` to the EXEC arguments, generated decision schema, normalizer, host validation, controller instructions and protocol documentation. An input identifies an eligible public file or directory prefix, not an arbitrary host path. Example:

```json
{"argv":["node","products/demo/build.js"],"inputs":["products/demo/","products/research/example.json"],"outputs":["products/demo/result.json"]}
```

`inputs: []` means a fresh empty workspace. Relative paths stay unchanged, and `cwd` must refer to a directory created by the selected export or explicitly initialized under the existing workspace rules. No argument parsing of shell code or inferred dependencies is safe enough to replace explicit input selection.

For older tasks with `inputs` absent, attempt the existing public-input view under a per-job capacity check. Small legacy tasks retain their behavior. When that view exceeds the job's real resource allowance, refuse only that job before running its program, returning a fixed error code, measured selected bytes and an instruction to declare narrower inputs or process chunks. Do not silently drop files, run with partial inputs, shrink the corpus, classify the entire world as stopped or block subsequent unrelated tasks. Existing task IDs, immutable request hashes and execution journals must still prevent uncertain execution from being retried automatically. The limit must reserve capacity for outputs/runtime work rather than filling the entire tmpfs with inputs.

Every stored product remains addressable through the host catalog, regardless of whether a single job can load the entire corpus. Explicit history reads can use an authorized retained commit; history is never deleted to meet a job budget. Storage pressure is a separate observed operational condition, not a reason to invent a maximum number of products or prohibit a strategy.

## Acceptance evidence required before integration

1. Create a temporary Git repository whose retained product corpus exceeds the old 16/20 MiB limits. A safe small selected EXEC still reaches the executor and returns its declared artifact. Every old product remains listed/readable; history/refs are preserved.
2. Include one oversized unrelated blob, one invalid selected mode and more than 500 products. List all eligible entries across pages exactly once; a later product is readable. Reject invalid selection without touching that source or blocking the next safe job.
3. Read a large UTF-8 file in ranges, including a multibyte character at the boundary. Concatenated returned bytes reconstruct the original; process/RAM bounds do not scale with the full blob or tree.
4. Change HEAD between list pages and between manifest/export. Explicit revision sessions remain coherent; default post-publication reads observe the published version. Pending publication is not falsely called committed or cause the program/payment to run again.
5. Reject pathspec metacharacter abuse, revision-expression injection, tabs/newlines, traversal, symlinks, submodules and destination links. Verify no Git/private credentials/control become container-visible.
6. Test legacy absent-input tasks, explicit empty inputs, selected directories, nonexistent files and aggregate selection overflow. Overflow fails before execution; a following tiny job succeeds. Preserve existing output limits, checks and receipts.
7. Run actor/site dry-run, offline switch, independent review, playbook/context, full progress comparison, queued result feedback and legacy daily worker regression tests using sparse inputs. Verify additions after the old listing cutoff count correctly.
8. Keep extraction memory bounded in a practical benchmark with a substantially larger temporary corpus. Report actual process/copy counts, wall time and peak memory. Source inspection alone is insufficient performance evidence.

## Implementation status

`public_source.PublicSource` resolves the confirmed `refs/globalland/published` revision (legacy HEAD fallback only when the ref is absent), streams tree/blob reads, validates object identities, and exports selected inputs atomically. `iter_entries` provides a single tree walk to whole-catalog consumers. List sessions use revision-bound cursors; byte reads include encoding, numeric next_offset and eof. The protocol documents their complete shapes.

EXEC accepts absent/null inputs for legacy selection, an empty list for an empty workspace, or explicit paths/prefixes under a 128 MiB per-job budget. Selection is preflighted and the public receipt includes its revision, size, file count and manifest digest. A refused oversized job does not stop the next independent job. Existing private fulfillment keeps its frozen case inputs and refuses public selectors.

The supervisor no longer archives the whole source. It reads queued tasks individually, stages the legacy ledger and a fresh private Treasury projection when needed, and stages optional Markdown playbooks with explicit omission notices. Controller, broker, progress, private service context, Actor and site publishers use the catalog. Publishers preserve existing review and content budgets. Pending publication cannot become the ordinary default read revision before the push succeeds.

Whole-branch verification and independent review must complete before integration. This document does not itself authorize deployment, paid operations or integration activation.
