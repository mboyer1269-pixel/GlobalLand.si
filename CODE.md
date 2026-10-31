# Architecture et état de GlobalLand

## Quatre variables officielles initiales

1. Trésorerie : **50 CAD**, réserve verrouillée **50 CAD**, disponible sans CEO **0 CAD**.
2. Revenus déclarés au genesis : **0 CAD**. Seul le ledger courant fait foi.
3. KPI : cashflow positif et solde de **100 CAD** ; objectif intermédiaire de **10 CAD** nets.
4. Limites : **1 Go RAM / 0,5 CPU** ; plafond constitutionnel **2 CAD/jour**. Le canal actuel n'autorise aucune tâche payante et ne possède aucune clé API.

## Frontière d'exécution

`/opt/globalland/control` contient le superviseur Python et les modules Node installés depuis un commit revu. Ce code ne se met jamais à jour automatiquement. Le cron appelle Python via un chemin fixe.

`source.git` est un dépôt bare privé. Aucun checkout Git ni fichier `.git` n'est monté dans le conteneur. Les exports Git refusent liens et fichiers spéciaux et sont plafonnés à 16 Mio, 1 Mio par fichier. L'index de publication est privé ; aucun hook ou filtre du dépôt téléchargé n'est exécuté.

`work` est un export éphémère, en lecture seule pour le conteneur non privilégié, hors réseau, sans clés, sans socket Docker. Seul le registre `SHELL/AUDIT` est public. Le tick quotidien est une opération interne de confiance.

`state` contient les journaux durables, le hash des octets d'entrée et les résultats préparés avant publication. Audit et file partagent un verrou. Un ID déjà connu ne peut pas lancer de nouveau travail. Une interruption est signalée et ne provoque jamais une relance automatique de l'action.

## Comptabilité

`ledger.json` reste la source financière. Le capital genesis n'est pas changé par cette correction. Les calculs CAD se font en centimes et sont rapprochés avec le solde. Les montants des transactions sont positifs : `REAL_REVENUE` ajoute, `REAL_EXPENSE` retranche. `approved_by: CEO` dans un ledger est une déclaration historique, pas une preuve cryptographique bancaire.

`NARRATIVE_SERVER_TAX` et l'ancien alias `SERVER_TAX_NARRATIVE` affectent uniquement le runway narratif ; `GLC_TRANSFER` reste séparé du CAD. Aucun prélèvement narratif nouveau n'est fabriqué automatiquement. Le runway affiche la réserve réelle diminuée du cumul des taxes narratives déjà inscrites, divisée par la taxe hebdomadaire, plus la grâce. Sans taxe hebdomadaire, le runway est illimité (`null` en JSON).

`DAY_TICK` vaut zéro et porte un horodatage UTC. Le premier tick valide enlève un jour ; les suivants enlèvent les jours UTC écoulés depuis `last_tick_date`, au plus jusqu'à zéro. Une seconde exécution le même jour ne change rien ; un retour d'horloge est refusé.

Le journal `logs/transactions.log` est une projection régénérable du ledger validé. Le superviseur publie les deux dans le même commit. Les écritures locales du CLI tick sont atomiques fichier par fichier, sans garantie transactionnelle inter-fichiers ; en cas d'interruption, relancer reconstruit le journal depuis le ledger. Le VPS utilise une préparation en mémoire puis un commit commun.

Le cashflow est la somme réelle des revenus moins dépenses des sept jours UTC se terminant au jour du rapport. Le capital initial, le narratif et les GLC en sont exclus. Aucun revenu ni paiement n'est inventé ; les preuves bancaires restent à valider par le CEO.
