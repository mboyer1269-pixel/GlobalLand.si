# Private commercial feedback

Commercial feedback is disabled by default. It interprets incoming correspondence
inside the existing responder call; it does not add a classifier, contact people,
verify customers, collect money, or establish a sales channel. Treasury remains
the only source of verified revenue. Revenue is not profit.

Enable it in the **private** host configuration, never in a public product file:

```json
{"agentmail":{"commercial":{"enabled":true,"synthetic_senders":["fixture@example.invalid"]}}}
```

The existing AgentMail connection and private mail scheduler are still required.
`enabled` must be a Boolean. `synthetic_senders` is an optional list of at most
100 exact email addresses, each at most 254 characters. Invalid settings produce
`UNAVAILABLE`; absence produces `DISABLED`. Configure synthetic senders **before**
any controlled real-model exercise. Such an exercise demonstrates an integration,
never customer acquisition. Deterministic tests mock the external model and mail
transport, and use the real private storage and projection functions.

The optional final summary field `observation` has exactly four keys:

```json
{"category":"PRICE_QUESTION","audience":"ORDINARY","experiment_id":"site:fictional-demo","evidence":{"field":"text","quote":"What is the price?"}}
```

This fictional event is an unverified price question, not a sale. Its quote must
occur literally in the incoming `text` or `extracted_text` field visible to the
responder, and contain 1–240 characters. Categories are `UNKNOWN`, `REQUEST`,
`EXPLICIT_INTEREST`, `PRICE_QUESTION`, `REJECTION`, `CUSTOMER_REPORTED_DELIVERY`,
`DELIVERY_ISSUE`, and `NONCOMMERCIAL`. `UNKNOWN` and `NONCOMMERCIAL` require null
evidence. Audience is `UNKNOWN`, `ORDINARY`, `TEST`, or `AUTOMATED`.
Missing or malformed observations become `UNKNOWN` while an otherwise valid
reply remains valid. There is no classification retry or extra model call.

The host assigns origin `SYNTHETIC`, `AUTOMATED`, `INBOUND_UNVERIFIED`, or `UNKNOWN`.
A configured sender fixture wins over model claims. Model TEST/AUTOMATED labels
can only downgrade provenance. Ordinary inbound mail never proves a human or a
customer. Only grounded commercial interpretations with `INBOUND_UNVERIFIED`
origin count as interpreted feedback. Refusals and reported problems count as
learning signals; neither indicates success, delivery, payment, or profit.

Experiments come from public `work/world/status.json` mission identifiers and
existing `work/products/sites/` directories. Their public references use
`mission:<id>` and `site:<slug>` to prevent collisions. The allowlist contains at
most 100 identifiers and exposes a truncation flag. Unknown model identifiers
become null and are never allocated public map keys. Attribution is
`MODEL_INFERRED` or `UNATTRIBUTED`; trusted attribution administration is deferred.

The normalized private record contains category, audience, experiment_id,
evidence, origin, attribution, provider, and observed_at. It is stored beside
the immutable READY decision in `state/private/fulfillment/<hash>/case.json`.
The mailbox copies it into `state/private/agentmail/<hash>.json` in the same
atomic write as STARTED or IGNORED, retaining it through ACCEPTED, UNKNOWN, and
pre-send retries. READY replay uses that stored interpretation without another
model call or a new observation time. Legacy READY cases remain unclassified.
Interpretation can be delayed until private work finishes.

`commercial.settings(config)` returns configuration state;
`allowed_experiments(root)` returns `ids`, `truncated`, and `available`;
`normalize_observation(raw, message, allowed_experiments, host_origin, provider)`
returns the private normalized record. `project(root, config)` rebuilds the
public view read-only. `progress_snapshot(root, config)` returns private hashed
`sources` and `interpreted_sources` plus availability, for the progress tracker
only. These private identities, quotes, timestamps, sender addresses, and model
prose never enter the director's commercial projection. Its fields are fixed
states, category counts, validated public experiment references, exclusion and
unclassified counts, and an evidence disclaimer.

Projection reads at most 2,000 journals of 128 KiB each. It rejects symlinks,
hardlinks, unsafe files, corrupt records, and source identity mismatches. The
state is `AVAILABLE`, `PARTIAL`, `UNAVAILABLE`, or `DISABLED`. Counts under PARTIAL
describe only valid scanned records and cannot establish complete zero demand or
freshness. Missing private storage is unavailable. Errors contain fixed strings,
never raw correspondence. Publication or projection failure does not initiate a
mail send or model computation.

The next normal director decision receives this view. Existing stall/outcome
counters keep their operational meaning. Separate counters track successful
turns without **new interpreted feedback** and without **new verified revenue**.
Technical mission conclusions and files do not reset either counter. A new
interpretation does not alter Treasury. Existing cumulative revenue establishes
a migration baseline, rather than appearing as a fresh receipt.

`state/private/progress.json` retains every seen private source hash, including
unclassified sources, across unavailable and partial scans. Reclassification,
retraction, replay, a missing record, or its restoration cannot manufacture a
new contact or reset freshness. An incomplete scan exposes an unknown feedback
counter and preserves its prior baseline. The private history limit is 100,000
sources; exceeding it makes tracking unavailable rather than forgetting older
identities. Baselines initialize on a complete scan; retries do not count as
successful turns.

Progress reads are bounded at 16 MiB and reject unsafe links and malformed
history. Lost/corrupt source history stays visibly unavailable across subsequent
turns; it is not silently rebuilt into fresh market evidence. Restore an intact
private history to recover continuity. A revenue gap with lost continuity stays
unknown until a new verified revenue gain establishes a fresh reference.

`state/private/progress.initialized.json` is a fixed, bounded initialization
anchor, not a second observation store. The first successful tracking commit
writes this host-only marker before the history. If the history is subsequently
missing, or a crash interrupted that first write, both gaps remain unknown.
An initialized baseline missing its required source-history fields is corrupt,
not a migration. If **both** the history and its anchor are removed, this local
implementation cannot distinguish that loss from a first installation; restore
both private files together when recovering a host. A valid source identity is
remembered even when its optional interpretation is malformed, so repairing it
cannot refresh feedback. Public progress states are independently allowlisted
when projecting the operational blocker board.

This increment adds no CRM, thread continuity, proactive wakeup, new scheduler,
financial integration, external acquisition channel, independent workers, or
economic cost attribution. Deployment and controlled real-model validation are
separate from local deterministic verification.
