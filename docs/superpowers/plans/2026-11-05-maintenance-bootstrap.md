# Maintenance reproductible — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline implementation, with one fresh whole-branch review.

**Goal:** Préparer et installer de façon vérifiable les horaires queue/daily/mail et la rotation des journaux d'une installation GlobalLand neuve.

**Architecture:** Un outil administratif distinct produit un aperçu sans mutation et applique uniquement ses configurations reconnues. Il conserve les horaires personnalisés en refusant de les remplacer, sauvegarde les fichiers gérés et restaure leur contenu si l'installation échoue. Le moteur, les permissions et le choix des agents sont inchangés.

**Tech Stack:** Python 3.12, bibliothèque standard, cron et logrotate sous Ubuntu/Debian avec systemd.

**Spec:** Audit `../globalland-graphify-20261105/AUDIT.md`, section bootstrap/reproductibilité ; `VISION.md`, `docs/MANDAT-DEVELOPPEMENT.md`. Le diagnostic est confirmé : setup/finalize créent contrôle/source sans horaires ; start_autonomy ne crée que think ; AgentMail suppose un fichier cron existant. Lecture distante du 5 novembre : queue/mail toutes les 5 minutes, daily à 08:00 selon l'horloge du serveur, logrotate.timer actif. Le VPS existant n'est pas dépourvu d'horaires.

## Global Constraints

- Aucun cron ni modèle démarré par `setup_vps.sh` ou par le mode aperçu. L'opérateur active explicitement la maintenance après vérification du contrôle/source/image.
- Aucune modification de la configuration des modèles, de World, Treasury, des clés ou du mandat. Aucun accès ou paiement nouveau. Ne pas lancer think, queue, mail ou daily dans l'installateur.
- Le fichier `/etc/cron.d/globalland-think` reste entièrement géré par start_autonomy. Les horaires de base restent dans `/etc/cron.d/globalland`, suspendu par l'upgrader actuel.
- Rotation dans `/etc/logrotate.d/globalland`, exécutée par le logrotate.timer système actif. Pas de service système activé/modifié par cet outil.
- Queue/mail : `*/5 * * * *`; daily : `0 8 * * *`, horloge du serveur explicitement indiquée. Un verrou non bloquant propre à chaque horaire empêche l'empilement ; le superviseur garde son verrou global.
- Logs précis seulement : queue.log, daily.log, think.log et mail-cron.log. `daily`, `rotate 7`, `maxsize 10M`, `missingok`, `notifempty`, `compress`, `delaycompress`, `create 0600 root root`, `su root root`. Pas de copytruncate, ni suppression des états/reçus. maxsize est évalué au passage de logrotate, pas une borne disque instantanée.
- Mail absent par défaut ; activation explicite après configuration/test réel existants. Un appel ultérieur sans option conserve le mail déjà géré. Les fichiers custom, liens symboliques de destination et permissions d'écriture non administratives sont refusés, sans écrasement.
- Les tests sur fichiers et faux contrôles systemctl ne prouvent pas la reconstruction complète d'une VM ni l'authentification de ses comptes. Cette limite doit rester explicite.

## Review Focus

1. Configuration personnalisée ou liée : préserver strictement, pas d'écrasement silencieux (Task 1).
2. Échec après remplacement/fsync : restaurer les deux fichiers cohérents, conserver la sauvegarde si le retour échoue (Task 1).
3. Réexécution et ajout de mail : pas de désactivation involontaire, même rendu idempotent (Task 1).
4. Service cron/rotation absent, commande obsolète ou source non initialisée : refus avant installation active (Task 1).
5. Rotation pendant une écriture : préserver le fichier ouvert par renommage et compression différée ; aucun wildcard sur les données financières (Task 2).

### Task 1: Aperçu et installation des dépendances d'exploitation

**Files:** Create `scripts/install_maintenance.py`, `tests/test_install_maintenance.py`.

**Interfaces:** `Paths(root, cron, rotation, logs)` contient les chemins absolus d'installation (injection de chemins temporaires dans les tests). `preview(paths, with_mail=None) -> dict` inspecte sans écrire et rend templates, empreintes/états des destinations et prérequis. `install(paths, with_mail=None, run=subprocess.run) -> dict` vérifie cron/logrotate.timer et logrotate --debug, prend le verrou superviseur, sauvegarde et installe ; retourne revision, changements et chemin de sauvegarde, sans données de configuration privée.

- [x] Écrire d'abord les tests d'installation vierge, aperçu sans mutation, idempotence, mail facultatif/conservé, custom/refus, liens, service inactif, rollback après remplacement et verrou occupé.
- [x] Exécuter `python3 -B -m unittest discover -s tests -p test_install_maintenance.py -q` : échec attendu, module absent. Conserver la preuve RED.
- [x] Implémenter les deux opérations et le CLI (aperçu par défaut, `--apply`, `--with-mail`). Vérifier SHA installé, source bare présente, exécuteur configuré ; ne lire aucun contenu de credential. Sorties limitées aux fichiers de maintenance et répertoires privés de sauvegarde/logs.
- [x] Rejouer les tests, puis les suites start_autonomy/preflight/upgrade existantes. Attendu : succès et invariants conservés.
- [x] Commit autonome.

### Task 2: Procédure d'installation et preuves de reconstruction

**Files:** Modify `INSTALL.md`, `docs/AGENTMAIL.md`, messages `scripts/setup_vps.sh` / `scripts/finalize_setup.sh`; extend `tests/test_install_maintenance.py` if a verified integration needs a regression.

**Interfaces:** Utilise le CLI de Task 1 ; aucune nouvelle interface runtime.

- [x] Documenter ordre : prérequis système → setup SHA/image → deploy key/known_hosts/finalize → cycle manuel queue/daily vérifié → aperçu/apply maintenance → configuration/vérification modèles puis start_autonomy → mail explicite après test.
- [x] Remplacer l'hypothèse d'un cron existant par la commande nouvelle pour une installation neuve. Conserver une voie manuelle documentée pour les horaires personnalisés ; ne pas les adopter automatiquement.
- [x] Vérifier le fichier avec un vrai `logrotate --debug` et une rotation forcée sur des logs synthétiques dans un environnement isolé si le binaire est disponible. Sinon consigner la vérification manquante et la préparer en CI Ubuntu ; aucun changement de journaux réels.
- [x] Suite Python/Node complète et tests Linux ciblés. Relecture indépendante finale ; aucune installation sur le VPS dans cette phase.
- [x] Commit documentation/preuves, préparer PR intégrable. Déploiement distinct selon autorisation.
