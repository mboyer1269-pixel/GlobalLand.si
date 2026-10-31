# Installer GlobalLand v3

Prérequis : Ubuntu/Debian, Python3.12+, Git, Docker Compose, image Node22 vérifiée et environ1Go disponible pour une tâche isolée. Les services Oria restent séparés. Ne lancer aucun code depuis un checkout modifiable par les agents dans le cron.

Pour une nouvelle installation, télécharger un SHA complet revu, vérifier un arbre Git propre et exécuter `sudo bash scripts/setup_vps.sh SHA_COMPLET node:22-bookworm@sha256:DIGEST_VERIFIE`. L'installeur crée `/opt/globalland`, contrôle séparé, Git bare et clé dédiée ; il ne démarre ni modèle ni cron. Enregistrer uniquement la clé publique `ssh/deploy_key.pub` comme Deploy Key d'écriture sur ce dépôt. Installer les clés hôte GitHub vérifiées dans `ssh/known_hosts` mode600 avec StrictHostKeyChecking=yes ; ne jamais publier la clé privée.

Sur une installation existante v2, suivre la mise à niveau ci-dessous ; ne pas relancer l'installeur initial. Lire SECURITY.md, CODE.md et queue/PROTOCOL.md. Les placeholders SHA/digest/version doivent être remplacés par les valeurs réellement vérifiées, pas copiés littéralement.

# Mise à niveau vers le monde autonome v3

L'installation v2 continue de fonctionner tant que le contrôle v3 n'a pas été installé explicitement. Ne jamais exécuter un nouveau superviseur depuis le dépôt mutable. Utiliser un nouveau checkout propre au SHA complet revu/fusionné.

```bash
git clone https://github.com/mboyer1269-pixel/GlobalLand.si.git /root/globalland-v3
cd /root/globalland-v3
git checkout --detach SHA_COMPLET_REVU
sudo bash scripts/upgrade_vps.sh SHA_COMPLET_REVU
sudo python3 /opt/globalland/control/supervisor.py status
```

Le script désactive temporairement uniquement le fichier cron GlobalLand, attend son verrou, sauvegarde contrôle/état/Git/clé dédiée/releases, installe une release versionnée et conserve les credentials. Il restaure les anciens horaires queue/daily ; il ne lance aucun modèle et ne prétend pas avoir financé la Banque. Ne jamais supprimer les SQLite/WAL/journaux pour changer de version. Le fichier `backups/upgrade-date/state-before.tgz` est privé et contient la clé dédiée ; ne pas le publier.

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

Le drapeau d'attestation suppose que tu as effectivement vérifié les comptes. Il n'est pas une preuve automatisée de leur facturation. Pour utiliser un seul abonnement, fournir `--providers codex` ou `--providers claude`. Aucun repli API ni achat de crédits n'est effectué si un quota est atteint.

Vérifier une décision THINK, des tâches produites et leurs résultats/artefacts sur GitHub avant d'activer la réflexion périodique. Ajouter ensuite dans un fichier dédié `/etc/cron.d/globalland-think` mode644 :

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/5 * * * * root /usr/bin/python3 /opt/globalland/control/supervisor.py think >> /var/log/globalland/think.log 2>&1
```

Le verrou est commun aux trois cycles ; les agents pensent et travaillent entre les cycles. La rotation `/var/log/globalland/*.log` existante couvre ce nouveau journal. Ne pas toucher aux cron ou conteneurs Oria.

## Banque réelle

Le monde peut faire du travail gratuit avec les abonnements connectés avant le dépôt. La Banque reste UNFUNDED tant qu'un service réel dédié et son vérificateur ne sont pas configurés. Voir docs/INTEGRATIONS.md pour les possibilités ; aucun faux reçu fourni dans les tests ne doit être importé dans l'instance réelle.

L'adaptateur privé `/opt/globalland/integrations/finance` est exécuté uniquement par le contrôle hôte. Il doit fournir quote/submit/reconcile/verify et vérifier les preuves du service choisi. Les agents ne reçoivent ni carte ni clé de retrait. Une attestation JSON ne constitue pas à elle seule un plafond fournisseur. L'ouverture/KYC et le dépôt réel restent à effectuer par le propriétaire du compte.

## Retour arrière v3

Désactiver seulement les cron GlobalLand (queue/daily/think), attendre le verrou et conserver une sauvegarde privée de l'état courant. Repointer `control` vers la release précédente conservée ; restaurer sa configuration et uniquement ses horaires compatibles. Ne pas supprimer les journaux de paiements, restaurer un vieux solde ou relancer un ancien paiement. Si v3 a engagé des opérations, les rapprocher avant de réactiver v2 ; v2 ne connaît pas cette trésorerie et n'est pas un moteur productif de secours. Oria reste en place.
