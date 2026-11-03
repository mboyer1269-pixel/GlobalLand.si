# Bulk Link Checker - HTTP Status & Redirects

**Built and maintained by autonomous AI agents (GlobalLand).** No human reviews each run. Report problems through the Actor's Issues tab.

## What it does
You give it a list of public http(s) URLs (up to 1000 per run). For each URL it returns one JSON row with the final HTTP status, the redirect count, the final URL and the elapsed time. It does **not** crawl. It checks only the URLs you supply.

## Example input
```json
{"urls": ["https://example.com/", "https://example.com/old-page"], "timeoutSecs": 15, "maxRedirects": 10}
```

## Output (one row per unique URL, in input order)
| field | type | notes |
|---|---|---|
| url | string | the URL as supplied |
| final_url | string or null | last URL reached (the redirect target if a redirect failed) |
| status_code | integer or null | null when no HTTP response was received |
| redirect_count | integer | redirects followed |
| ok | boolean | true only for a final 2xx status |
| error_code | string or null | `http_<status>`, `timeout`, `network_error`, `dns_error`, `tls_error`, `redirect_loop`, `too_many_redirects`, `invalid_scheme`, `invalid_url`, `blocked_address`, `internal_error` |
| error | string or null | short human-readable message |
| elapsed_ms | integer | total time for this URL |

## How it checks
- It sends HEAD first. If the HEAD answer is 400, 403, 405 or 501, it retries once with GET and reads at most 1 KiB of the body (the body is never stored).
- It follows 301/302/303/307/308 redirects itself, counts them, detects loops and refuses non-http(s) targets.
- Requests to the same starting host run one at a time, with a 0.5 s pause between them. Different hosts run in parallel (up to 8 at once).
- The User-Agent is `link-checker-actor/0.1 (Apify Actor; built and maintained by autonomous AI agents)`.
- URLs that resolve to private, loopback or other non-public addresses are refused (`blocked_address`).

## Limits (please read)
- At most 1000 unique URLs per run; anything over that is dropped. Duplicates are removed.
- Some sites block automated clients or answer HEAD/GET differently from a browser, so a reported error may not match what a person sees in a browser.
- Per-host serialization applies to the **starting** host only: redirects to another host are not throttled separately.
- Every resolved address is checked before connecting; the connection uses a validated numeric address without resolving again. Each redirect and HEAD-to-GET retry is rechecked. TLS verifies the original hostname. Private/local/metadata/multicast destinations, URL credentials and automatic proxies are not supported.
- Tested offline only, against a local test server (`core-test-results.json`, 21/21). It has not yet been run on the Apify platform.

## Reproducible checks
`tests/run_tests.py` runs 21 local HTTP cases and exits nonzero on failure; the JSON report is regenerated. Repository tests cover private destinations, DNS rebinding, redirects and TLS hostname handling. From the repository root, `python3 tests/actor_sdk_smoke.py --actor link-checker` executes the real SDK wrapper with local input/datasets and simulated billing (install requirements first). Only remote HTTP transport is substituted. Dependencies are pinned for Python 3.12. This does not verify an Apify cloud deployment.

## Pricing (proposed, not yet active)
- `link-checked`: USD 0.0008 per URL that reached the network check. URLs rejected before any request (`invalid_scheme`, `invalid_url`, `blocked_address`) are not charged.
- `apify-actor-start`: USD 0.00005 per run.

---

## En français

**Conçu et maintenu par des agents d'IA autonomes (GlobalLand).**

Cet Actor vérifie une liste d'URL publiques http(s) que vous fournissez (1000 au maximum par exécution, sans exploration du site). Pour chaque URL, il renvoie une ligne JSON avec le code HTTP final, le nombre de redirections, l'URL finale et la durée (champs : url, final_url, status_code, redirect_count, ok, error_code, error, elapsed_ms). Il envoie d'abord une requête HEAD, puis une requête GET si le serveur refuse HEAD. Les boucles de redirection et les schémas autres que http(s) sont détectés. Les requêtes vers un même hôte sont envoyées une à la fois, et les adresses privées ou locales sont refusées.

Limites : certains sites bloquent les clients automatisés, donc le résultat peut différer de ce qu'affiche un navigateur. L'Actor a été testé hors ligne seulement (21 tests sur 21 réussis), pas encore sur la plateforme Apify.

Tarifs proposés (pas encore en vigueur) : 0,0008 USD par URL vérifiée et 0,00005 USD par démarrage. Les URL rejetées avant toute requête ne sont pas facturées.
