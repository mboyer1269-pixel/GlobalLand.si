# Validation du moteur autonome v3

Base de développement : f221559de98c9e8e698d2628395b426ee071b69c. L'instance actuellement déployée reste v2 jusqu'à mise à niveau explicite. Les nouvelles connexions d'abonnement et financières ne sont pas supposées actives.

## Résultats locaux

- Node24 local : `node tests/runtime.test.js` 8/8 ; `node tests/executor.test.js` 2/2.
- Python3.12 : `python3 -m unittest discover -s tests -p 'test_*.py'` 60 tests,59 passent,1 smokeDocker explicitement sauté (pas d'accès au démon ici).
- Syntaxe Python : `python3 -m py_compile scripts/*.py` passe.
- Syntaxe shell : `bash -n scripts/*.sh` passe.
- `git diff --check` passe.
- Aucun appel de modèle, connexion de compte, achat, trade ou transfert d'argent dans ces vérifications.

Les fixtures corrigent une fragilité de v2 : ses tests dépendaient du ledger vivant et d'une tâche inbox déjà consommée par le VPS. Le ledger réel du dépôt n'a pas été modifié pour faire passer les tests.

## Couverture concrète

Trésorerie : 5000centimes utilisables en totalité une fois prouvés, refus5001, réservations concurrentes, types stricts, preuve rejetée par défaut, anti-rejeu et identité des demandes, paiement UNKNOWN retenu après redémarrage, annulation prouvée, dette observée non masquée, extinction terminale, positions et liquidation rapprochées atomiquement, revenus synchronisés sans double comptage.

Monde : identités, prêts et transferts GLC, émission explicite, missions hiérarchiques, concurrence des baux, preuves de clôture, messages, politiques et cycles idempotents, liquidation/réaffectation et extinction persistante. Les preuves de mission ne constituent pas des reçus financiers.

Contrôleur : configuration absente affichée honnêtement, modèles d'abonnement sans reprise API, vérification CLI/login sans inférence, lecture des vrais journaux, décisions validées, outbox récupérée après changement d'horodatage, acquittement après publication, nettoyage du conteneur nommé et invalidation de readiness après échec. Les tests remplacent les appels CLI par des réponses factices.

Outils/transport : commandes choisies librement dans le sandbox, chemins protégés, liens/hardlinks, secrets, HTTP public/DNS fixé, limites d'I/O y compris stdin bloqué, artefacts et hashes, Git bare réel, tâche WORLD/FETCH vers produit publié, FETCH→EXEC dans un même lot, conflit concurrent préservé, reprise d'un push sans réexécution, conservation d'un témoin Oria à l'extinction et suppression des copies de travail EXEC.

La CI utilise Node22/Python3.12 et un vrai Docker pour `test_docker_smoke.py` : programme choisi par l'agent, fichier produit dans tmpfs, résultat remonté sans accès aux fichiers hôte. Les résultats CI sont consultables dans la PR ; une réussite locale ne remplace pas ce test.

## Revues et corrections

Analyses indépendantes de l'architecture financière et du runtime ; revues dédiées de Treasury, World et Controller ; revue globale de l'intégration. Les défauts confirmés ont eu des régressions reproduites avant correction : effacement d'une dette par le financement initial, extinction oubliée après dépassement, fausse extinction lors de liquidation, décisions orphelines, conteneurs non arrêtés, readiness incohérente, lecture de contexte, publication écrasant une modification amont, source périmée entre tâches et copies persistantes.

## Décisions et limites

- Les revenus réinvestissables augmentent l'enveloppe uniquement après preuve de règlement. Aucune mise personnelle supplémentaire.
- Les50CAD déclarés historiquement sont distincts de l'argent effectivement vérifié ; UNFUNDED n'est pas une faillite.
- Le zéro d'argent réservé n'est pas un patrimoine perdu. Les positions et produits de liquidation sont rapprochés avant une extinction irréversible.
- Les images locales identifiées par sha256 immuable sont acceptées, sans registre payant obligatoire.
- Les fournisseurs réels, comptes/KYC, limites de débit et extra usage des abonnements ne sont pas configurés ou vérifiés ici. Aucun prestataire de réception de carte étudié ne garantit, à lui seul, une responsabilité totale limitée à50CAD. Voir docs/INTEGRATIONS.md.
- Quelques frontières World restent sans assertion dédiée : seconde exacte d'expiration de bail, mauvais propriétaire avant expiration, arrondi indépendant d'intérêt, action d'un agent désactivé, limite de projection des événements, rejeu après opération invalidée. Aucun comportement incorrect identifié dans leur revue.

Aucun déploiement de v3 ni moteur d'inférence réel connecté n'est revendiqué par ce rapport. La procédure fournit une mise à niveau avec conservation de l'état, des connexions officielles privées, un contrôle de disponibilité et des tests manuels avant horaires think.
