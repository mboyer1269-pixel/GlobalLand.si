# Installer GlobalLand v3

Prérequis : Ubuntu/Debian, Python3.12+, Git, Docker Compose, image Node22 vérifiée et environ1Go disponible pour une tâche isolée. Les services Oria restent séparés. Ne lancer aucun code depuis un checkout modifiable par les agents dans le cron.

Pour une nouvelle installation, télécharger un SHA complet revu, vérifier un arbre Git propre et exécuter `sudo bash scripts/setup_vps.sh SHA_COMPLET node:22-bookworm@sha256:DIGEST_VERIFIE`. L'installeur crée `/opt/globalland`, contrôle séparé, Git bare et clé dédiée ; il ne démarre ni modèle ni cron. Après cette préparation, enregistrer uniquement la clé publique `ssh/deploy_key.pub` comme Deploy Key d'écriture sur ce dépôt. Installer les clés hôte GitHub vérifiées dans `ssh/known_hosts` mode600 avec StrictHostKeyChecking=yes ; ne jamais publier la clé privée. Finaliser ensuite avec `sudo bash /opt/globalland/control/finalize_setup.sh` ; le clone SSH fonctionne aussi pour un dépôt privé.

Sur une installation existante v2, suivre la mise à niveau ci-dessous ; ne pas relancer l'installeur initial. Lire SECURITY.md, CODE.md et queue/PROTOCOL.md. Les placeholders SHA/digest/version doivent être remplacés par les valeurs réellement vérifiées, pas copiés littéralement.

# Mise à niveau vers le monde autonome v3

L'installation v2 continue de fonctionner tant que le contrôle v3 n'a pas été installé explicitement. Ne jamais exécuter un nouveau superviseur depuis le dépôt mutable. Utiliser un nouveau checkout propre au SHA complet revu/fusionné.

```bash
GIT_SSH_COMMAND='ssh -i /opt/globalland/ssh/deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/opt/globalland/ssh/known_hosts' \
  git clone git@github.com:mboyer1269-pixel/GlobalLand.si.git /root/globalland-v3
cd /root/globalland-v3
git checkout --detach SHA_COMPLET_REVU
sudo bash scripts/upgrade_vps.sh SHA_COMPLET_REVU
sudo python3 /opt/globalland/control/supervisor.py status
```

Le script suspend temporairement uniquement les fichiers cron globalland (queue/daily) et globalland-think s'ils existent, attend leur verrou partagé, sauvegarde contrôle/état/Git/clé dédiée/releases, installe une release versionnée et conserve les credentials. Le piège de sortie restaure aussi les horaires déjà suspendus si la préparation échoue à mi-chemin ; les copies sont conservées sous backups/upgrade-date/cron-globalland et cron-globalland-think. Il ne lance aucun modèle et ne prétend pas avoir financé la Banque. Ne jamais supprimer les SQLite/WAL/journaux pour changer de version. Le fichier `backups/upgrade-date/state-before.tgz` est privé et contient la clé dédiée ; ne pas le publier.

## Smoke test gratuit de v3

Après la mise à niveau : `status` doit montrer le monde et ses agents, une Banque UNFUNDED si aucune preuve réelle n'a été intégrée et un contrôleur en attente. Soumettre une tâche TOOL/WORLD créant une mission, puis une tâche EXEC produisant un petit README sous products/. Vérifier le produit et son reçu de hash sur GitHub ; le solde CAD ne doit pas être inventé. Le test `tests/test_docker_smoke.py` peut également être exécuté avec `GLOBALLAND_DOCKER_SMOKE=1` depuis le checkout après téléchargement de Node22.

## Codex et Claude Code avec les abonnements

Les documents officiels et les étapes se trouvent dans docs/INTEGRATIONS.md. Ne jamais coller un token de connexion dans GitHub ou dans la conversation. La procédure utilise seulement les CLIs officielles, pas une extraction de leur OAuth pour appeler une API.

1. Construire une image privée avec des versions officielles exactes et une base Node identifiée par digest :

```bash
docker build -f docker/Brain.Dockerfile \
  --build-arg BASE_IMAGE=node:22-bookworm@sha256:DIGEST_VERIFIE \
  --build-arg CODEX_VERSION=VERSION_OFFICIELLE_EXACTE \
  --build-arg CLAUDE_CODE_VERSION=VERSION_OFFICIELLE_EXACTE \
  -t globalland-brain:VERSION .
docker image inspect globalland-brain:VERSION --format '{{.Id}}'
```

Un ID local immuable `sha256:...` convient, sans imposer un registre payant. Vérifier les versions et flags avec `--help` ; le contrôleur refuse les options requises absentes. Les placeholders ne sont pas des versions à copier telles quelles.

2. Connecter les abonnements personnellement dans le terminal privé :

```bash
sudo bash /opt/globalland/control/login_subscriptions.sh codex sha256:ID_IMAGE
sudo bash /opt/globalland/control/login_subscriptions.sh claude sha256:ID_IMAGE
```

Codex ouvre une connexion ChatGPT par code d'appareil. Claude ouvre sa connexion officielle. Vérifier que les plans incluent ces CLIs. Désactiver l'extra usage, les achats/recharges de crédits et les bascules facturées dans les comptes utilisés. Les abonnements déjà payés sont distincts du capital50 ; cette version ne doit déclencher aucune facturation supplémentaire à leur nom.

3. Vérifier sans inférence, puis activer la configuration :

```bash
sudo python3 /opt/globalland/control/configure_subscriptions.py \
  --image sha256:ID_IMAGE --providers codex,claude \
  --confirm-extra-usage-disabled
sudo python3 /opt/globalland/control/supervisor.py think
sudo python3 /opt/globalland/control/supervisor.py queue
```

Pour donner au cerveau Claude ses outils GlobalLand pendant un tour (plusieurs actions observées par cycle), ajouter `--broker on` ; `--broker off` les retire ; sans l'option, le réglage actuel est conservé. Valeurs par défaut : 40 appels, 20 actions, 900 secondes et 40 tours de modèle par cycle (`controller.broker` dans config.json). Lancer ensuite un `think` manuel et vérifier `state/broker/THINK-*/calls.jsonl` et les résultats publiés avant de réactiver l'horaire.

**Codex avec les outils (optionnel, à éprouver d'abord).** Par défaut, seul Claude reçoit le courtier ; Codex reste à une décision par cycle. Pour l'ajouter : `--broker-providers claude,codex`. Codex reçoit alors uniquement le serveur `globalland`, limité à ses cinq outils, pré-approuvé (le courtier hôte valide et budgète chaque appel) et requis au démarrage. Un pont cassé fait échouer le tour Codex, puis la bascule passe à Claude, au lieu de tourner sans outils. Ces réglages viennent du code source officiel de Codex (`enabled_tools`, `default_tools_approval_mode`, `required`, `tool_timeout_sec`) et n'ont pas été exécutés avec la CLI de l'image du VPS. Après activation : lancer un `think` manuel, puis vérifier que `state/broker/THINK-*/calls.jsonl` contient des appels pendant un tour Codex. Sinon : `--broker-providers claude`.

Le drapeau d'attestation suppose que tu as effectivement vérifié les comptes. Il n'est pas une preuve automatisée de leur facturation. Pour utiliser un seul abonnement, fournir `--providers codex` ou `--providers claude`. Aucun repli API ni achat de crédits n'est effectué si un quota est atteint.

Vérifier une décision THINK, des tâches produites et leurs résultats/artefacts sur GitHub avant d'activer la réflexion périodique. Après les tours réellement publiés de Codex et Claude, l'opérateur root peut lancer depuis son checkout administratif au SHA exact revu :

```bash
python3 scripts/start_autonomy.py
```

Le script recontrôle le service cron, la version installée, les tours publiés et les connexions CLI. Il conserve les attestations d'usage existantes, sauvegarde la configuration puis sélectionne codex/claude. L'image et la connexion Cursor restent en place ; Cursor n'est pas sélectionné pour ces tours automatiques. Il écrit atomiquement un unique horaire toutes les30 minutes, sans remplacer un horaire différent existant et sans toucher aux tâches queue/daily ou Oria. Un échec d'installation de l'horaire avant sa publication restaure la configuration précédente. Le cron appelle exclusivement le contrôle installé, jamais le checkout administratif. Aucune mise à niveau du contrôle ou de l'image n'est nécessaire pour cette opération.

L'horaire dédié `/etc/cron.d/globalland-think` mode644 contient :

```cron
*/30 * * * * root /usr/bin/python3 /opt/globalland/control/supervisor.py think >> /var/log/globalland/think.log 2>&1 && /usr/bin/python3 /opt/globalland/control/supervisor.py queue >> /var/log/globalland/think.log 2>&1
```

Le script effectue ensuite un lancement immédiat think/queue. Son retour sans erreur ne suffit pas à qualifier chaque tâche de réussie : vérifier les nouveaux résultats et leurs artefacts dans GitHub, puis un tour ultérieur déclenché à :00 ou :30 avec le journal `/var/log/globalland/think.log`. Les connexions et quotas restent des dépendances réelles ; aucun résultat commercial n'est garanti. Le verrou est commun aux trois cycles et la rotation `/var/log/globalland/*.log` couvre le nouveau journal. Pour arrêter la réflexion périodique, déplacer seulement ce fichier cron dans le dossier de sauvegarde privée ; garder queue/daily pour la reprise des travaux déjà soumis. La configuration antérieure se trouve dans le dossier backups/autonomy-* annoncé par le script ; ne pas restaurer un ancien solde ou rejouer des opérations financières.

Un lancement immédiat en échec après « horaires installés » laisse l'horaire installé ; ces deux faits sont distincts. Contrôler world/controller.json : last_turn décrit les essais de modèles et reason_code explique un blocage sans exposer d'exception brute. Un échec transitoire peut être repris par un autre abonnement configuré ; la reprise conserve les contrôles de chaque tâche. Attendre la fin d'une opération Hostinger avant toute installation et vérifier ensuite l'intégrité de l'état et des services ; ne déduire ni une migration ni une réinstallation du seul message d'attente.

## Apify Store (premier rail de revenu)

1. Créer un compte Apify au nom du fondateur, faire la vérification d'identité exigée pour la monétisation, et définir un nom d'utilisateur.
2. **Plafonner les coûts : rester sur le plan gratuit, sans carte.** Il donne 5 $ de crédits de plateforme par mois. Une fois ces crédits épuisés, le compte est bloqué jusqu'au cycle suivant, sans facture : c'est un plafond réel (page officielle des tarifs, vérifiée le 2026-11-01). Ne pas ajouter de carte : un plan payant facture les dépassements. Les constructions et essais d'Actors consomment ces crédits ; les exécutions des clients d'un Actor à l'événement sont déduites des gains, jamais facturées au développeur.
3. Créer un token API et l'installer sans jamais le coller dans GitHub ni dans un chat :

```bash
sudo install -d -m 700 /opt/globalland/credentials/apify
sudo sh -c 'umask 077; cat > /opt/globalland/credentials/apify/token'   # coller le token, Entrée, Ctrl-D
```

4. Activer dans `/opt/globalland/control/config.json` : `"apify": {"enabled": true, "max_event_price_usd": 0.05, "allow_public": false, "require_review": true, "build_wait_seconds": 240}`. `require_review` impose la règle des deux clés : une mise en vente publique exige l'approbation (WORLD `review`) de la version exacte des sources par un agent autre que celui qui publie. Laisser `allow_public` à false jusqu'à la vérification d'une première construction privée, puis le passer à true.

## Cloudflare : sites publics (PUBLISH_SITE)

1. Créer un compte Cloudflare gratuit au nom du fondateur, puis choisir un sous-domaine workers.dev (Workers & Pages > Overview).
2. Créer un token API **limité à ce compte** avec la seule permission « Workers Scripts : Edit ». Cloudflare ne permet pas de restreindre un token à un seul script : l'hôte ne touche donc qu'aux scripts préfixés `globalland-`.
3. Installer le token sans le coller dans GitHub ni dans un chat :
   ```bash
   sudo install -d -m 700 /opt/globalland/credentials/cloudflare
   sudo sh -c 'umask 077; cat > /opt/globalland/credentials/cloudflare/token'   # coller, Entrée, Ctrl-D
   ```
4. Activer dans `config.json` : `"cloudflare": {"enabled": true, "account_id": "<32 caractères hexadécimaux>", "script_prefix": "globalland-", "require_review": true}`.
5. Coupure d'urgence d'un site : tâche `PUBLISH_SITE {"site": "<nom>", "online": false}`, sans revue.

## Vérifier que tout est prêt

```bash
sudo python3 /opt/globalland/control/preflight.py
```
Le verdict GO ou NO-GO liste chaque manque avec sa correction, sans jamais afficher un secret. Les éléments OPTIONAL (courtier, Apify, Cloudflare) n'empêchent pas le démarrage.

## Être prévenu quand le monde s'arrête

Le workflow `.github/workflows/watchdog.yml` vérifie `main` chaque heure, depuis GitHub, sans le VPS. Si le superviseur se tait plus de 2 h, si le contrôleur est bloqué, STALE ou DEGRADED, ou si des actions attendent le fondateur, il ouvre une issue « GlobalLand : le monde a besoin d'attention ». GitHub envoie un courriel à l'ouverture, puis l'issue est mise à jour en silence. Elle se ferme d'elle-même au rétablissement. Le workflow s'active une fois fusionné dans `main`.

## Le monde est muet ou bloqué : triage en une commande

L'outil fonctionne depuis n'importe quelle copie du dépôt, même si la version installée est ancienne. Il ne modifie rien et n'affiche aucun contenu de fichier ni de journal : seulement des codes d'erreur fixes, des âges, des compteurs et la correction de chaque constat. Sa sortie peut être recollée telle quelle dans un chat ou une issue.

```bash
# Le dépôt est privé : copier le fichier depuis ton poste (ou le coller dans `sudo tee /tmp/incident.py`).
scp scripts/incident.py <vps>:/tmp/incident.py
sudo python3 -I /tmp/incident.py /opt/globalland
```
Constats possibles, du plus grave au moins grave :
- un cycle coincé qui tient le verrou ;
- des cycles en pause après une mise à jour interrompue, avec la commande de restauration ;
- cron qui ne lance plus rien ;
- Docker arrêté ;
- conteneurs restants, disque plein ou connexion absente ;
- code d'échec du planificateur, avec le détail par fournisseur.

Ne jamais supprimer `state/` ni les journaux pour « débloquer ».

## Revue d'une mise en vente par le fondateur

Si un seul fournisseur IA est configuré, ou pour trancher une revue :
```bash
sudo python3 /opt/globalland/control/review_admin.py approve --actor <nom> --digest <review_digest>
sudo python3 /opt/globalland/control/review_admin.py approve --site <nom> --digest <review_digest>
```

### Chaque mois : versements Apify vers la Banque

Apify n'expose aucune API de versement. Deux gestes du fondateur, moins de 5 minutes par mois :

1. **Du 11 au 14 :** dans la console Apify (Development > Insights > Payouts), vérifier et approuver la facture, puis l'enregistrer comme **créance**. Ce n'est pas de l'argent et elle n'est jamais dépensable :
   ```bash
   sudo python3 /opt/globalland/control/payouts.py invoice --month 2026-11 --usd 23.40
   ```
2. **Après réception (du 21 au 25) :** sur un compte dédié à GlobalLand (Wise ou PayPal, seuil de 20 $ US ; 100 $ US par virement), convertir en CAD, puis enregistrer le montant **réellement reçu** :
   ```bash
   sudo python3 /opt/globalland/control/payouts.py received --month 2026-11 \
     --cad-cents 3180 --method WISE --reference ID_TRANSACTION --evidence /root/releve-2026-11.pdf
   ```

La Banque reçoit un REVENUE marqué `attestation: FOUNDER` et publie `founder_attested_revenue_cents` à part du revenu vérifié automatiquement. Seules les empreintes de la référence et du relevé sont conservées, jamais leur contenu. La commande refuse un mois sans facture et un taux CAD/USD hors de 1,0 à 2,0 (protection contre les fautes de frappe), sauf avec `--force`. Relancer la même commande ne crédite rien deux fois ; un autre montant pour le même mois est refusé. `payouts.py status` affiche les créances. `bank/status.json` les publie sous `receivables`.

## Banque réelle

Le monde peut faire du travail gratuit avec les abonnements connectés avant le dépôt. La Banque reste UNFUNDED tant qu'un service réel dédié et son vérificateur ne sont pas configurés. Voir docs/INTEGRATIONS.md pour les possibilités ; aucun faux reçu fourni dans les tests ne doit être importé dans l'instance réelle.

L'adaptateur privé `/opt/globalland/integrations/finance` est exécuté uniquement par le contrôle hôte. Il doit fournir quote/submit/reconcile/verify et vérifier les preuves du service choisi. Les agents ne reçoivent ni carte ni clé de retrait. Une attestation JSON ne constitue pas à elle seule un plafond fournisseur. L'ouverture/KYC et le dépôt réel restent à effectuer par le propriétaire du compte.

## Retour arrière v3

Désactiver seulement les cron GlobalLand (queue/daily/think), attendre le verrou et conserver une sauvegarde privée de l'état courant. Repointer `control` vers la release précédente conservée ; restaurer sa configuration et uniquement ses horaires compatibles. Ne pas supprimer les journaux de paiements, restaurer un vieux solde ou relancer un ancien paiement. Si v3 a engagé des opérations, les rapprocher avant de réactiver v2 ; v2 ne connaît pas cette trésorerie et n'est pas un moteur productif de secours. Oria reste en place.

## Ajouter Cursor à l'image existante

Après récupération du SHA revu, utiliser le constructeur dédié :

```bash
bash scripts/build_cursor_image.sh
```

Un ID local sha256:... passé directement à FROM est interprété comme un nom de dépôt par BuildKit et provoque pull access denied. Le script vérifie l'image locale, lui attribue un tag GlobalLand dérivé de son ID complet, vérifie ce tag avant/après construction et fournit cette référence avec --pull=false. Il vérifie la version sans réseau, puis enregistre atomiquement le nouvel ID dans state/private/cursor-image.txt. L'ancien brain-image.txt reste inchangé. Il ne publie aucune image et ne touche à aucun conteneur existant.

Lancer ensuite login_subscriptions.sh cursor avec l'ID de cette nouvelle image. Conserver l'ancien brain-image.txt tant que les trois vérifications ne passent pas ; ne pas écraser les volumes Codex/Claude. Une fois les logins et facturations vérifiés, configurer l'image étendue avec --providers codex,claude,cursor. Le simple login ne démarre aucune pensée et aucun achat. Le contrôleur utilise Cursor en mode ask et garde l'exécution dans les outils de GlobalLand.

Avant le premier think avec Cursor, consulter SECURITY.md et tester les lectures/recherches avec un canari aléatoire sans secret placé hors /tmp dans son HOME privé. Inspecter la trace privée pour vérifier que les tentatives Read/Grep/Glob sont refusées, et non simplement omises par le modèle. Ne jamais tester en lisant un vrai fichier d’authentification. Un simple statut Logged in et des tests factices ne valident pas cette frontière. Ne pas activer le cron think avant cette vérification et un cycle productif vérifié.

La commande installée `python3 /opt/globalland/control/verify_cursor_canary.py` réalise ce diagnostic sur l'image configurée, avec le verrou partagé et nettoyage de ses fichiers de test. REVIEW_REQUIRED n'est pas un PASS ; examiner le rapport puis les événements utiles de la trace privée. La CLI productive utilise `--trust` uniquement pour sa racine /tmp temporaire isolée ; ses règles d'outils ne changent pas. Ce correctif nécessite seulement la mise à jour du contrôle au SHA exact, sans reconstruire l'image ni reconnecter les comptes.
