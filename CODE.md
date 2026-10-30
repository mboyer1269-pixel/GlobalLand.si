# 💻 CODE.md — Architecture Technique et État de la Banque Centrale

> **NOTE POUR LE DIRECTEUR SI/OP (GROKBOT) :** ce fichier contient les **4 variables officielles** et l'emplacement des logs. Ne jamais inventer de chiffres en dehors de ce qui est écrit ici.

## 1. Les 4 Variables Officielles (État Initial Post-Choc)

1. **Trésorerie :** 50,00 $ CAD (réserve réelle verrouillée, détenue par le CEO ; disponible pour les agents sans approbation CEO : 0,00 $ CAD).
2. **Revenus :** 0,00 $ CAD (le monde sort de l'état de choc, tout est à bâtir).
3. **KPI :** cashflow positif et atteindre 100,00 $ CAD de solde Banque Centrale. Objectif intermédiaire « Premier Sang » : premiers 10,00 $ CAD de revenus nets à coût d'exécution 0,00 $.
4. **Limites :** conteneur Docker `globalland-core` plafonné à 1 Go RAM / 0,5 CPU ; plafond API de 2,00 $ CAD / jour ; aucune dépense réelle sans signature du CEO.

> **⚠️ NOTE POUR LE DIRECTEUR SI/OP (GROKBOT) — Taxe narrative vs dépenses réelles :**
> Conformément à la décision CEO du 2026-10-30 (voir `VISION.md`, section 3), la taxe serveur de 2,00 $ CAD / semaine est une **pression narrative** : elle décompte dans le runway de `ledger.json` mais **ne correspond à aucune sortie d'argent réelle** (le VPS hôte est un coût coulé déjà payé).
> * **Dépense narrative (aucun impact réel) :** la taxe hebdomadaire de 2,00 $ / semaine (type `SERVER_TAX_NARRATIVE`) — elle réduit le runway calculé, jamais le capital réel disponible.
> * **Dépense réelle (impact sur les 50,00 $) :** tout achat API, abonnement, domaine, service payant — exige la signature du CEO, une transaction de type `REAL_EXPENSE` au ledger, et débite réellement `current_balance` et `available_for_agents_without_ceo_approval` selon le plafond.
> **Règle de comptabilisation :** toute nouvelle transaction doit porter un type explicite (`NARRATIVE_*` ou `REAL_*`). Un agent ne doit jamais confondre les deux registres ni « rembourser » la taxe narrative avec de l'argent réel.

## 2. Emplacement des Logs et du Grand Livre

| Fichier | Rôle | Responsable |
|---|---|---|
| `ledger.json` | Grand livre officiel de la Banque Centrale (source unique de vérité) | Directeur SI/OP |
| `logs/transactions.log` | Journal horodaté de chaque action financière (append-only) | Agent Auditeur |
| `scripts/audit.js` | Audit quotidien : runway, écart KPI, rapport froid | Directeur SI/OP |
| `bank/audits/` | Rapports d'audit quotidiens et stress-tests hebdomadaires | Directeur SI/OP |
| `products/` | Actifs monétisables construits par les agents | Agent Builder |

**Règle :** toute action financière (revenu, dépense, taxe serveur, transfert GLC) doit être inscrite simultanément dans `ledger.json` (nouvelle transaction + mise à jour de `current_balance`) et dans `logs/transactions.log` avant d'être considérée réelle.

## 3. Structure du Dépôt

```text
GlobalLand.si/
├── VISION.md          # Constitution : lore, loi d'extinction, partage des profits
├── AGENTS.md          # Organigramme exécutif et fiscalité interne
├── CODE.md            # Ce fichier : architecture, 4 variables, logs
├── CURSOR.md          # Règles de développement pour agents IA
├── CLAUDE.md          # Copie des règles (compatibilité Claude Code)
├── ledger.json        # Grand livre (CAD)
├── logs/
│   └── transactions.log
├── scripts/
│   ├── audit.js       # Audit financier (Node.js pur, zéro dépendance)
│   └── setup_vps.sh   # Reproduction de l'infrastructure sur un VPS
├── bank/
│   └── audits/        # Rapports quotidiens
└── products/          # Actifs monétisables des agents
```

## 4. Architecture d'Exécution

* **Runtime :** Node.js 22 (image Docker `node:22-bookworm`), conteneur `globalland-core` plafonné à 1 Go RAM / 0,5 CPU, `no-new-privileges`, redémarrage automatique.
* **Code :** zéro dépendance npm par défaut. Toute dépendance externe doit être justifiée par un gain de revenus direct et approuvée par le Directeur SI/OP.
* **Hébergement gratuit autorisé (coût 0 $) :** GitHub Pages, GitHub Actions (CI/CD), Cloudflare Pages/Workers (offre gratuite), Vercel Hobby. Tout service payant exige l'approbation du CEO.
* **Passerelle de paiement :** toute **sortie** d'argent réel exige la signature du CEO. Les **entrées** (liens de paiement, ventes d'actifs, sponsors) sont configurées avec le CEO dès que le produit est prêt.
* **Secrets :** aucune clé d'API ou credential dans le repo (le dépôt est public). Les secrets vivent dans les variables d'environnement du conteneur ou dans GitHub Secrets.

## 5. Contraintes d'Infrastructure (VPS hôte)

L'infrastructure vit dans `/opt/globalland` sur le VPS, isolée du reste des projets de la machine hôte :

```text
/opt/globalland/
├── docker-compose.yml      # Conteneur globalland-core (0,5 CPU, 1 Go RAM)
├── .ssh/
│   ├── globalland_deploy_key       # Clé privée de déploiement (chmod 600)
│   └── globalland_deploy_key.pub   # À enregistrer dans les Deploy Keys GitHub
└── workspace/GlobalLand.si/         # Dépôt git monté dans le conteneur
```

* Le conteneur n'expose **aucun port** vers l'hôte.
* La clé SSH de déploiement est dédiée à ce seul repo (Deploy Key GitHub, accès lecture/écriture).
* L'audit quotidien s'exécute avec : `docker exec globalland-core node scripts/audit.js`.
