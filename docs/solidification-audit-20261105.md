# Solidification après l'audit Graphify

Mandat : exécuter les priorités de l'audit du 5 novembre, en conservant VISION.md comme autorité. Les agents choisissent leurs marchés, produits et stratégies. Une intégration ne devient jamais une obligation commerciale. Les preuves synthétiques ne sont ni des clients ni des revenus.

Base de développement : `7f166e862b784e6ef0eb484ff7221afaaced96c6`. Audit initial : `4e02f09bd1c8280271a9ce36b557978cb57d2075`. Les ajouts intermédiaires sont des résultats opérationnels ; les constats sont revalidés sur le code courant.

## Exécution et preuves attendues

1. EXE-01 : valider les artefacts FETCH avant le résultat terminal, y compris la taille encodée et les motifs de secrets. Un refus ne doit pas empêcher la tâche suivante.
2. EXE-02 : séparer l'état WORLD complet de son transport public borné et paginé. Préserver les missions, leur consultation et leur clôture malgré un grand monde.
3. EXE-03/05 : transmettre une enveloppe de résultat indépendante des artefacts, conserver la publication en attente et dédupliquer les événements sans rejouer l'action.
4. F1/F2 : identifier les règlements indépendamment des mois et partager une lecture validée des créances. Une source auxiliaire invalide ne bloque pas le travail indépendant ; elle ne devient pas un zéro fictif.
5. F3 : relier l'offre privée à la version vérifiable du programme promis, puis vérifier la demande et la correction dans un même fil AgentMail réel, hors statistiques commerciales.
6. Acquisition et encaissement : vérifier une expérience choisie par les agents ; relever les dépendances de compte, d'autorisation et de règlement. N'inventer ni paiement ni compatibilité bancaire.
7. EXE-04/C1 : permettre la croissance du dépôt et une reconstruction propre, sans supprimer l'historique ni les résultats.
8. C2/C3/C4 : tests exécutables des quatre Actors, échec CI réel, réseau public borné du CSV avant activation.
9. Cohérence : réexaminer le mandat proposé en PR #11, identifier la source de la ville et son raccordement, actualiser les procédures et la carte après les changements.
10. Travailleurs parallèles : après le retour fiable, vérifier les besoins et la capacité de tâches complémentaires avec bail, budget et résultats distincts ; aucun double engagement.

## Méthode

Superpowers : diagnostic sur reproduction, tests de régression échouant avant correction, travaux indépendants en parallèle, revue croisée puis validation intégrée. Les changements de code sont préparés sur une branche isolée. Les comptes, paiements, contacts externes et installations restent dans les autorisations effectivement applicables.

## Journal

- Démarrage : copie Git fraîche, aucun historique local hérité poussé. Finance, produits/bootstrap et retours du directeur confiés à trois agents ; exécution/projections et intégration conservées par le coordinateur.
- Décision : conserver l'état interne complet du monde et paginer son transport. Réduire la taille d'un message ne doit pas réduire les stratégies ou supprimer des missions.
- Toutes les preuves d'achèvement restent à recueillir ; ce plan ne constitue pas un compte rendu de déploiement.

## Premier incrément en cours de vérification

Les correctifs EXE-01/02/03/05, F1/F2/F3 et C1/C2/C3/C4 sont implémentés sur cette branche. La suite intégrée et la revue finale font autorité pour leur validation ; aucun déploiement n'est déclaré ici. La relecture a également repéré et corrigé une liste de missions non bornée dans la carte de blocage, sans tronquer les missions de l'état interne.

La [validation du premier incrément](verification/2026-11-05-solidification.md) documente les 603 tests Python, les contrôles Node, Docker, SDK et leurs limites. Le test de livraison du programme dans un vrai conteneur a réussi ; il ne remplace pas l'échange AgentMail réel.

L'augmentation du dépôt EXE-04 demande un catalogue Git et des entrées sélectionnées par travail : [conception détaillée](solidification-source-catalog.md). Augmenter simplement la limite d'archive ne corrigerait pas la recopie intégrale dans chaque conteneur. Ce chantier reste à implémenter.

La ville a été retrouvée dans la copie locale distincte `GlobalLand.si/prototypes/ville-globalland`, avec son dernier changement propre au prototype au commit `58256bcd3e5a7d04004722606f5e61b36a2c7943`. Elle contient un serveur local, une maquette et une lecture de publications Git. Elle n'est donc pas perdue ; son intégration dans cet arbre, la prise en compte de la pagination et le parcours visuel restent à vérifier séparément. Aucun historique local hérité ne doit être poussé pour la récupérer : seuls ses fichiers relus seront transférés.

Le mandat commun reste proposé dans la [PR #11](https://github.com/mboyer1269-pixel/GlobalLand.si/pull/11), relue comme cohérente avec VISION.md. Son intégration, le test AgentMail réel déjà autorisé, l'expérience commerciale, les connexions de paiement et les travailleurs parallèles restent distincts de cette validation de code. Une validation locale ne satisfait pas ces exigences.
