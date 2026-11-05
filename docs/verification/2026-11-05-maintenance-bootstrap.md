# Maintenance reproductible : preuves et limites

Le bootstrap préparait le contrôle et le dépôt bare, mais les guides supposaient déjà présents les horaires queue/daily et la rotation. Le VPS existant possédait ces éléments lors du contrôle en lecture seule ; le défaut concerne la reproductibilité d'une installation neuve.

## Livraison

`scripts/install_maintenance.py` propose un aperçu sans mutation et une application administrative explicite. Il vérifie la révision installée, le dépôt bare, l'image locale et les services requis, puis revalide les sources sous le verrou du superviseur. Il ne remplace que ses propres configurations reconnues, sauvegarde les versions précédentes et restaure les fichiers après une erreur détectée. Le courrier reste facultatif et un horaire mail déjà géré est conservé.

Les journaux diagnostiques sont privés, créés en `0600` et protégés par `umask 077` dans les nouvelles entrées cron. La rotation cible quatre fichiers précis, sans toucher aux bases, reçus ou écritures comptables. Une réexécution répare les dossiers et journaux absents même si les configurations sont identiques, sans réécriture ni sauvegarde supplémentaire. Les choix commerciaux et les interfaces des agents ne changent pas.

## Régressions reproduites

- Un fichier de log croissant était lu comme une configuration : validation par métadonnées seulement.
- Un dépôt non bare pouvait satisfaire le contrôle superficiel : vérification Git réelle.
- La commande cron recréait un log supprimé en `0644` : test exécutant réellement `/bin/sh`, corrigé par `umask 077`.
- Une modification administrative entre précontrôle et verrou pouvait introduire une image non vérifiée : seconde validation sous verrou.
- La relecture indépendante a reproduit un retour anticipé laissant un dossier de logs manquant : commande queue en échec avant le superviseur. Deux tests ont échoué avant correction, puis vérifient la réparation des fichiers, leurs permissions, les empreintes/horodatages des configurations et le nombre de sauvegardes.

Une seule passe de correction a suivi cette relecture globale. Aucun constat Critical ou Minor ; le constat Important ci-dessus a été accepté et corrigé.

## Vérification

Arbre testé : `33f0c5f9ce449611ae9fd0297cfab68feeea454b`. Archive SHA-256 : `d335e9ab5443fb34eb6a14e9154539080d495a77e7a6fb68846c2749462ff41e`. Les ajouts ultérieurs au présent rapport et au plan sont documentaires.

- Suite ciblée : **18 tests réussis**, sans exclusion, sous Linux en administrateur dans des dossiers synthétiques. Git est réel ; les contrôles systemctl et Docker sont simulés. Le test de rotation utilise réellement logrotate pour le précontrôle, la rotation forcée et l'écriture pendant le renommage.
- Suite complète sur une archive exacte extraite dans un nouveau dossier Linux : **621 tests Python réussis, dont 8 ignorés** (CLI externes et scénarios Docker optionnels), **13 tests Node réussis**, syntaxe Bash et aide CLI validées. Le test réel logrotate fait partie de cette suite. Preuves locales : `output/globalland-bootstrap-evidence-20261105/v4/`.

La CI ajoute le même test réel de logrotate sous Ubuntu, en complément des tests Python, Node, Docker et des quatre wrappers SDK de produits. Aucun identifiant de compte n'est requis.

## Portée non prouvée

- Les tests isolés ne démontrent pas la reconstruction intégrale d'une VM, le déclenchement par un daemon cron neuf ou la reconnexion des comptes externes. Ces vérifications restent distinctes.
- Le retour arrière couvre les erreurs détectées. Une coupure entre deux remplacements n'est pas une transaction atomique : inspecter les fichiers et la sauvegarde avant reprise.
- Le verrou coordonne les opérations qui le respectent ; il ne protège pas d'un autre administrateur privilégié modifiant les fichiers hors protocole.
- `delaycompress` protège la première archive pendant la fin d'une écriture bornée, pas un descripteur conservé indéfiniment sur plusieurs rotations. `maxsize` est contrôlé au passage de logrotate, pas un plafond disque instantané.
- Aucun déploiement, financement, contact commercial ou paiement n'est démontré par cette livraison. Les anciennes configurations personnalisées sont préservées et demandent une migration revue, pas un remplacement forcé.
