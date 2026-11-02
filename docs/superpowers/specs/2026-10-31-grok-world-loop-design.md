# Boucle Grok → GlobalLand → spécialistes

**Statut : proposition de conception, pas une intégration déployée.** Préparée avec Superpowers à la demande du fondateur. L’application est désormais identifiée : **Grok Bot de xAI**. Ses fonctions natives sont documentées ; les accès et routines du compte de l’opérateur restent à vérifier. L’opérateur confirme que Cursor ouvre ou rouvre une PR.

## Intention

Le fondateur parle à ses Grok Bots. Ceux-ci travaillent, choisissent les missions et utilisent Codex ou Claude comme spécialistes. Le superviseur GlobalLand organise l’exécution sur le VPS et conserve les preuves. Le fondateur ne doit pas recopier une commande Hostinger pour chaque mission.

L’opérateur rapporte désormais un chemin **Grok Bot → Cursor → PR GitHub**. Ce circuit convient au développement ; une PR de tâches attend sa livraison à main avant consommation par le VPS. GitHub est déjà un transport prévu : ce sont le chemin, la branche, le format et le retour des résultats qui déterminent si une action atteint le monde.

## Vérification du produit officiel

Le [guide xAI Grok Bot 101](https://x.ai/bot/guides/grok-bot-101) et la [page produit](https://x.ai/bot), lus le 31 octobre 2026, documentent un ordinateur cloud persistant, un terminal, les applications, des routines programmées, des déclencheurs et les messages entre bots. Le guide décrit la délégation à Cursor Cloud Agent avec ouverture d’une PR. Il annonce aussi les mêmes serveurs MCP, plugins et skills que Cursor. Le produit ne doit donc pas être assimilé à une simple application de chat sans reprise autonome.

Ces capacités sont des fonctions annoncées par le fournisseur, pas des essais réalisés dans le compte de l’opérateur. Un déclencheur GitHub PR est donné en exemple ; aucun déclencheur particulier sur un fichier de résultat de queue n’est établi. Le premier parcours proposé utilise une routine native qui consulte les résultats périodiquement. Il n’exige pas de présumer une API xAI distincte ou un nouvel abonnement.

## État de départ et limites

- `queue/inbox/TASK-NNNN.json` sur `main` transporte les tâches. Les résultats sont publiés dans `queue/done/` ou `queue/failed/`. TASK-0003 possède un résultat DONE ; des cycles natifs plus récents ont produit des missions et artefacts vérifiés.
- Le contrôleur actuel consulte directement Codex/Claude ; ce fonctionnement ne prouve pas une délégation commandée par Grok. Il ne comporte pas d’action DELEGATE.
- Les deux abonnements sont configurés pour l’horaire de réflexion. L’horaire a été installé, puis le lancement immédiat a échoué. La dernière projection lue affiche WAITING_SUBSCRIPTION_AUTH ; cette projection peut refléter un cache de vérification vide et ne prouve pas une déconnexion.
- Les corrections locales de reprise des fournisseurs sont publiées dans la PR #3, mais leur déploiement sur le VPS reste à vérifier. Une opération Hostinger était annoncée en cours ; son type et son résultat ne sont pas connus.
- Cursor, utilisé comme relais par l’application selon l’opérateur, peut être distinct de la CLI Cursor installée sur le VPS. Les délais dépassés de cette dernière ne prouvent pas une panne du relais externe.
- La banque est UNFUNDED. Le capital autorisé n’est pas un dépôt rapproché. Cette conception ne choisit ni n’ouvre un compte financier.

## Approches

| Approche | Apport | Dépendance ou coût de changement |
| --- | --- | --- |
| **Routine native Grok Bot + queue existante** | Utiliser l’ordinateur et la reprise déjà documentés du produit ; conserver le moteur et les abonnements. | Vérifier les accès GitHub, la routine dans le compte et la déduplication des suites. Cursor n’est pas obligatoire. |
| Faire passer les missions par le relais Cursor existant | Prouver rapidement le parcours si le relais peut aussi livrer des tâches sur main. | Aujourd’hui, seule l’ouverture d’une PR est rapportée ; une intervention par mission ne satisfait pas l’objectif. |
| Outil MCP GlobalLand connecté à Grok Bot | Proposer des outils directs de soumission et de lecture. | Serveur authentifié accessible et connecteur à installer/vérifier ; aucun n’est présent aujourd’hui. |
| Connecter directement une API Grok au VPS | Réveil programmable si l’offre et l’identité de service le permettent. | Connexion et facturation distinctes possibles ; aucune API autorisée ou configurée n’est établie. |
| Migrer toute l’orchestration vers un framework | Apporter des abstractions de reprise et de coordination. | Migration sans résoudre à elle seule l’accès à l’application Grok ni la banque. |

**Choix proposé : commencer par une routine native Grok Bot et la queue existante.** Le bot livre ses tâches via un connecteur dont les capacités auront été éprouvées, ou un petit client GitHub sur son ordinateur cloud. Il consulte les résultats lors de sa prochaine routine et poursuit la mission. Cursor reste utile au développement. Le MCP constitue une évolution possible si le parcours natif montre un besoin concret ; aucune nouvelle API de modèle n’est requise par cette conception.

## Deux circuits explicites

**Mission du monde :** Grok prépare une intention ; un adaptateur supporté livre les enveloppes nécessaires dans la queue sur main, directement ou via le relais Cursor. Le superviseur les consomme et publie les résultats. Un relais limité à l’ouverture de PR n’est pas qualifié de transport autonome tant que leur livraison à main n’est pas réglée par un mécanisme réellement disponible.

**Développement du logiciel :** Cursor modifie le code sur une branche et ouvre une PR. Sa fusion ne change pas la release du contrôle installée sur le VPS ; la mise à niveau reste une opération administrative distincte.

Les instructions destinées au relais nomment toujours le circuit. Un changement du README ou une PR de code ne constitue pas une mission exécutée dans le monde.

## Délégation à un spécialiste

Ajouter une action TOOL `DELEGATE` avec les arguments fermés suivants :

```json
{
  "provider": "auto",
  "mission_id": "FIRST-PRODUCT",
  "instruction": "Propose les tâches nécessaires pour produire un petit prototype vérifiable."
}
```

`provider` vaut `auto`, `codex` ou `claude`. `mission_id` reprend la grammaire d’identifiant WORLD et désigne une mission OPEN ou RUNNING ; le résident auteur doit exister et être actif. La délégation ne clôture ni ne réclame la mission et ne remplace pas ses règles de bail. `instruction` contient 1 à 10000 caractères non vides. L’enveloppe garde les champs et la grammaire TASK actuels ; `estimated_cost_cad: 0` décrit l’appel via les abonnements existants, pas un budget de dépense financière.

Le spécialiste reçoit la mission, un contexte public borné et l’instruction. Il utilise sa CLI officielle dans le conteneur de réflexion existant et retourne une **proposition structurée**, validée avec les mêmes règles de décisions et d’enveloppes que les tâches actuelles. Il n’exécute pas son code dans le conteneur qui possède sa connexion. Les programmes proposés passent ensuite par EXEC, les opérations financières par SPEND/RECONCILE.

Le résultat de DELEGATE publie `products/delegations/TASK-NNNN.proposal.json` et son empreinte. Il ne crée pas automatiquement les tâches proposées. Grok lit la proposition, décide de la suite et transmet un nouveau lot par le relais. Le JSON proposé reste une donnée, jamais une commande hôte interprétée. Les propositions peuvent demander d’autres délégations ; chaque nouvel appel reste une tâche séparée et traçable.

`auto` essaie une fois les fournisseurs configurés et disponibles, avec le comportement de reprise existant. Un fournisseur nommé est utilisé seul ; un autre n’est pas présenté sous son identité. Aucun repli API payant ou achat de crédits. Cursor pourra être ajouté à cette liste après validation native de sa CLI ; il ne bloque pas ce premier parcours.

## Reprise et retour vers Grok

La tâche et son empreinte sont enregistrées avant invocation. Une proposition validée est sauvegardée dans une outbox privée avant publication. Une reprise de publication réutilise ces octets. Une interruption à résultat inconnu n’est pas déclarée réussie et ne relance pas aveuglément le modèle.

Le retour réutilise le résultat durable sur GitHub. Une routine native du bon Grok Bot consulte les IDs qu’il a soumis et reprend depuis son journal de mission. Le relais conserve les octets exacts avant envoi ; une nouvelle consultation retrouve la tâche en attente ou son résultat et ne la redépose pas. Les suites proposées par Grok doivent elles aussi être enregistrées avant transmission, afin de ne pas fabriquer de nouveaux IDs après une livraison incertaine.

La progression utilise une barrière de lot : le bot attend les résultats publiés de toutes les tâches du lot, puis une seule source agrégée permet le lot suivant. Le journal de mission conserve cette association et le lot actif ; deux routines concurrentes ne peuvent pas produire deux suites. Cela n’assimile pas un résultat d’outil à un règlement financier : les opérations financières UNKNOWN restent à rapprocher via leurs identités d’origine.

**Dépendance déterminante :** la routine doit être effectivement configurée et exécutée dans le compte. Sa documentation seule, comme l’accès GitHub seul, ne prouve pas une reprise de GlobalLand. Avant cet essai, publier `WAITING_GROK_TRANSPORT` ou `WAITING_GROK_RESUME` selon la dépendance constatée et conserver les résultats. Ne pas appeler une session Codex de remplacement « Grok » et ne pas qualifier ce parcours d’autonomie complète.

La configuration du coordinateur est distincte des connexions des spécialistes. Un état dédié `world/coordinator.json` décrit `mode`, `state`, `automatic_resume_verified` et les références publiques du dernier événement. La readiness des abonnements ne sert pas de preuve du réveil de Grok. L’état et les codes sont fermés ; pas d’exception brute, token, détail de compte ou trace privée.

La capacité de livraison vise l’arrivée effective sur main, par écriture directe ou fusion automatique vérifiée, pas une obligation d’utiliser un mécanisme particulier. Un essai administratif peut fonctionner en état VALIDATING avant la preuve d’autonomie : il concerne une mission nommée et deux lots de suite maximum via le relais, conserve `automatic_resume_verified: false` et ne s’active pas lui-même en READY. Le journal du relais compte les lots et applique cette borne atomiquement, y compris après redémarrage ; une consultation sans nouveau lot ne consomme pas la borne. Cette propriété ne prétend pas limiter les conversations ou tous les réveils de l’application xAI. Cela permet de mesurer la vraie boucle avant d’autoriser son fonctionnement normal.

Dans le mode coordonné, un seul coordinateur conduit les suites de missions. Les horaires queue/daily demeurent ; le cycle think ne lance pas simultanément une stratégie indépendante ignorant Grok. La bascule est explicite, réversible et conserve les outboxes en cours.

## Banque et recherche open source

Le travail de délégation n’exige pas de financer la banque. La trésorerie existante conserve ses réservations atomiques, identités d’opérations et rapprochements. Les revenus doivent provenir d’une intégration de confiance ; la taxe serveur narrative et les GLC ne deviennent pas des débits ou dépôts réels.

| Référence consultée le 31 octobre 2026 | Ce qui est utile | Limite pour GlobalLand |
| --- | --- | --- |
| [TigerBeetle](https://github.com/tigerbeetle/tigerbeetle), Apache-2.0 | Comptes, montants réservés, transferts en deux phases et contraintes de solde. | Grand livre, pas banque dépositaire. Ne pas libérer une réservation externe UNKNOWN parce qu’un délai local expire. |
| [Blnk](https://github.com/blnkfinance/blnk), Apache-2.0 | Double entrée, rapprochement et transactions en cours. | Service supplémentaire ; les écritures internes ne prouvent pas seules le règlement externe. |
| [LangGraph](https://github.com/langchain-ai/langgraph), MIT | Checkpoints, fils persistants et reprise des étapes terminées. | N’apporte ni accès à l’application Grok ni garantie automatique de paiement unique. |
| [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety), Apache-2.0 | Interactions et expériences multi-agents. | La v1 historique contient les modules économiques urbains ; la v2 est une plateforme de recherche différente. Le démarrage documenté demande une connexion LLM. |
| [Generative Agents](https://github.com/joonspk-research/generative_agents), Apache-2.0 | Mémoire et simulation d’habitants. | Le parcours documenté utilise une API OpenAI ; pas une liaison automatique aux abonnements déjà détenus. |
| [AI Economist](https://github.com/salesforce/ai-economist), BSD-3-Clause | Expériences sur travail, gouvernement et fiscalité simulés. | Dépôt archivé ; aucune preuve de revenus commerciaux réels. |
| [AgentKit](https://github.com/coinbase/agentkit), Apache-2.0 selon LICENSE.md | Portefeuilles et actions onchain. | Accès, frais, garde et intégration à vérifier ; pas un compte CAD prêt à brancher. |
| [x402](https://github.com/x402-foundation/x402), Apache-2.0 | Paiements pour des ressources HTTP. | Le dépôt canonique est désormais celui de la fondation ; le facilitateur public de test n’est pas une preuve d’exploitation mainnet. |

Sources de mécanismes : [réservations TigerBeetle](https://docs.tigerbeetle.com/coding/two-phase-transfers/), [contraintes des comptes](https://docs.tigerbeetle.com/reference/account/), [checkpoints LangGraph](https://docs.langchain.com/oss/python/langgraph/checkpointers). Les fonctionnalités ont été lues dans les sources officielles ; aucun de ces projets n’a été installé ou exécuté pour cette recherche.

## Preuve d’acceptation

1. Un message utilisateur identifiable devient une mission WORLD sur main, sans modification de code ni commande terminal par mission.
2. Grok transmet une DELEGATE à Codex ; le VPS publie une proposition, puis Grok choisit et transmet une tâche EXEC issue de cette proposition.
3. Un artefact et son reçu sont publiés. Grok reçoit le résultat et produit une décision suivante sans relance de l’utilisateur. Claude est éprouvé par une délégation distincte.
4. Une panne de publication, un doublon et une indisponibilité de fournisseur sont testés sans refaire un effet incertain. Les statuts et identités correspondent aux invocations réelles.
5. Aucun fonds réel n’est déplacé pendant cette preuve. La banque reste UNFUNDED. Les tests avec reçus financiers factices demeurent isolés de l’instance réelle.

Des tests locaux avec faux transports prouvent le logiciel, pas ce parcours natif. L’autonomie de bout en bout reste non démontrée tant que l’exécution de la routine réelle de Grok et sa décision suivante ne sont pas observées. Les fonctions documentées de Grok Bot rendent ce chemin plausible ; elles ne constituent pas une preuve de sa configuration chez l’opérateur.
