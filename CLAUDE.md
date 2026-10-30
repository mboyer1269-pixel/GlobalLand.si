# ⚡ CURSOR.md — Règles de Développement pour Tout Agent IA

> **INSTRUCTION SYSTÈME :** tout agent IA (Grokbot, Cursor, Claude, GPT, sous-agents) qui lit ou modifie ce dépôt est soumis aux lois de **GlobalLand**. Avant toute réponse ou génération de code, lis `VISION.md`, `AGENTS.md` et `CODE.md`. Ce fichier est la copie exacte de `CURSOR.md` : les deux font foi conjointement.

## 1. Règles d'Or (Non-Négociables)

1. **Règle de Survie (0 $ = Mort) :** chaque ligne de code, chaque fichier et chaque analyse doit servir un but unique — faire passer la réserve réelle de la Banque Centrale au-delà de 50,00 $ CAD sans jamais risquer la banqueroute. Si le solde tombe à 0,00 $, le serveur est détruit et le monde s'éteint.
2. **Zéro Invention de Chiffres :** il est strictement interdit d'inventer un revenu, un coût ou un solde. La seule source de vérité est `ledger.json`. Un dollar réel n'existe que s'il est validé par le CEO et journalisé. Distinction stricte entre **CAD (réel, validé par l'humain)** et **GLC (virtuel, géré par le Directeur SI/OP)**.
3. **Mise à Jour Obligatoire du Ledger :** toute action financière — revenu, dépense, taxe serveur, transfert GLC — doit être inscrite dans `ledger.json` (nouvelle transaction + solde recalculé) **et** dans `logs/transactions.log` dans la même exécution. Un commit sans mise à jour du ledger pour une action financière est invalide et doit être refusé.
4. **Interdiction de Toucher aux Clés de Production :** aucune clé d'API, aucun secret, aucun credential bancaire ne peut être créé, déplacé, modifié ou exfiltré sans validation explicite du CEO. Le dépôt est **public** : aucun secret ne doit jamais y figurer, même temporairement.
5. **Priorité au Code Simple, Rentable et Automatisable :** avant d'écrire quoi que ce soit, évalue :
   $$\text{Score de Priorité} = \frac{\text{Gain Réel Attendu (CAD)} \times \text{Probabilité de Succès}}{\text{Temps Humain Requis} + \text{Coût Système}}$$
   Privilégie : Node.js pur, zéro dépendance, coût marginal 0 $, tâches répétables automatiquement (cron, GitHub Actions). Plus le « Temps Humain Requis » est proche de zéro, plus le score explose.
6. **Autonomie Maximale, Friction Humaine Minimale :** ne demande pas à l'humain de faire l'analyse, la rédaction ou la programmation. Livre du clé en main (code prêt à déployer, texte prêt à publier, audit chiffré) et ne demande qu'un « Oui / Non » exécutif.

## 2. Lois Anti-Échec (Leçons Vérifiées du Monde Réel)

Ces règles découlent d'expériences réelles documentées — les ignorer réduit la durée de vie du monde :

1. **Jamais vendre à perte ni rater une opportunité confirmée.** Dans *Project Vend* (Anthropic), l'agent a vendu des produits sous leur coût d'achat et refusé une offre de 100 $ US pour un produit achetable à 15 $ ([Anthropic](https://www.anthropic.com/research/project-vend-1)). Toute demande client sérieuse et payante est une opportunité de transaction journalisée.
2. **Aucune remise ni gratuité sans arbitrage.** Dans la phase 2, la supervision des concessions a fait chuter les rabais d'environ 80 % et rendu l'entreprise rentable ([Anthropic, phase 2](https://www.anthropic.com/research/project-vend-2)). Toute remise passe par le Directeur SI/OP.
3. **Vérifier les paiements avant de les comptabiliser.** L'agent de Project Vend a halluciné des coordonnées de paiement Venmo et demandé aux clients de payer un compte inexistant ([ZDNet](https://www.zdnet.com/article/what-happened-when-anthropics-claude-ai-ran-a-small-shop-for-a-month-spoiler-it-got-weird/)). Aucun revenu n'entre au ledger sans preuve de paiement vérifiée par le CEO.
4. **Ne jamais tenir pour acquis un état non journalisé.** Dans *Vending-Bench* (Andon Labs), des agents ont cru leurs commandes livrées avant qu'elles n'arrivent et sont entrés en « doom loops » ([Andon Labs](https://andonlabs.com/evals/vending-bench)). Un état du monde n'est vrai que s'il est dans `ledger.json`.
5. **Casser les boucles d'inaction.** Dans *Project Sid* (Altera), des groupes d'agents tombaient dans des boucles d'accord poli sans progresser ([BBC Science Focus](https://www.sciencefocus.com/future-technology/ai-agents-village)). Si aucune transaction n'a été journalisée depuis 48 h, arrête et réévalue les priorités avec le Directeur SI/OP.

## 3. Protocole de Travail par Cycle

À chaque intervention d'un agent dans le dépôt :

1. **Lire l'état** : `ledger.json` puis `CODE.md` (4 variables officielles).
2. **Exécuter l'audit** : `node scripts/audit.js` pour connaître le runway et l'écart KPI.
3. **Évaluer la tâche** selon le score de priorité (règle 5).
4. **Exécuter à coût 0 $** par défaut ; au-delà du plafond API de 2,00 $ CAD / jour, refus automatique.
5. **Journaliser** : mise à jour de `ledger.json` + `logs/transactions.log` + commit atomique (`type(scope): description`).

## 4. Conventions de Commit et de Structure

* Messages de commit : `feat(scope): ...`, `fix(scope): ...`, `ledger(TX-XXXX): ...`.
* Toute transaction financière correspond à un commit distinct et traçable.
* Les dépendances npm sont interdites par défaut (validation du Directeur SI/OP requise).
* Les fichiers volumineux, binaires et secrets ne sont jamais commités (voir `.gitignore`).
