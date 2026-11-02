# Diagnostic et remise en route — 2 novembre 2026

Mandat du propriétaire : diagnostiquer les incohérences, puis fiabiliser et activer les capacités existantes. Audit du dépôt et du VPS ; aucun achat, aucun changement d'Oria, aucun identifiant privé dans ce rapport.

## Constats vérifiés

| Priorité | Preuve | Effet et traitement |
| --- | --- | --- |
| Critique | VPS : contrôle installé `4c5de507a427ac6782085b0cde3ab454a66f92c5` ; cerveau et exécuteur configurés absents de Docker. Les deux CLIs rendaient le code Docker 125 « No such image ». | La panne actuelle précède l'authentification et l'inférence. Base Node épinglée restaurée et cerveau reconstruit avec Codex 0.166.0 / Claude Code 2.1.316, les versions documentées du projet. La cause de suppression des anciennes images est inconnue. |
| Haute | Horaire installé, journal encore écrit ; Docker joignable, aucun cerveau résiduel, verrou libre, environ 134 Go disponibles au diagnostic. | Un cron présent ne prouve pas un agent fonctionnel. Vérifier un tour, les résultats et les artefacts publiés. |
| Haute | Dans le cerveau reconstruit, Codex est officiellement connecté par abonnement et ses restrictions CLI sont vérifiées. Claude répond `loggedIn=false`, méthode `none`. | Codex est utilisable ; Claude nécessite une reconnexion officielle. Ne pas présenter deux cerveaux authentifiés comme opérationnels. |
| Haute | Les correctifs sont répartis entre `main`, #3 et #5 empilée sur #3. `main` au début de l'audit : `a29552d061c5a953632a81d4ddea0a627caa8c96`. | Un test vert sur une branche ne prouve pas son déploiement. Cette correction part de la tête revue de #5 : `8a272e353c6449b81e205b13ad9d34e4858854c8`. Elle conserve les correctifs, le MCP et les éditeurs existants sans fusionner les PR ouvertes. |
| Haute | Sur le VPS au diagnostic : courtier non configuré, Apify/Cloudflare désactivés et sans credentials, aucun adaptateur financier, caisse et réservations CAD nulles. | Un prompt ne crée pas ces accès. Un fichier dans `products/` ne crée pas une URL publique ni une vente. Les dépendances absentes restent explicites. |
| Haute | WORLD recevait les arguments sans l'identité de `submitted_by`. Les outils productifs ne contrôlaient pas le statut du résident. | Correction : résident actif avant effet ; propriétaire des messages, transferts, baux, leçons et revues lié à l'auteur. Émission, politique, cycles et registre réservés au DIRECTOR. L'hôte conserve son chemin administratif. |
| Moyenne | Des identifiants comme `helper.1` étaient enregistrables mais refusés dans une tâche. | Registre et schéma alignés sur `[A-Z0-9_-]{1,64}`. Un nouvel agent créé peut réellement travailler. Aucun résident ancien n'est renommé automatiquement. |
| Moyenne | `preflight` vérifiait les empreintes et Docker, sans vérifier les images présentes ; GO était possible sans moteur. | Contrôle local des deux images ajouté, sans téléchargement implicite. Régression reproduite avant correction. |
| Moyenne | `core.autocrlf=true` convertissait les scripts Bash en CRLF dans ce checkout Windows ; échecs Linux reproduits. | `.gitattributes` impose LF. Le test MCP découvre le binaire Node au lieu d'imposer son emplacement. |

## Effet pour les agents

Le contexte du contrôleur, STATUS et `world_status` du MCP partagent l'état des neuf outils : `BUILT_IN` pour l'implémentation locale, `CONFIGURED_UNVERIFIED` pour des prérequis présents sans promettre une authentification ou un déploiement, `NOT_CONFIGURED` avec les prérequis manquants. Aucun contenu de credential ni identifiant de compte n'est transmis.

EXEC conserve son réseau direct coupé ; FETCH fournit le Web public. Les langages disponibles dépendent de l'image effectivement installée. Les éditeurs Apify/Cloudflare nécessitent leurs comptes et leurs revues de publication. SPEND nécessite des fonds vérifiés et l'adaptateur privé. Aucun outil n'est présenté comme connecté simplement parce qu'il figure dans le protocole.

Les résidents sont des rôles persistants d'un contrôleur partagé. La correspondance d'auteur garantit l'intégrité des tâches ; elle ne prouve pas cinq modèles indépendants. Le contrôleur peut choisir le rôle qui soumet une action. La revue entre fournisseurs conserve sa provenance hôte distincte.

Les nouvelles opérations WORLD incluent l'auteur dans leur digest d'idempotence. Le chemin administratif historique est conservé. Ne pas rejouer un ancien ID comme une nouvelle action : le superviseur conserve son journal et les tâches interrompues demandent un nouvel ID après revue.

## Validation

Suite locale sous Ubuntu 24.04 / Python 3.12 / Node 22.22.3 : **315 tests Python, 310 réussis et 5 optionnels ignorés**. Les échecs initiaux de préparation (Node absent et CRLF) ont été corrigés avant cette validation. Une régression Node supplémentaire couvre le diagnostic d'un artefact binaire après le premier cycle réel.

Les régressions couvrent les actions au nom d'autrui, les agents désactivés, la liaison auteur/idempotence, les identifiants, les opérations mal formées, les capacités et les images absentes. Les contrôles existants de reprise Git, banque, publications, MCP et arrêt terminal sont conservés. La relecture indépendante a relevé deux incohérences supplémentaires, corrigées avec régressions observées avant correction.

Les cinq tests optionnels demandent Docker ou un contrat CLI explicite ; ils ne sont pas présentés comme exécutés par la suite standard. Les vérifications réelles du VPS sont consignées séparément après activation. Voir INSTALL.md pour la sauvegarde et le retour au contrôle précédent ; ne pas restaurer d'anciens soldes financiers.

## Limites restantes

- Banque sans financement ni revenu vérifié au diagnostic : 50 CAD déclarés ne sont pas un dépôt.
- Pas de nouveau navigateur authentifié, d'intégration ou de compte ajouté par cette correction.
- La maintenance GLC peut désactiver les résidents ; pas de remboursement ni de réactivation automatique. Le DIRECTOR peut adapter la politique et distribuer des récompenses virtuelles. Les références de preuve déclarées ne sont pas des recettes CAD.
- Les jetons de bail restent présents dans les projections historiques ; ils ne sont pas une authentification des fournisseurs.
- Taille du contexte, missions ouvertes et autonomie sur plusieurs jours restent à éprouver sur la durée.
- #4 (produit), #6 (directives), #7/#8 (plans) restent distinctes. Leurs changements de gouvernance ne sont pas adoptés implicitement.
