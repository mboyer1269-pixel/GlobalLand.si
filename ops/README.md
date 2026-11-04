# Operator publication helper

`publish_welfare_brief.py` records the exact one-off publication operation audited on 4 November 2026. It targets `/opt/globalland`, the dedicated `global-land` Workers subdomain and a pinned content digest. It is not a generic publisher or a scheduled job.

On the Linux host, with the installed controller and existing private configuration:

```sh
python3 ops/publish_welfare_brief.py inspect
python3 ops/publish_welfare_brief.py publish
```

Run from a checkout containing this file, as the existing host administrator. The operator copy installed during this audit lives at `/opt/globalland/state/private/publish-contact-site.py`. A repository merge does not install or schedule the helper automatically.

`inspect` verifies the account/subdomain and reports whether a matching review exists. Its successful exit alone does **not** mean publication is authorized or complete. `publish` also requires the existing exact-digest review and checks the world/treasury through the installed executor. Both Codex and Claude are treated as content authors for this page. This helper never creates a founder review or relaxes the review policy.

The supervisor lock serializes the operation with normal cycles. A private request file binds this digest to one task ID. Re-running the helper reuses that request and the supervisor journal, rather than issuing another deployment. Success requires all three: task `DONE`, site `ONLINE_VERIFIED`, and journal `PUBLISHED` (the public Git receipt exists). A pending receipt remains pending on replay, even when the executor no longer returns its transient `publication` field.

Do not delete or edit the request/journal to force a retry after an uncertain result. Inspect and reconcile the existing operation first. A changed page requires fresh review and a separately reviewed operation. Re-entry of a completed operation proves recovery/idempotency, not fresh site health; a new read-only HTTP check is needed to assess later availability.

Regression tests are offline and do not contact Cloudflare:

```sh
python3 -m unittest discover -s tests -p 'test_site_operation.py'
```
