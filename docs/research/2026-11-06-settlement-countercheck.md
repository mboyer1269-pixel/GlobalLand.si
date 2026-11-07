# Encaissement — contre-vérification des pistes proposées

État public examiné : `87f422ad00de48fb1a1bb88a6690f94b33f81dd3`.
Sources officielles consultées le 6 novembre 2026. Travail documentaire,
sans accès bancaire, inscription, acceptation de conditions ou paiement.

## Ce qui motive cette vérification

`products/research/platform-managed-settlement-fit.json` propose Gumroad sous
condition d'ouverture d'un compte. `world/blockers.json` reprend cette étape
dans `SERVICE-PAYMENT-COLLECTION`. La recherche a consulté tarification,
versements et conditions, mais n'analyse pas la responsabilité financière
restant au vendeur. Cette omission change la prochaine action : désigner un
compte ne suffit pas à démontrer la conformité au mandat financier.

Le rapport des agents reste intact. Ce complément peut servir à leur prochaine
réévaluation ; il ne change ni leurs missions ni leurs conclusions dans SQLite.

## Résultats sourcés

| Point | Preuve | Conséquence pour GlobalLand |
|---|---|---|
| Gumroad prend en charge le traitement des litiges, mais peut en répercuter les sommes et coûts raisonnables au vendeur | [Conditions, section 7.1](https://gumroad.com/terms) | « Merchant of record » ne démontre pas une responsabilité plafonnée. |
| Un solde Gumroad négatif peut entraîner un débit bancaire par le processeur | [Aide sur les soldes](https://gumroad.com/help/article/269-balance-page) | Un solde local de 50 CAD ne suffit pas à borner un débit externe. |
| Apify ramène à zéro le profit mensuel négatif d'un Actor PPE | [Gestion des versements](https://docs.apify.com/actors/monetize/monthly-payouts) | Cette règle porte sur le calcul du profit de cet Actor, pas tous les engagements du créateur. |
| Apify laisse les coûts des services tiers au créateur et peut demander le remboursement de certains versements frauduleux ou non conformes | [Conditions, sections 5.1 et 10.4.4](https://docs.apify.com/legal/store-publishing-terms-and-conditions) | Une absence de carte ou un plan gratuit ne prouve pas à elle seule une absence de toute obligation future. |

Autre incertitude concrète : l'aide Apify annonce un seuil de 20 USD pour PayPal
et Wise, alors que les conditions de publication réservent 20 USD à PayPal et
annoncent 100 USD pour les autres moyens. Ne pas garantir un seuil Wise sans
confirmation applicable au compte choisi. Cette divergence ne prouve ni une
erreur du compte, ni une indisponibilité du service.

## Ce que cela ne démontre pas

Il ne s'agit pas d'un avis juridique exhaustif ni de la preuve qu'aucun montage
compatible n'existe. Aucun incident ou dette de GlobalLand n'a été observé.
Aucune solution de remplacement n'est déclarée admissible par défaut.

Le mandat existant demande des engagements financiers bornés et protège les
autres fonds du fondateur. La conclusion technique est donc **compatibilité
non établie**, et non « activer dès que le compte est créé ». Une configuration
ou un engagement contractuel applicable peut fournir une preuve complémentaire ;
un changement de mandat relève du fondateur, pas d'un paramètre silencieux.

## Prochain raccordement utile

Identifier les comptes dédiés déjà disponibles, puis examiner le parcours
exact : action accessible aux agents, collecte, livraison, frais, règlement,
remboursement et reprise. Ne coder l'adaptateur spécifique qu'avec un contrat
d'accès documenté et une preuve du service réellement accessible.

La recherche d'un marché et d'une offre reste du ressort des agents. Le test
commercial devra conserver les étapes distinctes : réponse observée, commande,
livraison, versement et crédit rapproché. Un lien de paiement ou un reçu d'envoi
ne remplit pas toute cette chaîne.
