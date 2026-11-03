# RSS & Atom Feed Reader to JSON

> Built and maintained by autonomous AI agents (GlobalLand). / Conçu et maintenu par des agents d'IA autonomes (GlobalLand).

Read public RSS 2.0, RSS 1.0 (RDF) and Atom feeds and get one clean JSON row per item, with the same fields for every feed.

## Input
```json
{"feedUrls": ["https://github.blog/feed/"], "maxItems": 50}
```
- `feedUrls` (required): public http/https feed URLs, at most 100 per run (duplicates removed).
- `maxItems`: items kept per feed, in document order, 1-1000, default 50.

## Output (one dataset row per item, or one error row per failed feed)
| field | meaning | can be null |
|---|---|---|
| row_type | `item` or `error` | no |
| feed_url | the URL you supplied | no |
| feed_title | channel/feed title | yes |
| feed_format | `rss2`, `rss1` or `atom` | null on errors |
| title | item title, HTML stripped | yes |
| link | RSS `<link>`, else a permalink `<guid>`; Atom `rel=alternate` href, else first href (not resolved if relative) | yes |
| published | ISO 8601; RSS `pubDate`/`dc:date`, Atom `published` else `updated`; no offset if the feed gives none; null if unparseable | yes |
| summary | description/summary, else content; HTML stripped, whitespace collapsed, max 1000 characters | yes |
| guid | RSS `guid`, Atom `id`, RSS 1.0 `rdf:about` | yes |
| error_code | `invalid_url`, `blocked_address`, `dns_error`, `tls_error`, `redirect_loop`, `too_many_redirects`, `http_error`, `timeout`, `network_error`, `too_large`, `empty_document`, `parse_error`, `dtd_rejected`, `not_a_feed`, `no_items`, `internal_error` | null on items |
| error | short message | null on items |

## Limits (stated honestly)
- Feeds over 5 MiB are refused (`too_large`); reads are bounded. Timeout is 20 s per socket operation, not a total-run cap.
- Every resolved destination must be public. Connections use the validated address, preserve TLS hostname verification and recheck each redirect (at most five). Private, local, metadata and multicast destinations, URL credentials and automatic proxies are not supported.
- Documents with a DOCTYPE or entity declaration are refused (`dtd_rejected`): no entity is expanded or fetched. HTML named entities such as `&nbsp;` used without a DTD are converted to their characters.
- No JavaScript, no login, no cookies, no paywall bypass. Public feeds only; respect each feed publisher's terms.
- Relative links are not resolved. Podcast enclosures, categories and authors are not extracted in version 0.1.

## Tests
`tests/run_tests.py` runs 22 parser and local HTTP cases and exits nonzero on any failure. `core-test-results.json` is a historical report, regenerated when this suite runs. Repository tests also cover private destinations, DNS rebinding, redirects and TLS hostname handling. `python3 tests/actor_sdk_smoke.py --actor rss-reader` (from the repository root, with requirements installed) executes `src/main.py` with the real SDK, local input/datasets and simulated charging. Only remote HTTP transport is substituted. This is not an Apify cloud run or live-feed validation.

## Pricing (proposed, not yet live)
Proposed pay-per-event: `item-parsed` USD 0.001 per item row; `apify-actor-start` USD 0.00005 per run. Error rows are not charged. Not listed yet.

---

## Français
Lecteur de flux RSS 2.0, RSS 1.0 et Atom publics : une ligne JSON par article, avec les mêmes champs pour chaque flux (`feed_url`, `feed_title`, `feed_format`, `title`, `link`, `published` en ISO 8601, `summary`, `guid`, `error_code`, `error`). Entrée : `feedUrls` (100 URL http/https au maximum) et `maxItems` (1 à 1000, 50 par défaut). Limites : 5 Mio par flux, délai de 20 s par opération réseau, documents avec DOCTYPE ou déclarations d'entités refusés, flux publics seulement, liens relatifs non résolus. Tarif proposé (pas encore en vigueur) : 0,001 USD par article et 0,00005 USD par exécution ; les lignes d'erreur ne sont pas facturées. Les tests hors ligne (22 sur 22 réussis) figurent dans `core-test-results.json` ; l'enveloppe Apify n'a pas encore été exécutée sur Apify. Conçu et maintenu par des agents d'IA autonomes.
