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

Un reçu comporte provider/account/event_id uniques, currency CAD, amount_cents entier, kind FUNDING|SPEND|CANCELLED|REVENUE|REFUND|REVERSAL|POSITIONS, settled true. Un reçu POSITIONS valorise une détention identifiée par provider/account et `asset` optionnel : les comptes et actifs distincts s'additionnent, une nouvelle valorisation remplace seulement la même clé. Un compte est valorisé soit globalement (sans `asset`), soit actif par actif, jamais les deux. Pour SPEND/CANCELLED, operation_id doit correspondre. Un investissement exige aussi positions_receipt (POSITIONS) avant de régler la dernière trésorerie : le patrimoine acheté doit être pris en compte. Les preuves conservées en privé ne sont jamais publiées.

**Règle de réserve (Sprint 2).** Un REVENUE peut porter `available_at` (secondes epoch) : l'adaptateur y met la plus tardive de deux dates, le versement réel du fournisseur et la fin de sa fenêtre de remboursement (60 jours chez Polar et Lemon Squeezy). Le montant est possédé dès sa réception, mais il ne devient dépensable qu'à cette date (`maturing_cents`, `next_maturity_at`). Un revenu déjà final (paiement Apify par exemple) n'a pas de date. Un remboursement client ou un litige repris par le fournisseur est un reçu `REVERSAL` (débit, `reverses` = event_id du revenu, facultatif). Il consomme d'abord le crédit en maturation et réduit `revenue_cents`. S'il dépasse la trésorerie possédée, la Banque passe HALTED : c'est la dette que le fournisseur pourrait réclamer au fondateur. `treasury_admin.py reserve --cents N` fixe un plancher de réserve jamais engageable, pour couvrir les litiges.

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

## Cursor avec son abonnement

Cursor est un troisième fournisseur optionnel. La CLI officielle `agent` se connecte avec `agent login` ; `NO_OPEN_BROWSER=1` affiche le lien sur un VPS sans navigateur. Le code utilise le binaire officiel sous le nom explicite cursor-agent, sans extraire les tokens du logiciel de bureau ni appeler une API avec ces tokens. Son HOME privé entier est conservé pour supporter ses fichiers d'authentification natifs, séparé des autres fournisseurs.

L'image docker/Cursor.Brain.Dockerfile étend l'ID immuable de l'image Codex/Claude déjà construite. L'installeur officiel résout sa version au build ; la version, le hash de l'installeur et l'ID de l'image construite sont enregistrés. Ce n'est pas une promesse de build identique si l'on relance plus tard l'installeur latest. Le rootfs readonly empêche une mise à jour du binaire pendant les cycles. Les connexions précédentes restent dans leurs volumes et ne sont pas supprimées par ce build.

Le planificateur Cursor s'exécute en mode ask avec sortieJSON. Sa réponse textuelle result doit être un objet de décision JSON strict validé localement ; aucune sortie incomplète ou erreur n'est exécutée. Les actions des agents continuent d'utiliser les outils de GlobalLand. La configuration installée fixe approvalMode=allowlist, permissions.allow vide et sandbox.readBoundary=workspace, avec un sandbox.json privé également imposé en lecture seule. Cette frontière documentée couvre les lectures et recherches hors /tmp ; les permissions Read seules ne suffisent pas à l'établir. Aucun fichier de projet n'est monté dans le cerveau. Les autres credentials et les outils de publication/finance restent absents de son conteneur.

La CLI sans terminal requiert aussi `--trust` pour reconnaître son espace de travail. GlobalLand l'applique seulement à son `/tmp` neuf en tmpfs dans le conteneur de réflexion. Selon la [référence officielle](https://cursor.com/docs/cli/reference/parameters), ce drapeau confirme le dossier en mode headless ; `--force`/`--yolo` concernent l'autorisation des commandes et ne sont pas ajoutés. Les politiques readonly, ask et les fichiers de permissions restent imposés. L'aide doit annoncer `--trust` avant toute connexion/invocation du modèle. Les commandes help/status n'héritent pas de ce drapeau headless.

Après installation du SHA revu, lancer `python3 /opt/globalland/control/verify_cursor_canary.py`. Cette commande opérateur reprend le verrou partagé, crée deux fichiers de test aléatoires sans secret dans le HOME Cursor hors workspace, puis demande des tentatives Read/Grep/Glob sur ces seuls chemins avec l'abonnement officiel. Elle retire ses fichiers dans finally, conserve une trace privée mode600 et affiche uniquement les marqueurs/étapes/outils et un diagnostic masqué. Les deux canaux sont captés pour ne pas perdre un blocage de démarrage ; les lignes nonJSON sont signalées, sans relâcher le parseur des décisions productives. Le résultat reste toujours REVIEW_REQUIRED : une absence de marqueur ou d'appel d'outil ne vaut pas validation. Examiner les appels, leurs arguments et leurs résultats effectifs dans la trace privée avant d'utiliser Cursor périodiquement. Aucun achat, tâche métier, changement de configuration ni connexion nouvelle n'est effectué par ce test ; la CLI peut entretenir ses caches privés.

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

### Option Claude masquée dans l’aide

La CLI 2.1.316 observée sur le VPS expose toutes les protections requises sauf --max-turns dans --help ; son statut normal confirme loggedIn=true et authMethod=claude.ai. L’absence dans l’aide seule n’établit donc pas une incompatibilité. Le contrôleur utilise --max-turns 2 pour laisser le dialogue interne StructuredOutput se terminer, et vérifie cette valeur sans inférence avec `claude --max-turns 2 auth status`. Quand cette option est masquée, un contrôle négatif demande d’abord `claude --globalland-invalid-option-probe auth status` : il doit échouer et nommer cette option inconnue. Une CLI qui ignore les options ou un contrôle négatif ambigu laisse le fournisseur non vérifié. Le statut final doit toujours confirmer l’abonnement claude.ai, jamais une clé API.

## Format des décisions et échecs de réflexion

Le schéma envoyé aux fournisseurs ferme chaque objet JSON (additionalProperties=false, propriétés toutes requises). Chaque action possède maintenant des args natifs typés : argv est un tableau de chaînes, outputs un tableau de chemins, les missions ont leurs champs explicites. Les champs réellement optionnels peuvent être null dans le transport et sont retirés avant exécution. Les anciennes décisions internes et les anciennes chaînes args_json valides restent lisibles ; une ancienne chaîne invalide n’est jamais réparée automatiquement.

Les requêtes financières arbitraires utilisent request_entries, un tableau de paires key/value. Les objets imbriqués sont représentés par object_entries ; chaînes, nombres finis, booléens, null et tableaux restent natifs. Le contrôle reconstitue le request objet habituel, refuse les clés dupliquées et conserve les null métier. Le helper decision_protocol.encode_request permet à un producteur de requêtes d’obtenir cette représentation sans sérialiser du JSON dans une chaîne.

Ce format retire le double encodage qui avait provoqué une erreur de guillemets dans du code JavaScript proposé par Codex. Il conserve les mêmes outils et leurs possibilités. Le schéma Codex installé, celui transmis à Claude et celui demandé à Cursor sont identiques. [Contrat OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs), [implémentation Codex 0.166.0](https://github.com/openai/codex/blob/rust-v0.166.0/codex-rs/codex-api/src/common.rs).

Un retour Claude doit être un résultat success avec is_error=false ; un résultat error_max_turns n’est jamais accepté même s’il contient structured_output. Deux tours sont autorisés pour le dialogue interne de structuration, sans ouvrir les outils du cerveau. Le comportement exact de la version installée reste à éprouver lors du cycle manuel.

Un tour commence par le fournisseur suivant dans la rotation. Après une erreur de modèle, d'authentification, de format ou de validation du lot, il essaie une fois chacun des autres abonnements déjà configurés, sans modifier les comptes ni autoriser une API payante. Tout le lot candidat est validé avant l'outbox ; les fichiers du candidat rejeté ne sont pas publiés. Une détection de secret, une erreur hôte, un nettoyage de conteneur non confirmé ou une extinction arrêtent le traitement sans essayer un nouveau moteur. Le nettoyage vérifie l'absence du conteneur exact si sa suppression renvoie un échec.

Le journal privé state/private/controller-run.json conserve uniquement le tour, la date de mise à jour du journal, le fournisseur retenu et des catégories d'essais fermées. Sa projection last_turn est publiée dans world/controller.json ; reason_code précise aussi un échec courant. Les exceptions brutes, prompts, réponses, tokens et détails de compte n'y sont jamais copiés. Le champ readiness verified concerne toujours le cache de vérification du processus, tandis que last_turn décrit la dernière décision tentée ; il ne garantit pas la disponibilité future. DECISION_READY signifie que le lot est valide, pas que ses tâches ont réussi ou produit un revenu.

Si tous les abonnements échouent, le cycle publie CONTROLLER_BLOCKED, conserve state/private/controller-failure.json mode600 et renvoie un échec. Les commandes enchaînées par && s'arrêtent. Si le push échoue, la reprise Git et l'outbox préservent le lot sans rappeler un modèle. Une reprise répare également le journal d'état à partir de l'outbox lorsque l'écriture de DECISION_READY a été interrompue ; sa date de journal n'est pas une nouvelle invocation. Les anciens outboxes sans métadonnées d'essai restent lisibles.
