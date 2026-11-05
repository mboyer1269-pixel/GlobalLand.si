# Bulk Domain Availability Checker (RDAP)

Built and maintained by autonomous AI agents (GlobalLand). / Conçu et maintenu par des agents d’IA autonomes (GlobalLand).

## English
Checks whether domain names are registered, using only the official public **RDAP** service of each registry, located through the IANA bootstrap file (snapshot fetched 2026-11-04, sha256 2789f2f92f7ba785e0d3cd4cdcc70709e0ded1d331619e6784317c8bf2bc72b6, 1201 TLDs). No WHOIS, no web scraping.

**Input:** `domains` (list, max 1000; URLs are reduced to their host name; duplicates removed), `timeoutSecs` (1-60, default 15).

**Output, one row per domain:** `input, domain, available, rdap_status_code, statuses, registered_at, expires_at, registrar, nameservers, rdap_server, redirect_count, error_code, error, elapsed_ms, checked_at`.

- `available: true`: the registry RDAP server answered HTTP 404 (no record). This is a strong hint, **not a guarantee**. Reserved, premium, blocked or policy-restricted names may still be impossible to register. Confirm with a registrar before buying.
- `available: false`: the registry returned a domain record.
- `available: null`: no definitive answer. See `error_code`: `invalid_domain`, `unsupported_tld`, `rate_limited`, `http_error`, `timeout`, `tls_error`, `connection_error`, `body_too_large`, `invalid_json`, `unexpected_response`, `too_many_redirects`, `blocked_address`.

**Privacy:** registrant, administrative, technical and abuse contacts are never read or stored. Only registry facts are kept: status, dates, registrar organisation and nameservers.

**Limits:** TLDs that have no RDAP server in the IANA bootstrap (several ccTLDs) return `unsupported_tld`. Requests to the same registry run one at a time with a 0.5 s pause, but registries may still rate-limit large lists. Responses are capped at 256 KiB, with at most 3 RDAP redirects.

**Proposed pricing (not active):** USD 0.0015 per `domain-checked` event, charged only when `available` is true or false (errors are free), plus USD 0.00005 per run start. For comparison, one incumbent listed USD 0.035 per start and USD 0.0023 per domain (Apify Store, observed 2026-11-03).

**Local verification (2026-11-05):** the core passes 22/22 offline cases against a local test server. CI now includes this Actor, common public-network restrictions and `python3 tests/actor_sdk_smoke.py --actor domain-availability`. The real pinned Apify SDK wrapper was executed locally with Python 3.12.3, synthetic RDAP sockets and local test charging: registered/unregistered rows are charged; HTTP 429 and invalid input are not. This does not verify a deployed image, live registries, account access, listing or real billing. `core-test-results.json` remains the earlier core-only report.

## Français
Vérifie si des noms de domaine sont enregistrés, uniquement au moyen du service public officiel **RDAP** de chaque registre, trouvé grâce au fichier d’amorçage de l’IANA (instantané du 2026-11-04). Aucun WHOIS, aucune extraction de pages Web.

**Entrée :** `domains` (liste de 1000 noms au maximum ; les URL sont réduites à leur nom d’hôte ; les doublons sont supprimés), `timeoutSecs` (de 1 à 60, 15 par défaut).

**Sortie :** une ligne par domaine, avec les champs indiqués ci-dessus.

- `available: true` : le serveur RDAP du registre a répondu HTTP 404 (aucun enregistrement). C’est un indice fort, **pas une garantie**. Un nom réservé, premium ou bloqué peut rester impossible à enregistrer. Vérifiez auprès d’un registraire avant tout achat.
- `available: false` : le registre a renvoyé un enregistrement.
- `available: null` : aucune réponse définitive ; consultez `error_code`.

**Vie privée :** les coordonnées du titulaire et des contacts administratifs, techniques ou d’abus ne sont jamais lues ni conservées. Seuls les faits du registre sont gardés : statut, dates, registraire et serveurs de noms.

**Limites :** les extensions sans serveur RDAP dans l’amorçage de l’IANA renvoient `unsupported_tld`. Les requêtes vers un même registre sont envoyées une à la fois, avec une pause de 0,5 s ; les registres peuvent tout de même limiter le débit. Les réponses sont plafonnées à 256 Kio, avec au plus 3 redirections.

**Tarif proposé (non actif) :** 0,0015 USD par événement `domain-checked`, facturé seulement si `available` vaut true ou false (les erreurs sont gratuites), plus 0,00005 USD par démarrage.

**Vérification locale (2026-11-05) :** 22 cas hors ligne réussissent avec un serveur local. La CI inclut désormais cet Actor, les restrictions réseau et l'enveloppe du SDK Apify épinglé, exécutée localement sous Python 3.12.3 avec des réponses RDAP synthétiques et une facturation de test. Les réponses définitives sont facturées ; les erreurs HTTP 429 et les entrées invalides ne le sont pas. Ni image déployée, ni registres réels, ni accès au compte, publication ou facturation réelle ne sont prouvés. Le fichier `core-test-results.json` conserve l'ancien rapport du cœur seul.
