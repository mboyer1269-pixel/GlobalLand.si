# Grok World Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relier les missions de Grok aux outils du monde et aux spécialistes Codex/Claude, avec résultats durables et preuve explicite de reprise de Grok.

**Architecture:** Conserver Python/Node, la queue GitHub sur main, les conteneurs et les abonnements officiels. Utiliser une routine native de Grok Bot xAI pour transmettre le travail et consulter les résultats ; ajouter les délégations explicites à Codex/Claude. Le relais GitHub conserve les décisions avant envoi. Aucun service de notification ou API Grok supplémentaire n’est prévu pour le premier parcours.

**Tech Stack:** Python 3.12+, Node.js 22, SQLite/JSON privés existants, Git et Docker ; aucune nouvelle dépendance de framework prévue.

**Spec:** [Conception Grok → GlobalLand → spécialistes](../specs/2026-10-31-grok-world-loop-design.md).

## Global Constraints

- Le fondateur parle aux Grok Bots ; Codex/Claude sont des spécialistes, pas des remplaçants présentés sous leur identité.
- Les tâches sont consommées depuis main ; une PR ouverte n’est pas une preuve de livraison ou d’exécution.
- Les 50 CAD sont autorisés, pas encore rapprochés. Aucun mouvement réel d’argent pour vérifier cette boucle.
- Aucun repli API payant, achat de crédits, accès aux autres fonds, changement d’Oria ou installation d’un framework supplémentaire.
- Réutiliser la grammaire TASK de 4 à 12 chiffres, les règles WORLD et les cinq actions maximum d’une décision.
- Tous les appels de modèle passent par les CLIs officielles et leurs contrôles existants. Aucun code de produit ne s’exécute avec leurs credentials.
- Déploiement et preuve native attendent la disponibilité et la vérification de l’état du VPS ; les tests locaux ne les remplacent pas.

## Review Focus

1. Une tâche présente uniquement dans une PR reste PENDING_MAIN_DELIVERY ; elle n’est pas annoncée comme soumise au VPS.
2. Cursor externe et CLI Cursor du VPS sont distingués ; l’indisponibilité de la seconde ne bloque pas une délégation Codex/Claude valide.
3. Un crash après réponse du modèle mais avant publication réutilise la proposition durable ; une réponse inconnue n’est pas inventée ou relancée aveuglément.
4. Un résultat livré deux fois ou sans accusé ne provoque pas une nouvelle suite de tâches sous de nouveaux IDs.
5. Une réservation UNKNOWN, un état terminal ou un faux reçu ne deviennent ni argent disponible ni redémarrage du monde.

## Ordre de réalisation

Les étapes ci-dessous sont **à réaliser**. Ce document n’ajoute encore ni action DELEGATE, ni connexion Grok, ni cron et ne soumet aucune tâche. Le produit est identifié : Grok Bot de xAI, dont le guide officiel documente ordinateur cloud, routines, déclencheurs, échanges entre bots et délégation à Cursor. Premier contrôle externe : vérifier les droits GitHub et une routine réellement enregistrée dans le compte de l’opérateur. Utiliser ces fonctions natives avant d’envisager une API xAI, un serveur MCP ou un service de notifications supplémentaire.

### Task 1: Distinguer livraison des missions et développement

**Files:**
- Create: `scripts/coordinator.py`, `tests/test_coordinator.py`.
- Modify: `scripts/supervisor.py`, `queue/PROTOCOL.md`.

**Interfaces:**
- Consumes: configuration privée `coordinator = {mode: "grok_coordinated", transport: "disabled"|"grok_bot_native", bot_id: "identifiant ou nom de bot relevé dans le compte"}` et compte rendu privé de capacités éprouvées dans le compte, jamais une simple déclaration dans un commit de l’agent. L’identifiant est non vide, au plus 128 caractères et ne contient aucun secret ; il reste privé.
- Produces: `coordinator_readiness(config: dict, capabilities: dict | None) -> dict`, projection fermée `world/coordinator.json` et état `WAITING_GROK_TRANSPORT`, `WAITING_GROK_RESUME`, `VALIDATING`, `READY`, `HALTED` ou `EXTINCT`.
- Capabilities exactes : `deliver_main`, `read_results`, `resume_grok`, `deduplicate_events`, toutes booléennes. `deliver_main` signifie livraison effective sur main : écriture directe ou mécanisme automatique de fusion/merge queue éprouvé ; une PR seule ne suffit pas. `automatic_resume_verified` ne devient vrai qu’après le parcours natif attesté dans la configuration administrative privée ; READY exige cette preuve.
- Pour produire cette preuve sans dépendance circulaire, la configuration administrative peut demander `validation_mode: true` et un `validation_mission_id` existant. Après contrôle des accès du bot et de sa routine native, ce mode publie VALIDATING avec `automatic_resume_verified: false`. Le relais applique, dans son journal privé, une borne de deux lots de suite pour cette mission d’essai ; cette borne ne limite pas les conversations ou réveils de la plateforme xAI. L’essai ne peut activer READY lui-même. Le mode normal reste désactivé jusqu’à consignation de la preuve. Ces bornes concernent uniquement l’essai, pas les stratégies du monde en fonctionnement.

- [ ] Écrire `test_pr_only_transport_is_not_ready`, `test_automatic_delivery_to_main_is_eligible`, `test_missing_resume_stays_waiting`, `test_validation_mode_runs_without_claiming_ready`, `test_terminal_state_wins` et `test_coordinator_status_has_no_raw_account_data`. Vérifier le refus d’un relais PR-only même avec des logins valides ; la borne effective de soumission est testée dans Task 4, au niveau du relais.
- [ ] Lancer `python3 -m unittest discover -s tests -p 'test_coordinator.py'` et observer les échecs attendus avant implémentation.
- [ ] Implémenter la projection et la validation fermée des capacités ; garder le statut des abonnements distinct. L’absence de configuration conserve le fonctionnement existant.
- [ ] Relancer les tests ciblés et `test_think_failure.py` ; exiger succès et absence de changement financier.
- [ ] Commit : `feat(coordinator): expose actual Grok transport readiness`.

### Task 2: Permettre une demande explicite à Codex ou Claude

**Files:**
- Create: `scripts/specialist.py`, `tests/test_specialist.py`.
- Modify: `scripts/tools.py`, `scripts/controller.py`, `scripts/decision_protocol.py`, `scripts/decision.schema.json`, `queue/PROTOCOL.md`.

**Interfaces:**
- Consumes: enveloppe TOOL/DELEGATE décrite dans la spec ; `Controller.plan(provider, prompt)`, `Controller.context()`, `decode_model_decision`, `validate_envelope` et les contrôles de secrets existants.
- Produces: `Specialist(root, world, treasury, config).run(task: dict) -> tuple[dict, dict]`, même retour result/files que Toolbox, avec `products/delegations/<task_id>.proposal.json` et reçu SHA-256.
- La proposition contient exactement `task_id`, `input_sha256`, `mission_id`, `provider`, `summary`, `actions`. Les actions sont des propositions sans ID ; leur validation utilise des enveloppes temporaires non publiées. Aucun nouveau lot n’est soumis à cette étape.

- [ ] Écrire des tests de contrat : fournisseur nommé conservé ; auto essaie une fois chaque abonnement configuré ; mission absente/terminale et auteur inactif refusés ; arguments inconnus et secrets refusés ; Cursor VPS non sélectionné ; proposition invalide sans fichier partiel.
- [ ] Écrire `test_delegate_produces_proposal_without_executing_actions` : une proposition EXEC valide retourne un fichier et son hash, avec zéro exécution de programme et zéro appel financier.
- [ ] Lancer les tests et constater les échecs avant ajout de l’action.
- [ ] Ajouter l’action aux schémas interne/modèle et au Toolbox. Réutiliser les chemins de contrôle CLI, le nettoyage et les motifs de secrets ; séparer la construction du prompt de la création de tâches du contrôleur courant.
- [ ] Lancer `test_specialist.py`, `test_controller.py` et les tests du protocole existants ; vérifier les anciennes actions et le format sans double encodage JSON.
- [ ] Commit : `feat(tools): delegate proposals to subscription specialists`.

### Task 3: Reprendre une délégation sans refaire son appel

**Files:**
- Modify: `scripts/specialist.py`, `scripts/supervisor.py`.
- Create: `tests/test_specialist_recovery.py`.

**Interfaces:**
- Consumes: ID et empreinte de l’enveloppe originale ; journal existant du superviseur.
- Produces: journal privé `state/private/specialists/<task_id>.json`, états `RUNNING`, `VALIDATED`, `UNKNOWN`, `FAILED`, et `Specialist.recover(task: dict) -> tuple[dict, dict] | None`.
- VALIDATED conserve la proposition, ses octets publics et leur empreinte. `recover` renvoie ces mêmes result/files sans modèle. RUNNING retrouvé après interruption devient UNKNOWN, avec diagnostic fixe ; aucune réinvocation automatique. Une entrée de même ID mais d’empreinte différente est refusée.

- [ ] Écrire des tests injectant une panne après sauvegarde VALIDATED, avant enregistrement du résultat superviseur, puis après commit local avant push. Exiger une seule invocation, des octets identiques et une publication finale cohérente.
- [ ] Écrire les tests RUNNING incertain et ID réutilisé avec d’autres octets. Exiger absence de second appel et résultat distinct d’un succès.
- [ ] Constater les échecs puis brancher la récupération spécialisée dans la reprise du superviseur, avant que le mécanisme générique ne clôture la tâche comme interrompue. Conserver la reprise actuelle des autres outils et des paiements.
- [ ] Lancer les tests ciblés et `test_supervisor.py`, `test_autonomous_integration.py`, `test_provider_failover.py`.
- [ ] Commit : `fix(specialist): preserve validated responses across publication failures`.

### Task 4: Utiliser la routine native de Grok Bot et un relais durable

**Files:**
- Create: `scripts/grok_relay.py`, `tests/test_grok_relay.py`, `tests/test_grok_loop.py`.
- Modify: `scripts/coordinator.py`, `scripts/supervisor.py`, `docs/GROK.md`.

**Interfaces:**
- Le relais s’exécute dans l’ordinateur cloud de Grok Bot, depuis une version revue. Il ne reçoit ni credentials VPS/finance ni accès aux autres comptes. Il utilise une connexion GitHub officielle du compte ; ne pas extraire les tokens d’un autre connecteur.
- `GitHubBackend` fournit `snapshot() -> str`, `read(path: str, ref: str) -> bytes | None` et `publish(base_sha: str, files: dict[str, bytes]) -> str`. Le dernier appel crée un commit et avance main sans forcer, ou signale un conflit ; il n’ouvre pas une PR. Le premier backend utilise la CLI GitHub officielle `gh api` avec JSON stdin, sans shell. Sa disponibilité, son login et ses droits doivent être vérifiés dans le bot ; ils ne sont pas présumés présents.
- `source_event_id(kind: str, data: dict) -> str` calcule le SHA-256 d’un objet JSON canonique `{kind, data}`. `kind=MISSION` accepte exactement mission_id/goal pour le premier lot ; `kind=BATCH_RESULT` accepte exactement batch_id/results, results étant la liste triée par task_id des objets fermés task_id/input_sha256/result_sha256. Canonicalisation Python : sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False. Les empreintes sont de 64 caractères hexadécimaux minuscules.
- `GrokRelay(journal_root, backend).stage(source_event_id: str, tasks: list[dict]) -> dict` valide et conserve le lot entier avant envoi. Un nouvel appel pour la même source retourne le lot conservé ; une proposition différente signale un conflit, sans nouveaux IDs. Le journal et les curseurs associent chaque suite à sa source, sans demander au modèle d’inventer une nouvelle clé lors d’une reprise.
- `GrokRelay.submit(source_event_id: str) -> dict` transmet uniquement le lot conservé. Il lit les tâches et résultats existants au même snapshot. Même ID/empreinte dans inbox = en attente ; résultat correspondant = terminé ; octets différents = conflit. Une erreur réseau impose de relire l’état avant nouvelle tentative. Aucun nouvel ID ni nouvel appel de modèle pour reprendre un envoi.
- `GrokRelay.poll(task_id: str) -> dict` retourne `PENDING`, `DONE`, `FAILED` ou `UNKNOWN`, avec la référence, l’empreinte d’entrée, les chemins publics et le JSON du résultat conservant son statut exact, y compris REJECTED/TIMEOUT/INTERRUPTED. Le journal privé, les octets du lot et les curseurs survivent à un redémarrage du bot. Un résultat absent ne signifie pas succès.
- `GrokRelay.poll_batch(batch_id: str) -> dict` attend un résultat publié et lié à la bonne entrée pour toutes les tâches du lot, puis produit une seule source BATCH_RESULT. Un résultat isolé ne crée pas de suite. Les statuts financiers internes restent disponibles : un résultat d’outil DONE n’est jamais une preuve de règlement et UNKNOWN appelle un rapprochement, pas une nouvelle soumission du paiement.
- Le journal est un fichier JSON par mission, avec verrou exclusif et remplacement atomique. Il conserve les lots, leurs sources, le lot actif et `followup_batches`. `stage` refuse une nouvelle source tant que le lot actif n’a pas tous ses résultats ; la source suivante doit être celle de ce lot terminé. Le batch_id est le hash canonique des octets du lot conservé. Deux appels concurrents pour le même lot ne créent pas deux suites.
- En VALIDATING, le journal conserve la mission autorisée et `max_followup_batches=2`. Le premier lot MISSION ne compte pas ; chaque nouvelle source BATCH_RESULT acceptée par stage incrémente le compteur dans le même remplacement atomique que son lot. Poll, reprise d’envoi et appel répété pour la même source ne l’incrémentent pas. Après redémarrage, un troisième lot de suite est refusé. Cette propriété concerne le relais ; elle ne prétend pas désactiver Grok Bot ou interdire ses autres activités.
- Le connecteur GitHub déjà présent peut être utilisé à la place du backend gh uniquement si ses capacités et sa déduplication satisfont ce contrat. S’il est limité aux PR, conserver l’état d’attente ; ne pas inventer un droit sur main ou un login gh.
- La routine native vérifie les missions et lots en attente, lit les résultats puis prépare le lot suivant avec Grok. Fréquence initiale proposée : toutes les 30 minutes, à vérifier dans le compte et selon ses quotas. Le produit documente les routines, pas la garantie de cette fréquence ni d’un trigger spécifique aux résultats de queue. Aucune boucle d’attente active.
- Le mode coordonné laisse la routine Grok conduire les missions. Le cycle think conserve reprise/publication et diagnostics, sans lancer une stratégie directe concurrente ; queue/daily restent en place. Aucun service `/integrations/grok`, callback ou serveur public supplémentaire n’est nécessaire pour ce premier chemin.

- [ ] Écrire des tests de relais avec deux clones Git locaux : panne après commit avant retour client, réponse réseau perdue, résultat déjà publié, même ID avec octets différents, conflit concurrent sur main et décision différente pour la même source. Ajouter un lot de plusieurs tâches publiant leurs résultats séparément : aucune suite avant le dernier résultat, puis une seule suite malgré deux routines concurrentes.
- [ ] Écrire les tests du journal VALIDATING : deux lots de suite acceptés, troisième refusé même après redémarrage ; polls et reprises d’un même lot sans incrément ; panne pendant écriture sans compteur séparé du lot. Exiger un seul lot durable et aucune redéposition après résultat.
- [ ] Écrire le scénario local : mission → DELEGATE Codex → proposition → routine Grok factice → nouvelle tâche EXEC → artefact → deuxième décision Grok factice. Simuler la routine via le pilote de test, sans la présenter comme une routine xAI réellement installée.
- [ ] Ajouter les cas relais PR-only, gh absent/non connecté, droits insuffisants, bot non identifié et Cursor externe disponible avec CLI Cursor VPS indisponible. Le statut expose la dépendance et aucune API payante n’est appelée.
- [ ] Observer les échecs, puis implémenter les méthodes du relais, le journal et le backend gh. Publier uniquement des enveloppes sous queue/inbox, jamais une modification de contrôle. Conserver les règles de conflit et de secret du transport existant.
- [ ] Documenter et préparer la routine dans Grok Bot : reprendre son journal, traiter les résultats inconnus avant nouveau travail, réutiliser les lots déjà enregistrés et rapporter les preuves. Vérifier sa création et une exécution réelle dans le compte ; une instruction en langage naturel ne suffit pas à déclarer la routine activée.
- [ ] Lancer les tests ciblés puis les suites Python/Node. Vérifier que le mode par défaut reste inchangé et que le mode coordonné ne double pas la planification.
- [ ] Commit : `feat(grok): support native routines with durable GitHub handoffs`.

### Task 5: Vérifier le parcours réel et conserver la banque honnête

**Files:**
- Modify: `INSTALL.md`, `docs/INTEGRATIONS.md`, `docs/GROK.md`, `README.md`.
- Create: `docs/verification/YYYY-MM-DD-grok-loop.md` au jour de l’essai réel.
- Reuse: `tests/test_treasury.py`, `tests/test_gateway.py`, `tests/test_autonomous_integration.py`.

**Interfaces:**
- Consumes: release exacte revue, VPS de nouveau accessible et vérifié, identités officielles connectées, relais GitHub éprouvé, routine native enregistrée et preuves des tâches/artefacts.
- Produces: rapport distinct des fixtures indiquant l’application, la release, les IDs, commits, empreintes, invocations et deux décisions successives de Grok. Sans cette preuve, `automatic_resume_verified` demeure faux.

- [ ] Exécuter les régressions financières existantes : deux réservations concurrentes de 3000 cents sur 5000 n’en acceptent qu’une ; UNKNOWN conserve ses fonds après redémarrage ; même reçu appliqué une fois ; faux reçu refusé ; EXTINCT reste terminal et Oria inchangée.
- [ ] Vérifier les prérequis Hostinger et le SHA réellement installé avant mise à niveau. Conserver credentials, état, journaux, outboxes et horaires ; suivre le retour arrière existant. Aucun effacement ou restauration d’un ancien solde.
- [ ] Activer le mode d’essai VALIDATING pour la mission choisie, sans activer READY. Effectuer cette mission sans dépense réelle depuis Grok, transmise sur main sans intervention terminal par mission. Vérifier sa délégation Codex, sa décision de suivi, l’artefact EXEC et le second retour vers Grok ; éprouver Claude séparément. Ne consigner `automatic_resume_verified` qu’après observation et rapport ; le passage au mode normal est distinct.
- [ ] Observer une interruption et sa reprise puis un déclenchement périodique. Recalculer les empreintes et distinguer proposition, tâche exécutée et résultat commercial.
- [ ] Documenter ce qui manque si la routine n’est pas disponible ou n’a pas pu reprendre automatiquement dans ce compte ; ne pas activer un indicateur de réussite pour contourner cette dépendance. Banque et compte réel forment un chantier séparé : aucun dépôt inventé, aucun test financier factice importé dans la production.
- [ ] Commit du rapport factuel seulement après observation des résultats.

## Ce que le fondateur devra pouvoir faire

Écrire à Grok : « Choisis une première opportunité mondiale, utilise Codex et Claude pour avancer, et reviens avec un produit vérifiable. » Le système doit montrer où en est la mission et reprendre après une erreur. Une PR doit être annoncée comme proposition de développement ou livraison de tâche en attente, jamais comme preuve que les habitants ont déjà travaillé.
