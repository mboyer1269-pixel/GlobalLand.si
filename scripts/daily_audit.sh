#!/usr/bin/env bash
# GlobalLand — Audit quotidien automatisé (à exécuter par cron sur le VPS)
# Prérequis : infrastructure installée via scripts/setup_vps.sh
# Crontab (audit chaque matin à 8h, heure de l'hôte) :
#   0 8 * * * /opt/globalland/workspace/GlobalLand.si/scripts/daily_audit.sh >> /opt/globalland/workspace/GlobalLand.si/logs/audit_cron.log 2>&1
set -uo pipefail

GL_ROOT="/opt/globalland"
REPO="$GL_ROOT/workspace/GlobalLand.si"
SSH_KEY="$GL_ROOT/.ssh/globalland_deploy_key"
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new"
DATE=$(date +%F)
REPORT="$REPO/bank/audits/audit-$DATE.md"

echo "[daily_audit] $(date -Iseconds) — début"

# 1. Synchroniser le dépôt (les ordres du Directeur SI/OP arrivent par GitHub)
cd "$REPO" || exit 1
git pull --ff-only origin main

# 2. Décrémenter la période de grâce (une fois par jour, par l'Agent Auditeur)
node -e '
const fs = require("fs");
const p = "ledger.json";
const l = JSON.parse(fs.readFileSync(p, "utf8"));
if (l.grace_period_days_remaining > 0) {
  l.grace_period_days_remaining -= 1;
  l.transactions.push({ id: "TX-" + String(l.transactions.length + 1).padStart(4, "0"), type: "DAY_TICK", amount: 0, approved_by: "AUTO_AUDITOR", note: "Décrément période de grâce (jour écoulé)" });
  fs.writeFileSync(p, JSON.stringify(l, null, 2) + "\n");
  console.log("[daily_audit] période de grâce décrémentée :", l.grace_period_days_remaining, "jour(s) restants");
} else {
  console.log("[daily_audit] période de grâce écoulée");
}'

# 3. Exécuter l'audit dans le conteneur et archiver le rapport
mkdir -p "$REPO/bank/audits"
{ echo "# Rapport d'audit automatique — $DATE"; echo ""; docker exec globalland-core node scripts/audit.js; } > "$REPORT" 2>&1 || \
  { echo "# Rapport d'audit automatique — $DATE"; echo ""; node scripts/audit.js; } > "$REPORT"

# 4. Journaliser et publier (le ledger fait foi)
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | AUTO | DAILY_AUDIT | 0.00 CAD | AUTO_AUDITOR | Audit quotidien archivé ($DATE)" >> "$REPO/logs/transactions.log"

git add ledger.json logs/transactions.log bank/audits/
git -c user.name="globalland-auditor" -c user.email="auditor@globalland.local" \
  commit -m "ledger(audit): daily audit $DATE" --quiet && \
  git push origin main || echo "[daily_audit] rien à publier ou push refusé (clé en lecture seule ?)"

echo "[daily_audit] $(date -Iseconds) — terminé"
