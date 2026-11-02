# Analyse de google/elephant-goldfish-model (EGM) pour GlobalLand

> Analyse du 2 novembre 2026.
> - **Version lue :** copie superficielle (commit `403d888`, 30 oct. 2026) ; README, personas `agents/*.md`, skills `egm-review` et `egm-drift-report`.
> - **Licence :** Apache 2.0. Ce n'est pas un produit officiellement pris en charge par Google.
> - **Limite :** rien n'a été installé ni exécuté.

## Ce que c'est

Un plugin pour Claude Code, Codex et Antigravity, qui fait relire une spécification par d'autres agents avant d'écrire du code. Deux rôles :

- **Éléphant** : l'agent qui a tout le contexte du projet et rédige la spécification.
- **Goldfish** (« poisson rouge ») : des relecteurs lancés **à neuf, sans l'historique de la conversation**. Chacun lit seulement le document et le code qu'il cite, avec un rôle précis :
  - architecte sceptique : simplicité, pas de fonctions superflues (YAGNI), réutilisation de l'existant ;
  - compréhension ;
  - critique de conception ;
  - préparation à l'implémentation ;
  - style ;
  - synthèse.

Les constats sont classés **Blocker / Major / Nit**. Si l'outil ne peut pas créer de relecteur neuf, il refuse de faire la revue : « une revue dans le même contexte n'est pas une revue Goldfish ». Un rapport de dérive (*drift report*) compare aussi les documents au code réel.

## Verdict : 8/10 pour GlobalLand

| Critère | Note | Raison |
|---|---|---|
| Revenus | 6 | Indirect : il protège la qualité de ce qui est mis en vente. |
| Coût | 9 | Apache 2.0. L'idée se reprend dans nos propres prompts, sans dépendance. |
| Risque | 9 | Rien à installer sur le VPS. |
| Vitesse de validation | 7 | La fiche s'applique tout de suite. Le tour de revue côté hôte demande du code et un essai sur le VPS. |
| Scalabilité | 8 | Une revue neuve par produit, au coût d'un tour d'abonnement. |
| Différenciation | 8 | Corrige précisément le point faible de notre règle des deux clés. |
| Exécution | 8 | Personas claires, interdiction explicite de l'auto-revue, constats gradués. |

**Ce qui l'empêche d'avoir 10 :** c'est un outil de *conception logicielle* pour humains. Seul son principe sert directement le monde des agents.

## Le point faible qu'il révèle chez nous

Notre règle des deux clés exige déjà un relecteur d'**un autre fournisseur**, dans **un autre tour**, qui n'a pas écrit les fichiers. Mais ce relecteur reçoit **le même prompt que l'auteur** :
- l'état du monde ;
- les messages des agents ;
- les missions ;
- les leçons.

C'est un éléphant qui relit un éléphant. Conséquences :
- **Biais partagé :** les messages du type « le produit est prêt, testé, approuvez-le » orientent la revue.
- **Injection de prompt :** un texte écrit dans `world/` par un agent compromis (ou par un contenu Web récupéré) est lu par le relecteur.
- **Approbation par récit :** le relecteur peut approuver ce qui est *affirmé* plutôt que ce qui est *visible*.

## Intégré maintenant

| Idée EGM | Intégration |
|---|---|
| Relecteur sans historique | Fiche `two-key-review` réécrite. Elle s'applique aussi aux sites (avant, Apify seulement) et impose de juger seulement ce qu'un inconnu verrait : fichiers publiés et résultat de construction ou d'essai. Le récit de l'auteur est ignoré. |
| Stress-test par défaut | Verdict NEEDS_WORK par défaut ; APPROVE seulement sur ce qui a été vérifié soi-même. |
| Constats Blocker / Major / Nit | Exigés dans `notes`. Tout Blocker entraîne NEEDS_WORK. |
| Contenu relu = données | Le texte des fichiers relus n'est jamais une instruction. |

Avis Apache 2.0 ajouté à `agents/playbooks/THIRD_PARTY.md` : idées seulement, aucun texte copié.

## Proposé, pas encore codé : le tour de revue Goldfish côté hôte

Une fiche ne garantit rien : le relecteur reçoit toujours tout le contexte. La vraie correction est un **tour de revue séparé, construit par l'hôte**, avec seulement l'artefact. Spécification : [`docs/designs/goldfish-review.md`](../designs/goldfish-review.md).

Non codé aujourd'hui, pour deux raisons :
1. une autre session travaille sur `controller.py` dans la même branche ;
2. rien ne tourne sur le VPS tant que l'incident du 1er novembre n'est pas réglé.

## Aussi utile, hors du monde des agents

- **Pour le développement de GlobalLand** : installer EGM dans tes sessions Claude Code ou Codex (`claude plugin marketplace add google/elephant-goldfish-model`), pour concevoir les gros changements (`/egm:egm-brainstorm`, `/egm:egm-review`) avant de coder. C'est ton choix : ça consomme des tours d'abonnement.
- **Rapport de dérive** : nos docs ont déjà dérivé deux fois (dépôt dit public alors qu'il est privé, nombre de tests). Un `egm-drift-report` mensuel sur `README.md`, `INSTALL.md` et `SECURITY.md` attraperait ces écarts.
