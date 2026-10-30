#!/usr/bin/env node
/**
 * GlobalLand — Exécuteur de tâche de la file d'instructions (s'exécute DANS le conteneur).
 * Usage : node scripts/run_task.js queue/inbox/TASK-XXXX.json
 *
 * Sécurité :
 *  - Liste blanche de préfixes d'actions autorisées (node, bash scripts/, bash products/, npm run).
 *  - Motifs interdits bloqués (sudo, curl, ssh, rm -rf, etc.).
 *  - Timeout d'exécution par tâche.
 *  - Toute tâche avec coût estimé > 0 exige "approved_by": "CEO".
 * Le résultat est écrit dans queue/done/ (ou queue/failed/) sous forme de .result.json.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const REPO = path.resolve(__dirname, "..");
const QUEUE_DIR = path.join(REPO, "queue");
const TASK_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes max par tâche shell
const AGENT_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes max par tâche d'agent de code
const MAX_OUTPUT_CHARS = 8000;

// Agents de code autorisés (exécutés via npx, sans shell — aucune injection possible)
const CODE_AGENTS = {
  "claude-code": { pkg: "@anthropic-ai/claude-code", args: (prompt) => ["-p", prompt, "--output-format", "text", "--permission-mode", "acceptEdits"] },
  "codex": { pkg: "@openai/codex", args: (prompt) => ["exec", prompt] },
};

const ALLOWED_PREFIXES = [
  "node ",
  "bash scripts/",
  "bash products/",
  "npm run ",
];
const BLOCKED_PATTERNS = [
  /sudo/, /\bcurl\b/, /\bwget\b/, /\bssh\b/, /\bscp\b/, /git push/, /git commit/,
  /rm\s+-rf/, /chmod\s+777/, /\beval\b/, /base64/, /mkfs/, /dd\s+if=/, /:\(\)\s*\{/,
  /shutdown/, /reboot/, /\/etc\/(passwd|shadow)/, /\.env/, /deploy_key/,
];

function nowIso() { return new Date().toISOString(); }

function writeResult(dir, id, result) {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, id + ".result.json"), JSON.stringify(result, null, 2) + "\n");
}

function main() {
  const rel = process.argv[2];
  if (!rel) {
    console.error("[run_task] usage : node scripts/run_task.js queue/inbox/TASK-XXXX.json");
    process.exit(2);
  }
  const taskPath = path.join(REPO, rel);
  let task;
  try {
    task = JSON.parse(fs.readFileSync(taskPath, "utf8"));
  } catch (e) {
    console.error("[run_task] tâche illisible (" + rel + ") : " + e.message);
    process.exit(2);
  }

  const id = task.id || path.basename(rel, ".json");
  const action = String(task.action || "");
  const taskType = task.type || "SHELL";
  const startedAt = nowIso();
  let status = "DONE";
  let exitCode = 0;
  let output = "";

  // --- Validation ---
  const problems = [];
  if (taskType === "AGENT_CODE") {
    // Tâche d'agent de code (Claude Code / Codex) : coût API réel, gouvernance stricte.
    if (!CODE_AGENTS[task.agent]) {
      problems.push("agent inconnu (autorisés : " + Object.keys(CODE_AGENTS).join(", ") + ")");
    }
    if (!task.prompt || typeof task.prompt !== "string" || task.prompt.trim().length < 10) {
      problems.push("prompt manquant ou trop court (min. 10 caractères)");
    }
    if (!(task.estimated_cost_cad > 0)) {
      problems.push("coût estimé obligatoire et > 0,00 $ CAD (un agent de code consomme de l'API réelle)");
    }
    if (task.approved_by !== "CEO") {
      problems.push("tâche AGENT_CODE : approbation explicite du CEO requise (\"approved_by\": \"CEO\")");
    }
  } else {
    if (!action) problems.push("action manquante");
    if (action && !ALLOWED_PREFIXES.some((p) => action.startsWith(p))) {
      problems.push("action hors liste blanche (autorisé : " + ALLOWED_PREFIXES.join(" | ") + ")");
    }
    if (action && BLOCKED_PATTERNS.some((r) => r.test(action))) {
      problems.push("action contenant un motif interdit (réseau, secrets, ou destruction)");
    }
    if ((task.estimated_cost_cad || 0) > 0 && task.approved_by !== "CEO") {
      problems.push("coût estimé > 0,00 $ CAD sans approbation explicite du CEO");
    }
  }

  if (problems.length > 0) {
    status = "REJECTED";
    output = "Refusée par le garde-fou : " + problems.join(" ; ");
  } else if (taskType === "AGENT_CODE") {
    // --- Exécution d'un agent de code (npx, arguments en tableau : aucune injection shell) ---
    const spec = CODE_AGENTS[task.agent];
    const res = spawnSync("npx", ["-y", spec.pkg, ...spec.args(task.prompt)], {
      cwd: REPO, // les modifications de l'agent atterrissent dans le dépôt
      timeout: AGENT_TIMEOUT_MS,
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
      env: process.env, // les clés API sont passées par le runner via docker exec -e
      stdio: ["ignore", "pipe", "pipe"],
    });
    if (res.error) {
      status = res.error.code === "ETIMEDOUT" ? "TIMEOUT" : "FAILED";
      exitCode = -1;
      output = String(res.error);
    } else {
      exitCode = res.status;
      status = res.status === 0 ? "DONE" : "FAILED";
      output = ((res.stdout || "") + (res.stderr ? "\n[stderr]\n" + res.stderr : "")).trim();
    }
    if (output.length > MAX_OUTPUT_CHARS) {
      output = output.slice(0, MAX_OUTPUT_CHARS) + "\n[... sortie tronquée]";
    }
  } else {
    // --- Exécution dans le répertoire du dépôt ---
    const res = spawnSync("bash", ["-c", "cd " + JSON.stringify(REPO) + " && " + action], {
      timeout: TASK_TIMEOUT_MS,
      encoding: "utf8",
      maxBuffer: 4 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
    if (res.error) {
      status = res.error.code === "ETIMEDOUT" ? "TIMEOUT" : "FAILED";
      exitCode = -1;
      output = String(res.error);
    } else {
      exitCode = res.status;
      status = res.status === 0 ? "DONE" : "FAILED";
      output = ((res.stdout || "") + (res.stderr ? "\n[stderr]\n" + res.stderr : "")).trim();
    }
    if (output.length > MAX_OUTPUT_CHARS) {
      output = output.slice(0, MAX_OUTPUT_CHARS) + "\n[... sortie tronquée]";
    }
  }

  const result = {
    id,
    submitted_by: task.submitted_by || "UNKNOWN",
    action,
    status,
    exit_code: exitCode,
    started_at: startedAt,
    finished_at: nowIso(),
    output,
  };

  const outDir = status === "DONE" ? path.join(QUEUE_DIR, "done") : path.join(QUEUE_DIR, "failed");
  writeResult(outDir, id, result);
  try {
    fs.renameSync(taskPath, path.join(outDir, path.basename(rel)));
  } catch (e) { /* la tâche a déjà été déplacée */ }

  console.log("[run_task] " + id + " -> " + status + " (exit " + exitCode + ")");
}

main();
