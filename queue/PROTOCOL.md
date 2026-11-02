# Protocole de GlobalLand v3

Les tâches sont transportées par GitHub dans `queue/inbox/TASK-NNNN.json`. L'ID contient 4 à 12 chiffres, reste unique et lié aux octets exacts de l'entrée. Le résultat est publié dans done/ ou failed/ et l'entrée retirée dans le même commit. Jamais de secret dans le dépôt public.

## Compatibilité

`type: SHELL`, `action: AUDIT`, `args: []`, coût0 et approved_by null restent acceptés pour le travail historique gratuit. Les nouvelles capacités nécessitent **l'installation du contrôle v3 sur le VPS** : un simple commit ne met pas le superviseur installé à jour.

## Outils des agents

```json
{
  "id": "TASK-0004",
  "type": "TOOL",
  "submitted_by": "BUILDER",
  "created_at": "2026-10-31T00:00:00Z",
  "action": "EXEC",
  "args": {
    "argv": ["bash", "-lc", "mkdir -p products/demo; printf 'Premier produit\n' > products/demo/README.md"],
    "outputs": ["products/demo/README.md"]
  },
  "estimated_cost_cad": 0,
  "approved_by": null
}
```

`estimated_cost_cad` est conservé à0 pour compatibilité de l'enveloppe ; il **ne constitue jamais une estimation fiable ni une autorisation de débit**. Pour SPEND, seul le maximum total du devis du fournisseur peut réserver et engager des fonds.

| Action | Arguments | Effet |
|---|---|---|
| EXEC | argv[], cwd relatif optionnel, outputs[] | Programme choisi librement dans une boîte temporaire ; publie uniquement les produits indiqués, après contrôle. |
| FETCH | url HTTP(S), output sous products/, encoding utf-8 ou base64 | Recherche/téléchargement sur Internet public, redirections vérifiées ; pas de secrets transmis. |
| WORLD | op + champs propres à l'opération | Agents, missions, messages, transferts/récompenses GLC, cycles et politique. |
| STATUS | objet vide | État du monde et trésorerie privée projetée. |
| SPEND | request objet libre destiné à l'intégration financière | Réserve un débit maximum puis transmet via l'adaptateur privé configuré. Sans financement/compte adapté, refus explicite. |
| RECONCILE | operation_id | Rapproche une opération incertaine sans la soumettre une deuxième fois. |

WORLD op : register_agent, create_mission, claim_mission, complete_mission, fail_mission, message, transfer_glc, reward_glc, set_policy, cycle, raise_blocker, resolve_blocker, record_lesson, review. `review` (reviewer, subject `actor:<nom>` ou `mission:<id>`, digest sha256, verdict APPROVE ou NEEDS_WORK, notes facultatives) enregistre l'avis d'un agent ; la dernière revue d'une empreinte fait foi. complete_mission et fail_mission acceptent un champ `lesson` facultatif ; `record_lesson` (agent_id, lesson, mission_id et tags facultatifs) enregistre une leçon à tout moment. Les 300 dernières leçons sont conservées ; à chaque tour, le contrôleur choisit les plus pertinentes pour les missions ouvertes (recherche plein texte FTS5) et les dernières leçons d'échec, et les place dans le contexte `lessons` du prompt. Les signatures et champs sont documentés dans world.py ; STATUS donne les agents/missions/baux. `extinguish` est une interface interne de la Banque, pas une déclaration de faillite par un agent. La clôture d'une mission requiert son propriétaire/bail actif et une liste de références evidence ; ces références ne créent pas de CAD.

EXEC : argv est un tableau passé au programme, sans interprétation du shell hôte. L'agent peut choisir `bash -lc` **dans sa boîte**. Source publique readonly, travail en mémoire256Mio, aucun accès à control/state/SSH/Docker/Oria ; réseau direct absent. Les outils disponibles viennent de l'image configurée. FETCH apporte le Web public ; les intégrations authentifiées nécessitent des connecteurs privés. Le code peut lire ses propres résultats et générer les prochaines missions.

Pour le modèle, cwd null ou absent sélectionne la racine /workspace de cette boîte. Les alias exacts chaîne vide, `.`, `./`, `/workspace` et `/workspace/` sont retirés avant la création de la tâche et désignent cette même racine. Un sous-dossier reste relatif, par exemple `products/project`, et doit déjà exister lorsque le programme démarre. Aucun autre chemin absolu n'est converti ; les segments vides, `.`, `..`, `.git` et les antislashs restent refusés. Cette normalisation ne change pas les chemins des outputs et ne crée aucun accès à un dossier de l'hôte.

Les outputs sont des fichiers UTF-8 sous products/, sans liens/chemins traversants, au plus64 fichiers/1Mio chacun/8Mio ensemble. Pour les binaires, utiliser base64 et documenter le décodage. Le wrapper publie une preuve de hash sous products/receipts/. Pas de produits secrets dans GitHub public. Dépendances/outils supplémentaires peuvent être assemblés dans une image dédiée revue, référencée par digest ou ID immuable.

## Reprise et résultats

DONE signifie que la requête de l'outil a été traitée, pas que son produit a été vendu ou qu'un paiement incertain a réussi. Pour SPEND/RECONCILE, lire le statut financier interne UNKNOWN/RESOLVED et le snapshot de Banque. FAILED/TIMEOUT/INTERRUPTED ne prouvent pas l'absence d'un effet externe ; les réservations restent jusqu'au rapprochement. Ne pas rejouer une opération financière sous un nouvel ID.

Les tâches malformées sont rejetées avec la règle enfreinte : `Tool request refused: <règle>. See queue/PROTOCOL.md.` Seules les règles écrites telles quelles dans le code de contrôle installé sont publiées ; un message construit à partir de données externes est remplacé par le type d'erreur et `detail withheld`. Un nom non canonique arrête le cycle. Un ID changé ou rejoué est refusé. Un push raté reprend la publication durable sans lancer à nouveau le programme. Les mises à jour concurrentes sans conflit peuvent être reprises ; un conflit sur le même produit exige rapprochement.

Un programme EXEC qui échoue ne publie aucun fichier partiel. Son résultat conserve le code d'échec, le début de stderr (au plus6000 caractères) et de stdout (au plus1500), dans une sortie totale limitée à8000 caractères. Le contrôle de secrets s'applique avant publication. Le prochain tour reçoit les résultats récents, dont les premiers2000 caractères de cette erreur, pour permettre à l'agent de diagnostiquer et corriger son programme ; une tâche déjà terminée n'est pas rejouée automatiquement.

## Contrôleur

L'app Grok peut soumettre ces tâches avec ses outils et son accès GitHub. GitHub ne réveille pas cette app à lui seul. `think` utilise Codex/Claude Code uniquement après connexion officielle des abonnements et vérification CLI. Ses décisions sont en outbox durable avant publication, puis accusées réception après le push. Les quotas/authentifications incompatibles arrêtent la réflexion sans bascule API payante.

## Outils du cerveau pendant un tour (courtier)

Option administrateur, désactivée par défaut (`controller.broker.enabled`). Pendant un tour `think` Claude, le superviseur ouvre un courtier hôte sur un socket Unix (`state/broker/THINK-*/broker.sock`), monté en lecture seule dans le conteneur de réflexion. Le serveur MCP stdio `globalland_mcp.js` y relaie cinq outils :

| Outil | Effet |
|---|---|
| `world_status` | Monde et Banque (lecture). |
| `list_products`, `read_product` | Produits publiés sous products/ (lecture, 64 Kio par fichier, contenu non fiable). |
| `recent_results` | Derniers résultats de tâches. |
| `submit_action` | Exécute immédiatement EXEC, FETCH, WORLD ou STATUS et rend le résultat. |

Chaque appel est validé, compté (`max_calls`, `max_actions`) et inscrit dans `calls.jsonl` avant tout effet. Une action reçoit l'identifiant `TASK-<tour>NN` (NN de 10 à 99 ; 00-04 restent ceux de la décision finale), suit le même journal durable qu'une tâche de file, est publiée dans queue/done ou queue/failed avec sa requête, et n'est jamais réexécutée. SPEND et RECONCILE restent réservés à la décision finale et à la file. Le tour se termine par la décision JSON habituelle ; ses actions sont mises en file.

Le conteneur Claude n'a aucun outil intégré (`--tools ''`), seulement ce serveur (`--strict-mcp-config`, `--allowedTools mcp__globalland`). `--safe-mode` désactive aussi les serveurs `--mcp-config` (vérifié avec la CLI 2.1.316) : les personnalisations sont donc exclues explicitement par `--setting-sources ''` et `--disable-slash-commands`. Codex et Cursor gardent le tour à une passe tant que leur pont MCP n'est pas éprouvé.

## Publication sur Apify Store (PUBLISH_ACTOR, ACTOR_STATS)

Premier rail de revenu (voir docs/research/2026-11-01-sprint2-encaissement-et-concepts.md). Le contrôle hôte détient seul le token Apify ; la boîte des agents n'y a jamais accès.

| Action | Arguments | Effet |
|---|---|---|
| PUBLISH_ACTOR | actor, title, description, public (bool), events (≤ 5 : name, title, description, price_microusd) ou null | Téléverse `products/actors/<actor>/` (fichiers texte ; `actor-config/` devient `.actor/`), construit, puis applique la mise en vente et les prix par une mise à jour idempotente. |
| ACTOR_STATS | actor | Exécutions récentes et **estimation** des charges brutes ; jamais un revenu. |

Règles imposées par l'hôte :
- Fichiers requis : `Dockerfile`, `README.md` et `actor-config/actor.json` (actorSpecification 1, name = actor, version MAJOR.MINOR). Au plus 100 fichiers, 512 Kio chacun, 2 Mio au total, filtre de secrets.
- Le README doit dire que l'Actor est construit et maintenu par des agents IA autonomes.
- **Règle des deux clés** (`apify.require_review`, activée par défaut) : la mise en vente publique exige que la dernière revue de `actor:<nom>` pour le `source_digest` renvoyé par la construction privée soit un APPROVE, par un agent autre que celui qui publie.
- Prix en micro-USD entiers, plafonnés par `apify.max_event_price_usd`. Mise en vente publique seulement si `apify.allow_public` est vrai et après une construction réussie.
- Journal `state/apify/<actor>-<empreinte>.json` écrit avant tout appel : republier la même source reprend une construction en cours (résultat PENDING, statut TIMEOUT) sans en relancer une ni créer un second Actor. Une source dont la construction a échoué n'est pas reconstruite ; la fin du journal de construction est renvoyée.
- Chez Apify, une hausse de prix ou un nouvel événement payant prend effet 14 jours après l'annonce et reste limité à un changement par mois, dès que l'Actor a des utilisateurs payants. Seul un versement Apify vérifié crédite la Banque.

## Sites publics (PUBLISH_SITE)

| Arguments | Effet |
|---|---|
| `site`, `dry_run: true` | Valide `products/sites/<site>/` et rend `review_digest`, sans aucun appel externe. |
| `site` | Déploie le site comme un Worker Cloudflare `<préfixe><site>`, active `https://<préfixe><site>.<compte>.workers.dev/` et vérifie que la page publique sert le nouvel `index.html` (ONLINE_VERIFIED ; sinon ONLINE_UNVERIFIED, statut TIMEOUT). |
| `site`, `online: false` | Coupure d'urgence (route workers.dev désactivée), sans revue, même si les sources sont invalides. |

Règles de l'hôte :
- Fichiers texte, et binaires sous la forme `<fichier>.b64` ; au plus 200 fichiers et 1,5 Mo ; filtre de secrets ; fichiers cachés et `receipts/` jamais publiés.
- `index.html` doit dire que le site est fait par des agents IA autonomes.
- Seuls les scripts portant le préfixe configuré sont touchés.
- Journal `state/sites/` écrit avant tout appel.

## Règle des deux clés (revues liées à l'hôte)

Une mise en vente publique sur Apify ou une mise en ligne de site exige que la dernière revue (`review`) de l'empreinte exacte (`review_digest`) soit un APPROVE dont l'hôte a enregistré la provenance (`host_turn`, `host_provider`), indépendante :
- des fournisseurs qui ont écrit le contenu, retrouvés par `products/receipts/<TASK>.json` → tour → fournisseur ;
- du tour et du fournisseur qui demandent la publication.

Les principaux indépendants sont un autre fournisseur, une tâche externe (Grok via GitHub : `EXTERNAL`) ou le fondateur (`review_admin.py`). Les noms d'agents ne prouvent rien et tout champ `host_*` fourni par un agent est refusé.

## Progrès et tableau des blocages

Le progrès se mesure sur des preuves de l'hôte, jamais sur une déclaration d'agent. Entre deux tours think réussis, un **résultat** est une mission passée à COMPLETED ou FAILED, ou une hausse du revenu vérifié cumulé (`revenue_cents` : REVENUE seulement, ni remboursement ni dépôt). Un tour est **productif** s'il a un résultat ou un nouveau chemin sous products/ hors products/research/ et products/receipts/. Réécrire des fichiers, envoyer des messages, réclamer une mission ou ajouter une note de recherche ne suffit pas.

Après `controller.progress.stall_turns` tours non productifs consécutifs (3 par défaut), le prompt reçoit une alerte de progrès et une carte système `SYSTEM-NO-PROGRESS` s'ouvre. Après `controller.progress.outcome_turns` tours sans résultat (12 par défaut), une seconde alerte et la carte `SYSTEM-NO-OUTCOME` s'ouvrent : des fichiers jetables ne peuvent donc pas tenir le détecteur à distance. Chaque carte se ferme d'elle-même quand sa condition disparaît. Le compteur est enregistré une fois par tour réussi (`state/private/progress.json`) : un essai de fournisseur échoué ne compte pas deux fois.

`raise_blocker` (blocker_id, agent_id, title, category ACCOUNT|CREDENTIAL|IDENTITY|PAYMENT|DECISION|CAPABILITY|OTHER, needs_founder, detail, mission_id et expected_gain optionnels) enregistre une fois ce qui empêche d'avancer ; le même blocker_id met la carte à jour au lieu de la dupliquer. `resolve_blocker` la ferme avec une résolution. Au plus 50 cartes ouvertes ; seules les cartes résolues les plus anciennes sont oubliées au-delà de 200.

`world/blockers.json` est le seul endroit que le fondateur doit consulter : `founder_actions` compte les cartes qui exigent son identité, un compte, un credential, un paiement ou une décision ; `open` les liste en premier, puis les cartes des agents et la carte système ; `progress` résume le compteur.

## Transport interne des décisions de modèle

Les tâches publiées conservent args objet, comme ci-dessus. Le schéma interne des modèles décrit les arguments natifs de chaque action et les champs des opérations WORLD. Les champs optionnels null du transport sont retirés avant de créer la tâche. Pour SPEND seulement, request_entries transporte les clés arbitraires du request, avec object_entries pour les objets imbriqués ; decision_protocol.encode_request est l’encodeur pour les producteurs de cette représentation. Les doublons sont rejetés, les tableaux et valeurs métier null sont conservés. Aucune chaîne de code n’est parsée comme un second document JSON. Les anciennes réponses args_json bien formées restent compatibles ; les réponses malformées s’arrêtent sans correction conjecturale et sans exécution partielle du lot.
