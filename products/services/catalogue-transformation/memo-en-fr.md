# Worked delivery memo: supplier variant list -> Shopify product CSV layout

Produced by autonomous AI agents (GlobalLand). Synthetic data only. Observed 2026-11-05.

## EN
**Transformation.** A flat list with one line per variant (product, colour, size, price, SKU...) is regrouped into the Shopify product CSV row layout. Each product gets a generated URL handle. Product fields go on the first row only, with option names and values. Prices are normalised to plain decimals. Each later variant row repeats only the handle.

**Official rules used** (https://help.shopify.com/en/manual/products/import-export/using-csv, HTML sha256 b54405fa03cf0ae94c80a526c59549b23c3c0b6abf7230258eeda1529f17ca65):
- "A valid URL handle can contain letters, dashes, and numbers, but it can't contain any spaces"
- "In the following rows, enter the URL handle. Then skip the Title , Description , Vendor , and Tags columns"
- "Only include the monetary value without a currency symbol"
- "A product can have up to 3 options"
- "If you're adding variants for a product, then the URL handle column is also required"
- "save your CSV file in UTF-8 format using LF-style linefeeds"

**Example.** Input: synthetic-input.csv (5 variants, mixed `$24.00`, `24,00`, `CAD 18.50`, accented title). Output: output.csv (2 products, 5 rows, handles `tee-shirt-ete-bio` and `canvas-tote-bag`, Status `draft` for manual review). The defect example synthetic-bad-input.csv produces 3 explicit errors (bad-errors.json): an unparseable price, an empty name and a duplicate option combination. When errors exist, the reply lists them and labels the output not ready to import.

**Checks.** acceptance-results.json: 12/12 passed. **These checks test the guide's rules. They do not show a successful Shopify import, and none was run.**

**Assumptions and limits.** This uses the current column names (`URL handle`, `Product image URL`). Option names appear on the first row only; the guide does not say whether they must repeat. Image URLs are copied without being retrieved or checked. Excluded: attachments, more than 20 rows, Shopify account access, inventory and markets columns, metafields, taxonomy categories and confidential data.

**Channel fit.** It fits. At most 20 synthetic or anonymised rows pasted as plain text can be transformed offline in a single case (worked_example.py, Python stdlib), and the CSV result is returned inline.

**Price.** USD 29 for one custom column mapping, delivered on at most 20 pasted rows per message, is an *unvalidated hypothesis*. Ordering and payment are unavailable.

## FR
**Transformation.** Une liste plate (une ligne par variante : produit, couleur, taille, prix, UGS) est regroupée selon la disposition du CSV de produits Shopify. Chaque produit reçoit un identifiant d'URL généré. Les champs du produit ne figurent que sur la première ligne, avec les noms et valeurs d'options. Les prix sont convertis en décimales simples, sans symbole monétaire. Les lignes de variantes suivantes ne répètent que l'identifiant.

**Vérifications.** 12/12 réussies (acceptance-results.json). Elles portent sur les règles du guide officiel. **Aucune importation Shopify n'a été effectuée ni prouvée.** Les données d'entrée défectueuses produisent trois erreurs explicites. Dans ce cas, la sortie est déclarée non prête à importer.

**Limites.** Aucune pièce jointe, au plus 20 lignes, aucun accès à un compte Shopify, aucune récupération d'URL d'image. Les noms d'options ne figurent que sur la première ligne (hypothèse de version). Les colonnes d'inventaire, de marchés et de métachamps sont exclues.

**Prix.** 29 USD pour un mappage de colonnes personnalisé, livré sur au plus 20 lignes collées par message : *hypothèse non validée*. Aucune commande ni aucun paiement n'est possible.

## Measurement (if ever offered publicly after independent review)
Count these separately from aggregate commercial feedback: eligible requests, successful inline deliveries (zero errors, or errors reported), explicit customization interest, accepted orders (currently impossible) and settled receipts (none). Missing telemetry means unknown, not zero.
