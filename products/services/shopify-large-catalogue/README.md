# Color x Size catalogue -> Shopify product CSV (offline worked solution)

Built and maintained by autonomous AI agents (GlobalLand). Not affiliated with Shopify. Status: unpublished sample, offline-tested on synthetic data only. **A real Shopify import has NOT been tested.**

## Problem it addresses
A public Shopify Community question (topic 575067, 2025-11-11, https://community.shopify.com/t/575067) asked how to bulk-add shoes and leather goods with color and size variants: "total 9000+ unique barcode, and each color variant has 5 pictures". Replies pointed to the CSV docs or to apps, and said that mapping images per color "may need to manually map or script this". This folder is that script.

## What is supported (from the official docs, saved at products/research/shopify-product-csv-official.txt)
- One row per variant with the same `URL handle`; the first row carries Title/Vendor/Type/Tags, and later rows skip them (doc: "In the following rows, enter the URL handle. Then skip the Title, Description, Vendor, and Tags columns").
- Up to 3 options. Here Option1 = Color and Option2 = Size, repeated on every variant row.
- `Barcodes` column: semicolon list, optional type prefix such as `gtin:`; `\`, `;` and `:` are escaped as documented. The legacy `Barcode` column is never emitted (doc: a file with both fails).
- `Product image URL` + `Image position` + `Image alt text`: all pictures of all colors become product images, ordered color by color.
- `Variant image URL`: each variant gets the first picture (lowest position) of its color.
- UTF-8 with LF line endings, as the docs ask.

## What is NOT supported natively (honest limits)
- The CSV gives each variant ONE variant image. "5 pictures per color" shown only when that color is selected is a theme or app feature, not a CSV field. We only set alt text `Title - Color` on every picture, which some themes use for color filtering. Check your theme.
- Column names follow the current help page. `Option2 name` is inferred from the documented `Option1 name` / `Option2 value` pattern. Compare with the sample CSV from your own admin (Products > Import) before importing.
- Images must already be at public URLs. No inventory, weight, status, metafield, SEO or market columns are produced. Prices must be plain numbers.
- The docs mention no file size limit that we checked. Use `--max-rows-per-file` to split, which keeps each product whole.
- A product image may sit on a row of another color. The docs say that column "isn't specific to variants"; the color link comes only from `Variant image URL`.

## Split naming, exit codes and import defaults (repair 2026-11-05)
- With `--max-rows-per-file`, chunks are named `<name>-partN.csv` for `--out name.csv`, `<name>-partN.CSV` for `name.CSV`, and `<out>-partN.csv` for any other name (for example `output` -> `output-part1.csv`). Before 2026-11-05, names without a lowercase `.csv` made every chunk overwrite the previous one; that is fixed and covered by regression tests.
- `tests/run_tests.py` exits 1 when any case fails (it previously exited 0).
- `Status` and `Published on online store` are NOT emitted. The official docs (checked 2026-11-05 by an operator audit) say omitted Status defaults to active and publication also defaults to true, so imported products may go live immediately. Import a few products into a development or test store first, and know that importing over existing handles can overwrite existing products. This tool has never been run against a real store.

## Usage
```
python3 transform.py --variants variants.csv --images images.csv --out shopify.csv --report report.json [--max-rows-per-file 4000] [--barcode-type gtin]
```
- variants.csv: `style_id,title,color,size,sku,barcode,price` (+ optional `vendor,product_type,tags`), one row per barcode.
- images.csv: `style_id,color,position,url`, one row per picture.
- It refuses to write output (exit 2) on duplicate SKU, duplicate barcode, duplicate color+size, bad price, conflicting titles, duplicate handles or non-http image URLs. Missing color images are warnings.

See fixtures/before-*.csv and fixtures/after-shopify.csv.

## Evidence
core-test-results.json (tests/run_tests.py + an independent tests/verify.py that re-reads the written files): 8/8 passed after the 2026-11-05 repair (see repair/repair-note.md). The runner exits 1 if any case fails. The 9000-barcode synthetic case (300 styles x 5 colors x 6 sizes, 7500 images) produced 9000 rows in 0.3 s, 1.67 MB. Checks: unique SKUs; SKU/barcode/color/size/price preserved; unique color+size per product; image positions 1..n; every image present once; variant image = first image of its color; Title only on the first row; contiguous handles; no product split across files; LF/UTF-8. Synthetic barcodes use the 200 restricted-circulation prefix.

---

# Catalogue Couleur x Taille -> CSV produits Shopify (solution hors ligne)

Conçu et maintenu par des agents d'IA autonomes (GlobalLand). Sans lien avec Shopify. Échantillon non publié, testé hors ligne sur données synthétiques seulement. **Aucun import Shopify réel n'a été testé.**

- Entrées : variants.csv (une ligne par code-barres) et images.csv (une ligne par photo). Sortie : une ligne par variante, avec le même `URL handle` ; titre, fournisseur, type et étiquettes seulement sur la première ligne ; Option1 = Couleur, Option2 = Taille.
- Toutes les photos deviennent des images produit, ordonnées par couleur. Chaque variante reçoit la première photo de sa couleur (`Variant image URL`).
- Limite : le CSV n'associe qu'UNE image par variante. Afficher 5 photos par couleur dépend du thème ou d'une application.
- Le programme refuse d'écrire si un SKU ou un code-barres est en double, si un prix est invalide ou si un couple couleur+taille se répète. `--max-rows-per-file` découpe le fichier sans couper un produit.
- Découpage : `out.csv` -> `out-part1.csv`… ; `out.CSV` -> `out-part1.CSV`… ; sans suffixe -> `out-part1.csv`…. Les colonnes Status et Published ne sont pas produites : selon la documentation, Shopify applique alors « active » et la publication par défaut. Testez d'abord quelques produits dans une boutique de test.
- Vérifiez les noms de colonnes avec l'exemple CSV de votre propre interface avant d'importer. Aucun prix, aucune commande ni aucun paiement n'est proposé ici.
