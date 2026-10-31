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

Un reçu comporte provider/account/event_id uniques, currency CAD, amount_cents entier, kind FUNDING|SPEND|CANCELLED|REVENUE|REFUND|POSITIONS, settled true. Pour SPEND/CANCELLED, operation_id doit correspondre. Un investissement exige aussi positions_receipt (POSITIONS) avant de régler la dernière trésorerie : le patrimoine acheté doit être pris en compte. Les preuves conservées en privé ne sont jamais publiées.

Initialisation réelle : le premier FUNDING vérifié vaut exactement5000centimes. Ensuite seuls les revenus/remboursements réglés augmentent l'enveloppe. Le script treasury_admin.py peut importer les preuves via ce vérificateur ; il ne propose pas de bouton pour fabriquer une banque financée. Les fluctuations/positions se rapprochent par les preuves du service choisi.

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

## Cursor avec son abonnement

Cursor est un troisième fournisseur optionnel. La CLI officielle `agent` se connecte avec `agent login` ; `NO_OPEN_BROWSER=1` affiche le lien sur un VPS sans navigateur. Le code utilise le binaire officiel sous le nom explicite cursor-agent, sans extraire les tokens du logiciel de bureau ni appeler une API avec ces tokens. Son HOME privé entier est conservé pour supporter ses fichiers d'authentification natifs, séparé des autres fournisseurs.

L'image docker/Cursor.Brain.Dockerfile étend l'ID immuable de l'image Codex/Claude déjà construite. L'installeur officiel résout sa version au build ; la version, le hash de l'installeur et l'ID de l'image construite sont enregistrés. Ce n'est pas une promesse de build identique si l'on relance plus tard l'installeur latest. Le rootfs readonly empêche une mise à jour du binaire pendant les cycles. Les connexions précédentes restent dans leurs volumes et ne sont pas supprimées par ce build.

Le planificateur Cursor s'exécute en mode ask avec sortieJSON. Sa réponse textuelle result doit être un objet de décision JSON strict validé localement ; aucune sortie incomplète ou erreur n'est exécutée. Les actions des agents continuent d'utiliser les outils de GlobalLand. La configuration installée fixe approvalMode=allowlist, permissions.allow vide et sandbox.readBoundary=workspace, avec un sandbox.json privé également imposé en lecture seule. Cette frontière documentée couvre les lectures et recherches hors /tmp ; les permissions Read seules ne suffisent pas à l'établir. Aucun fichier de projet n'est monté dans le cerveau. Les autres credentials et les outils de publication/finance restent absents de son conteneur.

Après construction et login Cursor, vérifier l'authentification sans inférence, puis choisir explicitement `--providers codex,claude,cursor`. La connexion ne prouve ni quota illimité ni absence d'on-demand. Vérifier dans le compte Cursor les limites d'usage supplémentaire et désactiver les dépenses additionnelles ; le code ne les active pas et ne relaie aucune variable CURSOR_API_KEY du VPS.

Sources officielles : [installation](https://cursor.com/docs/cli/installation), [authentification](https://cursor.com/docs/cli/reference/authentication), [paramètres](https://cursor.com/docs/cli/reference/parameters), [configuration](https://cursor.com/docs/cli/reference/configuration), [JSON de sortie](https://cursor.com/docs/cli/reference/output-format), [limites de dépenses](https://cursor.com/help/account-and-billing/spend-limits). La compatibilité exacte du binaire installé et son authentification doivent être testées sur le VPS avant activation.

La [frontière de lecture officielle](https://cursor.com/docs/agent/security/run-modes#read-access) est récente (Cursor 3.23, octobre 2026). Les flags --help et un login réussi ne démontrent pas seuls son application par une version de CLI. Vérifier le binaire Linux réellement construit et un test de lecture/recherche sur un fichier canari sans secret avant toute activation périodique. Les hooks/plugins de compte restent une dépendance au fournisseur ; aucun contrôle officiel par invocation permettant de tous les désactiver n’a été établi. Ne pas présenter cette intégration comme une preuve de confinement interne exhaustive. Les tests locaux utilisent un transport factice et ne prouvent ni connexion réelle, ni application des politiques par Cursor, ni quotas.

## Compatibilité des commandes installées

Avec Codex 0.166.0, les options --ignore-user-config et --ignore-rules appartiennent à exec : `codex exec --ignore-user-config --ignore-rules ...`. Le statut se vérifie séparément avec `codex login status`. Référence immuable : [déclaration CLI exec](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/exec/src/cli.rs). Claude renvoie du JSON par défaut avec `claude auth status` ; --json n’est pas nécessaire selon sa [référence officielle](https://code.claude.com/docs/en/cli-reference).

Le contrôle capte les deux canaux de sortie pour l’aide et le statut texte Codex/Cursor. Les décisions du modèle et le statut JSON Claude conservent stdout seul pour que des avertissements sur stderr ne corrompent pas le JSON. Les erreurs précisent désormais le fournisseur, le code de sortie et les options manquantes. Un login réussi reste distinct de la compatibilité du planificateur.

Pour diagnostiquer une CLI sans lancer de modèle : `python3 /opt/globalland/control/diagnose_subscriptions.py --image sha256:ID_IMAGE --provider claude`. Ce programme n’appelle que version/aide/statut, masque les extraits d’aide et ne publie pas le texte d’authentification. Il ne modifie pas la configuration GlobalLand ; les CLIs peuvent entretenir leurs propres caches et fichiers privés dans leurs volumes. Un échec Claude doit être diagnostiqué dans l’image réelle ; ne pas retirer aveuglément ses protections pour passer le contrôle.

## Gemini Pro / Google AI Pro

Le fondateur possède l’application Gemini avec un abonnement Pro. La voie adaptée à cet abonnement est la CLI officielle Gemini, authentifiée par « Sign in with Google » avec le même compte. Google documente l’utilisation des plans Google AI Pro/Ultra et leurs quotas dans cette CLI. Une clé Gemini API / Vertex AI utilise une voie de facturation distincte ; l’abonnement de l’application ne prouve pas un quota API payant inclus.

Sources : [authentification Gemini CLI](https://geminicli.com/docs/get-started/authentication/), [quotas et tarifs](https://geminicli.com/docs/resources/quota-and-pricing). L’intégration Gemini n’est pas implémentée par ce correctif et aucune connexion Google n’est déclarée vérifiée. Les identifiants restent à fournir directement au flux Google officiel lors de son installation.
