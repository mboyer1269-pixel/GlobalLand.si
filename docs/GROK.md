# Parler à Grok pour faire travailler GlobalLand

**Situation actuelle :** l’opérateur indique que Grok envoie ses demandes à Cursor, qui ouvre ou rouvre une PR. La boucle autonome complète reste à réaliser et à vérifier.

## Le produit est identifié : Grok Bot de xAI

Le [guide officiel Grok Bot 101](https://x.ai/bot/guides/grok-bot-101), consulté le 31 octobre 2026, décrit un agent avec ordinateur persistant dans le cloud, terminal, applications, routines programmées, déclencheurs et échanges entre bots. Il décrit aussi exactement le chemin vers un Cursor Cloud Agent qui construit du logiciel et ouvre une PR. Cette observation de l’opérateur correspond donc à un usage documenté du produit.

**Le parcours recommandé commence par ces fonctions natives :** Grok Bot prépare et transmet les missions, puis une routine vérifie leurs résultats sur GitHub et décide de la suite. La routine et ses accès doivent être testés dans le compte de l’opérateur ; leur présence dans la documentation ne signifie pas qu’ils sont déjà activés pour GlobalLand. La lecture périodique est un choix proposé : le guide ne garantit pas un déclencheur spécifique pour chaque résultat de queue.

Une clé API xAI n’est pas une condition établie pour utiliser ces routines. Les [connecteurs MCP personnalisés de Grok](https://docs.x.ai/grok/connectors) constituent une autre liaison documentée ; le guide Bot annonce les mêmes serveurs MCP/plugins/skills que Cursor. Leur disponibilité dans le compte et leur authentification restent à vérifier. Un service MCP GlobalLand serait un chantier distinct, pas une connexion déjà installée.

## Grok travaille aussi lui-même

Grok Bot peut rechercher, utiliser ses applications, écrire et exécuter du code sur son ordinateur cloud, puis échanger avec d’autres bots. Il peut donc réaliser des tâches et coordonner une équipe. Dans le parcours proposé pour GlobalLand, il cherche des opportunités, prépare les missions, effectue les travaux accessibles à ses outils et analyse les résultats ; Codex et Claude apportent leur aide spécialisée. Ce sont les capacités documentées du produit et le rôle visé, pas une preuve de connexion de tous ces outils au monde déjà installé.

## Une PR et une mission ont des effets différents

| Demande | Chemin | Preuve attendue |
| --- | --- | --- |
| Améliorer le logiciel ou sa documentation | Grok → Cursor → branche et PR | Diff, vérifications, puis version effectivement installée si le contrôle change. |
| Donner du travail aux habitants | Grok → relais → tâche dans queue/inbox sur main → superviseur VPS | Résultat done/failed, empreinte d’entrée et artefacts vérifiables. |

Une PR peut contenir une tâche valide, mais celle-ci n’atteint le superviseur qu’après son arrivée sur main. Le bon fonctionnement du premier chemin ne prouve donc pas celui du second. Ne pas confondre non plus la CLI Cursor du VPS avec le Cursor utilisé par l’application externe.

Les issues GitHub peuvent servir à discuter d’un objectif. Le superviseur actuel ne les consomme pas : une issue seule ne lance pas une tâche. Le premier parcours conserve les fichiers queue/inbox déjà pris en charge.

## Message simple à envoyer aujourd’hui

> Cette demande concerne une mission dans le monde GlobalLand. Lis AGENTS.md et queue/PROTOCOL.md, puis choisis une petite opportunité de revenus mondiale et prépare un premier travail concret avec les moyens disponibles. Vérifie si tu peux transmettre des tâches valides à queue/inbox sur main. Si ton accès permet seulement d’ouvrir une PR, indique que la livraison au VPS est en attente. Donne les IDs, le commit et les résultats vérifiés ; distingue ce qui est proposé, transmis et exécuté. Aucun dépôt d’argent ni revenu ne doit être inventé.

Ce message ne crée pas un connecteur. Le relais doit réellement pouvoir écrire au bon endroit et le superviseur doit fonctionner. Il ne faut pas envoyer l’action DELEGATE proposée dans le plan ci-dessous avant son implémentation et son installation.

## Ce qui manque pour poursuivre tout seul

1. Vérifier comment Grok Bot peut livrer les missions au monde sans faire fusionner une PR au fondateur pour chaque demande : connecteur GitHub capable, ou petit relais dans son ordinateur cloud.
2. Permettre à Grok de demander explicitement l’aide de Codex ou Claude via les abonnements officiels.
3. Configurer une routine native du bon Grok Bot pour lire les résultats, puis vérifier qu’il décide de la suite sans nouveau message du fondateur.
4. Conserver les tâches et propositions après une panne, avec des statuts honnêtes et sans refaire une opération incertaine.

Le produit et ses capacités de routines sont maintenant identifiés dans les sources officielles. Les droits d’écriture sur main, la routine effectivement enregistrée, son exécution dans le compte et l’appel aux spécialistes de ce VPS restent à prouver. Les travaux et résultats peuvent être conservés en attendant ; le statut doit exposer ces dépendances, sans présenter l’application comme incapable de se réveiller.

→ [Conception de la boucle](superpowers/specs/2026-10-31-grok-world-loop-design.md) · [Plan de réalisation](superpowers/plans/2026-10-31-grok-world-loop.md) · [Protocole actuel](../queue/PROTOCOL.md)
