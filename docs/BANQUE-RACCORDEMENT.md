# Raccorder la Banque CAD à un compte réel

Le logiciel possède déjà la comptabilité et la passerelle. Il manque le service réel et son adaptateur privé. Les 50 CAD du mandat sont un capital autorisé ; seule une preuve de dépôt réglé peut les rendre utilisables. Ce guide ne crée aucun compte, paiement, secret ou financement. Le prestataire n'est pas encore choisi.

## Parcours minimal en cinq étapes

1. **Nommer le compte dédié et le canal de recettes.** Le fondateur indique seulement les noms des services existants, ou « aucun ». Le compte doit isoler le patrimoine GlobalLand ; les identifiants de connexion du compte personnel complet ne sont jamais transmis aux agents. Vérifier ensuite dans les conditions du service choisi : admissibilité du titulaire, frais, devise, export/API de transactions et possibilités réelles de plafonnement. L'ouverture, l'identité et les coordonnées de versement se traitent directement dans l'interface officielle du prestataire.
2. **Commencer par la lecture et les preuves.** Développer un adaptateur spécifique au service pour `verify` et `sync`, avec accès limité au compte dédié et aux seules données nécessaires. Installer cet exécutable sur l'hôte sous contrôle administrateur, hors du dépôt et des conteneurs agents. Il doit refuser toute opération de dépense tant que `quote`/`submit`/`reconcile` ne sont pas implémentés et validés. Un accès de lecture prouve des transactions ; il n'autorise pas des débits autonomes.
3. **Rapprocher le dépôt initial réel.** Quand le fondateur a effectivement versé 50 CAD nets sur le compte dédié et que le règlement est confirmé, l'adaptateur fournit un reçu `FUNDING` unique de `5000` centimes CAD. `verify` contrôle ce reçu contre le service réel. Importer la preuve via `sync` ou la commande administrateur ci-dessous. Le résultat attendu est `funding_verified: true`, avec le cash correspondant ; le disponible tient aussi compte des réserves et engagements existants. Modifier `ledger.json`, donner un JSON à un agent ou réussir un test ne finance rien.
4. **Relier les recettes au même périmètre comptable.** Configurer le compte de versement dédié chez le prestataire de vente choisi, puis rapprocher les montants réellement reçus, frais et change compris. Une facture, une commande et un paiement encore en attente ne sont pas des liquidités utilisables. Chaque recette réglée devient un `REVENUE` vérifié ; les remboursements de dépenses sont des `REFUND`, les reprises de recettes des `REVERSAL`. Fixer `available_at` et le plancher de réserve selon le contrat réel du service. Ne pas compter à la fois la vente et son versement bancaire comme deux recettes : le transfert interne ne crée pas de revenu.
5. **Autoriser les dépenses seulement après preuve du plafond externe.** Ajouter `quote`, `submit` et `reconcile` pour les opérations que le service sait réellement borner, frais et change compris, sans découvert, crédit ni recharge. Valider d'abord sans argent réel les rejeux, erreurs et réponses perdues. Une réserve locale ou une clé API restreinte ne garantit pas que le prestataire ne puisse réclamer plus que le capital. Si cette garantie manque, conserver le raccordement en lecture/encaissement et refuser la dépense concernée.

## Contrat exact déjà implémenté

Références : [`gateway.py`](../scripts/gateway.py), [`treasury.py`](../scripts/treasury.py), [`treasury_admin.py`](../scripts/treasury_admin.py), [`INTEGRATIONS.md`](INTEGRATIONS.md).

`Gateway` lance `/opt/globalland/integrations/finance ACTION`. Une requête JSON arrive sur stdin, une réponse JSON sur stdout. Le processus reçoit seulement `PATH` comme environnement explicite : il ne faut pas supposer qu'une variable secrète de l'hôte est héritée. L'adaptateur devra accéder à un fichier privé ou un mécanisme de secrets explicitement prévu, administré et inaccessible aux agents. Aucun secret ne doit apparaître sur stdout, dans Git ou dans la projection publique.

L'exécutable doit être un fichier régulier, non symbolique et non modifiable par groupe/autres. La propriété administrateur et l'absence d'écriture des agents sont aussi des exigences de déploiement ; `Gateway.invoke` ne vérifie pas à lui seul le propriétaire du fichier.

| Action | Requête | Réponse attendue et effet |
| --- | --- | --- |
| `verify` | `{receipt}` | `{valid:true}` uniquement après contrôle réel de provenance, compte, événement, montant, devise et règlement. Une erreur vaut refus. |
| `sync` | `{cursor}` | `{receipts:[...],next_cursor,complete:boolean}` ; 256 reçus maximum par lot, de type `FUNDING`, `REVENUE`, `REFUND`, `REVERSAL` ou `POSITIONS`. Application atomique et dédoublonnée, puis sauvegarde du curseur. `complete:true` affirme que le périmètre de compte est entièrement rapproché. Les `SPEND`/`CANCELLED` passent par `submit`/`reconcile` ; leur présence dans `sync` fait rejeter le lot. |
| `quote` | `{request,operation_id}` | `{currency:"CAD",max_debit_cents:entier,bounded:true,idempotent:true,settlement_kind:"expense"}` ; `investment` est l'autre valeur possible. Le plafond inclut tous les débits possibles. |
| `submit` | `{request,operation_id,idempotency_key,max_debit_cents}` | `{receipt:...}` si terminal ; sans reçu terminal la réserve reste `UNKNOWN`. Cette action s'appelle `submit`, pas `execute`. |
| `reconcile` | `{operation_id,request}` | État du même appel auprès du service, avec le même reçu terminal si disponible ; aucun nouvel achat. |

Avant `submit`, la Banque réserve le maximum, marque l'opération `UNKNOWN` et la passerelle enregistre `SUBMITTING`. Une réponse perdue garde la réserve. Un timeout n'est jamais une annulation. Un reçu `CANCELLED` vérifié de montant zéro libère la réserve ; un `SPEND` vérifié comptabilise le débit réel. Un dépassement constaté provoque un arrêt financier `HALTED`, ou `EXTINCT` si les fonds et positions vérifiés sont épuisés : la comptabilité détecte la violation, elle ne l'empêche pas chez le fournisseur.

Pour `investment`, la réponse terminale doit aussi fournir `positions_receipt`. Un `revenue_receipt` complémentaire et `account_complete:true` sont pris en charge. Les positions d'un compte se valorisent globalement ou actif par actif, sans double comptage. Le parcours minimal n'a pas besoin d'investissements.

### Reçu de dépôt : forme, jamais preuve à lui seul

```json
{
  "provider": "SERVICE_A_PRECISER",
  "account": "IDENTIFIANT_PROJET_PRIVE",
  "event_id": "EVENEMENT_REEL_UNIQUE",
  "currency": "CAD",
  "amount_cents": 5000,
  "kind": "FUNDING",
  "settled": true
}
```

Ce modèle est documentaire. Ne pas l'importer comme preuve réelle. Le vérificateur doit retrouver la transaction authentique du compte autorisé ; des chaînes de caractères ou `settled:true` fournis par un appelant ne suffisent pas. Une identité `(provider, account, event_id)` déjà appliquée ne peut pas être réutilisée avec un contenu différent. Le dépôt initial n'est accepté qu'une fois et pour exactement 5000 centimes.

Les autres types de reçus sont `REVENUE`, `REFUND`, `REVERSAL`, `POSITIONS`, `SPEND` et `CANCELLED`. Pour les deux derniers, `operation_id` doit correspondre à la demande. Les montants sont des centimes CAD entiers ; une vente en USD exige une conversion réellement établie, pas un taux deviné.

### Commandes opérateur disponibles sur le VPS Linux

Ces commandes existent déjà ; elles ne sont pas exécutées par ce guide. Les imports exigent l'adaptateur réel et un reçu privé vérifié. Les exécuter sous le mécanisme de verrouillage administratif habituel, sans cycle financier concurrent.

```sh
python3 /opt/globalland/control/treasury_admin.py status
python3 /opt/globalland/control/treasury_admin.py funding --receipt /CHEMIN_PRIVE/preuve-depot.json
python3 /opt/globalland/control/treasury_admin.py revenue --receipt /CHEMIN_PRIVE/preuve-recette.json
python3 /opt/globalland/control/treasury_admin.py reserve --cents MONTANT_A_DETERMINER
```

`treasury_admin.py` exige l'administrateur, utilise `/opt/globalland/state/private/treasury.sqlite3` et appelle le même `Gateway.verify`. Il ne permet pas de déclarer un dépôt sans vérification. `Gateway.sync()` est aussi appelé avant le travail par le superviseur si l'exécutable financier est installé ; il reprend les opérations `SUBMITTING`. Il n'existe pas de sous-commande `treasury_admin sync`.

## Recettes Apify : chemin déjà disponible, attestation explicite

[`payouts.py`](../scripts/payouts.py) sépare `invoice` (créance, jamais cash) de `received` (montant CAD effectivement reçu sur le compte dédié). La deuxième commande exige l'administrateur et produit un `REVENUE` portant `attestation:"FOUNDER"`, avec empreinte de référence et, seulement si `--evidence` est fourni, empreinte du relevé privé. Le vérificateur temporaire n'accepte que le reçu exact construit par cette commande. Ce chemin ne remplace pas le vérificateur du dépôt initial et ne nécessite pas de prétendre qu'une API bancaire est branchée.

`founder_attested_revenue_cents` permet d'identifier ces recettes. Attention : le champ générique `revenue_verified` devient aussi vrai pour une recette attestée ; ce booléen seul ne démontre donc pas une vérification automatique par API.

L'aide officielle Apify exige l'identité vérifiée et distingue facture, versement et réception bancaire. Elle indique actuellement des versements mensuels et des seuils selon le moyen de paiement ; il faut les confirmer dans le compte avant de choisir cette voie. Les déductions possibles font aussi partie du rapprochement. [Processus officiel des versements Apify](https://help.apify.com/en/articles/10057167-how-developer-payouts-work).

## Validation avant une mise en service réelle

Les tests existants (`test_treasury.py`, `test_gateway.py`, `test_payouts.py`) couvrent le refus sans preuve, l'unicité du dépôt, les rejeux, les réservations, la reprise après réponse perdue, la synchronisation atomique, les recettes attestées et les réserves. Ils emploient des preuves factices et ne valident aucun compte réel.

Pour le service retenu, le raccordement devra en plus démontrer :

- le compte dédié exact et des droits limités, avec refus d'un reçu d'un autre compte ou d'un environnement de test ;
- le rapprochement des frais/change et l'absence de double comptage vente/versement ;
- le rejet d'une fausse preuve, les rejeux sans second crédit, la reprise de curseur et les retards de règlement ;
- la prise en compte des remboursements/litiges et de la disponibilité effective ; aucune durée générique de réserve ne constitue une garantie ;
- avant toute dépense autonome, l'idempotence et la borne de débit garanties par le service, plus la reprise d'une réponse perdue sans nouvel achat.

À titre d'exemple de précautions à vérifier si Stripe est le service nommé : ses clés restreintes limitent les permissions, et ses secrets restent côté serveur. Cela ne supprime pas son mécanisme de solde négatif, qui peut débiter le compte bancaire lié. Ce n'est donc pas une preuve de responsabilité limitée aux 50 CAD. [Clés API Stripe](https://docs.stripe.com/keys), [protection des clés](https://docs.stripe.com/keys-best-practices), [versements négatifs](https://docs.stripe.com/payouts#negative-payouts). Aucun choix de Stripe n'est effectué ici.

## Ce qui peut avancer maintenant

Le contrat et les cas de validation peuvent être préparés sans compte ni secret. L'adaptateur spécifique, les autorisations, les frais réels et les garanties de plafonnement dépendent du prestataire. L'identité, l'ouverture du compte et un éventuel virement initial dépendent ensuite du fondateur. Le monde peut continuer les recherches et la production autorisées ; aucun fichier local ne doit le présenter comme financé par anticipation.

Information minimale à obtenir : **« Quel compte ou prestataire dédié GlobalLand possède déjà ? Son nom seulement, ou “aucun”. »** Si le compte de garde et le service de vente sont différents, indiquer les deux noms suffit pour la prochaine étape technique. Ne fournir aucun mot de passe, token, numéro de compte, relevé ou pièce d'identité dans le chat.
