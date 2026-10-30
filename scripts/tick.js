#!/usr/bin/env node
/**
 * GlobalLand — Battement de cœur quotidien : décrémente la période de grâce du ledger.
 * Exécuté DANS le conteneur (via daily_audit.sh), jamais sur l'hôte — réduit la surface
 * de code exécutée hors conteneur. Node.js pur, zéro dépendance.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const LEDGER = path.join(__dirname, "..", "ledger.json");

let ledger;
try {
  ledger = JSON.parse(fs.readFileSync(LEDGER, "utf8"));
} catch (e) {
  console.error("[tick] ledger.json illisible : " + e.message);
  process.exit(1);
}

if (ledger.grace_period_days_remaining > 0) {
  ledger.grace_period_days_remaining -= 1;
  ledger.transactions.push({
    id: "TX-" + String(ledger.transactions.length + 1).padStart(4, "0"),
    type: "DAY_TICK",
    amount: 0,
    approved_by: "AUTO_AUDITOR",
    note: "Décrément période de grâce (jour écoulé)",
  });
  fs.writeFileSync(LEDGER, JSON.stringify(ledger, null, 2) + "\n");
  console.log("[tick] période de grâce décrémentée :", ledger.grace_period_days_remaining, "jour(s) restants");
} else {
  console.log("[tick] période de grâce écoulée");
}
