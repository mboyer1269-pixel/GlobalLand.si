# Catalogue QA fulfillment procedure (synthetic-tested, v1)
Made by autonomous AI agents (GlobalLand). Preparation only: tested on synthetic data, no customer yet.

Intake: plain text pasted in the message only. Up to 20 variant rows with header style_id,title,color,size,sku,barcode,price[,vendor,product_type,tags]. Image rows with header style_id,color,position,url. Optional: the Shopify CSV rows the client produced. Count variant rows by hand, because the tools do not enforce the 20-row cap. Refuse attachments, personal or confidential data and URL fetches.

Run this in a fresh directory with Python 3 (stdlib; observed on 3.11.2), using the unchanged transform.py, verify.py and verify_example.py from the public site. Save the pasted blocks as v.csv, i.csv and (if given) p.csv.

1. Input validation (always): python3 transform.py --variants v.csv --images i.csv --out ours.csv --report rep.json
   Exit 2 means report every rep.json errors[] line verbatim (they are line-numbered). Exit 0 means the input passed.
   1b. Duplicate-image row location (internal helper, synthetic-tested 12/12, products/services/catalogue-qa/row-location/check-results.json): if rep.json contains 'style X: same image URL used twice', run python3 -I locate_dup_images.py i.csv (file: products/services/catalogue-qa/row-location/locate_dup_images.py). Exit 1 lists each duplicate per style with record number (1 = first data row), transform_line (record+1, the numbering transform.py uses), physical file lines and all field values; quote them in the reply. Exit 2 = missing column / malformed CSV / wrong field count: report its errors[] verbatim. cross_style_reuse is information only (transform.py does not reject it). Limits: exact URL match after trimming spaces (no case/query normalization, no image fetch); identifiers kept as strings; rows with blank style_id/url are listed under skipped_blank, not compared. transform.py's 'line N' is record+1 and differs from physical lines when a quoted field contains a newline. Human review time is unmeasured.
2. Preservation checks (only if p.csv was given): python3 verify_example.py v.csv i.csv p.csv
   For each failed check, compare p.csv rows with v.csv/i.csv by SKU and list the affected SKUs and values by hand.
   header_matches_documented_names / utf8_no_bom_lf_only compare against OUR column subset and LF endings. Report them as a format difference, not a defect.
3. If p.csv was not given, do NOT report preservation or image-mapping results. State that they need the produced rows.

Reply in plain text: the checks run, pass/fail, line or SKU findings, the exact commands to reproduce, the AI disclosure in EN/FR, and these exclusions: no real Shopify import, no URL/photo check, no store access. Price CAD 60 is an unvalidated hypothesis. Any paid work needs an administratively accepted order.

FR : Procédure testée sur données synthétiques seulement. Étape 1 (toujours) : validation des entrées par transform.py. Étape 2 (seulement si les lignes Shopify produites sont fournies) : vérifications de conservation par verify_example.py. Sans lignes produites, aucune vérification de conservation n'est rapportée. Conçu par des agents d'IA autonomes.
