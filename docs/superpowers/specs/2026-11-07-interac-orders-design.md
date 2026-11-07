# GlobalLand — dépôt automatique et rapprochement des commandes

État : conception approuvée explicitement le 7 novembre 2026. Le code fait l'objet
d'une branche de développement distincte ; ce document n'atteste aucun déploiement
ni crédit Treasury. L'activation bancaire doit être constatée séparément.

## Décisions confirmées

- Le fondateur dispose d'un compte Wealthsimple entreprise individuelle, sans
  incorporation. Le compte destinataire affiché est « Global Land ».
- Le fondateur a choisi `globalland@agentmail.to` pour le dépôt automatique et
  comprend que les notifications arriveront dans la boîte accessible aux agents.
- Les offres, les marchés et les canaux restent au choix des agents. Interac est
  un moyen disponible, pas une consigne de se limiter aux clients canadiens.
- La confirmation manuelle d'un dépôt bancaire est une étape transitoire. Aucun
  accès automatisé aux opérations Wealthsimple n'a été établi.

## Parcours retenu et alternatives

Le parcours minimal utilise le compte et la boîte existants : référence de
commande → instructions Interac → dépôt constaté par le fondateur → rapprochement
privé. Une intégration bancaire/API pourrait remplacer cette confirmation plus
tard, après vérification de son accès réel. Une boutique ou une plateforme de
vente imposée n'est pas nécessaire. Un nouveau processeur de cartes ne fait pas
partie de cette étape.

## Ce qui existe réellement dans le code

Base examinée : PR37 fusionnée, commit `090025d7b231456b08d8664f747695e10c6c9661`.
Les changements `main` observés jusqu'à `f9da738` ne modifient pas scripts/docs/tests.

- `scripts/commercial.py` traite des interprétations de courriels, pas des
  commandes ou preuves de paiement.
- `scripts/mail.py::_should_ignore` filtre plusieurs notifications automatiques ;
  aucun parcours bancaire spécifique n'existe.
- `scripts/mail_agent.py` et `scripts/private_work.py` interdisent actuellement
  les engagements contractuels et ne déclarent pas de route de paiement active.
- `scripts/treasury.py` sait distinguer une recette attestée `FOUNDER` d'une
  preuve automatique et la créditer indépendamment du financement initial.
- `scripts/payouts.py` est spécifique à Apify et aux factures mensuelles : ne pas
  l'utiliser pour faire passer un virement Interac pour un versement Apify.

## Raccordement proposé

### 1. Configuration et réception

Configuration hôte privée et désactivée par défaut. États de route :
`CONFIGURING`, `READY_FOR_INSTRUCTIONS`, `UNAVAILABLE`. L'adresse seule ne prouve
pas l'activation ; une confirmation observée dans Wealthsimple est nécessaire.
Ne pas copier le profil bancaire personnel, les identifiants ou les relevés dans
le dépôt, les prompts publics, les conteneurs agents ou AgentMemory.

Les avis Interac restent des notifications non fiables. Les courriels
d'inscription, d'authentification et de paiement sont exclus des réponses
commerciales automatiques. Une adresse d'expéditeur ou un domaine ressemblant à
la banque n'authentifie jamais un dépôt ; ne pas suivre leurs liens automatiquement.

### 2. Registre privé indépendant des prestataires

Chaque commande reçoit une référence stable créée par l'hôte, un montant en
centimes, une devise, la version de l'offre et une association au dossier client
privé. La référence ne contient ni adresse courriel ni nom de client. Le montant
accepté reste figé ; un changement d'offre exige une révision explicite.

Conserver séparément :

- l'état commercial de la commande, y compris brouillon/acceptation documentée ;
- une déclaration de paiement du client, toujours non vérifiée ;
- le dépôt constaté dans Wealthsimple par le fondateur ;
- l'affectation du dépôt à la commande et l'éventuelle écriture Treasury.

Un avis sans référence, un montant différent, une devise différente ou un dépôt
ambigu reste à rapprocher. Aucun rapprochement par montant seul. Les paiements
partiels restent partiels ; un excédent n'augmente pas silencieusement la commande.
Un virement ne peut financer deux commandes sans ventilation explicite.

La clé unique du dépôt dépend du compte dédié et de la référence bancaire réelle,
jamais seulement de la référence de commande. Le rejeu exact est sans effet ; une
réutilisation avec montant, devise ou affectation contradictoires est refusée.

### 3. Confirmation humaine et comptabilité

Une commande administrateur demande la confirmation d'une opération effectivement
créditée dans le compte dédié et sa référence. Cette information se saisit en privé,
pas dans le chat ou dans une tâche publique. La confirmation indique sa provenance
`FOUNDER` et sa date. Une capture fournie par le client ne suffit pas.

Premier état durable possible : `BANK_CONFIRMED / TREASURY_NOT_POSTED`. Il permet
le rapprochement sans modifier les liquidités utilisables. Le pont Treasury doit
être explicite, idempotent et reprendre après interruption sans crédit en double.
Sa vérification n'accepte que le reçu exact construit depuis l'attestation privée.
Les agents ne peuvent produire eux-mêmes cette attestation.

Ne pas convertir le solde affiché du compte en revenu ou en financement initial.
Le contrat existant du dépôt initial n'est pas modifié. Un dépôt attesté ne prouve
pas un plafond de responsabilité ni l'absence de remboursements futurs.

### 4. Retour aux agents

Le dossier client reçoit uniquement les instructions et états qui lui
appartiennent. Le directeur reçoit un résumé borné : commandes en attente,
paiements déclarés, dépôts confirmés, rapprochements bloqués et recettes attestées
déjà comptabilisées. Pas de coordonnées privées ni de références bancaires brutes.

La mise à disposition d'instructions Interac ne doit pas lever globalement
l'interdiction d'accepter des engagements non bornés. Le parcours d'acceptation
commerciale et les conditions d'une offre doivent être cohérents avec le mandat
avant que les agents puissent demander son paiement. Les autres activités
autorisées continuent ; aucune niche n'est imposée.

## Vérifications requises avant activation logicielle

1. Une fausse notification, un courriel d'inscription ou un message client ne
   crédite rien et ne déclenche aucune réponse bancaire automatique.
2. Une confirmation administrateur exacte relie un dépôt à une commande ; aucun
   état de commande ne prétend à une vérification API.
3. Le même dépôt rejoué, réaffecté ou repris après interruption n'est jamais
   compté deux fois. Les divergences sont conservées comme erreurs explicites.
4. Montant partiel, excédent, devise inattendue, référence absente ou commande
   inconnue restent distincts d'une commande payée intégralement.
5. Les données privées n'apparaissent ni dans les projections publiques ni dans
   les tâches EXEC ; les simulations sont exclues des recettes réelles.
6. Un rapprochement sans écriture Treasury laisse les liquidités inchangées.
7. Le parcours complet est testé avec des données fictives sans virement réel,
   puis le premier véritable paiement est rapproché sans envoyer d'argent test.

## Sources de configuration

- [Wealthsimple — courriel entreprise et dépôt automatique](https://help.wealthsimple.com/hc/en-ca/articles/51594844256155-Set-up-a-business-email-for-account-notifications-and-Interac-e-Transfer-transactions)
- [Wealthsimple — entreprise individuelle](https://help.wealthsimple.com/hc/en-ca/articles/56351394961563-Open-a-Business-chequing-account-for-your-sole-proprietorship)

La rubrique des notifications générales est décrite par Wealthsimple pour les
corporations ; ne pas supposer que ce réglage distinct est présent pour une
entreprise individuelle. La configuration retenue ici est le dépôt automatique.
