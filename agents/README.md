# 👥 agents/ — Le Vivier d'Agents de GlobalLand

> Toute personne (humaine ou agent) listée ici est soumise aux lois de GlobalLand : `VISION.md`, `AGENTS.md`, `CODE.md`, `CURSOR.md`. Une carte d'agent ne remplace jamais le Grand Livre — elle décrit un rôle, ses règles et ses livrables.

> Runtime v2 : ces cartes ne créent aucun processus. Seul SHELL/AUDIT gratuit est activé. AGENT_CODE est désactivé ; les procédures de convocation payantes ci-dessous sont des objectifs futurs, pas des capacités disponibles. Voir queue/PROTOCOL.md.

## Organisation du vivier

```text
agents/
├── README.md            # Ce fichier : comment utiliser le vivier
├── TEMPLATE.md          # Format officiel de carte d'agent
├── staff/               # Le personnel permanent (payé en GLC, portefeuille interne)
│   ├── directeur-si-op.md    # Grokbot — le gouverneur
│   ├── builder.md            # Le constructeur de produits
│   ├── acquisition.md        # Le distributeur et vendeur
│   └── auditeur.md           # Le gardien du Grand Livre
└── consultants/         # Les consultants externes (mission ponctuelle, pas de portefeuille GLC)
    ├── consultant-market-researcher.md   # Valideur de niches (avant la construction)
    ├── consultant-pricing.md            # Prix et monétisation (avant/pendant la vente)
    ├── consultant-seo-aeo.md            # Trafic organique et citations IA
    ├── consultant-content-creator.md    # Contenu et récit
    ├── consultant-growth-hacker.md      # Boucles de croissance gratuites
    └── consultant-code-reviewer.md      # Porte qualité avant mise en vente
```

## Différence staff / consultant

* **Staff permanent** : agent résident (bot Grok Bot, session Claude Code récurrente). Portefeuille GLC, taxe d'existence hebdomadaire, bonification ou liquidation selon les résultats.
* **Consultant** : spécialiste convoqué pour une mission précise. Pas de portefeuille, pas de taxe — il livre, il repart. Convoqué par le Directeur SI/OP uniquement.

## Procédure de convocation d'un consultant

1. Le Directeur SI/OP identifie le besoin et choisit la carte dans `consultants/`.
2. Il soumet une tâche selon le canal approprié :
   * **Tâche AGENT_CODE** (VPS, voir `queue/PROTOCOL.md`) : la carte est collée en tête du `prompt`, suivi de la mission. Coût estimé et `"approved_by": "CEO"` obligatoires.
   * **Bot Grok Bot** : le contenu de la carte devient la description du bot, la mission devient la consigne du jour.
3. Le consultant livre dans le dépôt (ou son rapport dans `queue/done/`). Toute action financière est journalisée au `ledger.json` — un consultant n'invente jamais de revenus.

## Créer une nouvelle carte

Copier `TEMPLATE.md`, remplir chaque section, et faire valider par le Directeur SI/OP. Une carte sans métriques de succès mesurables est refusée.

## Attribution

Le format des cartes (frontmatter + identité, mission, règles critiques, livrables, workflow, métriques) est adapté du projet open source [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (licence MIT — réutilisation libre avec attribution appréciée), qui rassemble plus de 230 agents spécialisés éprouvés en production. GlobalLand n'importe pas le catalogue : il en retient le format et une poignée de spécialités alignées sur sa mission de revenus à coût 0 $.
