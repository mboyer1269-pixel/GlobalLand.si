# SQLite inventory reconciliation preview

A ten-minute exercise with fictional inventory. Find out why a missing count can disappear from a discrepancy report. Run `python3 run.py` from this directory with Python 3 and its standard SQLite module. Then open `before.sql` and `after.sql` and compare the filters. The first report shows DEMO-C, which was counted at 5 against 6 expected. The corrected report also shows DEMO-B and DEMO-D with a missing count. DEMO-D tests that an expected quantity of zero still differs from a missing count. DEMO-A is the matching control. This checks expected SKUs only. Try adding an unexpected counted SKU and consider what a second query would need to report.

## Aperçu de rapprochement des stocks avec SQLite

Un exercice de dix minutes sur des stocks fictifs. Découvrez pourquoi un comptage manquant peut disparaître d’un rapport d’écarts. Lancez `python3 run.py` dans ce dossier avec Python 3 et son module SQLite standard. Comparez ensuite les filtres de `before.sql` et `after.sql`. Le premier rapport affiche DEMO-C, avec 5 unités comptées pour 6 attendues. Le rapport corrigé affiche aussi DEMO-B et DEMO-D, dont le comptage manque. DEMO-D montre qu’une quantité attendue de zéro diffère d’un comptage manquant. DEMO-A sert de témoin concordant. L’exercice porte sur les références attendues. Ajoutez une référence comptée imprévue et réfléchissez à ce qu’une deuxième requête devrait signaler.

Produced by autonomous AI agents using original SQL, instructions and fictional data. / Produit par des agents IA autonomes avec du SQL, des instructions et des données fictives créés pour cet exercice.
