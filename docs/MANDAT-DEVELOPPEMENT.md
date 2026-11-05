# Mandat commun de développement — GlobalLand

Ce document guide les assistants qui aident le fondateur à concevoir et coder GlobalLand : Codex, Claude Code et tout autre collaborateur. Il concerne notre travail de développement et nos conférences. Sa rédaction ne configure ni ne déploie les agents du VPS.

## Cap à préserver

Construire un monde d'agents productifs et autonomes, capables de réfléchir à leur survie, choisir leurs stratégies, agir, observer leurs résultats et apprendre. Le fondateur fixe le mandat ; les agents choisissent leurs activités, leurs outils et leurs marchés dans ce cadre. [VISION.md](../VISION.md) porte le mandat du monde et ses limites financières.

Une plateforme, un prototype, une intégration déjà écrite ou une suggestion d'assistant ne devient jamais l'objectif du projet. Apify, un site, un service, une API ou une autre voie peuvent servir une stratégie ; aucun canal ni type de produit n'est imposé par les développeurs.

## Stratégie de collaboration

1. **Repartir du mandat et du blocage observé.** Lire les consignes du fondateur, VISION.md, ce document et les fichiers concernés. Utiliser AgentMemory s'il est disponible pour rappeler le contexte de développement, sans le confondre avec la mémoire des agents déployés.
2. **Diagnostiquer avant de proposer.** Examiner le code, les résultats et les dépendances réelles. Séparer faits vérifiés, hypothèses et propositions ; montrer les preuves utiles. Une idée plausible n'est pas un défaut confirmé.
3. **Choisir la plus petite amélioration utile de structure.** Expliquer ce que les agents pourront décider, faire ou apprendre de plus. Comparer les alternatives lorsqu'un choix important est ouvert. Un outil déjà disponible ne suffit pas à justifier son adoption.
4. **Préserver le choix des agents.** Faciliter leur raisonnement, leurs actions, leur retour d'expérience et leurs possibilités d'évolution. Ne pas remplacer cette autonomie par une niche choisie par le développeur, une liste fermée d'activités ou des validations humaines répétées pour les actions déjà déléguées.
5. **Vérifier puis transmettre.** Utiliser les compétences Superpowers pertinentes lorsqu'elles sont disponibles, des tests adaptés au changement et une revue des risques. Relier les constats au diff, aux résultats et aux limites encore ouvertes. Conserver un passage de relais commun plutôt que deux plans divergents Codex/Claude.

## Vérification du cap avant chaque changement

- Quel besoin du mandat ou quel défaut observé justifie ce changement ?
- Quelle capacité de décision, d'action ou d'apprentissage devient réellement disponible ?
- Le changement impose-t-il sans décision du fondateur une plateforme, une activité, un modèle commercial ou une validation humaine supplémentaire ?
- Quels éléments restent seulement proposés, configurés, testés localement, déployés ou vérifiés en conditions réelles ?
- Les limites financières, la protection des secrets et d'Oria, la séparation du contrôle hôte et les revues indépendantes restent-elles respectées ?

Si une proposition change la finalité ou une règle du mandat, la présenter comme un arbitrage explicite au fondateur. Ne pas la faire passer pour une simple correction technique. Pour intervenir sur le VPS ou des comptes externes, s'appuyer sur la portée opérationnelle autorisée dans la session : cette consigne de collaboration ne l'étend pas. Une autorisation déjà donnée reste valable ; ne pas demander à nouveau un accord identique.

## Vérité et décisions ouvertes

Ne pas assimiler une décision valide, un fichier créé ou une mission déclarée terminée à une preuve d'utilité, de vente ou de survie. Distinguer fonctionnement technique, résultat exécuté, observation extérieure et revenu réellement encaissé.

Les GLC, le ledger historique, les crédits promotionnels et les fonds vérifiés sont des choses distinctes. L'attestation d'un dépôt initial, l'imputation des abonnements et les autres choix comptables restent soumis au mandat et aux décisions explicites du fondateur ; un assistant ne tranche pas à sa place.

Quand un accès ou une capacité manque, décrire précisément ce qui dépend du fondateur et poursuivre le travail indépendant utile. Un compte manquant sur une plateforme ne devient pas une consigne imposant cette plateforme.

## Passage de relais Codex / Claude

Transmettre : objectif du fondateur, portée autorisée, décisions déjà prises, branche et fichiers, preuves obtenues, risques et prochaine action. Signaler les contradictions dans les anciennes consignes au lieu de suivre un exemple qui dévie du mandat. Une correction explicite du fondateur doit être conservée dans les consignes communes pertinentes.

AgentMemory reste une mémoire locale de développement : aucun secret, justificatif bancaire personnel ou état privé des agents en production ne doit y être copié.

Ces consignes rendent le cap explicite et révisable ; leur présence ne garantit pas qu'un assistant les a lues. L'assistant doit les prendre en compte dès le début de son intervention et rendre son travail contrôlable, sans imposer au fondateur de les répéter.
