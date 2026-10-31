# Graphify pour GlobalLand

**Statut : outil documenté, pas encore installé ni exécuté sur GlobalLand.** Aucun graphe de ce dépôt n’est présenté comme généré ou vérifié.

[Graphify](https://github.com/Graphify-Labs/graphify), de Graphify Labs, construit une carte des relations d’un projet. Il complète la lecture du code et les tests : une relation extraite ou déduite reste à vérifier avant une modification.

## Ce qu’il peut apporter

Pour GlobalLand, les premières questions utiles sont :

- Quel chemin relie une décision du contrôleur à une tâche publiée ?
- Quels composants interviennent dans une dépense et son rapprochement ?
- Quelles fonctions dépendent d’un outil ou du format d’une décision ?
- Où vérifier les effets d’une modification du superviseur ?

Graphify distingue les liens `EXTRACTED`, explicites dans les sources, et `INFERRED`, obtenus par résolution. Le graphe aide à trouver le contexte ; il ne prouve ni qu’une tâche a tourné ni qu’un paiement a été effectué.

## Premier essai : cartographier le code localement

Le projet officiel demande Python 3.10+ et propose `uv` ou `pipx`. Son paquet PyPI s’appelle **`graphifyy`**, avec deux « y » ; la commande installée est **`graphify`**.

Dans un environnement de développement isolé, avec une copie du code GlobalLand :

```bash
uv tool install graphifyy
GRAPHIFY_BACKEND=none graphify extract . --code-only --out /tmp/globalland-graphify
```

Cette commande est une procédure à essayer, pas le compte rendu d’une exécution. L’installation télécharge le paquet et ses dépendances. L’extraction du code utilise les analyseurs syntaxiques locaux ; `GRAPHIFY_BACKEND=none` désactive les traitements LLM, dont les replis de labellisation, et `--code-only` écarte l’analyse sémantique des documents. Aucun abonnement Cloud ou backend API n’est nécessaire pour cet essai.

Le chemin de sortie proposé reste hors du dépôt. Le projet annonce notamment :

| Fichier | Utilité |
| --- | --- |
| `graph.html` | Explorer la carte dans un navigateur. |
| `GRAPH_REPORT.md` | Lire une synthèse du graphe. |
| `graph.json` | Réutiliser les nœuds et les liens ; conserver la version du schéma et de Graphify. |

Avant de partager ces fichiers, vérifier leur contenu : une carte peut reprendre noms, chemins et extraits des sources analysées. Utiliser une copie du code, séparée des credentials et de l’état privé du VPS. La version exacte de Graphify et les fichiers effectivement produits devront être consignés lors du premier essai.

## Utilisation dans un assistant

Graphify fournit aussi une skill pour Claude Code, Cursor, Codex et d’autres assistants. Son installation peut modifier leur configuration ; elle est distincte de l’extraction locale ci-dessus.

Exemple officiel pour un projet de développement utilisant Codex :

```bash
graphify install --project --platform codex
```

Codex invoque la skill avec `$graphify`. Claude Code et Cursor utilisent `/graphify .` selon leur installation. Les fonctions sémantiques qui consultent un modèle dépendent de son abonnement, de ses quotas et de la configuration choisie ; elles ne sont pas toutes gratuites.

La configuration de réflexion de GlobalLand reste dédiée aux décisions structurées. Cette documentation n’installe aucun hook ni plugin dans ses conteneurs, ne connecte pas l’application Gemini et n’active aucun service Graphify Cloud. Un usage par les agents de production reste à intégrer et à vérifier.

## Sources vérifiées

Lecture des sources officielles le **31 octobre 2026**, révision [`a0946f962af31b19bff941b453f6dae9a7077c7a`](https://github.com/Graphify-Labs/graphify/tree/a0946f962af31b19bff941b453f6dae9a7077c7a), branche amont `v8` :

- [README officiel](https://github.com/Graphify-Labs/graphify/blob/a0946f962af31b19bff941b453f6dae9a7077c7a/README.md) : installation, plateformes et fichiers de sortie.
- [Définition du paquet](https://github.com/Graphify-Labs/graphify/blob/a0946f962af31b19bff941b453f6dae9a7077c7a/pyproject.toml) : `graphifyy`, prérequis Python et licence Apache-2.0.
- [CLI officielle](https://github.com/Graphify-Labs/graphify/blob/a0946f962af31b19bff941b453f6dae9a7077c7a/graphify/cli.py) : `extract`, `--code-only`, `--out` et désactivation des backends LLM.
- [Documentation de démarrage](https://docs.graphify.com/quickstart).

[Retour au README](../README.md)
