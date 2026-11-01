# Historique de GlobalLand : ce qui est fait, ce qui reste

> Mis à jour le 2026-11-01. Trois déclarations restent toujours séparées :
> 1. **logiciel vérifié localement** (tests, CI) ;
> 2. **monde autonome éprouvé sur le VPS réel** ;
> 3. **revenus externes réellement encaissés**.
>
> Aujourd'hui : (1) oui pour le code des PR #3 et #5 ; (2) **non depuis le 1er nov. 00:30 UTC** : le contrôleur installé est `CONTROLLER_BLOCKED` et plus aucun cycle n'est publié (voir [l'audit de crise](AUDIT-2026-11-01.md)) ; (3) **non, 0 CAD encaissé**.

## Où on en est, en cinq lignes

- **Incident en cours : le monde est arrêté depuis le 1er nov. à 00:30 UTC** (`CONTROLLER_BLOCKED`, aucun commit depuis). La cause est dans l'état privé du VPS : `scripts/incident.py` la lit en une commande, sans secret dans la sortie.
- Avant l'incident, un cycle de réflexion tournait toutes les 30 minutes depuis le 31 octobre, avec Codex et Claude sur abonnements.
- Les agents ont fabriqué de la recherche et un prototype (`products/invoice-preflight`), puis ont tourné en rond, faute de canal de publication et de vente.
- Le code pour en sortir est écrit et testé (PR #5) : cerveau à plusieurs actions par cycle, détecteur d'absence de progrès, tableau des blocages, banque prudente, publication et vente sur Apify Store.
- **Rien de cela n'est encore installé sur le VPS.** Le prochain pas appartient au fondateur : fusionner, installer, ouvrir le compte Apify.
- Objectif économique inchangé : 100 CAD de patrimoine net vérifié. Aucun profit n'est garanti.

## Ce qui est fait, étape par étape

| # | Date | Étape | Où | Preuve |
|---|---|---|---|---|
| 1 | 30 oct. | File de tâches GitHub vers le VPS, garde-fous, premiers rôles d'agents (inspirés d'agency-agents) | `main` | Tâches TASK-0001 à 0003 traitées par le VPS |
| 2 | 30 oct. | Superviseur isolé, validation des tâches, état d'exécution durable | PR #1 (fermée, reprise ensuite) | — |
| 3 | 31 oct. | **Monde v3** : agents persistants, missions, GLC, banque déléguée, EXEC et FETCH dans une boîte isolée | PR #2, fusionnée | Code dans `main` |
| 4 | 31 oct. | Cerveaux sur abonnements (Codex, Claude, Cursor), bascule entre fournisseurs, diagnostics d'échec | PR #3 (Codex), **ouverte** | 159 tests ; cycles THINK réels sur le VPS |
| 5 | 31 oct. | Premiers cycles autonomes réels : missions sur les factures CSV, recherche, prototype | VPS → `main` | 47 commits `globalland-supervisor` en ~24 h |
| 6 | 31 oct. | Prototype de calculateur TPS/TVQ | PR #4 (Cursor), **ouverte**, non revue ici | — |
| 7 | 1er nov. | **Audit et plan revenus-d'abord** : le monde est bloqué par l'absence de publication et de vente, pas par la banque | PR #5 | `docs/superpowers/plans/…` |
| 8 | 1er nov. | **Sprint 0** : 4 défauts financiers corrigés, `controller.json` fidèle, refus explicites, cause du trou de cycles du 31 oct. | PR #5 | Tests qui échouaient avant la correction |
| 9 | 1er nov. | **Sprint 1** : courtier et serveur MCP (plusieurs actions observées par cycle), détecteur d'absence de progrès, `world/blockers.json` | PR #5 | Essai réel de la CLI Claude hors Docker ; tests |
| 10 | 1er nov. | **Audit du Sprint 1** : 11 défauts corrigés (dont risque de double action et publication Git concurrente) | PR #5 | Skill `code-review`, tests de régression |
| 11 | 1er nov. | **Sprint 2** : recherche d'encaissement (Apify d'abord), règle de réserve, leçons réinjectées, publication Apify, versements vers la Banque | PR #5 | `docs/research/…` ; tests |
| 12 | 1er nov. | **Inspiration open source** : règle des deux clés et quatre fiches de décision (headcount, agency-agents) ; n8n écarté pour sa licence | PR #5 | `docs/research/2026-11-01-repos-n8n-headcount-agency.md` |
| 13 | 1er nov. | **Audit de crise** : monde arrêté sans alerte → disjoncteur hors VPS ; faille des deux clés (un cerveau signait deux fois) corrigée ; état du monde borné sous 1 Mio ; `PUBLISH_SITE` (Cloudflare) ; vérification de démarrage GO/NO-GO ; prix plancher ; garde-fous juridiques ; 9 défauts de revue corrigés | PR #5 | [`docs/AUDIT-2026-11-01.md`](AUDIT-2026-11-01.md) ; 268 tests |

**État de la CI :** verte sur chaque commit de la PR #5 vérifié.

## Ce qui reste, étape par étape

### Étape 0 — Relancer le monde arrêté *(toi, maintenant)*
- [ ] Sur le VPS : `sudo python3 scripts/incident.py /opt/globalland` depuis une copie fraîche du dépôt (voir INSTALL, « triage en une commande »). La sortie ne contient aucun secret et peut être recollée à Claude ou à Codex.
- [ ] Si c'est un quota ou une session expirée : reconnecter le fournisseur (`login_subscriptions.sh <fournisseur>`), puis lancer un `think` manuel.
- [ ] Sinon, appliquer la correction indiquée par l'outil. Si le code d'échec est une décision invalide (`invalid_controller_*`, `invalid_task_path`), passer à l'étape A : la PR #5 met à jour le guide et le schéma.

### Étape A — Mettre le nouveau code en service *(toi, environ 1 h, une fois)*
- [ ] Relire puis fusionner la **PR #3** (Codex).
- [ ] Fusionner la **PR #5**. Si la branche de la #3 est conservée, repointer d'abord la #5 vers `main`.
- [ ] Installer la version fusionnée sur le VPS : `upgrade_vps.sh` avec le SHA revu.
- [ ] Activer le courtier : `configure_subscriptions.py … --broker on`.
- [ ] `sudo python3 /opt/globalland/control/preflight.py` → doit afficher **GO**.
- [ ] Lancer un `think` manuel, puis vérifier `state/broker/THINK-*/calls.jsonl`, `world/controller.json` (OPERATIONAL) et `world/blockers.json`.

### Étape B — Ouvrir le premier rail de revenu *(toi, environ 30 min, une fois)*
- [ ] Compte **Apify gratuit, sans carte** (5 $ de crédits par mois, blocage sans facture une fois les crédits épuisés), vérification d'identité, nom d'utilisateur.
- [ ] Créer un token API et l'installer dans `/opt/globalland/credentials/apify/token` (mode 600). Ne jamais le coller dans GitHub ni dans un chat.
- [ ] Ouvrir un compte Wise ou PayPal réservé à GlobalLand, pour recevoir les versements (seuil de 20 $ US).
- [ ] Activer Apify dans `config.json` avec `allow_public: false` et `require_review: true`.
- [ ] Compte **Cloudflare gratuit** : `account_id` dans le bloc `cloudflare` de `config.json`, token « Workers Scripts: Edit » dans `/opt/globalland/credentials/cloudflare/token` (mode 600). Premier site : la chronique publique du monde (`PUBLISH_SITE`).

### Étape C — Premier produit vendable *(les agents, sans toi)*
- [ ] Les agents choisissent un Actor, avec un verdict d'idée enregistré en leçon.
- [ ] Ils le construisent sous `products/actors/<nom>/`, puis le publient en privé.
- [ ] Un autre agent le revoit et l'approuve (`review` APPROVE de l'empreinte exacte).
- [ ] *(toi, quand la première construction privée est vérifiée)* passer `allow_public` à true.
- [ ] Mise en vente publique et prix par événement ; suivi avec `ACTOR_STATS` et le détecteur de progrès.

### Étape D — Encaisser *(toi, moins de 5 min par mois)*
- [ ] Du 11 au 14 : approuver la facture Apify, puis `payouts.py invoice`.
- [ ] Du 21 au 25 : après réception et conversion en CAD, `payouts.py received`.
- [ ] Premier revenu attesté visible dans `bank/status.json`.

### Étape E — Fiabilité prouvée sur le VPS *(code : Claude ou Codex ; essais : VPS)*
- [ ] Vérifier le socket du courtier à travers Docker (uid 1000, montage en lecture seule).
- [ ] Endurance de 72 h sans recopie de commandes ni fusion manuelle, redémarrage et panne simulée d'un fournisseur compris.
- [ ] Pont MCP pour Codex et Cursor, aujourd'hui limités à une passe par cycle.
- [ ] Routine Grok éprouvée et coordinateur de secours.

### Étape F — Élargir l'économie *(après un premier revenu)*
- [ ] Ventes directes via Polar, avec la règle de réserve (fenêtre de remboursement de 60 jours).
- [ ] Marché interne des GLC pour le temps de calcul, studios en compétition avec critère d'abandon.
- [ ] Vérification automatique des versements (API Wise, si elle est accessible à un compte personnel canadien : non vérifié).
- [ ] Tableau de bord privé.
- [ ] Objectif : **100 CAD de patrimoine net vérifié**.

## Règles qui ne changent pas
- Aucune dette, recharge personnelle ni accès aux fonds d'Oria. Le plafond, c'est l'argent de GlobalLand.
- Une créance, une estimation ou des GLC ne sont jamais de l'argent. Un revenu attesté par le fondateur est affiché comme tel.
- Aucune preuve fabriquée. Un agent ne valide jamais son propre travail pour une mise en vente publique.
- Le dépôt est privé. Aucun secret n'y entre, même privé.
