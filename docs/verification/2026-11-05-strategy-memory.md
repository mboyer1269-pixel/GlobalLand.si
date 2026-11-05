# Conclusions stratégiques révisables — 5 novembre 2026

Le contrôleur présentait les leçons comme des acquis à ne pas réapprendre, en retirant leur date. Une conclusion sur une expérience pouvait ainsi être réutilisée comme une restriction générale. Ce changement conserve les textes, leur ordre de sélection et leur provenance, ajoute leur date connue ou nulle, puis distingue les conclusions des agents des observations de l'hôte.

Les descriptions de blocages et les plans/produits restent des rapports d'agents. Leur répétition ne constitue pas une validation indépendante. Une mission achevée ne certifie pas toutes les conclusions de sa leçon. Les faits établis par les capacités, la trésorerie et les reçus gardent leur portée précise.

Le directeur est invité à expliciter dans son résumé le fait, les opérations dépendantes, sa conclusion et le déclencheur de réexamen lorsqu'il attend ou décrit un blocage général. L'attente reste autorisée ; aucune action, nouvelle stratégie ou niche n'est injectée. Aucun historique, droit, outil, format de décision ou stockage n'est modifié.

## Vérification

Les nouveaux tests ont d'abord échoué sur la projection absente, la sémantique manquante et l'ancienne instruction du prompt. Après correction, les suites ciblées passent sous Python 3.12/WSL avec Node 22 :

| Suite | Tests réussis |
|---|---:|
| strategy_memory | 4, avec variantes Claude/Codex et attente/action |
| lessons | 7 |
| controller | 15 |
| progress | 15 |
| decision_protocol | 21 |
| result_feedback | 11 |
| commercial_paths | 7 |

Les scénarios utilisent World et Treasury temporaires : conclusions répétées dans des leçons, blocages et produits ; changement d'un prérequis de l'exécuteur ; financement toujours `UNFUNDED` ; reprise du même tour sans nouvelle décision ; absence de mutation des leçons. Le catalogue de produits expose leurs chemins, pas automatiquement leur contenu : le test ne prétend pas que chaque produit a été lu par le modèle. Le supplément de contexte est vérifié sous 4 Kio avec les quotas actuels.

Ces tests prouvent le transport du contexte et la conservation des contrats. Les décisions de modèle sont simulées ; ils ne prouvent ni un raisonnement plus efficace, ni une initiative réelle, ni un revenu. La comparaison comportementale isolée et l'observation en production restent distinctes.

Les révisions structurées des leçons sont une phase ultérieure, séparée de cette correction sans migration. Cette branche ne dépend pas du catalogue de sources de la PR #29. Une installation nécessite la sauvegarde habituelle ; le retour à l'ancien contrôle ne demande aucune migration de données.
