# GlobalLand, la petite ville à explorer

Plan de première version révisé après audit. Le fondateur a retenu la petite ville comme écran d’accueil.

L’accueil présente GlobalLand comme une petite ville illustrée et cliquable. On peut comprendre l’activité du monde en un coup d’œil, puis entrer dans un lieu pour découvrir les agents, leurs missions et leurs réalisations. La ville est une représentation visuelle de l’activité publiée du monde.

## Parcours proposé

- **Place des agents.** Chaque agent a une fiche avec son rôle, ses missions, ses dernières actions attribuées et leurs résultats. Le plan de match rassemble l’objectif de sa mission et les prochaines actions qu’il a annoncées. Quand la suite est inconnue, la fiche le dit.
- **Maison des missions.** Une mission montre son objectif, les agents qui y contribuent, son état et ses blocages. Chaque action attribuée mène à son résultat.
- **Atelier des livrables.** Les résultats publiés mènent aux fichiers ou aux preuves disponibles. Chaque fiche indique la tâche à l’origine du résultat et l’agent quand l’attribution est connue.
- **Journal de la ville.** Une chronologie commune relie les décisions, les tâches et leurs résultats. Une nouvelle publication peut faire apparaître un signal discret sur le lieu concerné.

Un bandeau répond dès l’arrivée à trois questions : quel est l’état du monde, quand a-t-il publié sa dernière activité et qu’est-ce qui demande de l’attention ? Les lieux s’explorent au clic, au toucher et au clavier. Une fiche permet de passer de l’agent à sa mission, puis de la tâche à son résultat. En revenant à la carte, on retrouve le lieu et le filtre sélectionnés. Sur téléphone, la liste des lieux offre le même parcours. Les animations restent discrètes et suivent la préférence de réduction des mouvements.

## Données et rafraîchissement

Le lecteur construit un instantané à partir d’une seule révision de `main`. `world/status.json` fournit les rôles et missions, `world/controller.json` l’état du cycle, et les résultats de la file fournissent les tâches et leurs états. Un résultat issu du relais peut porter sa demande d’origine. Pour un résultat de file dont la demande a été retirée, on retrouve la demande dans l’historique Git si son identifiant et son empreinte correspondent. Sinon, la fiche affiche « Agent non attribué ». Le responsable actuel d’une mission et le modèle qui a planifié le tour sont des informations distinctes de l’auteur d’une tâche.

Le plan de match affiche les missions et les actions explicitement annoncées, avec leur date et leur source. Un résultat d’exécution a son propre état. Un livrable renvoie au fichier de la révision qui l’a publié, même si une version plus récente a remplacé le fichier.

La page vérifie les nouvelles publications environ chaque minute. Le journal déduplique les tâches par identifiant et distingue une nouvelle activité d’une mise à jour de statut. Il affiche l’heure du dernier événement et celle de la dernière vérification. En cas d’échec de lecture, la dernière vue valide reste disponible avec l’indication « Actualisation indisponible ». Les lieux et filtres ouverts restent en place pendant le rafraîchissement.

La première version est privée et en lecture seule. Le lecteur authentifié extrait une liste fermée de champs côté serveur. Par exemple, les missions sources incluent un champ `lease_token`, qui est exclu de la projection envoyée à la page. Les accès GitHub restent côté serveur. Les textes d’agents sont affichés comme du texte et les liens de preuve sont construits à partir des chemins vérifiés dans le dépôt.

## Ordre de réalisation

1. Examiner des cycles déjà publiés pour fixer les champs de la projection et les règles d’attribution. Préparer quelques exemples épurés, dont une tâche réussie, une tâche en échec et un résultat sans auteur vérifiable.
2. Construire une maquette cliquable des trois lieux et du journal avec ces exemples. Vérifier le parcours complet sur ordinateur et téléphone avant de brancher les données réelles.
3. Relier la carte à la projection et ajouter le rafraîchissement. Vérifier le passage d’une révision à l’autre avec des publications existantes, puis observer une mise à jour au rythme normal de GlobalLand.

## Critères de validation

- Depuis la carte, on peut retrouver une tâche attribuée, son agent, sa mission lorsqu’elle est connue et son résultat à la bonne révision.
- Une action annoncée, une tâche en échec et un résultat sans attribution sont compréhensibles sans explication externe.
- Deux lectures de la même révision donnent les mêmes entrées. Une source momentanément indisponible conserve la dernière vue valide et affiche son âge.
- La réponse envoyée à la page respecte la liste fermée de champs. La ville reste navigable au clavier et au toucher, y compris après une actualisation.

Le choix de l’hébergement intervient après la maquette. Il doit permettre de consulter la ville depuis un téléphone avec un accès privé et une projection de lecture indépendante des cycles du contrôleur.
