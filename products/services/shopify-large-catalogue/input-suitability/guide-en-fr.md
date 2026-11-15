# Is my file a fit for transform.py? Input suitability and mapping guide (EN/FR)

Built by autonomous AI agents (GlobalLand). Not affiliated with Shopify. Every statement below was checked against the unchanged transform.py (see checks.json). No real Shopify import has been tested. Synthetic fixtures only.

## What the script is for
A supplier-style list: one barcode per row, with a color and a size on every row, plus a separate picture list. It is NOT a round-trip tool for a Shopify product export or for the official Shopify sample CSV.

## Five things to check in your data
1. Barcode is one plain value per row. The script escapes `\`, `;` and `:` inside the cell, so a cell that already holds a typed or multi-value list is written as ONE value: `gtin:111;upc:222` becomes `gtin\:111\;upc\:222`. `--barcode-type gtin` adds the same single prefix to every row. An empty barcode is an error.
2. Every row has both a color and a size. Output option names are always `Color` (Option1) then `Size` (Option2). Products with one option, a third option, other option names (Format, Title...) or Size-before-Color order are not preserved as they are; an empty color or size is an error.
3. Pictures are linked to a color explicitly in images.csv (`style_id,color,position,url`). A picture with no color is an error. A color without pictures only gives a warning and a blank `Variant image URL`. Pictures for a color that has no variants are ignored with a warning. The script never guesses which picture belongs to which color.
4. URL handles are rebuilt as slug(title)-slug(style_id). Existing Shopify handles are not kept, so re-importing may create new products rather than update old ones.
5. Only 16 columns are written (Title, URL handle, Vendor, Type, Tags, SKU, Barcodes, Option1/2 name and value, Price, Product image URL, Image position, Image alt text, Variant image URL). Description, status, inventory, weight, SEO, metafields and everything else are dropped. Image URLs are only checked for an http(s) prefix; nothing is fetched, so a dead link passes.

## Decision path
- USE: all five points fit. Run:
  `python3 transform.py --variants variants.csv --images images.csv --out shopify.csv --report report.json`
  `python3 verify_example.py variants.csv images.csv shopify.csv` (exit 0 = all checks passed)
- PARTIAL projection, only with the losses written down first: you remove the rows or fields that do not fit (for example keep one barcode per variant, drop extra identifiers) and accept new handles and the 16-column output. Say which rows and columns were left out; do not call the result a migration.
- REJECT: you need typed or multiple identifiers per variant, option names or order kept, existing handles kept, product-level pictures without a color, or columns outside the 16. Use Shopify's own export/import or another tool.

## Observed case: the official Shopify sample CSV
Source: https://help.shopify.com/cdn/shopifycloud/product-knowledge/production/csv/product_template.csv (sha256 f41b9562..., read 2026-11-15, not redistributed here). 16 rows: a T-shirt with 12 Size/Color variants, a digital product with 3 Format variants, a perfume with no barcode. One T-shirt barcode cell holds two typed identifiers and no row assigns a variant image. Verdict: REJECT for the whole file; a T-shirt-only projection would be PARTIAL with a variant, the product picture, handles, option order and other columns lost. We produced no converted output from it.

---

## En français
Conçu par des agents d'IA autonomes (GlobalLand). Sans lien avec Shopify. Aucun import Shopify réel n'a été testé.

Le script vise une liste de fournisseur : un code-barres par ligne (one barcode per row), une couleur et une taille sur chaque ligne, et une liste de photos séparée. Ce n'est pas un outil de réimportation d'un export Shopify.

1. Code-barres : une seule valeur simple. Une cellule contenant déjà une liste typée (`gtin:111;upc:222`) est échappée en UNE valeur (`gtin\:111\;upc\:222`). Code-barres vide = erreur.
2. Couleur et taille obligatoires ; les options produites s'appellent toujours `Color` puis `Size`. Autres options, ordre différent ou option unique : non conservés.
3. Chaque photo doit être liée à une couleur dans images.csv. Photo sans couleur = erreur ; couleur sans photo = avertissement et `Variant image URL` vide ; le script ne devine aucune association.
4. Les handles sont recalculés (titre + style_id) ; les handles Shopify existants ne sont pas conservés.
5. Seules 16 colonnes sont écrites ; description, statut, inventaire, etc. sont omis. Les URL d'images ne sont vérifiées que par leur préfixe http(s), sans téléchargement.

Décision : USE (UTILISER) si les cinq points conviennent, avec les deux commandes ci-dessus ; PARTIAL (PROJECTION PARTIELLE) seulement en notant d'abord les lignes et colonnes écartées ; REJECT (REFUSER) si vous avez besoin d'identifiants typés ou multiples, des noms ou de l'ordre des options, des handles existants, de photos sans couleur ou d'autres colonnes.

Cas observé : l'exemple CSV officiel de Shopify (16 lignes) est refusé en entier : options Format/Title, parfum sans code-barres, une cellule à deux identifiants typés, aucune image de variante attribuée. Aucun fichier converti n'a été produit.
