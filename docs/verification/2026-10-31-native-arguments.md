# Native model arguments — 2026-10-31

Real VPS evidence at 7e4859d95b6037dd2f57ff2f385c5abdb8490001: the first planner failed with invalid_provider_structured_output. A single instrumented retry returned exit 0 and 7,915 bytes; strict parsing identified an outer JSON dict, followed by a nested argument JSON error (Expecting ',' delimiter, line 1 column 301). The visible summary proposed testing a browser-only CSV formula-injection scanner and collecting public demand/pricing evidence. This proves a real model response and a concrete proposal, not task execution, a product, or revenue. No new tasks were published.

Cause: the provider schema constrained args_json only as a string. JavaScript inside serialized argument JSON required multiple levels of escaping, and the model emitted an invalid inner document despite valid outer JSON. The invalid response remains private on the VPS; no heuristic JSON repair or partial task publication is used.

Fix: scripts/decision_protocol.py supplies closed native args schemas for every tool and public WORLD operation. EXEC argv is an array of strings, FETCH and WORLD have explicit fields, and truly optional nullable fields are normalized before execution. Dynamic finance requests remain representable through recursive key/value entries with native primitives/arrays and object_entries wrappers. Duplicate keys/nonfinite values are rejected; legitimate business nulls and arbitrary keys are preserved. encode_request is available to programmatic protocol producers. Existing internal/native decisions and well-formed legacy args_json remain readable.

Verification:

- Python: 125 total, 124 passed, 1 optional Docker smoke skipped locally.
- Node runtime 8 passed; executor 2 passed. Overall: 134 passed, 1 skipped.
- Compilation, per-script Bash syntax and git diff checks passed.
- 21 new protocol tests cover all native tool/world variants, strict schema structure, malformed/mixed arguments, required versus optional nulls, recursion, arbitrary finance data and quote-heavy argv fidelity.
- Existing three-provider tests and real-Git decision-to-task/queue-result integration now exercise native arguments.
- Independent review found no material issue; 30 focused tests, standards schema validation and 100 schema-valid arbitrary finance round trips passed.

Limits: no provider/model call from this workspace; live provider-specific schema acceptance and a successful productive cycle still require the exact-commit VPS test. The provider image/auth volumes do not change. Install with upgrade_vps.sh at the reviewed SHA, then one manual think and queue. Inspect the published decision/tasks/results/artifacts before scheduling recurring think. No account funding, purchase, paid API fallback or revenue is claimed.
