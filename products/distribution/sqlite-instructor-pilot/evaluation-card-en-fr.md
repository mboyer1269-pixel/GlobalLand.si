# SQLite classroom preview / Aperçu SQLite pour la classe

## English

Give learners a fictional inventory database. Ask them to predict which items a LEFT JOIN will retain when a condition on the joined table is placed in WHERE, then move the condition into ON and explain the change. Run `python3 run.py` from the extracted preview archive.

Use three answers to check understanding. The first query retains only DEMO-C. The corrected query retains DEMO-B, DEMO-C and DEMO-D. The right-hand value for DEMO-B and DEMO-D is NULL. A learner should be able to explain that the WHERE predicate filters out the NULL-extended rows, while the ON predicate limits matches and preserves rows from the left table.

The command exited 0 on SQLite 3.40.1 in the recorded offline run. Classroom use and timing are unmeasured. Autonomous AI agents made this exercise. This is a staged evaluation card for a free preview. It contains no order or payment instructions.

## Français

Présentez aux personnes apprenantes une base de données d’inventaire fictive. Demandez-leur de prédire quels articles une jointure LEFT JOIN conservera si une condition sur la table de droite figure dans WHERE. Faites ensuite déplacer la condition dans ON et expliquer le changement. Exécutez `python3 run.py` à partir du dossier où l’archive d’aperçu a été extraite.

Vérifiez trois réponses. La première requête conserve seulement DEMO-C. La requête corrigée conserve DEMO-B, DEMO-C et DEMO-D. La valeur de la table de droite est NULL pour DEMO-B et DEMO-D. Les personnes apprenantes doivent pouvoir expliquer que le prédicat WHERE élimine les lignes complétées par NULL, alors que le prédicat ON limite les correspondances et conserve les lignes de la table de gauche.

La commande s’est terminée avec le code 0 dans l’essai hors ligne consigné avec SQLite 3.40.1. L’utilisation en classe et la durée n’ont pas été mesurées. Des agents d’IA autonomes ont créé cet exercice. Cette fiche préparatoire accompagne un aperçu gratuit et ne contient aucune instruction de commande ou de paiement.

## Verification / Vérification

Execution receipt / Résultat d’exécution — TASK-179579196100

Preview archive SHA-256 — `8325a93711826740de4fffb9d43a312b048b26a43212280fd53df55fb5c11eb2`
