# Plan exécutable — déblocage Codex et Cursor (phases 0 à 3 de la PR #8)

Source : `docs/PLAN-DEBLOCAGE-OUTILS.md` (PR #8). Branche de travail : `claude/globalland-autonomous-world-nokkck` (PR #5), décision du boss du 2026-11-01.
Méthode : TDD (test rouge → vert → refactor), un commit par étape, lots de 3 avec point de contrôle.
Hors périmètre : VPS, fusion, dépense, secrets, `--force` Cursor.

Commandes de test complètes (doivent rester vertes après chaque étape) :

```bash
node tests/runtime.test.js && node tests/executor.test.js && python3 -m unittest discover -s tests -p 'test_*.py' && bash -n scripts/*.sh
```

Base mesurée avant tout changement : `Ran 287 tests … OK (skipped=1)` sur `33ccd6f`.

## Faits établis au lot 1 (preuves : `docs/2026-11-01-lot1.md`, PR #8)

- Codex `0.166.0` ignore `-c tools.view_image=false` (« `tools.view_image` is ignored ») ; la clé valide est `features.view_image` (stable, `true` par défaut). `features.image_generation` est aussi `stable true`.
- `codex doctor --json -c …` expose, sans inférence ni connexion, `checks.config.load.details["startup warning"]` (clés ignorées) et `["enabled feature flags"]`. C'est la base du test de contrat.
- Sans réseau, `codex exec` ne sort pas avant 120 s (reconnexions puis « waiting for network »).
- Un fichier monté `--bind -o ro` refuse le remplacement atomique (`EBUSY`) et l'écriture (`EROFS`).

## Lot A — Codex

### A1. Test unitaire : aucune clé `-c` ignorée par Codex dans `brain_command`
- Fichier : `tests/test_cli_contract.py` (nouveau).
- Test rouge : pour les deux variantes Codex (avec et sans courtier), l'argv ne contient pas `tools.view_image=false` et contient `features.view_image=false` et `features.image_generation=false` ; `exec` vient immédiatement après `codex`.
- Commande : `python3 -m unittest tests.test_cli_contract -v`
- Attendu avant correctif : ÉCHEC sur `tools.view_image`. Après : OK.

### A2. Correctif `scripts/controller.py`
- Remplacer `-c tools.view_image=false` par `-c features.view_image=false` et ajouter `-c features.image_generation=false` dans les deux argv Codex.
- Attendu : A1 vert, suite complète verte.

### A3. Test de contrat optionnel contre la vraie CLI (3.1)
- Même fichier, classe activée par `GLOBALLAND_CLI_CONTRACT=1` (sinon `skip`, jamais vert par défaut). Binaire : `GLOBALLAND_CODEX_BIN` (défaut `codex`).
- Vérifie : chaque drapeau de l'argv présent dans `codex exec --help` ; l'ordre de `main` (`codex --ignore-user-config … exec`) sort en code 2 ; `codex doctor --json` avec tous les `-c` de l'argv (sauf `mcp_servers.globalland.*`, qui exige le pont) n'a **aucun** « startup warning » et n'active ni `view_image`, ni `image_generation`, ni `shell_tool`, ni `multi_agent`, ni `hooks`.
- Commande : `GLOBALLAND_CLI_CONTRACT=1 GLOBALLAND_CODEX_BIN=/tmp/cx/node_modules/.bin/codex python3 -m unittest tests.test_cli_contract -v`
- Attendu : rouge sur `33ccd6f` (clé ignorée), vert après A2.

## Lot B — Cursor (dépend de l'ouverture réseau `cursor.com`, `downloads.cursor.com`, `api2.cursor.sh`)

### B1. Vérifier les drapeaux réels de la CLI Cursor
- `agent --version` ; `agent --help` ; `agent status --help` ; preuve que `status --format json` existe (sinon pas de B3).

### B2. Dossier de config jetable par tour (3.2, option retenue)
- Test rouge (`tests/test_cursor.py`) : l'argv Cursor ne monte plus `cursor-cli-config.json` ni `cursor-sandbox.json` en `readonly` ; il monte un dossier `dst=/home/node/.cursor` en écriture ; le dossier est créé par l'hôte avec les deux fichiers copiés depuis `control/`, et supprimé après le tour, même en cas d'exception.
- Reproduction 2.5 avec la vraie CLI : le fichier source dans `control/` garde sa taille et son empreinte après le tour.

### B3. `status --format json` (3.3)
- Tests avec fixtures `{"isAuthenticated": false}` / `true` et sortie non JSON → refus. Le code de sortie seul ne suffit jamais.

## Lot C — Délai, bascule, documentation

### C1. Délai configurable hors courtier (3.4)
- `controller.timeout_seconds` (entier, défaut 120, bornes 30–900), utilisé par `run_turn` hors courtier. Le courtier garde `broker.turn_timeout_seconds`. Test avec une fausse commande lente (`sleep`) et un délai court. Aucune hausse CPU/mémoire.

### C2. Bascule `479b990` (3.5)
- `python3 -m unittest tests.test_provider_failover -v` vert sur #3 (fait au lot 1 : 12 tests OK) et sur #5.

### C3. `CLAUDE.md` (3.6)
- « Le dépôt est public » → privé, avec la conséquence Actions facturées. Preuve : `gh api repos/…` → `"private": true`.

## Fin
- Cocher les cases dans `docs/PLAN-DEBLOCAGE-OUTILS.md` (branche de #8) avec la preuve sous chaque case.
- Revue de code avant de proposer quoi que ce soit ; options de fusion présentées, jamais exécutées.
