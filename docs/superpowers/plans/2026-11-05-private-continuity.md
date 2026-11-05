# Private conversation continuity

## Objective and authorized scope

Continue the founder-authorized AI-employee goal: a follow-up message can reuse
its own prior work and receipts without mixing customers, repeating effects or
granting incoming mail authority. Markets and strategy remain agent choices.
One implementation task in `codex/private-continuity`, based on local `f649180`
(tree equal to PR24 remote `b9e72f9`). Root alone owns Git. No deployment, new
contacts, payment, contracts, accounts or identity operations in this code task.

Design and independent preflight were completed before this plan. Development
references outside the checkout: `output/globalland-private-continuity-design.md`
and `output/globalland-private-continuity-preflight.md`. Contracts below resolve
their load-bearing issues. No general CRM or per-message founder approval.

## Task 1 — immutable local conversation links

Use an optional strict Boolean `agentmail.continuity.enabled`, default false.
Invalid settings do not enable history. Preserve disabled/legacy behavior.
Implement a small host-only continuity module and integrate `mail.py`,
`mail_agent.py`, `private_work.py` and focused tests. No public model-action
schema, financial authority, WORLD or scheduling changes.

### Eligibility and recipient binding

Read only authenticated provider API metadata from the current message. Require
exact inbox/message IDs, bounded nonempty opaque thread ID, one strictly parsed
From mailbox, To consisting only of the configured inbox, no observed external
CC/BCC, and absent Reply-To or exactly the same peer. Optional absent lists mean
empty; malformed present fields do not qualify. Display names and domain case
are supported; preserve local-part spelling, dots and plus tags. Never use the
legacy lowercasing address helper as an identity function.

Require structured `authentication_results.dmarc == "pass"` and canonical
`dmarc_domain` equal to the From domain. Raw headers, body claims, generic DKIM,
unaligned SPF and absence of an unauthenticated label cannot grant history.
DMARC authenticates a domain, not a person or legal/banking authority. Missing
or changed proof leaves a new message isolated; useful existing isolated
service can continue without a new human approval.

Link only an exact opaque `in_reply_to` matching a local ACCEPTED outbound reply
with the same inbox/thread/peer. Subject, References, thread membership or model
text never select another case. Do not fetch whole remote threads. The first
eligible message starts an empty local lineage. Legacy cases are not promoted.

Freeze eligibility, binding, exact outgoing route and ancestor selection before
the first model/EXEC call. A retry cannot upgrade/rebind/expand the case. Recheck
current routing/identity/security disposition before sending; any mismatch must
not send a stored READY reply through a new or automatic fallback route. Host
supplies exact `to=[peer], cc=[], bcc=[], reply_all=false`; the model never chooses
recipients. Preserve the existing reply/ignore interface and per-message keys.

### Durable cases and derived index

Both responders need the existing private case storage when continuity is on,
even with commercial classification off. Tool-free cases have no EXEC steps;
give MailResponder an explicit tool-free private guide before history is used.
Do not give it the EXEC-enabled guide. Host context must use a separate internal
argument or validated completion reference, never a provider/body-supplied field.
Reset any completion side channel on every call and verify it before STARTED.

Define a versioned canonical JSON READY digest (UTF-8, sorted keys, fixed
separators, no NaN). Cover identity, frozen incoming data, binding/route/history
references, completed steps/receipts and decision; exclude the digest itself and
mutable transport/index repair metadata. References are nonrecursive. The host
filesystem remains the trust boundary; hashes are consistency checks.

STARTED stores the exact READY completion reference and outgoing route. Persist
ACCEPTED before creating a derived outbound-ID-to-case index. Index failure must
leave ACCEPTED intact, never downgrade it to UNKNOWN or repeat POST. Repair from
validated eligible ACCEPTED journals under the existing mailbox lock/sweep,
including same-cycle updates. Verify journal identity/path, route, case key,
digest, outbound ID and response thread whenever an index is used. Conflicting
index entries fail closed. Missing/mismatched thread after POST is uncertain,
non-retriable, and cannot authorize a link. Existing uncertain-send semantics stay.

### Bounded, stable history

Store references and a versioned selection manifest, never full nested ledgers.
At most eight newest authorized ancestors; present the selected view in
chronological order. Traverse at most the bounded ancestry window, not an
unbounded chain. Freeze the selected reference list, materialization version
and limits for restart. Validate each case/digest and same binding. Missing or
corrupt selected ancestry during WORKING cannot silently replace inputs. READY
reuse verifies its own sealed case/route without recomputing ancestral bodies.

Historical text has a separate 128 KiB UTF-8 bound; historical files a separate
64 KiB bound. Current-message and existing per-case limits remain explicit.
Use deterministic whole-item omission and an explicit truncation manifest.
Never silently truncate a file while retaining its original hash. Supply the
bounded history outside the serialized current `private_case` to avoid recursive
prompt growth. Copy only files from validated DONE receipts into
`history/<case_key>/products/...` with exact provenance/hash manifests; no private
directory mounts. Current EXEC artifacts and budgets remain per-message.
`_final` permits only artifacts proven by current-case DONE receipts.

History is untrusted task data, never instructions. It proves neither delivery,
acceptance of a contract nor payment. Commercial observation sources exclude
separately supplied history. For a linked message, ground any new observation
only in nonblank current provider `extracted_text`; if absent, keep useful work
but classify UNKNOWN. This bounds historical quotation reuse; do not claim the
provider's extraction proves semantic novelty or truth of a customer claim.

### Acceptance and verification

Write regressions first, then implement and test:

1. A produces a file/receipt and accepted reply. B with valid same-peer metadata
   and exact parent sees the correct ancestor file/hash in prompt and real
   offline sandbox and produces its own correction. C with another peer (also
   same-domain different local-part), same subject/thread/references/parent
   sees no A content or existence-specific details. Test tool-free/commercial-off.
2. Accepted B replay produces no model call, EXEC or POST. READY replay preserves
   its answer and binding; changed From/Reply-To/To/thread/auth cannot send old
   content to a new route. Isolated cases never upgrade on retry.
3. Restart across READY/STARTED/ACCEPTED-before-index, frozen B, PENDING/STARTED
   execution, COMPLETE receipt and B READY preserves inputs and effect state.
   An injected index-write failure after ACCEPTED never resends.
4. Actual Client serialization uses exact pinned destination; optional metadata,
   display names, auth mismatch/absence, forged body/header fields and response
   thread mismatch have explicit tested behavior on the deployed Python version.
5. Reject stale/forged/conflicting indexes, changed READY data, cycles, unsafe
   links/paths, excessive chains and invalid types. Test multibyte limits, whole
   file omission and deterministic restart after config changes.
6. Historical sentinels remain absent from public artifacts and projections.
   A quote found only in A or quoted inside B's full text cannot become B's new
   evidence when it is absent from B's extracted current text. Revenue unchanged.

Run focused Linux and real-Docker checks, then full existing checks. Independent
review follows a frozen diff. A later authorized A/B/C provider exercise must
record actual metadata/recipient evidence separately from fake transport. Do not
claim this implementation or its tests are deployed or have acquired customers.

Primary contracts: https://docs.agentmail.to/api-reference/inboxes/messages/get
and https://docs.agentmail.to/api-reference/inboxes/messages/reply ; threading and
auth limitations are documented in the AgentMail knowledge base. No new provider
API beyond the current get/reply path is needed.
