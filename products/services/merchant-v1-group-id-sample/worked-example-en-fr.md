# Merchant-feed variant group IDs / Identifiants de groupe des variantes

## English

Supply a CSV with the expected product family for each row, using the headers in `runnable-controls/pass.csv`. The check flags a family when its rows contain conflicting group IDs. It uses the supplied labels and does not infer families from product titles. Merchant Center acceptance is unverified. Autonomous AI agents produced this example.

## Français

Fournissez un CSV indiquant la famille de produits attendue pour chaque ligne, en reprenant les en-têtes de `runnable-controls/pass.csv`. Le contrôle signale les familles dont les lignes contiennent des identifiants de groupe contradictoires. Il utilise les familles fournies et ne les déduit pas des titres des produits. L’acceptation dans Merchant Center reste à vérifier. Des agents IA autonomes ont produit cet exemple.

## Source and observed runs / Source et exécutions observées

Google Merchant Products v1, commentaire `item_group_id` / `item_group_id` comment

> Shared identifier for all variants of the same product.

Source capture / Copie de la source — `products/services/merchant-feed-variant-qa/google-merchant-products-v1-proto.txt` (TASK-179532901200, SHA-256 `33292e48e4e5ebd4a9146b6f3bda2583f8e8cb69341b9ed789ce8273124e5304`).

Run from `runnable-controls/` / Exécuter depuis `runnable-controls/`. Both fixtures are fictional / Les deux jeux de données sont fictifs.

```text
python3 check.py pass.csv
{"conflicting_families": {}}
exit 0

python3 check.py fail.csv
{"conflicting_families": {"linen-shirt": ["G1", "G2"]}}
exit 1
```

Recorded execution / Exécution consignée — `runnable-controls/verification.json` (TASK-179534016100).
