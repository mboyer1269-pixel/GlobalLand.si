# La ville de GlobalLand

Une carte illustrée à explorer pour suivre les agents, leurs missions et les fichiers publiés. Cette interface lit le dépôt public ; elle ne commande pas les agents et ne mesure pas les ventes.

Depuis la racine d'une copie Git du dépôt, avec Python 3 et Git :

```sh
python prototypes/ville-globalland/ville_locale.py
```

Ouvrir **http://127.0.0.1:8765/**. La page actualise sa lecture chaque minute. Le lecteur récupère `origin/main` sans modifier les fichiers de travail. Pour consulter seulement la copie Git locale, ajouter `--cached`. `--repo CHEMIN` permet de lire une autre copie du même dépôt ; `--port 8766` change le port.

Le serveur écoute uniquement sur la machine locale et refuse les autres en-têtes Host. L'affichage mobile est adapté aux petits écrans, mais un accès depuis le téléphone nécessite encore un hébergement authentifié séparé. Ne pas exposer ce serveur directement sur Internet.

## Ce que les données prouvent

- Les résidents, missions et blocages viennent de toutes les pages de projection, à une même révision Git.
- Le journal montre au plus 100 résultats distincts parmi les 150 dernières publications touchant les résultats, plus au plus 100 demandes encore en attente. Ce n'est pas l'historique intégral. Les heures désignent la publication dans Git, pas nécessairement le moment d'exécution.
- L'attribution d'un résultat exige une demande correspondante dont le condensat correspond à `input_sha256`. Sans elle, le résultat reste visible avec une attribution inconnue.
- Les liens de livrables pointent vers des fichiers ordinaires présents à la révision du résultat. Un résultat « Réussie » atteste le statut de l'outil ; il ne prouve ni qualité commerciale, ni commande, ni paiement.
- Le parcours guidé existe seulement lorsqu'un agent, une mission et un fichier peuvent être reliés. Les autres missions restent consultables.
- Un échec de lecture conserve le dernier instantané valide et signale l'erreur. Au premier échec, aucune activité fictive n'est affichée.

Les arguments bruts, sorties d'exécution et champs privés ne sont pas exportés dans l'API locale. Les liens de preuve ouvrent les documents déjà publics sur GitHub.

Pour exporter un instantané reproductible :

```sh
python prototypes/ville-globalland/ville_locale.py --snapshot --revision SHA_COMPLET
python -m unittest discover -s tests -p test_city.py
```

La carte est une projection en lecture seule. Aucun accès de messagerie, de publication, de banque ou au VPS n'est nécessaire.
