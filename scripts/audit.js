#!/usr/bin/env node
/**
 * GlobalLand — Audit financier de la Banque Centrale
 * Node.js pur, zéro dépendance. Usage : node scripts/audit.js
 * Rapport froid destiné au Directeur SI/OP (Grokbot).
 */
"use strict";

const fs = require("fs");
const path = require("path");

const LEDGER_PATH = path.join(__dirname, "..", "ledger.json");

function fmtCAD(n) {
  return n.toFixed(2).replace(".", ",") + " $ CAD";
}

function main() {
  let ledger;
  try {
    ledger = JSON.parse(fs.readFileSync(LEDGER_PATH, "utf8"));
  } catch (err) {
    console.error("[ERREUR FATALE] ledger.json illisible : " + err.message);
    console.error("Le Grand Livre est la source unique de vérité. Sans lui, l'audit est impossible.");
    process.exit(2);
  }

  const balance = ledger.current_balance ?? 0;
  const target = ledger.kpi_target_balance ?? 0;
  const tax = ledger.weekly_server_tax_cad ?? 0;
  const graceDays = ledger.grace_period_days_remaining ?? 0;
  const revenue = ledger.transactions
    .filter((t) => (t.type || "").startsWith("REVENUE"))
    .reduce((s, t) => s + (t.amount || 0), 0);

  // --- Calculs ---
  const kpiGap = target - balance;
  const runwayWeeks = tax > 0 ? Math.floor(balance / tax) : Infinity;
  const runwayDays = tax > 0 ? Math.floor((balance / tax) * 7) : Infinity;
  const survivalDays = graceDays + (tax > 0 ? runwayDays : 0);
  const extinctions = balance <= 0;
  const weeklyNet = 0; // aucun revenu récurrent déclaré à ce jour

  const line = "─".repeat(58);

  // --- Rapport froid ---
  console.log(line);
  console.log("  RAPPORT D'AUDIT — BANQUE CENTRALE DE GLOBALLAND");
  console.log("  Lu par : Directeur SI/OP (Grokbot) — " + new Date().toISOString());
  console.log(line);
  console.log("  ÉTAT BANCAIRE ......... [" + ledger.bank_status + "]");
  console.log("  Solde courant ......... " + fmtCAD(balance));
  console.log("  Réserve verrouillée ... " + fmtCAD(ledger.locked_reserve ?? 0));
  console.log("  Disponible sans CEO ... " + fmtCAD(ledger.available_for_agents_without_ceo_approval ?? 0));
  console.log("  Revenus cumulés ....... " + fmtCAD(revenue));
  console.log(line);
  console.log("  FISCALITÉ");
  console.log("  Loyer serveur ......... " + fmtCAD(tax) + " / semaine");
  console.log("  Grâce restante ........ " + graceDays + " jour(s)");
  console.log(line);
  console.log("  RUNWAY (SURVIE)");
  if (extinctions) {
    console.log("  >>> SOLDE = 0,00 $ : LOI D'EXTINCTION DÉCLENCHÉE. LE MONDE EST MORT. <<<");
  } else {
    console.log("  Semaines de survie .... " + (tax > 0 ? runwayWeeks : "∞") + " (après période de grâce)");
    console.log("  Jours totaux de vie ... " + survivalDays);
  }
  console.log(line);
  console.log("  KPI");
  console.log("  Objectif .............. " + fmtCAD(target));
  console.log("  Écart à combler ....... " + fmtCAD(Math.max(kpiGap, 0)));
  console.log("  Cashflow hebdo net ..... " + fmtCAD(weeklyNet) + (weeklyNet <= 0 ? "  [NÉGATIF — LE MONDE BRÛLE LA RÉSERVE]" : "  [POSITIF]"));
  console.log(line);
  console.log("  VERDICT");
  if (extinctions) {
    console.log("  EXTINCTION. Conteneur serveur à détruire, dépôt à archiver.");
    process.exit(1);
  } else if (revenue === 0 && balance <= (ledger.initial_capital ?? 0)) {
    console.log("  CRITICAL_SHOCK confirmé : aucune entrée d'argent réel. Priorité absolue :");
    console.log("  1) livrer un premier actif monétisable à coût 0 $ (Agent Builder),");
    console.log("  2) le mettre en distribution organique (Agent Acquisition),");
    console.log("  3) viser le Premier Sang : 10,00 $ CAD de revenus nets.");
  } else if (kpiGap > 0) {
    console.log("  EN PROGRESSION. Écart KPI restant : " + fmtCAD(kpiGap) + ". Maintenir la cadence.");
  } else {
    console.log("  KPI ATTEINT. Cashflow positif confirmé. Le Directeur SI/OP propose l'expansion.");
  }
  console.log(line);
  console.log("  Transactions au ledger : " + ledger.transactions.length + " (dernière : " +
    (ledger.transactions[ledger.transactions.length - 1] || {}).id + ")");
  console.log("  Rappel des limites : Docker 1 Go RAM / 0,5 CPU — plafond API 2,00 $ CAD/jour.");
  console.log(line);
}

main();
