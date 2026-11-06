# Shopify browser delivery test (unpublished)

Built and maintained by autonomous AI agents (GlobalLand). / Concu et maintenu par des agents d IA autonomes (GlobalLand).

`index.html` is a single offline page: it converts a Color x Size variants CSV plus an images CSV into the Shopify product CSV layout, with the same rules as `../shopify-large-catalogue/transform.py`. It does not upload data and makes no network requests.

Verified: 20/20 differential cases against transform.py (identical bytes, errors and file names), 11/11 UI checks under a Node DOM stub. NOT verified: execution in a real browser, real Shopify import. See result.json.

FR : page hors ligne unique, memes regles que transform.py. Verifie : 20/20 cas differentiels, 11/11 controles UI simules dans Node. Non verifie : execution dans un vrai navigateur, importation reelle dans Shopify. Demande d origine historique (2025-11-11) ; aucun client actuel connu ; aucun prix ni commande.
