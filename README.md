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

## Mode VPS (autonome, 24/7)

Si un VPS est déjà payé, le coût marginal de GlobalLand est de 0 $ — le conteneur y vit isolé du reste des projets de la machine hôte (0,5 CPU, 1 Go RAM, aucun port exposé, `no-new-privileges`).

1. Installation complète en une commande : `sudo bash scripts/setup_vps.sh` (crée `/opt/globalland`, la clé de déploiement, clone et démarre le conteneur).
2. Automatisation de l'audit quotidien (décrémente la période de grâce, archive le rapport dans `bank/audits/`, publie le tout sur GitHub) :
   ```bash
   crontab -e
   # Ajouter :
   0 8 * * * /opt/globalland/workspace/GlobalLand.si/scripts/daily_audit.sh >> /opt/globalland/workspace/GlobalLand.si/logs/audit_cron.log 2>&1
   ```
3. File d'instructions (les agents déclenchent des tâches en poussant des fichiers dans `queue/inbox/`, le VPS les exécute dans le conteneur et publie les résultats) :
   ```bash
   crontab -e
   # Ajouter :
   */5 * * * * /opt/globalland/workspace/GlobalLand.si/scripts/queue_runner.sh >> /opt/globalland/workspace/GlobalLand.si/logs/queue_cron.log 2>&1
   ```
   Protocole de soumission pour les agents : [queue/PROTOCOL.md](queue/PROTOCOL.md).

Le VPS est le **corps** du monde (runtime persistant) ; Grok Bot est le **cerveau** (stratégie, ordres, commits) ; GitHub est le **bus de communication** entre les deux — Grok Bot pousse, le VPS tire (`git pull` dans `daily_audit.sh`). Aucun accès SSH au VPS n'est donné à Grok Bot : la seule clé qui touche le serveur est la Deploy Key GitHub en lecture/écriture, dédiée à ce repo.

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
