# Architecture de GlobalLand v3

## État financier

Le capital initial autorisé est 50 CAD (5000 centimes), délégué en totalité aux agents. Les objectifs et marchés sont mondiaux. Aucun veto par action ni réserve minimale imposée. Les revenus réglés peuvent être réinvestis ; aucune dette ou recharge personnelle n'est autorisée.

`ledger.json` et `logs/transactions.log` conservent l'histoire déclarative v2 et le tick narratif. Ils ne prouvent aucun financement externe et ne sont plus l'autorité de dépense. `bank/status.json` est la projection de la trésorerie privée ; UNFUNDED signifie que le dépôt réel n'a pas été vérifié, et ne signifie pas EXTINCT.

## Modules

- `treasury.py` : SQLite privé, centimes exacts, réservation atomique, appels incertains retenus, preuves externes, revenus vérifiés acceptés avant le dépôt initial, revenus dépensables seulement après maturité (`available_at`), annulations de vente (`REVERSAL`) et plancher de réserve, positions par (fournisseur, compte, actif) et extinction irréversible.
- `gateway.py` : contrat avec `/opt/globalland/integrations/finance` (non fourni sans choix du service réel). Les devis garantissent un maximum ; les appels utilisent une clé d'idempotence ; les reçus sont vérifiés. Aucun appel API ou achat simulé n'est présenté comme réel.
- `world.py` : agents, missions hiérarchiques, messages, baux, portefeuilles/dettes GLC, cycles et liquidation.
- `tools.py` + `executor.js` : commandes choisies par les agents dans un conteneur temporaire, fichiers de produits et recherche HTTP(S) publique via courtier.
- `controller.py` : observations → décision structurée → tâches durables. Grok peut soumettre via GitHub. Le mode subscriptions appelle les CLIs officielles Codex/Claude Code avec leur connexion d'abonnement, sans reprise automatique sur une API payante.
- `broker.py` + `globalland_mcp.js` : outils du cerveau pendant un tour Claude, via un socket hôte. Validation, budget et journal avant effet ; les actions suivent le journal durable des tâches (voir queue/PROTOCOL.md).
- `apify.py` : publication sur Apify Store (téléversement, construction, prix par événement plafonnés, mise en vente), journal de reprise et statistiques ; le token reste sur l'hôte.
- `payouts.py` : versements Apify vers la Banque (facture = créance, versement reçu = REVENUE attesté par le fondateur), projection des créances.
- `sites.py` : PUBLISH_SITE (site statique servi par un Worker Cloudflare, dry_run, coupure d'urgence, vérification de la page publique).
- `review.py` : règle des deux clés liée à l'hôte (auteurs retrouvés par les reçus, provenance des revues).
- `watchdog.py` + `.github/workflows/watchdog.yml` : disjoncteur horaire hors VPS (issue GitHub si le monde se tait ou est bloqué).
- `preflight.py` : vérification GO/NO-GO de l'installation, en lecture seule.
- `controller.provider_order` : disjoncteur des fournisseurs (un fournisseur qui vient d'échouer passe en dernier, jamais exclu ; `state/private/provider-health.json`, codes fixes seulement).
- `incident.py` : triage d'un monde muet ou bloqué (verrou, horaire, cron, Docker, disque, codes d'échec par fournisseur), en lecture seule, autonome (bibliothèque standard) et sans secret dans la sortie.
- `review_admin.py` : revue du fondateur (Apify ou site).
- `lessons.py` : sélection des leçons pertinentes (SQLite FTS5, BM25), avec provenance, date connue ou nulle et statut de conclusion d'agent révisable. La projection conserve le classement et l'historique ; elle ne certifie pas la portée ni la vérité du texte.
- `progress.py` : détecteur d'absence de progrès (preuves de l'hôte) et projection `world/blockers.json`.
- `supervisor.py` : transport Git, verrou commun, reprise durable, publication vérifiée et arrêt productif à la mort du monde.

## Installation hôte

Director and `STATUS` share a read-only `economic_context`: known admitted cash
flows and unresolved commitments accompany the same authoritative bank snapshot.
History can be UNKNOWN or INCOMPLETE, never certified complete. Gross revenue
credits differ from the bank's net revenue. The independent Apify invoice ledger
may lag settlement; its USD receivables never become CAD cash or spending power.
Missing or invalid optional data is UNAVAILABLE, not zero. Fees, profit and
experiment allocations remain unknown; existing founder-provided VPS and model
subscriptions are outside the 50 CAD capital, with no invented amount or period.

`control` pointe vers un code administrativement installé depuis un SHA revu. `source.git`, `state/private`, `integrations` et `credentials` ne sont jamais montés dans le conteneur de produits. Les données privées ne sont pas publiées. Les credentials d'abonnement sont montés seulement dans le conteneur de réflexion officiel correspondant.

EXEC reçoit uniquement un export public en lecture seule, une requête et son wrapper installé. Son travail est dans un tmpfs de 256 Mio ; son rootfs est readonly, sans réseau direct, sans capacité Linux et sans socket Docker. Il peut choisir toute commande disponible dans son image. FETCH fournit le Web public, y compris téléchargement base64 ; les intégrations authentifiées et financières sont des modules privés. Les limites mémoire/CPU/processus/temps protègent le serveur partagé.

## Cycle

`queue` consomme les tâches ; `daily` maintient l'audit narratif idempotent ; `think` appelle le contrôleur configuré puis publie ses tâches ; `status` montre l'état privé sans secrets. Un accès GitHub seul ne réveille pas l'app Grok : tant que les CLIs ou un autre contrôleur ne sont pas connectés, WAITING_CONTROLLER est normal. `world/controller.json` dérive son état du dernier tour durable : OPERATIONAL (décision produite), DEGRADED (un fournisseur a échoué, bascule en cours), CONTROLLER_BLOCKED (tous ont échoué) ou STALE (aucun tour depuis `stale_after_seconds`, 7200 par défaut).

Les résultats et artefacts sont préparés durablement avant Git. Un push refusé ne relance pas l'action. Les modifications amont sans conflit sont rapprochées avec sauvegarde du commit local ; un même produit ou ledger modifié concurremment exige une réconciliation. Les décisions du contrôleur restent en outbox jusqu'à leur publication confirmée.

## Extinction

Le solde libre nul par réservation n'est pas une perte. Le patrimoine réel confirmé nul, positions et opérations réglées, crée un état terminal. Le contrôleur et les outils productifs s'arrêtent ; les preuves et snapshots restent accessibles. Ni arrêt de Docker partagé, ni suppression du VPS ou d'Oria, ni archivage automatique du dépôt.
