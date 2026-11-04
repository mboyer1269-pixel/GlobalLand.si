# Rétention des images GlobalLand

Les conteneurs de travail utilisent `--rm`. Entre deux tours, une image locale
peut donc n'avoir aucune référence de conteneur. Le nettoyage partagé
`docker image prune -af --filter until=24h` peut alors supprimer un cerveau
construit localement, même si son SHA est toujours configuré.

`scripts/image_guard.py` conserve les images configurées dans
`ROOT/control/config.json` : `controller.image` et `executor_image`. En mode
`external_grok` sans image de cerveau, il conserve seulement l'exécuteur.
Il crée des conteneurs de référence avec `docker container create`, sans les
démarrer : réseau `none`, racine en lecture seule, utilisateur 65534, point
d'entrée `/bin/false`, aucun montage ni secret transmis. Les images déclarant
des volumes sont refusées car Docker initialise ces volumes dès la création.

```bash
# Lecture seule : code 0 uniquement si toutes les images et références sont présentes.
sudo python3 /opt/globalland/control/image_guard.py --root /opt/globalland status

# Créer les références manquantes, sans téléchargement ni inférence.
sudo python3 /opt/globalland/control/image_guard.py --root /opt/globalland ensure
```

Les noms incorporent le rôle, une empreinte du chemin d'installation et l'ID
local complet de l'image. Les labels `org.globalland.image-guard*` enregistrent
l'appartenance. Une nouvelle exécution réutilise uniquement un conteneur du
même nom, des mêmes labels et de la même image, encore dans l'état `created`
et respectant les paramètres de sécurité vérifiés. Un conteneur démarré,
arrêté après exécution, étranger ou doté d'un montage produit `conflict` et
n'est pas modifié. Le programme ne supprime aucun conteneur ni aucune image.

Le JSON distingue `protected`, `unprotected`, `image_unavailable`,
`unsafe_image`, `conflict` et `create_failed`. Toute situation non protégée
donne le code 1. Une erreur Docker ou de configuration peut donner un objet
`error`. Les inspections de toutes les images et collisions précèdent toute
création ; une panne pendant les créations peut laisser une protection
partielle. Relancer `status`, puis `ensure` après correction est sans danger.

## Mise à niveau et changement d'image

`upgrade_vps.sh` prépare `BACKUP/config-pending.json`, valide la composition
Docker et protège les images avant de créer le répertoire final de release.
Un échec de protection laisse ainsi la mise à niveau réessayable après
réparation, sans modifier `control`. Pour contrôler une configuration préparée
manuellement, garder le même périmètre d'installation :

```bash
sudo python3 "$RELEASE/image_guard.py" --root /opt/globalland \
  --config "$RELEASE/config.json" ensure
```

Après une reconstruction ou un changement de configuration hors de ce script,
exécuter aussi `ensure`, puis `status`. Une image absente doit d'abord être
restaurée depuis une archive vérifiée ou reconstruite ; cette utilité ne
télécharge et ne reconstruit rien, et ne réécrit pas la configuration. Les
anciennes références sont conservées pour le rollback. Leur retrait éventuel
requiert une opération administrative distincte et ciblée après vérification
des versions encore nécessaires.

## Limites et sauvegardes

Cette protection vise `docker image prune`, qui exclut les images référencées
par un conteneur, même non démarré. `docker container prune` peut supprimer les
références ; `docker system prune` supprime aussi les conteneurs arrêtés. Les
références ne protègent pas d'une suppression explicite, d'une perte du disque
ou du stockage Docker. Ne pas modifier le nettoyage partagé d'autres services
comme Oria pour installer cette protection.

Conserver séparément une archive `docker image save` des IDs exacts nécessaires,
son empreinte SHA-256 et la configuration correspondante, avec une copie hors
du stockage Docker. Vérifier les IDs après `docker image load`, puis relancer
`ensure` et `status`. Une référence n'est pas une sauvegarde ; aucune restauration
d'archive n'est effectuée par ce programme.

Références Docker : [image prune](https://docs.docker.com/reference/cli/docker/image/prune/),
[container create et initialisation des volumes](https://docs.docker.com/reference/cli/docker/container/create/),
[system prune](https://docs.docker.com/reference/cli/docker/system/prune/).

## Vérification locale

```bash
python3 -m unittest discover -s tests -p test_image_guard.py
```

Les tests emploient des configurations temporaires et un faux processus Docker
avec état. Ils ne contactent aucun démon Docker et ne changent aucun service.
