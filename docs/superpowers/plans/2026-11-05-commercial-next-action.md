# Commercial next action

## Objective and authority

Continue the founder-authorized AI-employee implementation goal after PR23. Agents retain the choice of markets, platforms and tactics. Make their existing commercial options legible and connect interpreted feedback to a useful next decision. No new spending, contact channel, checkout, authority or scheduler is implied.

Design source: local development report `output/globalland-next-commercial-increment.md` (outside this checkout). Branch `codex/commercial-next-action`, initially based on local `5e76752`, whose tree equals PR23 remote `9f2629d`. Root owns staging and commits. One implementation task; independent scoped review follows.

## Task 1: Paths and decision guide

Implement a pure bounded `commercial_paths(capabilities, bank_snapshot)` in tools.py. Publish the same projection in STATUS and Controller.context. Derive fixed states/messages only from known capability states and treasury state; never copy arbitrary config, private mail or credentials. Research, offline building, public publication, marketplace listing, private incoming correspondence/fulfillment, outgoing acquisition, collection and settlement must be distinguished. Configured prerequisites do not establish working authentication or remote success. No generic outgoing acquisition or checkout operation exists; a finance executable alone cannot establish either. UNFUNDED still permits useful available work. HALTED/EXTINCT behavior remains authoritative. Unknown costs must remain unknown, not free.

Add a concise public-tick decision guide: consider feedback availability/provenance and attribution uncertainty; explain which observed fact affects the next step; choose an executable experiment or improvement with existing tools; reuse stable precise blockers when a needed capability is absent; continue independent useful work. Do not mandate an action type, funnel, niche, automatic pivot or human approval per action. Do not reject broker turns with final actions=[] after real broker effects. Keep this guide out of private correspondence.

Clarify progress.ALERT/DROUGHT prose: operational mission closure/files are not commercial success. Preserve counters and runtime enforcement. No WORLD, Treasury, Gateway, provider schema, scheduling or financial authority changes.

## Acceptance

- Tests with UNFUNDED and absent finance preserve feasible research/build/publication prerequisites while collection is explicitly unimplemented.
- A dummy executable finance adapter changes only existing SPEND/RECONCILE prerequisites, never makes checkout or revenue verified.
- STATUS and director context share the same bounded projection; arbitrary sentinel config/private strings cannot appear. New helper does no I/O or network.
- Actual captured public tick prompt combines current commercial feedback, path availability and decision guide. Partial/unavailable feedback is not zero demand. Tests establish wiring only, not model intelligence.
- Public decision guide is absent from private prompts; broker-completed actions=[] behavior still passes existing tests.
- Existing PR23 evidence, privacy, replay, legacy and corruption tests remain passing.
- After review, a separate controlled actual-model scenario should demonstrate useful work with a receipt in an isolated fixture. Label synthetic; no sale or acquisition claim from this test. Record failure honestly if useful action is not observed.

## Verification and scope

Preflight ruling: `PUBLISH_ACTOR=CONFIGURED_UNVERIFIED` does not establish permission for public listing; current capability data does not expose `apify.allow_public`. Represent this permission as unknown/subject to the existing host gate. No new approval flow. Generic checkout being absent does not rule out platform-managed monetization outside the implemented path.

Write meaningful regressions before changes, run focused tests then Linux full suite; independent reviewer checks changed behavior and preservation of autonomy. Report code readiness separately from installation, actual model behavior and market outcomes. Actual collection/channel connection and customer continuity remain goal milestones, not achievements of this patch.

Deferred coherence observation: existing tool-free MailResponder inherits Controller.plan's default public TOOL_GUIDE. Do not route this new public-tick guide through shared plan(); assess that older issue separately instead of broadening this task silently.
