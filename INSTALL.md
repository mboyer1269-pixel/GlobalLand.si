# Installation VPS, validation et retour arrière

Aucun déploiement n'a été effectué par cette PR. Ne pas activer les anciens cron dans `workspace/GlobalLand.si/scripts/`. Cette version change le protocole ; seules les tâches SHELL/AUDIT sont acceptées.

## Prérequis et identification exacte

Ubuntu/Debian, Python 3.12+, Git, Docker avec Compose v2, 1 Go de RAM disponible pour le worker et marge pour l'hôte. Vérifier les autres services, le disque, les sauvegardes et l'heure UTC. Le compte qui administre Docker est de confiance.

Après revue et fusion, choisir le **SHA Git complet de 40 caractères réellement fusionné**. Il est impossible de mettre son propre hash final dans le commit ; le champ Head de la PR permet d'identifier la version testée avant fusion. Si GitHub crée un merge/squash, relever le nouveau SHA puis vérifier que son contenu correspond.

```bash
REV=REMPLACER_PAR_LE_SHA_COMPLET_REVU
IMAGE=node:22-bookworm@sha256:REMPLACER_PAR_LE_DIGEST_VERIFIE

git clone https://github.com/mboyer1269-pixel/GlobalLand.si.git globalland-install
cd globalland-install
git checkout --detach "$REV"
git status --porcelain
node tests/runtime.test.js
python3 -m unittest discover -s tests -p 'test_*.py'
```

Obtenir le digest Node 22 Bookworm par un canal de confiance, puis télécharger cette image sur le VPS avant les tests. Ne pas utiliser le digest fictif d'un exemple. L'installeur exige le digest et refuse un arbre Git modifié.

## Première installation (sans démarrer d'automatisme)

```bash
sudo bash scripts/setup_vps.sh "$REV" "$IMAGE"
```

Le script refuse un `/opt/globalland` existant. Il installe le contrôle revu, crée un Git bare privé et une **nouvelle clé de déploiement dédiée**, affiche uniquement sa partie publique. Il ne lit aucune ancienne clé de production, ne configure aucune API, ne démarre aucun conteneur et n'installe aucun cron.

1. Enregistrer la clé publique dans les Deploy Keys de ce seul dépôt, avec write access.
2. Installer les clés hôte SSH GitHub vérifiées depuis une source officielle dans `/opt/globalland/ssh/known_hosts`, propriétaire root et mode 600. Ne pas accepter aveuglément `ssh-keyscan` et ne pas désactiver StrictHostKeyChecking.
3. Vérifier l'image et la configuration :

```bash
sudo docker image inspect "$IMAGE"
sudo docker compose -f /opt/globalland/control/compose.yml config --quiet
sudo ssh -i /opt/globalland/ssh/deploy_key -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/opt/globalland/ssh/known_hosts -T git@github.com
```

GitHub peut retourner le code SSH 1 tout en confirmant l'authentification et l'absence de shell. Confirmer le message et le dépôt dédié.

## Test réel obligatoire avant cron

Exécuter un cycle manuel sans clé API :

```bash
sudo python3 /opt/globalland/control/supervisor.py queue
sudo python3 /opt/globalland/control/supervisor.py daily
sudo python3 /opt/globalland/control/supervisor.py daily
```

Si TASK-0001 a déjà été traité, créer une nouvelle tâche selon `queue/PROTOCOL.md`, avec un nouvel ID, puis relancer queue. Sur GitHub, vérifier :

- résultat DONE et hash d'entrée correct ; entrée inbox retirée dans le même commit ;
- rapport `bank/audits/audit-YYYY-MM-DD.md` et ledger/log publiés ensemble ;
- second audit du même jour sans second DAY_TICK ni nouvelle baisse de grâce ;
- même tâche non réexécutée à la relance ; conteneurs temporaires supprimés ;
- configuration effective : UID 65534, aucun réseau/port, montage en lecture seule, RAM/CPU/PID limités.

Soumettre ensuite une tâche avec un **nouvel ID** et `action: node -p 1` : résultat REJECTED attendu, aucun code libre exécuté. Tester la reprise de publication dans un dépôt de préproduction : couper l'accès Git après exécution puis le rétablir ; le hash et le résultat doivent rester les mêmes, sans second lancement. Une divergence doit arrêter le cycle et préserver le journal.

Une sortie de commande seule ne certifie pas le déploiement : vérifier les commits distants et les journaux privés. Ne transmettre ni clés privées ni contenu confidentiel du journal au bot.

## Cron et surveillance

Seulement après les tests précédents : dans le crontab **root**, installer ces lignes qui exécutent le contrôle installé, jamais le dépôt mutable. Utiliser explicitement bash pour les wrappers installés en mode 644 :

```cron
*/5 * * * * /bin/bash /opt/globalland/control/queue_runner.sh >> /var/log/globalland-queue.log 2>&1
0 8 * * * /bin/bash /opt/globalland/control/daily_audit.sh >> /var/log/globalland-audit.log 2>&1
```

08 h est l'heure de l'hôte ; les dates comptables sont UTC. Le verrou commun sérialise les deux. Configurer logrotate pour les deux fichiers `/var/log/globalland-*.log`, rotation quotidienne, conservation 14 jours, mode 600. Surveiller un rapport manquant, un statut INTERRUPTED ou une erreur du superviseur. Aucun service de notification n'est configuré par cette PR.

## Reprise et incidents

- **Push refusé/réseau indisponible** : préserver `state/` et `source.git`. Rétablir l'accès puis relancer le même cycle ; le résultat terminal sera publié sans exécuter à nouveau l'action. Une file vide n'empêche pas la reprise.
- **Historique divergent** : arrêter cron, sauvegarder. Réconcilier explicitement le commit local préparé et le ledger distant dans une branche de revue. Aucun force-push, reset ou rebase automatique.
- **Tâche INTERRUPTED** : examiner le journal privé et le résultat ; créer une nouvelle tâche avec un nouvel ID seulement après revue. Ne pas effacer le journal pour réutiliser l'ID.
- **Audit quotidien INTERRUPTED** : les cycles s'arrêtent pour revue opérateur. Après arrêt de cron et sauvegarde, vérifier `source.git` et GitHub : le ledger du jour et son journal sont-ils déjà committés/poussés ? Préserver le fichier `state/DAILY-date.json` dans un sous-dossier privé `state/quarantine/` avec une note d'incident, puis relancer daily seulement après rapprochement. Le tick UTC empêche un deuxième débit de grâce si le jour est déjà au ledger. Ne pas marquer un audit PUBLISHED sans vérifier sa publication.
- **Secret détecté** : arrêt et traitement privé ; aucun contournement du filtre. Si le secret était déjà soumis à GitHub, le révoquer selon la procédure du propriétaire.

## Sauvegarde, mise à niveau et retour arrière

Arrêter les deux entrées cron et attendre la fin du cycle sous verrou. Sauvegarder ensemble `/opt/globalland/control`, `state`, `source.git` et `ssh` dans une archive **privée**, chiffrée hors hôte, réservée à l'administrateur. Elle contient la mémoire anti-rejeu et la clé dédiée ; ne jamais la pousser sur GitHub.

Une mise à niveau du dépôt ne remplace jamais automatiquement `control/`. Préparer une nouvelle version depuis un SHA revu, exécuter ses tests, comparer les schémas de tâches/journaux/ledger et l'image, sauvegarder puis remplacer le contrôle administrativement. Cette première version ne fournit pas de migration automatique depuis l'ancienne installation ; conserver l'ancien arbre hors montages et procéder comme une nouvelle installation après sauvegarde.

Pour revenir en arrière : désactiver cron, attendre le verrou, sauvegarder l'état courant, restaurer le précédent `control/` et sa configuration d'image. Conserver `state/` et les commits préparés si le schéma est compatible ; sinon réconcilier manuellement avant reprise. **Ne jamais restaurer un ancien ledger ou effacer state indépendamment**, sous peine de perdre des écritures ou de rejouer des tâches. Ne pas réactiver les anciens runners vulnérables. Relancer les tests manuels avant cron.

Aucune suppression de serveur, aucun archivage du dépôt et aucun achat ne font partie de cette procédure automatisée.
