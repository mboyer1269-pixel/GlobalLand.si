# Catalogue QA delivery sample / Exemple de rapport de contrôle de catalogue

**Operator copy. Fictional data.** Prepared by autonomous AI agents. Referenced offer price is provisional CAD 60. This companion leaves the exact draft and its pending operator decision intact.

**Copie pour l’opérateur. Données fictives.** Préparée par des agents IA autonomes. Le prix de l’offre est provisoire, à 60 CAD. Cet exemple laisse intact le texte exact de l’offre soumis à la décision de l’opérateur.

A separate offline comparison matched rows by unique SKU. Reordering produced no differences. Swapping the barcodes produced the changes below. Blank or repeated SKUs prevent a reliable match. Both before and after tables are required. Barcode values are compared as text.

Une comparaison hors ligne distincte a associé les lignes par UGS unique. Le changement d’ordre n’a produit aucun écart. La permutation des codes-barres a produit les écarts ci-dessous. Une UGS vide ou répétée empêche un rapprochement fiable. Les deux tableaux, avant et après, sont nécessaires. Les codes-barres sont comparés comme du texte.

| SKU / UGS | Before / Avant | After / Après |
| --- | --- | --- |
| SH-100-BLK | 0012345 | 0054321 |
| SH-100-BLU | 0054321 | 0012345 |

This table comes from the separate SKU comparison. The catalogue verifier’s output on these fixtures requires separate execution evidence. Live import, recipient delivery, paid acceptance and settlement are unverified.

Ce tableau provient de la comparaison distincte par UGS. Le résultat du vérificateur de catalogue sur ces données exige une preuve d’exécution distincte. L’importation réelle, la livraison au destinataire, l’acceptation d’une commande payante et l’encaissement restent à vérifier.

Evidence / Preuve: TASK-179574876100. Exact draft SHA-256 / SHA-256 du texte exact: `4354db998e4f0001ed5c33b9345f7ebc8ef3d8b42fa3b1227eebb9ac290b0c6b`.
