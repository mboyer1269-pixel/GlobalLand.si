# Premier incrément de solidification — 5 novembre 2026

Ce compte rendu valide le code du premier incrément après l'audit Graphify. Il ne déclare ni installation en production, ni connexion bancaire, ni vente. Le [plan complet](../solidification-audit-20261105.md) conserve les exigences encore ouvertes.

## Changements vérifiés

| Constat | Comportement et preuve |
|---|---|
| EXE-01 | FETCH vérifie aussi la taille après encodage et les motifs de secrets avant de produire un artefact. Test Git réel : refus publié, tâche suivante exécutée, reprise sans rejeu. |
| EXE-02 | WORLD conserve son état complet ; la projection et le courtier proposent des pages avec totaux et version. Un monde de plus de 1 Mio reste publié et une mission peut être clôturée. Les missions omises du contexte ne sont pas acquittées comme vues ; les baux prioritaires sont représentés explicitement. La carte de blocage borne également sa liste de missions. |
| EXE-03 | Résultats compacts privés séparés des contenus d'artefacts, migration bornée des anciens journaux et identité stable pour la déduplication. Les observations anciennes sans empreinte restent observables sans inventer une preuve d'entrée. Un cache corrompu ne remplace jamais le journal faisant autorité par un résultat public. |
| EXE-05 | L'action effectuée et la publication en attente restent distinctes dans la réponse du courtier, y compris lors d'une répétition du même identifiant. |
| F1 | La même référence de règlement ne peut créditer deux mois. Rejeu exact, concurrence, reprise après échec d'écriture et doublons historiques sont testés. Aucun solde historique n'est corrigé silencieusement. |
| F2 | Tous les consommateurs utilisent la même projection validée des créances. Absence ou corruption donne `UNAVAILABLE`, pas zéro. Une file continue de fonctionner avec un ledger auxiliaire invalide. |
| F3 | Les nouvelles demandes privées figent les sources de service complètes avec leurs empreintes. Elles entrent uniquement dans le conteneur hors réseau. Le test Docker exécute le diagnostic réellement proposé, vérifie sa version, ses octets de sortie, le reçu et la réponse préparée, puis le rejeu sans réexécution. |
| C1 | L'activation crée son répertoire de sauvegarde sur installation neuve. Le bootstrap l'initialise aussi. |
| C2/C3/C4 | Les quatre Actors sont dans la matrice CI ; le runner domain signale réellement les échecs. Le wrapper CSV contrôle DNS/IP, redirections et lecture bornée. Les quatre wrappers passent avec le SDK Apify réel et une facturation simulée. |

Les sources figées disponibles ne prouvent pas, à elles seules, qu'un modèle les a exécutées. Le reçu `input_service_sources` décrit les fichiers fournis ; la commande réellement exécutée, la sortie et les empreintes établissent le travail accompli.

## Validation intégrée

Archive source isolée : SHA-256 `3175a29568856b15c97b37d5cd664ddcc05ed256d44a1803b952293d8d73da83`. Exécution sous Linux, Python 3.12.3 et Node 22.23.4, sans les comptes ni l'état de production.

- `PYTHONPATH=scripts python3 -B -m unittest discover -s tests -p 'test_*.py'` : **603 tests, succès, 8 ignorés**. Les tests ignorés comprennent quatre contrats CLI réels et quatre tests Docker opt-in.
- `node tests/runtime.test.js` : **8 réussis** ; `node tests/executor.test.js` : **5 réussis**.
- Avec `GLOBALLAND_DOCKER_SMOKE=1`, `test_docker_smoke.py` : **3 réussis** ; `test_private_service_assets.py` : **8 réussis**, dont le nouveau test Docker. Quatre cas jusque-là ignorés sont donc vérifiés ; les sept autres cas de ce second fichier recoupent la suite principale.
- Les quatre `tests/actor_sdk_smoke.py --actor <nom>` passent sous WSL/Python 3.12.3, Apify 4.2.0. Lignes produites et charges simulées : RSS 2/1, liens 2/1, domaines 4/2, CSV 5/1. Aucun débit réel ni appel à un compte Apify.
- Syntaxe des scripts Bash et `git diff --check` : succès. Relectures croisées puis revue indépendante de l'ensemble : aucun défaut bloquant confirmé après corrections.

La première passe intégrée avait révélé 14 échecs, essentiellement la perte d'observations anciennes sans hash ; ils ont été corrigés avant la passe ci-dessus. Un essai Node natif Windows a échoué faute de permission de création de liens symboliques ; la suite complète Linux/Node 22 passe sans contourner ce test. Les assertions et limites de sécurité n'ont pas été retirées pour rendre les tests verts.

## Ce qui reste à prouver

L'échange réel AgentMail avec correction dans le même fil reste distinct des calculs et réponses préparées en tests Docker. Les modèles des tests sont scénarisés : ils ne prouvent pas le choix autonome d'une offre, l'intérêt d'un client ni un paiement.

Le [catalogue Git et les entrées sélectionnées](../solidification-source-catalog.md), les canaux d'acquisition et de paiement, l'intégration du mandat et de la ville, ainsi que les travailleurs parallèles restent des travaux du plan complet. L'ancien plafond d'extraction globale existe encore dans cet incrément. Les quatre contrats CLI optionnels n'ont pas été exécutés par cette validation.
