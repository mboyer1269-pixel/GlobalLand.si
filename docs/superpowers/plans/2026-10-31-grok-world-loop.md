# Grok World Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relier les missions de Grok aux outils du monde et aux spécialistes Codex/Claude, avec résultats durables et preuve explicite de reprise de Grok.

**Architecture:** Conserver Python/Node, la queue GitHub sur main, les conteneurs et les abonnements officiels. Ajouter une délégation spécialisée et un adaptateur de retour, distincts des PR de développement. Une capacité de transport manquante bloque l’autonomie annoncée sans empêcher l’accès aux résultats déjà publiés.

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

Les étapes ci-dessous sont **à réaliser**. Ce document n’ajoute encore ni action DELEGATE, ni connexion Grok, ni cron et ne soumet aucune tâche. Première dépendance externe : identifier l’application Grok Bot et ses capacités supportées de livraison et de reprise. On peut implémenter et tester les contrats avec des fixtures en attendant ; aucun adaptateur réel ne sera déclaré connecté sur cette seule base.

### Task 1: Distinguer livraison des missions et développement

**Files:**
- Create: `scripts/coordinator.py`, `tests/test_coordinator.py`.
- Modify: `scripts/supervisor.py`, `queue/PROTOCOL.md`.

**Interfaces:**
- Consumes: configuration privée `coordinator = {mode: "grok_coordinated", transport: "disabled"|"installed", bot_id: "identifiant fourni par l’application"}` et preuve de capacités fournie par l’adaptateur installé, jamais par un commit de l’agent. L’identifiant est non vide, au plus 128 caractères et ne contient aucun secret ; il reste privé.
- Produces: `coordinator_readiness(config: dict, capabilities: dict | None) -> dict`, projection fermée `world/coordinator.json` et état `WAITING_GROK_TRANSPORT`, `WAITING_GROK_RESUME`, `VALIDATING`, `READY`, `HALTED` ou `EXTINCT`.
- Capabilities exactes : `deliver_main`, `read_results`, `resume_grok`, `deduplicate_events`, toutes booléennes. `deliver_main` signifie livraison effective sur main : écriture directe ou mécanisme automatique de fusion/merge queue éprouvé ; une PR seule ne suffit pas. `automatic_resume_verified` ne devient vrai qu’après le parcours natif attesté dans la configuration administrative privée ; READY exige cette preuve.
- Pour produire cette preuve sans dépendance circulaire, la configuration administrative peut demander `validation_mode: true` et un `validation_mission_id` existant. Après identification du transport et contrôle de ses accès, ce mode autorise l’essai de cette seule mission et au plus deux reprises de Grok ; il publie VALIDATING avec `automatic_resume_verified: false`. L’essai ne peut activer READY lui-même. Le mode normal reste désactivé jusqu’à consignation de la preuve. Ces bornes concernent uniquement l’essai, pas les stratégies du monde en fonctionnement.

- [ ] Écrire `test_pr_only_transport_is_not_ready`, `test_automatic_delivery_to_main_is_eligible`, `test_missing_resume_stays_waiting`, `test_validation_mode_runs_without_claiming_ready`, `test_terminal_state_wins` et `test_coordinator_status_has_no_raw_account_data`. Vérifier le refus d’un relais PR-only même avec des logins valides, la portée à la mission d’essai et l’arrêt après deux reprises.
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

### Task 4: Livrer le résultat et obtenir une vraie reprise de Grok

**Files:**
- Create: `scripts/grok_transport.py`, `tests/test_grok_transport.py`, `tests/test_grok_loop.py`.
- Modify: `scripts/coordinator.py`, `scripts/supervisor.py`.

**Interfaces:**
- Consumes: adaptateur administrativement installé `/opt/globalland/integrations/grok` avec JSON stdin/stdout ; aucun exécutable tiré d’un chemin publié par l’agent.
- Produces: `GrokTransport.capabilities() -> dict`, `GrokTransport.deliver(event: dict) -> dict`, `GrokTransport.reconcile(event_id: str) -> dict` ; absence d’adaptateur = WAITING_GROK_TRANSPORT.
- Event exact : `event_id`, `bot_id`, `task_id`, `input_sha256`, `result_sha256`, `result_path`. `event_id` est le SHA-256 du JSON canonique des cinq derniers champs. Il est conservé à l’identique pendant les reprises et envoyé uniquement au transport privé.
- Réponse de transport : `event_id`, `bot_id`, `status` parmi `ACKED`, `UNKNOWN`, `UNSUPPORTED`. Les deux identifiants doivent correspondre à la requête. ACKED signifie livraison acceptée par le bon bot, pas décision suivante constatée. Le transport doit dédupliquer cet ID et reconnaître une livraison antérieure ; sinon l’autonomie complète reste non vérifiée.
- Outbox privée `state/private/grok-events/<event_id>.json`. `Coordinator.tick() -> dict` reprend d’abord cette outbox. Une livraison UNKNOWN passe par reconcile ; un ACKED n’est pas renvoyé.
- Le connecteur spécifique de l’application est hors réalisation tant que son identité et son mécanisme supporté ne sont pas connus. Choisir une liaison directe à GlobalLand si disponible, ou réutiliser Cursor si ses capacités sont établies. Un relais qui ne sait faire que des PR reste explicitement incomplet ; aucun endpoint ni API facturée n’est inventé.

- [ ] Écrire le scénario local : mission → DELEGATE Codex → proposition → livraison Grok fixture → nouvelle tâche EXEC → artefact → deuxième décision Grok fixture. Utiliser un Git local réel et des transports de modèle factices, comme les tests d’intégration existants.
- [ ] Ajouter les cas double livraison, accusé perdu, reprise du mauvais bot, sortie malformée, créateur PR-only et Cursor externe disponible avec CLI Cursor VPS indisponible. Exiger qu’aucun lot suivant ne soit recréé après un événement déjà reconnu.
- [ ] Observer les échecs ; implémenter le contrat, l’outbox et la reprise, sous le verrou partagé. Le mode coordonné remplace la stratégie directe du cycle think, sans exécuter les deux coordinateurs à la fois ; la configuration par défaut demeure inchangée.
- [ ] Vérifier l’absence de blocage circulaire : queue publie avant livraison ; le transport ne tente pas une commande superviseur synchrone depuis l’intérieur du verrou. Une session externe peut écrire des tâches GitHub pour le cycle suivant.
- [ ] Lancer les tests ciblés, puis les suites Python et Node existantes. Les traces restent privées et les projections publiques fermées.
- [ ] Commit : `feat(coordinator): deliver durable results to supported Grok transports`.

### Task 5: Vérifier le parcours réel et conserver la banque honnête

**Files:**
- Modify: `INSTALL.md`, `docs/INTEGRATIONS.md`, `docs/GROK.md`, `README.md`.
- Create: `docs/verification/YYYY-MM-DD-grok-loop.md` au jour de l’essai réel.
- Reuse: `tests/test_treasury.py`, `tests/test_gateway.py`, `tests/test_autonomous_integration.py`.

**Interfaces:**
- Consumes: release exacte revue, VPS de nouveau accessible et vérifié, identités officielles connectées, transport réel supporté et preuves des tâches/artefacts.
- Produces: rapport distinct des fixtures indiquant l’application, la release, les IDs, commits, empreintes, invocations et deux décisions successives de Grok. Sans cette preuve, `automatic_resume_verified` demeure faux.

- [ ] Exécuter les régressions financières existantes : deux réservations concurrentes de 3000 cents sur 5000 n’en acceptent qu’une ; UNKNOWN conserve ses fonds après redémarrage ; même reçu appliqué une fois ; faux reçu refusé ; EXTINCT reste terminal et Oria inchangée.
- [ ] Vérifier les prérequis Hostinger et le SHA réellement installé avant mise à niveau. Conserver credentials, état, journaux, outboxes et horaires ; suivre le retour arrière existant. Aucun effacement ou restauration d’un ancien solde.
- [ ] Activer le mode d’essai VALIDATING pour la mission choisie, sans activer READY. Effectuer cette mission sans dépense réelle depuis Grok, transmise sur main sans intervention terminal par mission. Vérifier sa délégation Codex, sa décision de suivi, l’artefact EXEC et le second retour vers Grok ; éprouver Claude séparément. Ne consigner `automatic_resume_verified` qu’après observation et rapport ; le passage au mode normal est distinct.
- [ ] Observer une interruption et sa reprise puis un déclenchement périodique. Recalculer les empreintes et distinguer proposition, tâche exécutée et résultat commercial.
- [ ] Documenter ce qui manque si l’application ne peut pas reprendre automatiquement ; ne pas activer un indicateur de réussite pour contourner cette dépendance. Banque et compte réel forment un chantier séparé : aucun dépôt inventé, aucun test financier factice importé dans la production.
- [ ] Commit du rapport factuel seulement après observation des résultats.

## Ce que le fondateur devra pouvoir faire

Écrire à Grok : « Choisis une première opportunité mondiale, utilise Codex et Claude pour avancer, et reviens avec un produit vérifiable. » Le système doit montrer où en est la mission et reprendre après une erreur. Une PR doit être annoncée comme proposition de développement ou livraison de tâche en attente, jamais comme preuve que les habitants ont déjà travaillé.
