# Spécification : tour de revue Goldfish côté hôte

> Statut : **proposé, non codé** (2 novembre 2026). Inspiré de google/elephant-goldfish-model (Apache 2.0, idées seulement).

## Problème

La règle des deux clés exige un relecteur indépendant de l'auteur et du publieur. Mais ce relecteur décide dans un tour de réflexion normal. Son prompt contient l'état du monde, les messages, les missions et les leçons, c'est-à-dire le récit de l'auteur et tout texte injecté. Il peut donc approuver ce qui est *affirmé* au lieu de ce qui est *visible*.

## Objectif

Une approbation publique ne vient que d'un tour qui a vu **seulement** :
1. les fichiers du produit, exactement ceux que l'hôte publiera ;
2. le résultat de la construction privée (Actor) ou de l'essai à blanc (site) ;
3. la grille de revue et les garde-fous juridiques.

Ce tour ne voit **aucun** message, mission, leçon ou état du monde.

## Hors périmètre

- Remplacer la revue du fondateur (`review_admin.py`), qui reste toujours valable.
- Revoir les missions internes : seules les publications publiques sont concernées.

## Fonctionnement proposé

1. **Demande.** Une action `REQUEST_REVIEW {"subject": "actor:<nom>" | "site:<nom>"}` est mise en file par un agent. Elle n'a aucun effet externe.
2. **Paquet.** L'hôte construit le paquet de revue :
   - avec les fonctions de chargement existantes, `apify.load_source` ou `sites.load_site` (mêmes filtres : fichiers cachés et reçus exclus, taille bornée) ;
   - plus le dernier résultat privé, construction ou essai à blanc, et l'empreinte `review_digest` correspondante.
3. **Tour Goldfish.** L'hôte lance un tour séparé avec un fournisseur choisi par le contrôle :
   - **Fournisseur :** différent des auteurs, retrouvés par `review.authors`, et du publieur prévu. S'il n'y en a aucun, la revue revient au fondateur.
   - **Prompt minimal :** la grille, le paquet entre balises « données non fiables » et un schéma de sortie `{verdict: APPROVE|NEEDS_WORK, findings: [{severity: Blocker|Major|Nit, where, why}], checked: [...]}`.
   - **Isolement :** aucun outil, aucun courtier, aucun contexte du monde. Délai `controller.timeout_seconds`.
4. **Enregistrement.** L'hôte, et non le modèle, enregistre la revue WORLD :
   - `host_provider` = fournisseur du tour Goldfish ;
   - `host_turn` = `REVIEW-<secondes>`, un identifiant distinct des tours THINK ;
   - `reviewer` = `GOLDFISH`.

   Tout constat `Blocker` force NEEDS_WORK, quel que soit le verdict rendu.
5. **Règle de publication.** `review.approved` n'accepte plus pour une publication publique que les revues `GOLDFISH` ou `FOUNDER`. Les revues WORLD des tours normaux restent possibles, mais deviennent des avis internes.

## Garanties à tester

- Le prompt du tour Goldfish ne contient aucune chaîne de `world.snapshot()` : test par sentinelle injectée dans un message du monde.
- Un fournisseur auteur n'est jamais choisi : ni seul, ni en bascule.
- Un Blocker dans `findings` donne NEEDS_WORK, même si `verdict` vaut APPROVE.
- Une empreinte différente (fichier modifié après la revue) annule l'approbation : comportement déjà garanti par le `review_digest`.
- Un tour Goldfish qui échoue ne produit aucune revue. Il n'est jamais remplacé par une approbation.
- Le paquet respecte les mêmes exclusions que la publication : le relecteur voit exactement ce qui sera publié.

## Coût et risques

- **Coût :** un tour d'abonnement de plus par produit à publier, sans coût API.
- **Risque d'injection :** le paquet lui-même peut contenir du texte hostile. La grille le traite comme des données, et la décision reste bornée à APPROVE ou NEEDS_WORK sur une empreinte précise : le pire cas est une approbation injustifiée d'un seul artefact, que le fondateur peut révoquer (NEEDS_WORK par `review_admin.py`) et couper (`online:false`).
- **Taille du prompt :** le paquet est borné par les limites de chargement existantes.

## Questions ouvertes pour le fondateur

1. Faut-il garder la revue WORLD normale comme clé valable, en plus de Goldfish et du fondateur ? Je recommande **non**, sinon la faille reste ouverte.
2. Avec un seul fournisseur actif, faut-il désactiver la publication publique ou passer par le fondateur ? Je recommande **le fondateur**.
