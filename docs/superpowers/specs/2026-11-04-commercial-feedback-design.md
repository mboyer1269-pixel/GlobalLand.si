# Private commercial feedback — first increment

## Authorization and purpose

The founder approved implementation by a team of the delivered commercial-autonomy analysis. This increment makes incoming commercial interpretations visible to the director, without treating mail transport, model claims or internal tests as sales. It preserves unrestricted choice of markets and business models under the existing mandate. Routine reversible implementation choices below are development proposals, not new founder financial decisions.

## Approach

Extend the existing private responder's final structured summary with an optional strictly validated observation. Keep that observation with the immutable READY decision, then project only allowlisted categories, counts and existing public experiment identifiers into the public planner context. No second classifier call or new external service. Existing responses remain usable when no observation is present or classification is invalid.

Alternative: a separate classification worker would add latency, consumption and replay complexity. A general CRM would exceed the smallest useful change. This increment uses the existing case journal and supervisor serialization.

## Evidence boundaries

- Message interpretation is explicitly unverified. It is never a verified customer, binding order, delivery receipt, payment or profit.
- Known synthetic test identities configured privately are excluded from market signals. Model identification of tests/automation can downgrade or exclude evidence, never upgrade provenance.
- Normal nonfixture incoming messages are unverified inbound, not verified humans. No founder registration per message is required for useful interpreted feedback.
- Experiment association may be unknown or inferred against a bounded allowlist of public mission/site identifiers. Never publish arbitrary message-derived IDs, subjects, names, quotes or model prose. Inference stays visibly distinct from trusted attribution.
- A quoted supporting fragment, if used, stays private and must occur exactly in the original incoming text. An extract proves what the message says, not that it is true.
- Refusals and problems are learning signals, not successes or money. Statements about payment remain claims; Treasury is the sole financial source.
- Duplicate observations and replays must not increase counts or refresh market evidence. Corrections replace/retract the interpretation for one source; they are not new contacts.

## Durable behavior

Use the existing private mail journal as the minimal observation store; no second database/outbox. `PrivateResponder` first stores its normalized observation alongside READY. `Mailbox` stores it in the same journal write that records STARTED or IGNORED and preserves it across terminal/uncertain states. Rebuild the public projection read-only from unique journals. Legacy unclassified records remain unclassified. An observation may be delayed until the private task finishes; this limitation is explicit.

Raw model observation has exact keys `category`, `audience`, `experiment_id`, `evidence`. Categories: UNKNOWN, REQUEST, EXPLICIT_INTEREST, PRICE_QUESTION, REJECTION, CUSTOMER_REPORTED_DELIVERY, DELIVERY_ISSUE, NONCOMMERCIAL. Audience: UNKNOWN, ORDINARY, TEST, AUTOMATED. Evidence is null for UNKNOWN/NONCOMMERCIAL, otherwise exactly `{field,quote}` with field text/extracted_text, literal nonempty quote at most 240 characters. Origins are host-controlled SYNTHETIC, AUTOMATED, INBOUND_UNVERIFIED, UNKNOWN. Attribution in this increment is MODEL_INFERRED or UNATTRIBUTED; trusted route administration is deferred because it is not necessary to deliver useful feedback.

Private config `agentmail.commercial` supports `enabled` (strict bool, default false) and `synthetic_senders` (bounded list of exact private sender email addresses). A host fixture match wins over all model output. Invalid config is unavailable, never silently enabled. Bound the source scan at 2000 journals, each at most 128 KiB; if exceeded mark PARTIAL and do not infer a complete zero or freshness. Bound the public experiment allowlist at 100 existing public mission/site IDs and report truncation. Never allocate arbitrary model IDs into a public map.

Persist observations alongside the immutable READY reply before sending; later projection failure must not cause a second computation or email. Ingestion and projections must recover deterministically from durable private evidence. Old READY cases with no observation remain compatible and must not trigger a new model call.

Storage is host-private, bounded, atomic and rejects symlinks/unsafe files. Invalid/missing/corrupt data produces an explicit unavailable/unknown projection, not a reassuring zero. Public error strings remain fixed and contain no customer data.

Activation is explicit under private AgentMail configuration, disabled by default. Disabled operation must preserve existing behavior without reading correspondence for classification. Configuration absence does not imply zero market demand.

## Director and operational progress

Inject a bounded commercial view into the director's actual context/prompt. Explain its evidence limitations and allow the director to choose a useful action, without a mandated niche or funnel. It must expose new information on the next normal decision; no new scheduling system in this increment.

Keep operational progress semantics for compatibility, but label them as operational. Track absence of newly observed interpreted commercial feedback and absence of verified revenue separately. Completed/failed technical missions and new product files must not reset those independent measures. If reliable commercial tracking is unavailable, show unknown rather than count a false drought. Do not call cash flow or revenue profit.

## Acceptance

1. A source-grounded price question/refusal becomes an unverified interpreted count visible in the next director prompt; no private marker appears in public outputs.
2. Unknown/invalid classification preserves the private reply without fabricating a category; existing tests/legacy responses remain compatible.
3. Synthetic and automated cases cannot become external-demand or revenue evidence; hostile content cannot promote its own provenance.
4. Repeated ingestion, READY replay and recovery after interrupted projection produce one observation and no repeated sending/computation. Revised classification does not add a contact or move its original observation time.
5. An unknown or malicious experiment ID cannot leak into the public view.
6. A technical mission conclusion does not reset the commercial/revenue gap; a commercial interpretation does not change Treasury.
7. Corrupt files, unsafe paths, oversized records and partial failures do not leak content or masquerade as healthy zero activity.
8. Tests inspect the actual controller prompt, not only a helper return. A controlled real-model exercise is distinct from mocked integration and must be labeled synthetic; do not claim actual customer acquisition.

## Subsequent milestones

Thread continuity, proactive wakeups, financial integration, acquisition channels, economic cost attribution and independent workers remain in the AI-employees roadmap. This increment must not claim those capabilities. No unsolicited outreach, spending, bank/account changes, new authority or production deployment is part of local code verification.
