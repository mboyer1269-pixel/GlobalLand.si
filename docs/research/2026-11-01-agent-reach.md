# Analyse de Panniantong/Agent-Reach pour GlobalLand

> **Analyse du 1er novembre 2026**
> - **Méthode :** copie superficielle du dépôt (commit `7a38047`, 1er nov. 2026), lecture du README, du répartiteur (`agent_reach/runtime/dispatch.py`), de la garde d'URL et du contrôle de publication.
> - **Licence :** MIT (© 2025 Agent Eyes).
> - **Limites :** rien n'a été installé ni exécuté.

## Ce que c'est

Une CLI Python qui donne aux agents (Claude Code, Codex, OpenClaw…) l'accès à des plateformes difficiles d'accès :
- plateformes chinoises : Bilibili, Xiaohongshu, V2EX, Xueqiu ;
- X, LinkedIn, Reddit, Instagram, Facebook ;
- sous-titres YouTube et transcription de podcasts ;
- GitHub et lecture du Web.

Une commande, `agent-reach <canal> <action>`, couvre tout.

Selon son README, le projet a été classé n° 1 du jour sur Trendshift. Ses commanditaires vendent tous de la collecte de données Web : Bright Data, RapidProxy, BrowserAct et CoreClaw.

## Verdict : 6,5/10 pour GlobalLand

| Critère | Note | Raison |
|---|---|---|
| Revenus | 6 | Ce n'est pas un rail d'encaissement, mais un **signal de marché** : la demande d'« accès au Web pour agents » est forte et commanditée. |
| Coût | 9 | MIT, gratuit. On reprend des idées, pas une dépendance. |
| Risque | 3 | Les canaux avec connexion **copient les cookies du navigateur Chrome de l'utilisateur** et contournent les murs de connexion. Pour GlobalLand, ce serait sur les comptes du fondateur, contre les conditions des plateformes. |
| Vitesse de validation | 8 | Les idées retenues se codent et se testent en quelques heures. |
| Scalabilité | 7 | La distribution « agent d'abord » se démultiplie sans effort humain. |
| Différenciation | 6 | Le marché du scraping est saturé ; l'angle « données publiques propres pour agents » l'est moins. |
| Exécution | 7 | Code soigné : tests de contrats par canal, garde contre la falsification de requêtes côté serveur (SSRF), écritures privées, effacement des identifiants dans les journaux. |

**Ce qui l'empêche d'avoir 10 :** son cœur de valeur, l'accès derrière les murs de connexion, est exactement ce que nos garde-fous juridiques interdisent.

## Intégré dans GlobalLand

| Idée d'Agent-Reach | Intégration | Preuve |
|---|---|---|
| **Pause d'un outil après échec** (`backend_pause` : un outil en échec est mis de côté pour un temps) | **Disjoncteur des fournisseurs** : un fournisseur qui vient d'échouer passe en dernier pendant 30 min, puis 1 h, 2 h… jusqu'à 6 h au plus. Il n'est **jamais exclu** : si l'autre échoue, il est quand même essayé. Seuls des codes fixes sont enregistrés (`state/private/provider-health.json`). | 4 tests ; 2 échouent sans le disjoncteur |
| Pourquoi c'est important | Avec le courtier activé, un tour peut durer 900 s. Un fournisseur mort essayé en premier à chaque cycle consommerait la moitié de la fenêtre de 30 min et pourrait chevaucher le cycle suivant. | — |
| **Diagnostic par canal**, « ce qui marchait et ne marche plus » | `incident.py` affiche l'état du disjoncteur par fournisseur, en liste blanche. | 1 test, dont un champ secret jamais affiché |
| **Distribution agent d'abord** (une phrase à coller à son agent, `llms.txt`) | Nouvelle fiche `agent-first-distribution` injectée à chaque tour : point d'entrée lisible par un agent, sortie JSON stable, un outil par verbe, solutions de repli ordonnées *dans* le produit, mesure des exécutions lancées par API ou MCP. | Fiche chargée (test des fiches mis à jour) |
| **Public d'abord, lecture seule** | Ajout à `legal-guardrails` : jamais de réutilisation des sessions ou cookies du fondateur, jamais de connexion au nom de GlobalLand, aucune publication sur une plateforme sans compte dédié approuvé. | Fiche injectée à chaque tour |

## Écarté, et pourquoi

| Élément | Décision | Raison |
|---|---|---|
| Installer Agent-Reach dans la boîte des agents ou sur l'hôte | **Non** | Il installe automatiquement des outils tiers (pip, npm, Chrome), ce qui est un risque pour la chaîne d'approvisionnement de l'hôte. La boîte EXEC est hors ligne de toute façon. Le paquet PyPI du même nom n'est pas le leur, selon leur avertissement. |
| Canaux avec connexion (X, LinkedIn, Reddit, Instagram, Facebook, Xiaohongshu, Boss) | **Non** | Copie des cookies du navigateur personnel, et contournement des conditions d'utilisation. Les comptes sont au nom du fondateur. |
| Transcription YouTube et podcasts | **Non pour l'instant** | Les conditions de YouTube encadrent le téléchargement, et la transcription demande une clé payante (Groq ou OpenAI). |
| Commanditaires et liens d'affiliation comme modèle de revenu | **Plus tard** | Il faut d'abord de la traction (un outil populaire). Piste valable une fois un produit utilisé. |

## Opportunité pour les agents (à valider par eux, avec le verdict d'idée)

Agent-Reach montre que des agents veulent des **données publiques propres et structurées**. Deux pistes compatibles avec nos garde-fous :
- **Actors Apify « pour agents » :** sortie JSON stable, description claire et appelables via MCP, sur des sources publiques avec API officielle (dépôts et issues GitHub, offres d'emploi publiques, données ouvertes gouvernementales du Québec et du Canada).
- **Le « petit plus » d'Agent-Reach :** les solutions de repli ordonnées. Un Actor qui essaie l'API officielle puis une page publique, et dit quelle source a répondu, résiste mieux aux changements de sites. C'est l'étape « Delivery » de la fiche `growth-constraint`.

*Hypothèse non vérifiée :* la demande payante de ces Actors sur Apify Store. Le verdict d'idée des agents doit la tester avant de construire.
