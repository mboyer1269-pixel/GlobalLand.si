# City projection implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the approved explorable city display actual published agents, missions, tasks and results without a hardcoded mission or invented activity.

**Architecture:** Keep the existing illustration and plain frontend. A read-only Python Git projection pins one public commit, loads complete world pages, and links recent queued/broker results to verified requests and versioned artifacts. The local HTTP server exposes only the projected allowlist and static city files; missing data is explicit.

**Tech Stack:** Python standard library, Git, HTML/CSS/JavaScript; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-11-03-global-land-city-design.md` (founder-approved city). The private multi-device host remains separate from this local implementation, as in the spec's hosting section.

## Global Constraints

- Agents keep their market and strategy choices. This is a read-only observer, no runtime, financial or scheduling mutation.
- Preserve the illustrated map, places, keyboard/touch routes, reduced-motion styling and selected view/filter during refresh.
- One Git SHA per snapshot; request IDs and input hashes verify attribution. Unknown attribution stays unknown.
- Never expose lease tokens, raw tool arguments, credentials or private runtime paths in the JSON response.
- No original prototype history may enter the branch: copy reviewed files only from the old checkout.
- Only bind to `127.0.0.1`; fail closed on unexpected Host. Remote/mobile hosting requires a later authenticated design.
- No Graphify viewer browser workaround: a separate city application can be tested normally, but do not expose the blocked graph through it.

## Review Focus

- Paginated world changes during refresh must not mix revisions or silently omit current missions.
- A result whose request is absent or hash mismatched must remain visible without false attribution.
- An artifact changed later must link to its result commit, not the current HEAD.
- Empty, failed or malformed data must not fall back to simulated successes or lose the last valid view.
- Untrusted mission text and new agent identifiers must not inject markup, break navigation or reveal private fields.

## Task 1: Restore the complete read-only city journey

**Files:** import reviewed `prototypes/ville-globalland/{index.html,ville.css,ville.js,ville-crepuscule.png,ville_locale.py}`; add `city_projection.py` alongside them; add `tests/test_city.py`; document local startup in `prototypes/ville-globalland/README.md` and link it from the root README.

**Interfaces:** `city_projection.snapshot(repo: Path, revision: str | None = None) -> dict` returns revision, publishedAt, controller, agents, missions, events, artifacts, optional journey, coverage. `ville_locale.SnapshotReader` caches a valid snapshot for 55 seconds and reports stale/checkedAt; `/snapshot.json` is read-only. Existing frontend IDs and map routes remain.

- [x] Write fixture Git repositories exercising full pages beyond preview, zero missions/artifacts, broker request hash verification, queued request recovered from the result commit's parent, wrong/missing hashes, terminal failures and artifact replacement.
- [x] Observe the existing implementation fail the behavioral tests. Do not mistake fixture syntax errors for RED evidence.
- [x] Implement the Git projection: bounded JSON reads, validate page metadata at one SHA, sanitize selected fields, collect recent result publications and current pending requests, retain status distinctions, optional journey. Show the task-history window explicitly; never imply it is all history. Missing/invalid individual task data yields an explicit warning, not fabricated success.
- [x] Verify the tests pass; add live HTTP tests for allowlisted responses, missing-source 503, stale-cache recovery and unexpected Host/path refusal.
- [x] Adapt the frontend to real-first empty state, optional journey, generic agents/missions, all returned artifacts, publication windows and retained focus/filter. Remove sample activity from the live page. Observe failures before fixing through local browser/HTTP checks.
- [x] Verify actual current public snapshots at two revisions, including the previously omitted Shopify missions and broker tasks. Check browser desktop/mobile/keyboard routes and refresh with existing tools; record any environmental limits truthfully.
- [x] Run the complete Python suite, Node suites and syntax checks, then commit. Scope does not justify skipping existing tests.
- [ ] Run one fresh whole-branch review, fix Important/Critical findings once with reproducing tests, record decisions and prepare a draft PR. Do not merge or install this new increment without its applicable authorization.

## Execution choices

Routine implementation is already authorized by the active goal and approved city direction. Native inline execution with one fresh final review follows the preceding increments; no new business or interface design decision is being substituted. Separate branch preserves the exact installed release/graph checkouts. The app's managed worktree tool rejected the nested repository sourceRoot, so Git fallback is used and its reason recorded. This plan is scoped to the existing local observer; it does not claim an authenticated remote deployment.
