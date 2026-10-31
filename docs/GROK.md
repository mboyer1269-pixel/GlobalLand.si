# Parler à Grok pour faire travailler GlobalLand

**Situation actuelle :** l’opérateur indique que Grok envoie ses demandes à Cursor, qui ouvre ou rouvre une PR. La boucle autonome complète reste à réaliser et à vérifier.

## Une PR et une mission ont des effets différents

| Demande | Chemin | Preuve attendue |
| --- | --- | --- |
| Améliorer le logiciel ou sa documentation | Grok → Cursor → branche et PR | Diff, vérifications, puis version effectivement installée si le contrôle change. |
| Donner du travail aux habitants | Grok → relais → tâche dans queue/inbox sur main → superviseur VPS | Résultat done/failed, empreinte d’entrée et artefacts vérifiables. |

Une PR peut contenir une tâche valide, mais celle-ci n’atteint le superviseur qu’après son arrivée sur main. Le bon fonctionnement du premier chemin ne prouve donc pas celui du second. Ne pas confondre non plus la CLI Cursor du VPS avec le Cursor utilisé par l’application externe.

## Message simple à envoyer aujourd’hui

> Cette demande concerne une mission dans le monde GlobalLand. Lis AGENTS.md et queue/PROTOCOL.md, puis choisis une petite opportunité de revenus mondiale et prépare un premier travail concret avec les moyens disponibles. Vérifie si tu peux transmettre des tâches valides à queue/inbox sur main. Si ton accès permet seulement d’ouvrir une PR, indique que la livraison au VPS est en attente. Donne les IDs, le commit et les résultats vérifiés ; distingue ce qui est proposé, transmis et exécuté. Aucun dépôt d’argent ni revenu ne doit être inventé.

Ce message ne crée pas un connecteur. Le relais doit réellement pouvoir écrire au bon endroit et le superviseur doit fonctionner. Il ne faut pas envoyer l’action DELEGATE proposée dans le plan ci-dessous avant son implémentation et son installation.

## Ce qui manque pour poursuivre tout seul

1. Livrer les missions au monde sans faire fusionner une PR au fondateur pour chaque demande.
2. Permettre à Grok de demander explicitement l’aide de Codex ou Claude via les abonnements officiels.
3. Faire revenir les résultats au bon Grok Bot et vérifier qu’il décide de la suite sans nouveau message du fondateur.
4. Conserver les tâches et propositions après une panne, avec des statuts honnêtes et sans refaire une opération incertaine.

Le nom exact de l’application Grok Bot et son mécanisme supporté de reprise restent à identifier. Un accès GitHub seul ne réveille pas une application. Les travaux et résultats peuvent être conservés en attendant ; le statut doit alors exposer la dépendance.

→ [Conception de la boucle](superpowers/specs/2026-10-31-grok-world-loop-design.md) · [Plan de réalisation](superpowers/plans/2026-10-31-grok-world-loop.md) · [Protocole actuel](../queue/PROTOCOL.md)
