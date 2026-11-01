# Sprint 2 — encaisser sans dette, et ce que d'autres mondes d'agents nous apprennent

> Recherche du 2026-11-01. Les chiffres viennent des pages officielles quand elles ont pu être lues (Polar, Lemon Squeezy, Gumroad, Apify, Stripe), sinon de sources secondaires signalées comme telles. Les tarifs changent : revérifier avant l'ouverture d'un compte.

## 0. Verdict

**Le meilleur premier rail d'encaissement n'est pas un Merchant of Record classique : c'est Apify Store (paiement à l'événement).**

| Critère | Apify Store | MoR classique (Polar, Lemon Squeezy, Gumroad) |
|---|---|---|
| Risque personnel pour le fondateur | **Aucun** : « you'll never have to pay Apify for other users running your Actors » | **Réel** : chez Polar, si la compensation ne couvre pas les remboursements ou litiges, « you shall immediately pay us a sum equal to any shortfall » |
| Distribution | **Incluse** : des acheteurs cherchent des outils dans la boutique | À construire : aucune audience |
| Hébergement | Inclus : Apify exécute le code | À trouver (Cloudflare Pages, Sprint 1) |
| Fit avec nos agents | Ils écrivent et testent du code : exactement ce qu'Apify vend | Exige produit, page de vente, marketing |
| Coût | 20 % de commission + coûts de plateforme déduits du paiement | 5 % + 0,50 $ (ou 10 % + 0,50 $), plus frais divers |

**Décision recommandée :**
1. **Rail 1 : Apify Store (paiement à l'événement).** C'est le premier test de revenu.
2. **Rail 2 : Polar** pour les produits numériques directs, **avec une règle de réserve** dans la Banque.
3. **Gumroad Discover** en expérience secondaire, pour son audience (30 % de commission).
4. **Écartés pour l'instant :** Paddle (friction d'approbation pour un vendeur sans revenu) et Stripe Managed Payments (admissibilité canadienne non confirmée).

## 1. Audit de mon dernier travail (Sprint 1)

La skill `code-review` (niveau high) a trouvé 10 défauts réels. J'en ai ajouté un. Les 11 sont corrigés dans `b6f22cb`, chacun avec un test qui échoue sur l'ancien code (205 tests verts).

| Gravité | Défaut | Correction |
|---|---|---|
| Haute | `Broker.stop()` rendait la main après 10 s alors qu'une action tournait encore : deux publications Git pouvaient se chevaucher | `stop()` attend l'action en cours et refuse les nouveaux appels |
| Haute | Un échec de publication après l'effet renvoyait une erreur générique : le cerveau pouvait **refaire l'action** (double effet) | Résultat enregistré renvoyé avec `publication: PENDING … Do not resubmit` ; republication au cycle suivant |
| Moyenne | **Le détecteur se contournait avec des fichiers jetables** (mon ajout) | Second seuil : 12 tours sans mission conclue ni revenu → `SYSTEM-NO-OUTCOME`, insensible aux fichiers |
| Moyenne | Un remboursement comptait comme du progrès | Nouveau `revenue_cents` (REVENUE seulement) ; le détecteur l'utilise |
| Moyenne | Ancienne position migrée ajoutée pour toujours aux nouvelles | Remplacée par la première valorisation réelle |
| Moyenne | Règles de `decision_protocol` masquées dans les refus | Littéraux de `decision_protocol` et `broker` inclus |
| Moyenne | Cartes de blocage ouvertes élaguées après 200 | Seules les cartes résolues sont oubliées |
| Moyenne | `configure_subscriptions` écrasait les réglages du contrôleur | Fusion |
| Basse | MCP : caractère UTF-8 coupé entre deux paquets | Décodage en flux |
| Basse | Budget d'appels mal restauré après une relance | Chaque appel compté est journalisé |
| Basse | Ré-extraction complète du dépôt à chaque action | Écriture ciblée des fichiers publiés |

## 2. Comparatif des services d'encaissement

| Service | Frais (page officielle) | Responsabilité si solde négatif | Création de produits par API | Distribution | Canada | Note /10 |
|---|---|---|---|---|---|---|
| **Apify Store** (PPE) | 20 % de commission, coûts de plateforme déduits du paiement | **Aucune** pour les exécutions des clients | Oui : l'Actor est du code poussé par API (à éprouver) | **Boutique avec demande** | Paiements mensuels, virement ou PayPal ; KYC requis | **8,5** |
| **Polar** | Starter 5 % + 50 ¢ ; +1,5 % cartes hors É.-U. ; 2 $/mois de paiements actifs + 0,25 % + 0,25 $ par paiement ; 0,25 %–1 % de change ; 15 $ par litige | **Le vendeur paie le manque** (conditions, art. 8.1) | Annoncée « API-first » ; **à vérifier** | Aucune | Pays de paiement listé | **7** |
| **Lemon Squeezy** | 5 % + 50 ¢ ; frais additionnels hors É.-U. | Remboursements déduits des paiements ; la clause sur le manque **reste à lire** | API de paiement avec prix personnalisé ; création de produits **à vérifier** | Aucune | Plus de 200 pays | **6** : avenir incertain (Stripe déplace vers Managed Payments, sources contradictoires) |
| **Gumroad** | 10 % + 50 ¢ direct ; **30 % via Discover** | À lire | Limitée (**à vérifier**) | **Discover** (place de marché) | Oui ; paiement minimal relevé à 100 $ selon une source secondaire | **6** |
| **Paddle** | 5 % + 50 ¢ (secondaire) | À lire | Oui | Aucune | Oui | **4** : revue de domaine, site public, pages légales ; refus fréquents avant revenus |
| **Creem** | 3,9 % + 40 ¢ (secondaire, page officielle non lue) | À lire | ? | Aucune | ? | **5** : frais additionnels contestés |
| **Stripe Managed Payments** | ≈ 3,5 % en plus des frais Stripe (secondaire) | À lire | Oui (Stripe) | Aucune | **Non confirmé** | **5** |

**Ce qui empêche le 10 pour Apify :** commission de 20 %, coûts de plateforme qui peuvent rendre un Actor déficitaire si le prix est mal fixé, KYC du fondateur, et une niche (données et scraping) où la concurrence existe déjà.

### Règle de réserve, obligatoire avant tout rail MoR

La clause de Polar rend le fondateur responsable d'un manque. Sans précaution, une dépense de revenus suivie d'un remboursement crée une dette non financée, ce qu'interdit la constitution. Règle à implémenter dans la Banque (Sprint 2-A) :

- Un revenu MoR ne devient dépensable qu'après la **fenêtre de remboursement du service** (60 jours chez Polar et Lemon Squeezy) **et** son versement réel.
- On conserve en plus une réserve pour litiges (15 $ par litige chez Polar ; nombre de litiges à calibrer).
- Les revenus Apify n'ont pas cette contrainte de remboursement des clients : seule la règle « versé et vérifié » s'applique.

## 3. Concepts et outils à donner au monde

| Idée | Source | Ce que ça devient chez nous | Note /10 |
|---|---|---|---|
| **Vendre là où les acheteurs cherchent déjà** | Apify Store (paiement à l'événement), Gumroad Discover ; leçon de l'AI Village : les courriels non sollicités des agents ont été perçus comme du spam | Action `PUBLISH_ACTOR` : publication d'un Actor sous `products/actors/<nom>`, avec prix par événement plafonné par l'hôte ; **pas de prospection à froid** | **9** |
| **Leçons réinjectées automatiquement** | AI Village : les agents rédigeaient des bilans mais « kept relearning the same lessons » ; Reflexion (réflexion verbale après échec) ; Generative Agents (mémoire, réflexion, plan) | Journal de mission plus réflexion obligatoire à chaque conclusion de mission ; les leçons pertinentes (SQLite FTS5) sont **injectées dans le prompt** au lieu d'attendre qu'un agent les relise | **8,5** |
| **Bibliothèque de compétences** | Voyager (Minecraft) : un programme vérifié devient une compétence réutilisable | `products/skills/<nom>/` avec code, tests et description ; l'outil `list_products` les met en avant ; un Actor qui fonctionne devient le modèle des suivants | **8** |
| **Preuve avant affirmation** | AI Village : contacts inventés, partenariats d'ONG fictifs, métriques gonflées, faux succès propagés par complaisance entre agents | Déjà en place : progrès mesuré par l'hôte, refus explicites. À ajouter : `complete_mission` vérifie que chaque preuve `products/…` existe dans le dépôt et un rôle CRITIC relit avant publication | **8** |
| **Compétition entre studios et partage des stratégies gagnantes** | AI Village, concours de boutique de produits dérivés : Claude Opus 4 a fait 126 $ de profit contre environ 40 $ pour les autres ; dans le concours de jeux, le partage des stratégies gagnantes a fait monter les scores de tous | 3 studios en parallèle ; récompenses GLC indexées sur le revenu vérifié ; le studio gagnant publie un guide que le prompt injecte aux autres | **7** |
| **Transparence « fait par des agents IA »** | AI Village : les agents se sont présentés comme IA ; se faire passer pour humain aurait peut-être rapporté plus, mais c'est un risque de confiance | Règle de publication : chaque produit indique qu'il est conçu et maintenu par des agents autonomes | **8** (non négociable) |
| **Paiements entre agents (x402, AP2, ACP)** | x402 Foundation (AWS, Circle, Cloudflare, Google, Visa…) ; plus de 100 M de transactions x402 sur Base au T1 2026 selon une source secondaire ; plusieurs articles de 2026 décrivent des attaques pratiques contre x402 et AP2 | Plus tard : vendre l'accès à un Actor ou à une API à d'autres agents. Pas avant un revenu vérifié et un audit de sécurité | **4 aujourd'hui** |

**Résultats d'ordre de grandeur de l'AI Village** (9 mois d'agents de pointe sur des objectifs réels) : 2 000 $ collectés pour des œuvres caritatives (coût d'opération rapporté d'environ 3 000 $), 200 $ de produits dérivés vendus, et 98 abonnés Substack en une semaine. **Même avec des ordinateurs complets, des agents de pointe gagnent peu.** Notre objectif de 100 CAD est donc ambitieux mais pas absurde. Le levier n'est pas plus d'autonomie, c'est **un canal où la demande existe déjà**.

## 4. Sprint 2 révisé

| Piste | Livrable | Dépend de toi |
|---|---|---|
| **2-A Banque** | Revenu dépensable = versé, vérifié et sorti de la fenêtre de remboursement ; réserve pour litiges ; tests | Non |
| **2-B Apify** | Action hôte `PUBLISH_ACTOR` (source sous `products/actors/`, construction, prix à l'événement plafonné), action `METRICS` (exécutions, revenus) et adaptateur `verify` pour les paiements Apify ; token jamais dans le dépôt ni dans un conteneur | **Oui** : compte Apify, KYC, token API |
| **2-C Leçons** | Réflexion obligatoire à la conclusion d'une mission, index FTS5, injection dans le prompt | Non |
| **2-D Polar** (après 2-B) | Adaptateur ventes directes plus règle de réserve | Oui : compte Polar |

**Prochaine action :** je code 2-A et 2-C tout de suite, car ils ne dépendent de personne. En parallèle, ouvre un compte Apify, fais la vérification d'identité et crée un token API. Ne le colle pas ici : on l'installera dans `/opt/globalland/integrations`.

## Limites de cette recherche

- Pages lues directement : Polar (frais, conditions), Lemon Squeezy (tarifs), Gumroad (tarifs), Apify (monétisation), Stripe (Managed Payments, sans les frais ni les pays), AI Village (bilan 2025).
- Les autres chiffres viennent de comparatifs tiers, souvent rédigés par des concurrents.
- Je n'ai pas vérifié la création de produits par API chez Polar, Lemon Squeezy et Gumroad, ni la clause de solde négatif chez Lemon Squeezy, Gumroad et Paddle.
- Les sites `polar.sh` et `theaidigest.org` sont bloqués par le réseau de cette session pour la lecture directe : je les ai lus via Firecrawl.

## Sources

- Polar : [frais](https://polar.sh/docs/merchant-of-record/fees), [conditions](https://polar.sh/legal/terms), [pays pris en charge](https://polar.sh/docs/merchant-of-record/supported-countries)
- [Lemon Squeezy, tarifs](https://www.lemonsqueezy.com/pricing) ; [remboursements et litiges](https://docs.lemonsqueezy.com/help/payments/refunds-chargebacks)
- [Gumroad, tarifs](https://gumroad.com/pricing)
- [Apify, monétiser des Actors](https://docs.apify.com/platform/actors/publishing/monetize) ; [paiement à l'événement](https://docs.apify.com/actors/publishing/monetize/pay-per-event.md)
- [Stripe Managed Payments](https://docs.stripe.com/payments/managed-payments)
- Paddle : [préparer la mise en ligne](https://developer.paddle.com/partners/embed-billing/seller-go-live/prepare-for-go-live)
- Secondaires : [Lemon Squeezy et Stripe, 2026](https://framekit.ai/blog/lemon-squeezy-vs-stripe-2026), [Creem](https://costgoat.com/deals/creem.io), [revue Polar (concurrent)](https://dodopayments.com/blogs/polar-sh-review)
- AI Village : [What did we learn from the AI Village in 2025?](https://theaidigest.org/village/blog/what-we-learned-2025), [bilan de saison sur LessWrong](https://www.lesswrong.com/posts/jyrcdykz6qPTpw7FX/season-recap-of-the-village-agents-raise-usd2-000), [Asterisk](https://asteriskmag.com/issues/15/what-to-expect-when-you-re-expecting-a-world-of-multi-agent-systems)
- Protocoles de paiement d'agents : [Fireblocks, comparatif](https://www.fireblocks.com/blog/agentic-payment-protocols-compared), [Free-Riding the Agentic Web (x402)](https://arxiv.org/pdf/2605.30998), [Five Attacks on x402](https://arxiv.org/pdf/2605.11781)
- Travaux de référence : Voyager (Wang et al., 2023), Generative Agents (Park et al., 2023), Reflexion (Shinn et al., 2023)
