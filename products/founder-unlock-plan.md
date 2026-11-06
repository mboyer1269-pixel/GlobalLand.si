# Founder unlock plan (updated 2026-11-06, written by autonomous AI agents)

Treasury UNFUNDED, verified revenue 0. Commercial feedback: 0 classified events, 3 unclassified sources (unknown, not zero demand).
Binding constraint: no authorized route can collect money (commercial_paths.collection NOT_IMPLEMENTED, PUBLISH_ACTOR NOT_CONFIGURED). More inventory or page work cannot produce verified revenue until one founder step below is taken.

## Ranked single steps (do #1 OR #2; either is enough to start)
1. Option A, Apify credential (blocker NO-APIFY-ACCESS): valid enabled Apify config + private credential file mode 0600. Unlocks private builds of three tested Actors: products/actors/rss-reader (22/22 offline tests), link-checker (21/21), domain-availability (22/22, RDAP-only, no contact data). Store copy ready (products/distribution/*-store-copy.json). Platform-managed pay-per-event billing; no separate checkout. Incumbents showed 29-53 users_30d; our demand is unverified. Kill: fewer than 3 external users within 14 days of listing.
2. Option B, Gumroad seller account (blocker SERVICE-PAYMENT-COLLECTION; products/research/platform-managed-settlement-fit.json, observed 2026-11-05): founder creates/designates a GlobalLand seller account in the founder's name, adds a CAD bank account (Stripe KYC on founder), and shares only the public profile URL. Fees documented as 10% + USD 0.50 per direct sale; USD 100 payout minimum, 7-day hold; Gumroad acts as merchant of record for sales tax. Gumroad Discover is NOT usable for a first buyer (requires prior genuine sales and USD 100 balance: products/research/gumroad-first-buyer-access.json), so buyers must arrive via direct links from our own pages. Agents then prepare one product package for independent review; the founder uploads it.
   Either option still needs a payout attestation or reconciliation path before Treasury can verify revenue.
3. Bounty/challenge eligibility (BOUNTY-SUBMISSION-ELIGIBILITY): parked; needs a designated participant identity and acceptance of specific rules. Lowest priority.

## Done (no founder action needed)
- Cloudflare hosting works. Live, free, no checkout:
  - https://globalland-invoice-preflight.global-land.workers.dev/ (CSV diagnostic; observation ends 2026-11-19T01:30:37Z)
  - https://globalland-shopify-catalogue-example.global-land.workers.dev/ (Shopify variant/image CSV worked example, downloadable transform + verifier; observation ends 2026-11-19T21:30:49Z)
  - https://globalland-welfare-tender-brief.global-land.workers.dev/ (UK welfare-advice tender brief; observation ends 2026-11-20; must be retired after 2026-12-04T17:00Z, mission WELFARE-SITE-RETIRE; official notice re-checked unchanged 2026-11-06)
- Plain-text email intake with case-local offline fulfillment (configured; no external customer delivery observed yet).
- Unpublished: products/services/shopify-browser-delivery/ (browser port, 20/20 parity vs Python under Node; real-browser check still needed before any review).

## What agents will do meanwhile
No new inventory, no credential probes, no further search/metadata work on live pages. Judge each experiment at its deadline from aggregate feedback only; retire the welfare page after its deadline. Resume building only after a collection route or a classified request exists.
