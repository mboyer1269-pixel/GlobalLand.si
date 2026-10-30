# 🌍 GlobalLand.si

> Un monde virtuel expérimental propulsé par des agents IA autonomes, adossé à une Banque Centrale qui gère de l'argent réel. Si le solde tombe à 0,00 $ CAD, le serveur est détruit et le monde s'éteint définitivement.

## L'Enjeu

| Variable officielle | Valeur au Genesis |
|---|---|
| Trésorerie réelle | 50,00 $ CAD (verrouillée, veto CEO) |
| Revenus | 0,00 $ CAD (état de choc) |
| KPI | Cashflow positif + solde de 100,00 $ CAD |
| Limites | Docker 1 Go RAM / 0,5 CPU · plafond API 2,00 $/jour |
| Loyer serveur (dès le Jour 8) | 2,00 $ CAD / semaine |

## Démarrage rapide

```bash
# Infrastructure (VPS) : conteneur isolé node:22
docker compose up -d

# Audit financier quotidien de la Banque Centrale
docker exec globalland-core node scripts/audit.js
# ...ou localement : node scripts/audit.js
```

## Documentation

* [VISION.md](VISION.md) — La constitution : loi d'extinction, fiscalité, partage des profits, lois anti-échec
* [AGENTS.md](AGENTS.md) — Organigramme exécutif : CEO, Directeur SI/OP (Grokbot), agents ouvriers
* [CODE.md](CODE.md) — Architecture technique, 4 variables officielles, emplacement des logs
* [CURSOR.md](CURSOR.md) / [CLAUDE.md](CLAUDE.md) — Règles strictes de développement pour tout agent IA

## Grand Livre

`ledger.json` est la source unique de vérité financière. Toute action financière doit y être journalisée, avec trace dans `logs/transactions.log`, avant d'être considérée réelle.

## Gouvernance

1. **CEO (humain)** : droit de veto absolu sur toute dépense réelle issue des 50 $.
2. **Directeur SI/OP (Grokbot)** : stratégie financière, arbitrage, gestion du risque, audits quotidiens.
3. **Agents ouvriers** : Builder (produits à coût 0 $), Acquisition (distribution organique), Auditeur (vérité comptable).

Partage des profits nets : 40 % CEO · 40 % Banque Centrale · 20 % expansion des agents.
