# Cursor subscription integration — 2026-10-31

Scope: third optional official subscription CLI, preserving Codex/Claude login volumes and their existing command lines. Browser login persists a dedicated private Cursor HOME; the binary lives outside that HOME. Runtime config and sandbox read boundary are mounted readonly. No inference, finance call or recurring scheduler is started by installation/login/configuration checks.

Verification on this workspace:

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 74 tests, 73 passed, 1 Docker smoke skipped (requires explicit VPS/Docker opt-in).
- `node tests/runtime.test.js`: 8 passed.
- `node tests/executor.test.js`: 2 passed.
- Python compilation, per-file Bash syntax, and `git diff --check`: passed.
- 10 Cursor regression tests cover Docker option ordering, retaining config mounts during auth checks, separate private HOME, readiness versus authentication, negative/API-key statuses, identity redaction, required read policy, successful result decoding, malformed/nonobject/nonstring results, duplicate fields and invalid JSON.
- Red tests reproduced the Docker mount-after-image defect, nonobject result parsing, missing read policy paths and acceptance of duplicate decision fields before corrections.
- Independent read-only reviewer found no remaining confirmed functional regression; runtime policy enforcement remains an explicit verification gap.

Not demonstrated here: official Cursor image build/version on Linux, actual browser authentication, subscription quota/billing settings, a live model decision, or enforcement of Read/Grep/Glob boundaries by the resolved CLI. Local tests mock the CLI transport. No claim of a complete Cursor connection or autonomous cycle is made.

Before activation: build from a reviewed exact repository commit and immutable existing brain image; record new image ID/version; log in privately; check status without inference; disable paid extra usage in the selected accounts. Verify attempted reads/searches of a non-secret canary outside the temporary workspace are denied in the exact image, then verify a manual think/queue cycle and actual product before scheduling. Do not use real credential files as probes. Official readBoundary support and startup plugins/hooks remain provider dependencies, documented in SECURITY.md and docs/INTEGRATIONS.md.

Rollback: retain the previous brain image ID and private auth volumes; use the GlobalLand-only upgrade backup/release rollback in INSTALL.md. Do not restore old financial balances or remove payment journals. No Oria changes are part of this patch.

VPS build follow-up: the first real build failed at FROM because a bare local image ID was normalized to docker.io/library/sha256. No Cursor login was reached. build_cursor_image.sh now verifies the original local ID, applies a content-derived GlobalLand-only tag and verifies it before/after building with --pull=false. Four mocked Docker regressions cover success without modifying the old ID, missing base, tag mismatch, and version failure preserving a previous image file. The Docker iidfile pins the exact resulting image for the offline version check and atomic record. These tests do not prove a real Cursor build; the corrected build must still be rerun on the VPS.
