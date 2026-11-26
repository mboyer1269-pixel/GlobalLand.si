# SQLite invoice totals regression exercise / Exercice de régression sur les totaux de factures SQLite

Package SHA-256 / Empreinte SHA-256 du fichier ZIP décodé : `80b451146e7cdf45c3adada847d22dbe1dcaa8c192077cdf08b6d1fe323c6364`.

## English

Built by autonomous AI agents. The exercise uses five fictional datasets to show how joining invoices to tags can inflate totals and how summing distinct amounts can suppress separate invoices with the same amount. It runs locally and is intended for practice with SQLite queries.

Extract the ZIP into an empty folder. Keep `invoice-regression.py` and `invoice-fixtures.json` together. From that folder, run:

- `python3 invoice-regression.py exists` — exit 0, all five cases pass.
- `python3 invoice-regression.py join` — exit 1, one invoice with two tags totals 200 instead of 100.
- `python3 invoice-regression.py distinct_amount` — exit 1, two invoices with equal amounts total 100 instead of 200.

Reference execution used Python 3.11.2 and SQLite 3.40.1. Review the `expected`, `actual` and `passed` fields in each JSON result. The files contain fictional inputs and cover the five included cases.

## Français

Créé par des agents d’IA autonomes. L’exercice utilise cinq jeux de données fictifs pour montrer comment une jointure avec des étiquettes peut gonfler le total des factures et comment la somme des montants distincts peut écarter des factures différentes de même montant. Il s’exécute localement et sert à pratiquer les requêtes SQLite.

Décompressez le fichier ZIP dans un dossier vide. Gardez `invoice-regression.py` et `invoice-fixtures.json` dans le même dossier. Depuis ce dossier, exécutez les commandes suivantes.

- `python3 invoice-regression.py exists` — code de sortie 0, les cinq cas réussissent.
- `python3 invoice-regression.py join` — code de sortie 1, une facture avec deux étiquettes donne 200 au lieu de 100.
- `python3 invoice-regression.py distinct_amount` — code de sortie 1, deux factures de même montant donnent 100 au lieu de 200.

L’exécution de référence utilisait Python 3.11.2 et SQLite 3.40.1. Consultez les champs `expected`, `actual` et `passed` des résultats JSON. Les fichiers contiennent des données fictives et couvrent les cinq cas fournis.
