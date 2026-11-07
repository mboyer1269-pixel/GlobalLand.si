# Operator handoff: first Interac service order (administrative)

Status: PREPARED, NOT EXECUTED. No order, customer, payment or receipt exists. Produced by ACQUISITION (autonomous AI agent) for the host operator/founder.

## Basis (docs/INTERAC-COMMANDES.md, read via TASK-179408556112)
- Order creation and acceptance are administrative; models cannot conclude contracts or attest deposits.
- Commands run as the service admin with private JSON files under /opt/globalland/state/private/ (never in argv, never published).
- case_key comes from host message metadata (order_context.case_key), never from agents or customer text.
- Client declaration = CLAIMED_UNVERIFIED; only founder-observed deposit + allocate + post yields founder_attested revenue.

## Trigger (all required)
1. A real inbound email in the private cycle asking for the welfare follow-on brief, from a UK welfare-advice provider, before 2026-12-04T17:00Z.
2. Scope confirmed in writing in the same thread against terms v1 (below).
3. Operator decides to accept. Agents never accept.

## Terms
File: products/services/payment-handoff/terms-welfare-followon-v1.md
terms_sha256: 8da570ec00daaead3172576d80a5dfd535b0f6c4496ec6c15d0f154d5ff1f64a
Operator copies these exact bytes to private storage; any edit changes the hash and needs a new version.

## Command sequence (placeholders in angle brackets; fill privately)
1. status  -> confirm state READY_FOR_INSTRUCTIONS.
2. create  -> {"case_key": <from host for the thread>, "amount_cents": 4900, "currency": "CAD", "terms_sha256": "8da570ec00daaead3172576d80a5dfd535b0f6c4496ec6c15d0f154d5ff1f64a", "source_id": <id of the inbound message>}
3. accept  -> {"order_id": <host-issued>, "acceptance_source_id": <id of the customer message confirming terms v1>}
   The private cycle may then show payment instructions in that case only.
4. claim (optional, if the customer says they paid) -> {"order_id", "source_id", "amount_cents": 4900, "currency": "CAD"}
5. confirm -> founder observes the Wealthsimple deposit: {"account_alias", "reference", "amount_cents": 4900, "currency": "CAD", "observed_at", "evidence_sha256", "attestation": "FOUNDER_OBSERVED_BANK_DEPOSIT"}
6. allocate -> {"deposit_id", "order_id"}
7. post -> {"deposit_id", "attestation": "FOUNDER_OBSERVED_BANK_DEPOSIT"}

## Acceptance check
Pass only if the public projection then shows treasury founder_attested_revenue_cents increased by 4900 and order_payments counts show one bank-confirmed deposit allocated, with no customer data published. Anything less (claim only, deposit not posted) is not revenue.

## Unresolved prerequisites
- No eligible inbound request is observed (commercial_feedback: 0 classified, 3 unclassified = unknown; last cycle processed 0, skipped 6).
- order_payments.orders_count is UNAVAILABLE (ORDER_REGISTER_UNAVAILABLE) in the public projection, so creation is unobserved.
- Whether the private responder presents terms v1 / quotes CAD 49 is unverified; the operator must confirm scope manually.
- Live welfare page labels CAD 49 an unvalidated hypothesis; it is not changed by this handoff.
- Apify path (NO-APIFY-ACCESS) is a separate credential dependency.
