# Socle de compétences : changements et vérification

Demande approuvée : compléter les compétences de départ et vérifier qu'elles permettent des actions utiles, en conservant la liberté stratégique des agents.

## Intervention

Les six guides existants couvrent déjà opportunités, contraintes de revenu, distribution, preuve de réalisation, revue indépendante et accès autorisés. Le choix retenu est de les compléter brièvement. L'installation du dépôt SEED ne répondrait pas directement au chargement du contrôleur.

- `idea-verdict.md` : qualifier demande, livraison acceptable, admissibilité au paiement, frais et délai plausible d'encaissement ; poursuivre une piste réalisable quand un accès manque.
- `completion-evidence.md` : transmission facultative de la mission, de l'artefact, du résultat observé et de la prochaine action testable ; coordination des baux et travail indépendant en parallèle.
- `growth-constraint.md` : formulation raccourcie pour conserver les six guides dans le contexte de 8 000 caractères.
- `tests/test_lessons.py` : comparer le contenu complet des six guides au contexte effectivement envoyé, pour Claude et Codex, et vérifier la continuité entre deux cycles.

Ces méthodes n'ajoutent aucune plateforme obligatoire, validation systématique du fondateur, intégration payante ou autorisation d'envoi commercial. Elles utilisent les missions, outils et leçons existants.

## Vérification effectuée

Commande Linux/WSL : `python3 -B -m unittest discover -s tests -p test_lessons.py -v`.

Sept tests réussis. Pour chaque fournisseur, un premier cycle reçoit une décision simulée FETCH, exécute la file avec une réponse HTTP de fixture, puis publie l'artefact dans un dépôt Git temporaire. Le deuxième cycle reçoit les guides complets, la référence au produit et un résultat DONE ; sa décision simulée WORLD enregistre une leçon vérifiée dans la base du monde.

Les dépôts, la file et la base sont réellement manipulés dans des installations temporaires. L'authentification, les décisions du modèle et le réseau sont remplacés par des fixtures. Ces tests prouvent le transport et l'exécution des actions choisies, sans mesurer la qualité commerciale d'un modèle en production.

Un agent de revue a également traité quatre scénarios synthétiques avec les guides avant modification : publication bloquée avec artefact réutilisable, erreur de chemin, bounty inaccessible et bail détenu par un autre agent. Les quatre réponses proposaient déjà des actions utiles. Les clarifications rendent la continuité explicite ; aucun gain causal d'intelligence ou de revenu n'est établi par cet échantillon.

## Critère pour la suite en production

Après intégration, vérifier les publications durables : artefact utile relié à une mission, résultat repris au tour suivant, blocage résolu ou prochaine expérience justifiée. Suivre séparément demande observée, offre distribuée, vente et encaissement confirmé. Un cycle techniquement réussi ne suffit pas à prouver une vente.

État de cette livraison : préparation et validation locale ; activation et observation de décisions réelles restent à effectuer après intégration. Aucun accès bancaire ou nouveau compte n'est créé.
