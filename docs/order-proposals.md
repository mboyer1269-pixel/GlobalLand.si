# Private administrative product proposals

This bridge turns a saved customer request into a versioned product proposal and an administrative order. It prepares payment instructions without sending them. It does not yet give agents a structured proposal output, automatic contract acceptance, or automatic product delivery. Markets, product types and prices remain open; no marketplace is required.

Run only on the Linux host as its existing administrator after this code is installed. No installation is implied by this document. Inputs and outputs belong in `state/private`, mode `0600`, under private directories. Never paste customer records into public tasks or repository files. The examples below contain placeholders and are not production requests.

## 1. Prepare the product proposal

Use an existing saved READY case. Its completion reference is `{version:1, case_key, ready_digest}` from the private mail record or continuity completion. The source must remain eligible against the **current** `control/config.json`: matching inbox/address, authenticated single sender, no holds/automatic messages, and no configured synthetic sender. The same checks apply again at acceptance and instruction preparation. An exact excerpt documents the source of demand; it does not prove a sale.

Prepare a private request:

```json
{
  "completion": {"version": 1, "case_key": "<saved-case-sha256>", "ready_digest": "<saved-ready-sha256>"},
  "demand_excerpt": "<exact excerpt from current incoming text>",
  "terms": {
    "version": 1,
    "product_id": "reusable-checklist",
    "product_version": "1.0",
    "offer_version": 1,
    "title": "Reusable checklist",
    "scope": "One copy of the existing product.",
    "exclusions": "No custom development or ongoing service.",
    "license": "<actual use rights offered>",
    "support": "<actual bounded support terms>",
    "amount_cents": 1900,
    "currency": "CAD",
    "delivery": {
      "mode": "MANUAL_ARTIFACT",
      "artifact_path": "products/checklist.zip",
      "artifact_sha256": "<sha256 of the actual file>"
    }
  }
}
```

The integer amount is the complete agreed total for the stated scope. No tax, exchange-rate, quantity, subscription, or fee calculation is inferred. The artifact must actually exist under `products/`, be an independent regular file with safe permissions, and match the digest. Text and binary files are supported as **evidence**, with the existing per-product output bound of 1 MiB. No contents are included in the payment export. `MANUAL_ARTIFACT` means an operator must arrange and perform delivery; this software supplies no ZIP attachment, private download link, executable distribution, or delivery entitlement. The filesystem evidence check is not a review of product quality or licensing.

The 1 MiB evidence bound fits small documents and archives. A packaged Windows utility may exceed it; support for a larger verified artifact and its delivery remains separate work. This bridge does not make such an application ready for sale or autonomous delivery.

```sh
python3 /opt/globalland/control/orders_admin.py propose --request /opt/globalland/state/private/proposal-request.json
```

The result includes `proposal_id`, `order_id`, `terms_sha256` and `commercial_status: DRAFT`. Preserve those identifiers privately. The private snapshot is saved under `state/private/order-proposals/`; the existing order register stores its digest and source. No payment instructions are available for a draft.

The product ID identifies the reusable product; product version identifies the artifact release; offer version identifies this proposal's commercial revision. An exact retry returns the same order. Changed terms under the same source/product/offer version are refused. To revise the price or terms, increment `offer_version`; review and communicate that exact new version. A new order for another purchase requires a separate customer purchase source. Creating a draft does not transmit an offer.

## 2. Review and record acceptance

The operator must verify that the buyer received and explicitly accepted these exact terms. A transport `ACCEPTED` receipt, interest, a price question, a classifier label, or a paid claim is insufficient. The machine verifies evidence consistency; the explicit administrative assertion remains the operator's interpretation of customer assent.

Reference a **different** saved incoming READY case in the same authenticated inbox/thread/sender binding:

```json
{
  "proposal_id": "<propose result>",
  "order_id": "<propose result>",
  "terms_sha256": "<propose result>",
  "completion": {"version": 1, "case_key": "<acceptance-case-sha256>", "ready_digest": "<acceptance-ready-sha256>"},
  "acceptance_excerpt": "<exact acceptance excerpt in current incoming text>",
  "attestation": "ADMIN_REVIEWED_EXACT_TERMS"
}
```

```sh
python3 /opt/globalland/control/orders_admin.py accept-proposal --request /opt/globalland/state/private/accept-proposal-request.json
```

The order becomes `ACCEPTED`, still `UNPAID`. Exact retries are safe. Changed source evidence is refused, and one incoming acceptance source cannot accept two orders or offer revisions. Acceptance evidence is stored separately under `state/private/order-acceptances/`. Product changes since proposal preparation prevent acceptance and instruction export; prepare the new product/offer version deliberately.

## 3. Prepare current payment instructions

```json
{
  "proposal_id": "<propose result>",
  "order_id": "<propose result>",
  "output": "/opt/globalland/state/private/payment-instructions-001.json"
}
```

```sh
python3 /opt/globalland/control/orders_admin.py instructions --request /opt/globalland/state/private/instructions-request.json
```

Only a matching accepted, unpaid CAD order and a ready configured route produce instructions. The output must be a **new** private file; existing files are never overwritten. Its payment reference is the existing opaque order ID. The CLI stdout remains sanitized. The exact requested order is selected even if newer drafts push it outside the normal ten-order mail context window; other conversations remain isolated.

The file is a preparation snapshot, not a message, payment, delivery receipt or bank verification. Review current order state immediately before use. Re-run into a new private file after any relevant change. A customer payment claim or confirmed deposit suppresses further payment instructions. No automatic sender consumes these files, and the existing mail send guard still rejects cached responses built against stale payment context.

## 4. Settle through the existing founder path

Use the existing [Interac order procedure](INTERAC-COMMANDES.md) to record a customer claim, then separately confirm an actually observed founder bank deposit, allocate it, and explicitly post it. This bridge changes none of those authorities. It never automatically confirms the initial funding, credits revenue, or treats a customer screenshot/notification as a deposit.

Evidence is persisted before the corresponding ledger mutation. Publication uses a private lock, atomic replacement of a new snapshot, and directory fsync. A crash before the ledger write can be retried with the same request; a crash after it reuses the same immutable source. Do not delete snapshots or change requests to force replay. A corrupt/missing source or snapshot requires private investigation.

## Local verification

From the repository root, `python3 -B -m unittest discover -s tests -p test_order_proposals.py -v` runs only fictional cases in a temporary directory, including one complete proposal → administrative acceptance → instructions → customer claim → founder confirmation → allocation → posting flow. Posting twice credits 1900 fixture cents once, while initial funding stays unverified. The test does not use production paths, contact a bank/provider, or send mail.
