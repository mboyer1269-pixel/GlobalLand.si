# Commandes privées et dépôts Interac

Ce parcours ajoute une option d'encaissement indépendante du produit et du canal
de vente. Il ne connecte pas une API Wealthsimple, n'envoie aucun virement et ne
modifie pas le contrat du financement initial. Les agents choisissent toujours
leurs offres et leurs marchés.

## Capacités et limites de cet incrément

- Registre privé de commandes, déclarations de paiement, dépôts attestés,
  affectations et écritures Treasury séparées.
- Instructions de paiement disponibles dans un dossier client authentifié
  uniquement pour une commande administrativement acceptée et encore impayée.
- État de paiement transmis au même dossier ; pas de deuxième demande automatique
  après déclaration de paiement ou réception confirmée.
- Résumé agrégé disponible au directeur, sans coordonnées ou références bancaires.
- Avis Wealthsimple/Interac mis à l'écart des réponses commerciales automatiques.

La création et l'acceptation des commandes restent administratives dans cet
incrément. Il ne donne pas aux modèles le pouvoir de conclure de nouveaux contrats
ou d'attester un dépôt. L'acceptation commerciale autonome d'une offre exige un
parcours qui borne ses engagements réels ; une adresse Interac ne le prouve pas.
L'interprétation de courriels, une signature DKIM/DMARC, une capture du client et
une notification bancaire ne constituent jamais un crédit Treasury.

## Configuration de la réception

Dans Wealthsimple, sélectionner le compte entreprise dédié → Virement Interac →
Paramètres → Dépôt automatique. Inscrire l'adresse choisie et terminer l'inscription
dans le courriel Interac. Vérifier ensuite la confirmation dans Wealthsimple.
Une inscription « En attente » ne suffit pas.

Après cette observation, l'administrateur prépare un fichier JSON mode `0600`
dans `/opt/globalland/state/private/`, avec les champs suivants :

```json
{
  "version": 1,
  "state": "READY_FOR_INSTRUCTIONS",
  "method": "INTERAC",
  "currency": "CAD",
  "recipient_email": "ADRESSE_ENTREPRISE_VERIFIEE",
  "account_alias": "IDENTITE_INTERNE_STABLE",
  "confirmed_at": "HORODATAGE_REEL_AVEC_FUSEAU",
  "confirmation": "FOUNDER_OBSERVED"
}
```

Ce modèle contient des espaces réservés, pas une configuration activable.
L'alias identifie toujours le même compte dédié, sans son numéro bancaire. Un
changement d'alias est refusé : il nécessite une migration et un rapprochement
explicites pour éviter de présenter un dépôt existant comme un nouveau paiement.
Le réglage des notifications générales d'entreprise est distinct du dépôt
automatique et peut différer pour une entreprise individuelle.

## Commandes opérateur

Sous le compte administrateur du service, les données sensibles sont lues depuis
un fichier privé, jamais passées dans les arguments de commande ni imprimées :

```sh
python3 /opt/globalland/control/orders_admin.py status
python3 /opt/globalland/control/orders_admin.py route --request /opt/globalland/state/private/route-request.json
python3 /opt/globalland/control/orders_admin.py create --request /opt/globalland/state/private/order-request.json
python3 /opt/globalland/control/orders_admin.py accept --request /opt/globalland/state/private/accept-request.json
python3 /opt/globalland/control/orders_admin.py claim --request /opt/globalland/state/private/claim-request.json
python3 /opt/globalland/control/orders_admin.py confirm --request /opt/globalland/state/private/deposit-request.json
python3 /opt/globalland/control/orders_admin.py allocate --request /opt/globalland/state/private/allocation-request.json
python3 /opt/globalland/control/orders_admin.py post --request /opt/globalland/state/private/post-request.json
```

| Action | Champs du JSON privé |
| --- | --- |
| `create` | `case_key`, `amount_cents`, `currency`, `terms_sha256`, `source_id`, éventuellement `synthetic` |
| `accept` | `order_id`, `acceptance_source_id` documentant l'acceptation de cette version de l'offre |
| `claim` | `order_id`, `source_id` du message, `amount_cents`, `currency` ; déclaration non vérifiée |
| `confirm` | `account_alias`, `reference` bancaire réelle, `amount_cents`, `currency`, `observed_at`, `evidence_sha256`, `attestation: "FOUNDER_OBSERVED_BANK_DEPOSIT"`, éventuellement `synthetic` |
| `allocate` | `deposit_id`, `order_id` |
| `post` | `deposit_id`, `attestation: "FOUNDER_OBSERVED_BANK_DEPOSIT"` |

`case_key` est calculé par `order_context.case_key(message, config)` à partir des
métadonnées du message lues par l'hôte et validées par `continuity.authorize_message`.
Il lie boîte, fil et correspondant. Il n'est jamais choisi par le modèle ni pris
dans le texte du client. Un changement de fil exige un nouveau rapprochement
administratif ; un numéro de commande cité ne donne pas accès à son dossier.

`terms_sha256` identifie les conditions privées immuables de l'offre. `source_id`
identifie l'événement réel à l'origine de la saisie ; réutiliser le même événement
avec d'autres montants est une erreur. La référence de commande est créée par
l'hôte et peut figurer dans le message du virement demandé au client.

La référence bancaire, le montant et le compte doivent être constatés dans
l'interface bancaire par le fondateur. `evidence_sha256` est l'empreinte du
justificatif conservé en privé ; elle sert à la traçabilité et ne démontre pas à
elle seule l'authenticité du justificatif. Aucun relevé brut n'est copié dans Git.

## États et comptabilité

Une déclaration client donne `CLAIMED_UNVERIFIED`, jamais un paiement vérifié.
Un dépôt confirmé et rapproché donne `BANK_CONFIRMED` avec provenance humaine ;
tant que `post` n'a pas réussi, il reste `TREASURY_NOT_POSTED` et n'ajoute aucune
liquidité utilisable. Paiement partiel, excédent ou devise incohérente restent
visibles. Les excédents et divergences bloquent l'écriture jusqu'au rapprochement.

`post` utilise un reçu immuable `REVENUE / FOUNDER`. Il réemploie l'identité du
dépôt, indépendamment de la commande. Après une interruption, relancer exactement
la même opération répare l'état du registre sans créditer une deuxième fois.
La recette attestée apparaît séparément dans `founder_attested_revenue_cents`.
Elle ne confirme jamais le dépôt initial de 50 CAD. Un transfert du fondateur,
une simulation et une vente ne sont pas interchangeables.

Le filtre des avis bancaires reconnaît les domaines officiels Interac et
Wealthsimple comme motif de mise à l'écart, pas comme preuve d'authenticité. Les
messages de domaines ressemblants ne reçoivent aucune autorité financière. Les
questions ordinaires des clients concernant leurs paiements restent traitables.

## Mise en service

Le [pont privé de propositions produit](order-proposals.md) ajoute un import
administratif depuis une demande authentifiée sauvegardée, une acceptation
explicitement revue et un export privé des instructions. Il ne donne pas aux
agents une acceptation contractuelle ni une livraison automatique.

Installer le code relu et testé avant de déclarer cette capacité disponible.
Conserver la route absente ou `CONFIGURING` tant que l'inscription n'est pas
confirmée. Tester le parcours avec des données fictives dans un répertoire isolé,
jamais en produisant de faux revenus dans l'installation réelle. Cet incrément
ne nécessite ni achat ni virement test. Pour la première vente réelle, contrôler
les conditions de l'offre, rapprocher le dépôt, puis vérifier la reprise du
résultat par le dossier client et le directeur.

### Reprises et limites historiques

Avant tout envoi, l'hôte compare à nouveau le destinataire et le contexte de
commande utilisé pour rédiger la réponse. Une ancienne réponse préparée avec
des instructions devenues périmées est refusée, même si elle était déjà prête.
Elle n'est pas réécrite implicitement ; un nouveau message ou une reprise
administrative explicite permet de préparer une réponse actuelle.

Le rapprochement refuse aussi les références bancaires identiques déjà
enregistrées par le chemin historique Apify BANK. Les anciennes empreintes Apify
conservaient la casse alors que ce registre normalise les références : des
empreintes différentes ne prouvent donc pas que deux anciens justificatifs
décrivent deux virements distincts. Leur migration exige un rapprochement privé,
sans reclasser le même versement comme une nouvelle vente.

Sources : [configuration Wealthsimple](https://help.wealthsimple.com/hc/en-ca/articles/51594844256155-Set-up-a-business-email-for-account-notifications-and-Interac-e-Transfer-transactions),
[entreprise individuelle](https://help.wealthsimple.com/hc/en-ca/articles/56351394961563-Open-a-Business-chequing-account-for-your-sole-proprietorship).
