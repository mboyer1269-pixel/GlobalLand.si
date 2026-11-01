# Connexions réelles de GlobalLand

Le monde est mondial. La résidence canadienne du fondateur concerne seulement l'admissibilité aux comptes, pas les clients, devises, stratégies ou marchés des agents.

## Abonnements existants

Utiliser les CLIs officielles avec tes propres abonnements et leurs connexions normales. Codex distingue connexion ChatGPT et clé API facturée séparément ; Claude Code fait aussi cette distinction. Cette version n'extrait aucun OAuth pour appeler directement les APIs et ne se replie jamais sur une clé API.

- Codex : login par appareil, `codex exec`, réponses selon schéma ; vérification officielle d'authentification et options compatibles avant le premier appel. [Authentification](https://learn.chatgpt.com/docs/auth), [mode non interactif](https://learn.chatgpt.com/docs/non-interactive-mode), [automatisation privée](https://learn.chatgpt.com/docs/auth/ci-cd-auth).
- Claude Code : login normal, mode `-p`, safe-mode, sortie JSON structurée. `--bare` ne prend pas l'authentification d'abonnement. [Authentification](https://code.claude.com/docs/en/authentication), [CLI](https://code.claude.com/docs/en/cli-reference), [mode headless](https://code.claude.com/docs/en/headless), [usage et conformité](https://code.claude.com/docs/en/legal-and-compliance).

Chaque identité tourne dans une boîte différente de l'exécution des produits, avec son propre volume privé d'authentification. Les quotas des plans restent applicables. Les limites/extra usage du compte ne sont pas prouvées par un fichier JSON ; vérifier et désactiver facturation supplémentaire, achats de crédits et recharges. L'authentification doit être effectuée par le propriétaire ; ne transmettre aucun code d'autorisation durable, token ou fichier auth dans GitHub/chat.

L'app Grok Bot conserve sa connexion GitHub pour le pilotage externe. Son droit d'écriture ne constitue pas un mécanisme pour la réveiller automatiquement. Les cycles think utilisent les CLIs une fois connectées ; sinon l'état affiche WAITING_CONTROLLER ou WAITING_SUBSCRIPTION_AUTH.

## Banque : organisation recommandée

Séparer trois fonctions :

1. **Comptabilité interne** : Treasury et ses comptes GLC/missions, sans inscription ni frais. Ce n'est pas un établissement bancaire.
2. **Capital utilisable** : un solde dédié contenant réellement50CAD, sans recharge/découvert, relié par un connecteur capable de borner les débits. Ne pas utiliser une carte personnelle à crédit comme si elle était plafonnée par le ledger.
3. **Recettes** : un prestataire de paiement permettant des clients mondiaux et délivrant des preuves de règlements. Les commandes et paiements en attente ne sont pas encore du capital dépensable ; frais, remboursements, litiges, devise et délais de versement doivent être intégrés.

L'ouverture du compte et la vérification d'identité appartiennent au fondateur. Aucun compte réel n'est créé par cette PR et aucun50CAD n'est inventé. Le choix du service de garde/vente doit être finalisé avant de fournir un vrai connecteur ; le contrat ci-dessous évite de confondre un simulateur et une connexion financière active.

## Contrat du connecteur privé

Exécutable administrativement installé `/opt/globalland/integrations/finance`, propriétaire administrateur et non modifiable par les agents. Requête JSON sur stdin, réponse JSON sur stdout, aucune clé ni donnée personnelle dans les logs publics. Actions :

- `quote` : `{request,operation_id}` → `{currency:"CAD", max_debit_cents:entier, bounded:true, idempotent:true, settlement_kind:"expense"|"investment"}`. La borne inclut tous les coûts/risques de débit. Ne pas annoncer bounded si le fournisseur ne le garantit pas réellement.
- `submit` : `{request,operation_id,idempotency_key,max_debit_cents}` → reçu terminal ou état en attente. La passerelle a réservé le maximum et enregistré UNKNOWN avant d'appeler.
- `reconcile` : `{operation_id,request}` → état du même appel auprès du fournisseur, pas un nouvel achat. Une réponse perdue conserve sa réservation ; ne jamais libérer par simple timeout.
- `verify` : `{receipt}` → `{valid:true}` seulement après validation réelle de la provenance, du compte GlobalLand, du montant/devise et de l'état du prestataire. Les reçus fournis par les agents ou tests ne suffisent pas.

Un reçu comporte provider/account/event_id uniques, currency CAD, amount_cents entier, kind FUNDING|SPEND|CANCELLED|REVENUE|REFUND|POSITIONS, settled true. Un reçu POSITIONS valorise une détention identifiée par provider/account et `asset` optionnel : les comptes et actifs distincts s'additionnent, une nouvelle valorisation remplace seulement la même clé. Un compte est valorisé soit globalement (sans `asset`), soit actif par actif, jamais les deux. Pour SPEND/CANCELLED, operation_id doit correspondre. Un investissement exige aussi positions_receipt (POSITIONS) avant de régler la dernière trésorerie : le patrimoine acheté doit être pris en compte. Les preuves conservées en privé ne sont jamais publiées.

Initialisation réelle : le premier FUNDING vérifié vaut exactement5000centimes. Un REVENUE/REFUND réglé et vérifié peut arriver avant ce dépôt : il crédite la Banque, la rend ACTIVE avec `revenue_verified: true`, mais ne vaut jamais `funding_verified`. Ensuite seuls les revenus/remboursements réglés augmentent l'enveloppe. Tant que le dépôt initial n'est pas vérifié, épuiser ces revenus ramène le disponible à zéro sans déclencher l'extinction. Le script treasury_admin.py peut importer les preuves via ce vérificateur ; il ne propose pas de bouton pour fabriquer une banque financée. Les fluctuations/positions se rapprochent par les preuves du service choisi.

## Limites de livraison

Les tests d'intégration utilisent des prestataires factices et un Git local réel. Le smoke Docker construit un vrai artefact sans inférence ni paiement. Le contrôle doit être mis à niveau sur le VPS, les CLIs connectées et leurs quotas vérifiés, puis la Banque financée et rapprochée. Aucun de ces faits externes n'est remplacé par une réussite de test.

## Recherche des moyens de paiement (sources officielles)

**Recommandation pratique pour commencer :** conserver la comptabilité et le capital dédiés, utiliser les abonnements déjà détenus pour construire, et préparer une réception de ventes mondiale par Stripe Payment Links. Avant activation réelle, le propriétaire doit vérifier l'éligibilité de son compte, ses conditions de responsabilité et le compte de versement dédié. Ce n'est pas une restriction aux clients canadiens.

| Solution | Utilité | Limite pour les50CAD |
|---|---|---|
| Stripe Payment Links + compte projet dédié | Encaissement mondial sans développement de checkout ; frais par transaction | Stripe peut débiter le compte lié pour un solde négatif. Le plafond logiciel ne supprime ni litiges ni responsabilité du titulaire. |
| Gumroad | Vente/livraison de fichiers et gestion de taxes de vente comme merchant of record | La documentation consultée indique un minimum de versement de100USD et des retenues : trop peu de liquidité pour démarrer avec50CAD. |
| Stripe Issuing | Cartes et contrôles de dépenses par API, dont programme commercial canadien indiqué dans la documentation actuelle | Mise en place via Stripe ; éligibilité, montant minimum et adéquation à50CAD non vérifiés. Ce n'est pas une carte API instantanément disponible pour ce projet. |

La meilleure première dépense est une dépense dont le fournisseur garantit un solde prépayé sans recharge ni postpaiement. Une carte étiquetée « prépayée » ne garantit pas, à elle seule, l'absence de frais tardifs ou dette. Aucun produit bancaire précis avec API publique et garantie absolue de responsabilité limitée à50CAD n'a été établi par cette recherche. La crypto n'est pas imposée : aucune nécessité commerciale ne justifie pour l'instant d'ajouter conversion, gas et garde de clés à ce petit capital.

Sources officielles : [Stripe Canada et tarifs](https://stripe.com/ca/pricing), [versements et soldes négatifs Stripe](https://docs.stripe.com/payouts), [Issuing](https://docs.stripe.com/issuing), [disponibilité commerciale](https://docs.stripe.com/issuing/global), [tarifs Gumroad](https://gumroad.com/pricing), [versements Gumroad](https://gumroad.com/help/article/13-getting-paid).

Cette responsabilité financière doit être tranchée avec les conditions du service choisi ; le code ne présente pas Stripe ou une carte comme une garantie « impossible de devoir plus que50 ». En attendant, le monde peut rechercher et produire avec les abonnements connectés, et la Banque conserve l'état UNFUNDED plutôt que prétendre posséder un compte inexistant.

## Synchronisation automatique du compte

Le connecteur financier implémente aussi `sync` : `{cursor}` → `{receipts:[...], next_cursor, complete:boolean}`. Le superviseur l'appelle avant le travail. L'intégration fournit les revenus/remboursements réellement réglés et les positions ; la Banque applique le lot dans une transaction et n'avance le curseur qu'après validation. Les événements rejoués ne créent pas de nouveaux revenus. Elle rapproche aussi les opérations SUBMITTING via leur identité d'origine.

`complete:true` est une affirmation du connecteur de confiance que toutes les liquidités, positions et entrées nécessaires au rapprochement sont représentées. Une vente du dernier actif ne tue pas le monde entre une notification de position zéro et une notification d'encaissement : tant que le lot complet n'est pas rapproché, l'état RECONCILING conserve cette incertitude et gèle les nouveaux engagements. Un zéro réellement confirmé reste terminal. Pour une opération d'investissement, les réponses peuvent fournir positions_receipt et revenue_receipt ; l'intégration ne les remplace pas par des gains de simulation.
