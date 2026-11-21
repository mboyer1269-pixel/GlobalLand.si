# Catalogue editor handoff / Consignes de correction du catalogue

**EN** · Produced by autonomous AI agents. In this fictional example, the checker reported `style SH-100: same image URL used twice` and exited 2. It identifies the style. The row location below comes from manual inspection.

1. Open `untouched-images.csv` and find the two SH-100 rows whose `url` ends in `/sh-100/brown-5.jpg`. Confirm that both rows also have color Brown and position 5 and that the complete rows match.
2. Save a copy as `editor-images.csv` with the repeated final row removed. Keep the earlier row and preserve the CSV header and other rows. If the two records differ, ask which record to keep before editing.
3. Place both the untouched file and the editor copy in the runner directory set up as described in the one-command QA demo. Run `python3 run_example.py --images untouched-images.csv` for the negative control, then `python3 run_example.py --images editor-images.csv` to check the edit. The producer's edited copy exited 0, matched the reference CSV byte for byte and passed all 12 example checks. The clean control also passed.

**FR** · Produit par des agents d’IA autonomes. Dans cet exemple fictif, l’outil a signalé qu’une URL d’image était utilisée deux fois pour le style SH-100 et a renvoyé le code 2. L’outil indique le style. Les lignes indiquées ci-dessous ont été repérées manuellement.

1. Ouvrez `untouched-images.csv` et repérez les deux lignes SH-100 dont le champ `url` se termine par `/sh-100/brown-5.jpg`. Vérifiez que les deux lignes indiquent la couleur Brown et la position 5 et qu’elles sont entièrement identiques.
2. Enregistrez une copie nommée `editor-images.csv` en supprimant la répétition en dernière ligne. Conservez la première occurrence, l’en-tête CSV et les autres lignes. Si les deux lignes diffèrent, demandez laquelle conserver avant toute modification.
3. Placez les deux fichiers dans le dossier préparé selon la démonstration en une commande. Lancez `python3 run_example.py --images untouched-images.csv` pour le contrôle négatif, puis `python3 run_example.py --images editor-images.csv` pour vérifier la correction. La copie corrigée par le producteur a renvoyé le code 0, reproduit le CSV de référence à l’octet près et réussi les 12 contrôles de l’exemple. Le témoin sans doublon a également réussi.

**Handoff / Transmission.** Raw output leaves the editor to interpret the finding and decide what to inspect and edit. This report supplies those instructions. The editor still verifies row identity, edits a copy and reruns the checker. An independent editor rehearsal is pending. / Avec la sortie brute, l’éditeur doit interpréter le signalement puis déterminer quoi vérifier et modifier. Ce rapport fournit ces consignes. L’éditeur doit toujours vérifier que les lignes sont identiques, modifier une copie et relancer l’outil. Un essai indépendant reste à faire.

**Scope / Périmètre.** Offline fictional fixture. Image retrieval, Shopify import and customer delivery are outside the test. / Jeu d’essai fictif hors ligne. La récupération des images, l’import Shopify et la livraison au client sont hors périmètre.
