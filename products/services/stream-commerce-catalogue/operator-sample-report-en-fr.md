# Sample catalogue QA report / Exemple de rapport de contrôle de catalogue

## English

On fictional CSV files, the baseline passed (exit 0). After one barcode was changed, the verifier returned exit 1 and flagged only the grouped check for SKU, barcode, color, size and price preservation. To identify which field and row changed, compare the source and produced rows manually using the SKU. In this example, the comparison concerns the barcode.

Autonomous AI agents prepared this example. The check ran offline on CSV data. It did not access a store or perform a Shopify import.

## Français

Sur des fichiers CSV fictifs, le lot de référence a réussi le contrôle (code de sortie 0). Après la modification d’un seul code-barres, le vérificateur a renvoyé le code 1 et signalé un échec uniquement pour le contrôle groupé de conservation du SKU, du code-barres, de la couleur, de la taille et du prix. Pour repérer le champ et la ligne en cause, comparer manuellement les lignes sources et produites à l’aide du SKU. Dans cet exemple, la comparaison porte sur le code-barres.

Des agents IA autonomes ont préparé cet exemple. Le contrôle a été effectué hors ligne sur des données CSV, sans accès à une boutique ni importation dans Shopify.

## Operator reference / Référence pour l’opérateur

Executed evidence / Contrôle exécuté: TASK-179567856110, `stream-barcode-evidence.json` (SHA-256 `054cd5eb38f152d41365a4eb914da103a04f4f8cc94738222642c1be8658240a`). Outreach draft / Brouillon de prise de contact: SHA-256 `4354db998e4f0001ed5c33b9345f7ebc8ef3d8b42fa3b1227eebb9ac290b0c6b`. The sample is optional supporting material for the unsent draft.
