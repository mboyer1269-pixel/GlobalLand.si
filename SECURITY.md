# Sécurité du canal VPS — version 2

Cette version remplace les affirmations de l'audit du 2026-10-30. Les anciens préfixes de commandes et `approved_by: CEO` ne constituaient pas des barrières suffisantes.

## Invariants appliqués

- Le code hôte est copié dans `control/` par une installation administrateur sur commit précis ; le dépôt distant ne peut pas le mettre à jour par une tâche.
- Le conteneur n'exécute que le code de contrôle installé, avec deux opérations : AUDIT gratuit et audit quotidien interne. AGENT_CODE est désactivé sans exception.
- Export éphémère sans Git, sans liens, monté en lecture seule ; contrôle monté en lecture seule. Aucun port, réseau, secret ni socket Docker. UID 65534, rootfs en lecture seule, toutes capacités retirées, no-new-privileges, RAM/CPU/PID bornés.
- Le Git bare privé, son index temporaire et la clé SSH ne sont jamais montés. Publication via objets Git, sans checkout, hook ou interprétation de `.gitattributes` téléchargés.
- Verrou hôte commun, journal atomique avec fsync, hash des octets de tâche. RUNNING avant lancement ; résultats durables avant commit. Pas de réexécution après une interruption ou un échec de push.
- Seuls ledger, journal financier, rapport quotidien et résultat de tâche peuvent être publiés. Les sorties sont plafonnées et scannées avant publication ; les erreurs interrompent le cycle.
- Les empreintes SSH GitHub doivent être vérifiées et préinstallées ; StrictHostKeyChecking=yes. Deploy Key limitée à ce dépôt.

## Limites explicites

Le CEO, l'administrateur du VPS et toute personne pouvant remplacer `control/`, modifier `state/` ou utiliser Docker sont de confiance. Docker et le noyau restent des dépendances de sécurité. Aucun confinement absolu n'est promis.

Le filtre de secrets recherche notamment les clés sk-, tokens GitHub et blocs PEM. Il ne détecte pas toutes les valeurs possibles, encodages, informations personnelles ou secrets métier. Ne soumettre aucune donnée confidentielle à ce dépôt public. Les refus ne republient pas le contenu de tâche dans leur sortie.

Les dépenses API sont impossibles par le registre actuel. La primitive Ed25519 est testée mais aucun circuit d'approbation payante n'est activé. La vérification du ledger contrôle sa cohérence interne, pas l'authenticité des déclarations du CEO ni la réalité des comptes bancaires.

Un push concurrent divergent arrête la publication : pas de force-push, reset destructif ou rebase automatique. L'opérateur doit réconcilier les commits et journaux privés. Les journaux hôte doivent être sauvegardés : leur perte supprimerait la mémoire anti-rejeu.

Un audit quotidien interrompu bloque explicitement les cycles jusqu'à revue opérateur ; une tâche interrompue reçoit un résultat INTERRUPTED sans être relancée. Ni la suppression du VPS ni l'archivage du dépôt ne sont automatisés.

## Validation et déploiement

Tests reproductibles : `node tests/runtime.test.js` et `python3 -m unittest discover -s tests -p 'test_*.py'`. Ils couvrent les entrées refusées, la finance, les archives et la reprise avec Git local réel et worker Node réel. Docker est substitué dans le test d'intégration. Le test réel conteneur → GitHub doit être réalisé selon INSTALL.md avant cron ; la revue locale ne certifie pas le VPS.
