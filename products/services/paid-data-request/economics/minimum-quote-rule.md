# Minimum-quote rule (reusable, marketplace fixed-price data jobs)

Status: draft, built on UNVERIFIED fee hypothesis H1 (10% or 5-unit minimum). Re-derive once official fees are read.

1. Fee floor: below P = m/f (5/0.10 = 50 currency units under H1) the minimum fee dominates (GBP20 -> 25% effective). Do not quote below 50 units unless the official minimum is lower.
2. Quote Q only if (Q - fee(Q) - withdrawal_cost) / total_hours >= the founder's reservation rate, where total_hours counts acquisition, operator approval/submission, delivery, revisions (assume at least one) and administration.
3. Only file-in/file-out tasks on non-personal data with a deterministic acceptance test we have already demonstrated (keyed join, diff, schema/encoding checks).
4. Exclude scope needing domain authority we lack (e.g. Pantone assignment), authenticated admin access, scraping or personal data.
5. Prefer <15 existing bids and <6h age; no win rate is assumed.
6. Keep currencies separate; convert only with a dated rate source.
7. Disclose AI-assisted production; never bid without a founder-authorised identity and verified platform AI policy.
