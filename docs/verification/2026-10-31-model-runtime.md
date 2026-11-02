# Model decision and failed-cycle verification — 2026-10-31

Historical record of the 7e4859d candidate. Its JSON-in-JSON transport later failed a real model response; the current native argument correction and latest evidence are recorded in 2026-10-31-native-arguments.md.

Real VPS evidence before this patch: Codex, Claude and Cursor all passed the installed subscription/auth/capability checks at commit 8653e8ab90f49643b1a134d1a6287f26c9d6f1d9. The output explicitly reported inference_performed=false. No productive native-model cycle has yet been demonstrated.

Preflight found that the logical decision schema used a free-form args object, while Codex 0.166.0 defaults to strict Responses output validation. Its immutable upstream core/src/client_common.rs defaults output_schema_strict=true; codex-api/src/common.rs forwards that setting. OpenAI's strict output contract requires closed object properties. MODEL_SCHEMA now transports args_json as a string; it is parsed with duplicate/nonfinite rejection and converted into the unchanged internal args object. Codex's installed schema, Claude's CLI schema and Cursor's prompt schema agree. Arbitrary nested tool arguments and old internal-format decisions remain supported.

Claude result wrappers must report success and is_error=false. Its turn budget is 2, allowing the internal StructuredOutput tool round trip; error_max_turns is never treated as successful work. Tool argument forms are supplied to the planner explicitly. Live inference and exact version behavior still need the manual VPS test.

A failed think previously published a generic blocked state and returned exit success. It now records a private 0600 failure category without raw exception text, publishes CONTROLLER_BLOCKED, and raises a static error. Failed publication preserves the existing Git retry path without replaying a failed model.

Verification:

- Python unittest discovery: 103 tests total, 102 passed, 1 optional Docker smoke skipped locally.
- Node runtime: 8 passed; Node executor: 2 passed. Overall 112 passed, 1 skipped.
- Python compilation, per-script Bash syntax, git diff checks passed.
- 8 model decision regressions cover strict schema structure, shared provider schemas, 3-provider decoding, arbitrary nested args, malformed/duplicate/nonfinite args, wrapper errors, legacy compatibility and structured-output turn budget.
- 4 real-Git failure tests cover blocked failure propagation, private/safe diagnostics, invalid model output and retry after failed blocked-state push without replanning.
- A real-Git integration replaces only authentication/model transport and public HTTP with fixtures: a wire decision becomes durable tasks, WORLD/FETCH execute, product and DONE results are pushed, outbox is acknowledged, and bank remains UNFUNDED. This does not prove a real provider response or a sale.
- Independent review found no material correctness/privacy/regression issues. Documentation was updated to the 2-turn budget.

No server deployment, external model call, paid API call, purchase or funding occurred from this workspace. Install the exact reviewed commit using upgrade_vps.sh, run one manual think then queue, and inspect the actual model turn, published tasks/results and artifacts before enabling recurring think. Keep old release/state/image records for rollback; never roll back a financial balance or delete operation journals.
