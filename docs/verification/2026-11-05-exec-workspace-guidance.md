# EXEC : erreurs de fichier absent et espace neuf

Deux tâches réelles ont tenté d'écrire le même fichier dans un dossier absent de leurs espaces distincts : `TASK-179390958111` et `TASK-179390958113`. Les corrections intermédiaires ont réussi. Ce constat confirme une difficulté d'utilisation répétée, pas une perte de l'artefact publié ni une panne de l'exécuteur.

Le guide du contrôleur et le protocole explicitent la durée de vie de l'espace, la sélection des fichiers publics antérieurs et la création des parents de sortie par le programme. Les erreurs Node `ENOENT` et Python `FileNotFoundError` reçoivent un rappel fixe, sans modifier leur statut, synthétiser un fichier ou relancer l'action. Le rappel distingue les `inputs` publics des fichiers fournis au dossier privé. Il ne constitue pas un diagnostic universel de toutes les erreurs d'interpréteurs.

## Preuves

- Les deux nouvelles régressions Node ont échoué sur l'absence de rappel, puis réussi après correction. Le test d'erreur sans rapport vérifie que le rappel n'apparaît pas ; les diagnostics verbeux restent bornés à 8 000 caractères.
- Archive exacte du code `762caa548bdc7af36b76ef3d397fa02b67d30cc4`, arbre `723eac3dfac6dadabda8817ee78884cd245cab65`, SHA-256 `1bc647b2ed5173739205feb52839e395de6407dc24d85450484d417cc0fe26c9` : **676 tests Python réussis, dont 10 ignorés**, **15 tests Node réussis**, syntaxe Bash valide. Ces exclusions comprennent les tests à services/CLI optionnels.
- Le [workflow GitHub 42104083825](https://github.com/mboyer1269-pixel/GlobalLand.si/actions/runs/42104083825) réussit ensuite la suite et les contrôles Docker, actifs dans ce job. Le nouveau scénario utilise réellement une entrée vide : premier programme en échec sur le dossier absent, seconde tâche corrigée qui crée son dossier et publie le contenu attendu avec un reçu d'entrée vide. Les autres tests Docker, catalogue, actifs privés et les quatre wrappers SDK réussissent aussi.
- Relecture indépendante globale : aucun constat Critical, Important ou Minor. Une tentative de tests natifs Windows du relecteur a rencontré `EPERM` dans le test préexistant de liens symboliques ; les mêmes tests passent sous Linux.

La création automatique des dossiers a été écartée pour préserver les programmes qui les créent eux-mêmes. Aucun changement d'autorité, de marché, de budget ou d'intégration. Cette livraison ne prouve pas que les modèles cesseront toute erreur de fichiers ; son effet comportemental après installation reste à observer. Les ajouts ultérieurs au plan et à ce document sont documentaires.
