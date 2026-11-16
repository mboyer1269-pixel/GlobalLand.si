# Preservation findings — synthetic example / exemple synthétique
Made by autonomous AI agents / Conçu par des agents d'IA autonomes.

EN: Synthetic changed-Barcodes case: source data record 1 (physical lines 2–3), produced data record 1 (physical line 2), SKU '001', field Barcodes: expected '0001', observed 'CHANGED'. These are exact strings, including leading zeros. The quoted title spans two physical lines. No customer data or real Shopify import was tested.
FR : Cas synthétique changed-Barcodes : enregistrement source 1 (lignes physiques 2–3), enregistrement produit 1 (ligne physique 2), SKU '001', champ Barcodes : valeur attendue '0001', observée 'CHANGED'. Les zéros initiaux sont conservés. Aucune donnée client ni importation Shopify réelle n'a été testée.

Reproduce / Reproduire:
python3 products/services/catalogue-qa/preservation-findings/run_checks.py
python3 products/services/catalogue-qa/preservation-findings/locate_preservation.py SOURCE.csv OUTPUT.csv [OUTPUT2.csv ...]

Exit 0: no localized findings; 1: differences or ambiguities; 2: invalid input/usage. Records exclude the header and restart in each file. Physical line ranges include quoted newlines. Exact raw SKU matching; no trimming, numeric conversion or fuzzy matching. Source field values follow verify_example.py's raw-string semantics. Known barcode prefixes and backslash escapes follow verify.py; unknown prefixes remain literal. BOM is accepted for localization, while the unchanged verifier may reject BOM/CRLF as format differences.

Duplicates on either side are ambiguous and never paired. Missing/extra SKU means absence under exact matching, not proof that a variant was deleted or added: a blank or changed key may explain it. Blank produced keys with any compared variant value are flagged; blank keys with all four compared values empty are listed as ignored image-only rows. That label is a scoped exclusion, not validation of the image row. No image mapping, file layout or import acceptance verdict is supplied. Always run the unchanged verifier separately. Tests cover 13 synthetic cases and the existing 20-variant synthetic pair. Human review time and customer delivery remain unmeasured.
