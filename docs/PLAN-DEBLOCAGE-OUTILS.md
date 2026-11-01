# Plan de déblocage — Cursor et Codex (diagnostic local)

> Pour : le boss. Rédigé le 2026-11-01 à partir du dépôt, des PR [#3](https://github.com/mboyer1269-pixel/GlobalLand.si/pull/3) et [#5](https://github.com/mboyer1269-pixel/GlobalLand.si/pull/5), de l'historique Git et des CLI officielles installées dans un dossier temporaire (Codex `0.166.0`, Cursor Agent `2026.10.22-27dcf5f`).
>
> **Hors périmètre : le VPS au complet.** Tu t'en occupes toi-même ; la dernière section te remet seulement ce que le local a prouvé.
> **Interdits :** fusionner une PR, toucher ou coller un secret (`auth.json`, `credentials/`, clé API, jeton), dépenser une cenne (pas de crédits, pas de clé API facturée, pas de hausse de limite).

Chaque étape donne quatre choses : la **commande ou le check exact**, le **résultat attendu**, la **preuve** à garder (sortie à coller, fichier, test vert) et la **marche à suivre si ça échoue**. Les étapes rapides passent en premier.

---

## Ce que le dépôt prouve déjà

| Fait vérifié | Preuve |
| --- | --- |
| Cinq tours THINK publiés aux 30 minutes, de 22:00 à 00:00 UTC le 31 oct., puis `CONTROLLER_BLOCKED` à 00:30 UTC le 1er nov. Aucun commit depuis. | `git log --format='%cI %s' origin/main \| grep -E 'THINK\|READINESS'` |
| Le VPS ne roule **pas** `main`. Le texte publié (`inspect state/private/controller-failure.json`) n'existe dans aucun fichier de `main`. Il apparaît au commit `7e4859d` de la PR #3. Le champ `reason_code`, ajouté à `479b990`, est absent du statut publié. Le contrôle installé est donc entre `7e4859d` et `0a0fd24`, ce qui concorde avec le `4c5de50` annoncé dans #3. | `git log --oneline --all -S "controller-failure.json" -- scripts/supervisor.py` et `git log --oneline --all -S "reason_code=details" -- scripts/supervisor.py` |
| Dans ce contrôle installé, le fournisseur est `providers[nombre de THINK-*.json % len(providers)]`. Un échec ne crée aucun fichier THINK : le **même** fournisseur est rechoisi à chaque cron, sans bascule. La bascule arrive seulement avec `479b990`, qui n'est pas déployé. | `git show 4c5de50:scripts/controller.py \| grep -n "providers\["` (ligne 220) |
| La CI rouge de #3 en 4 s n'est **pas un bug de code**. GitHub n'a pas démarré le job : *« The job was not started because recent account payments have failed or your spending limit needs to be increased »*. Le dépôt est **privé**, donc Actions consomme des minutes facturées. Toutes les exécutions échouent jusqu'au 31 oct. à 23:xx UTC et réussissent depuis le 1er nov. à 00:00 UTC. Le dernier run de #3 date du 31 oct. à 22:32 : il est périmé. | `gh api repos/mboyer1269-pixel/GlobalLand.si/check-runs/124677296547/annotations` |
| Les tests passent en local : `main` 60 Python OK (1 ignoré) plus les tests Node ; PR #3 159 Python OK (1 ignoré), Node OK et `bash -n` OK. | Section Phase 0, étape 0.3 |
| Sur `main`, `brain_command` met `--ignore-user-config --ignore-rules` **avant** `exec`. Codex 0.166.0 refuse cette forme (`error: unexpected argument '--ignore-user-config' found`, exit 2). La PR #3 (`f9e68bf`) a déplacé ces drapeaux après `exec`. Un déploiement de `main` serait cassé. | Phase 1, étape 1.3 |
| La CLI Cursor **réécrit** `~/.cursor/cli-config.json`, même en mode 0444 : remplacement atomique de 73 à 855 octets, avec des champs ajoutés. Sur le VPS, ce fichier est monté `readonly` dans le conteneur (PR #3). Un remplacement par-dessus un bind-mount en lecture seule échoue. C'est un suspect sérieux pour les échecs ou délais de Cursor. | Phase 2, étape 2.5 |
| Le push d'une branche `cursor/*` par un agent Cloud Cursor **fonctionne** sur ce dépôt : la branche de cette PR, ainsi que celles de #4, #6 et #7. `main` n'a pas de protection de branche. | `gh api repos/mboyer1269-pixel/GlobalLand.si/branches/main --jq .protected` donne `false` |

### Top 3 des causes racines soupçonnées

1. **Fournisseur bloqué sans bascule, probablement un quota d'abonnement.** Le contrôle installé rechoisit toujours le même fournisseur. Selon la parité des 7 fichiers THINK publiés (index 7 % 2 = 1), il s'agirait de **Claude**, pas de Codex : c'est à confirmer, car c'est une déduction. Un quota de fenêtre de 5 h ou hebdomadaire après 5 tours en 2 h colle au profil « réussit, réussit, puis bloque ». OpenAI documente des limites par fenêtre de cinq heures et des limites hebdomadaires ([Codex pricing](https://developers.openai.com/codex/pricing)).
2. **CLI et drapeaux désalignés entre branches et versions.** L'ordre des drapeaux Codex sur `main` est rejeté par la CLI actuelle. Cursor réécrit un fichier que le conteneur monte en lecture seule. Le délai fixe de 120 s de `bounded_run` laisse peu de marge : 0,5 CPU, et Codex fait jusqu'à 5 + 5 reconnexions avant d'échouer. PR #3 mentionne déjà des « délais dépassés » pour Cursor.
3. **Faux rouge de CI et code non fusionné.** La CI rouge (facturation Actions) donne l'impression que #3 est cassée, alors que ses 159 tests passent. Résultat : les correctifs de bascule (`479b990`) restent en attente, et la pile #3 → #5 ne bouge pas.

---

## Les 30 premières minutes

- [ ] **0–2 min : relancer la CI de #3.** Dans la PR #3 → onglet *Checks* → *Re-run all jobs*, ou `gh run rerun 41248645281` depuis ton terminal. **Attendu :** `tests` vert. **Preuve :** lien du run vert. **Si rouge en moins de 10 s :** GitHub → *Settings → Billing and plans* → paiement ou limite Actions. Ne hausse pas la limite sans décision d'argent.
- [ ] **2–6 min : installer les deux CLI dans `/tmp`**, sans toucher à ta config. Voir l'étape 1.1 et l'étape 2.1. **Preuve :** `codex-cli X.Y.Z` et `2026.xx.xx-…`.
- [ ] **6–10 min : contrat des drapeaux Codex** (étape 1.3). **Preuve :** six lignes `OK` et `ordre main: exit=2`.
- [ ] **10–15 min : état de connexion Codex et Cursor sur TA machine** (étapes 1.4 et 2.2). **Preuve :** `Logged in using ChatGPT` et `"isAuthenticated": true`.
- [ ] **15–20 min : quotas.** Lance `/status` dans Codex interactif et ouvre le tableau de bord d'usage Cursor (étapes 1.5 et 2.3). **Preuve :** capture sans courriel ni identifiant.
- [ ] **20–25 min : reproduire la réécriture de `cli-config.json`** (étape 2.5). **Preuve :** taille avant/après.
- [ ] **25–30 min : tests du dépôt sur `main` et sur #3** (étape 0.3). **Preuve :** `OK (skipped=1)` sur les deux.

---

## Phase 0 — CI et preuves du dépôt (GitHub, local)

- [ ] **0.1 Lire la vraie cause du rouge de #3**
  - **Commande :** `gh api repos/mboyer1269-pixel/GlobalLand.si/check-runs/124677296547/annotations --jq '.[].message'`
  - **Attendu :** le message de facturation (« recent account payments have failed… »).
  - **Preuve :** la ligne collée dans la PR de ce plan.
  - **Si autre chose :** `gh run view 41248645281 --log-failed` et traiter comme un vrai échec de test.
- [ ] **0.2 Relancer et obtenir du vert sur #3 et #5**
  - **Commande :** `gh run rerun 41248645281`, puis `gh pr checks 3` et `gh pr checks 5`.
  - **Attendu :** `tests pass` sur les deux.
  - **Preuve :** sortie de `gh pr checks`.
  - **Si échec rapide encore :** facturation Actions (lien en Sources). Option gratuite : vérifier le quota de minutes inclus du mois. Ne rien acheter.
- [ ] **0.3 Tests locaux sur trois révisions, sans toucher à ton checkout**
  - **Commande :**
    ```bash
    cd GlobalLand.si && git fetch origin
    for ref in origin/main origin/feature/cursor-subscription origin/claude/globalland-autonomous-world-nokkck; do
      d=/tmp/gl-$(echo $ref | tr '/' '-'); git worktree add -f "$d" "$ref" >/dev/null 2>&1
      ( cd "$d" && node tests/runtime.test.js >/dev/null && node tests/executor.test.js >/dev/null \
        && python3 -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -1 && bash -n scripts/*.sh && echo "$ref VERT" ) || echo "$ref ROUGE"
    done
    ```
  - **Attendu :** `OK (skipped=1)` puis `VERT` sur les trois révisions. La #3 prend environ 60 s.
  - **Preuve :** les trois lignes `VERT`.
  - **Si `ROUGE` :** relancer seulement la suite fautive avec `-v`, copier le nom du test, puis ouvrir un correctif sur la branche concernée. Ne pas fusionner.
- [ ] **0.4 Confirmer quelle révision le VPS roule (local, Git seulement)**
  - **Commande :** `git show origin/main:world/controller.json` et les deux `git log -S` du tableau plus haut.
  - **Attendu :** pas de `reason_code`, donc un contrôle entre `7e4859d` et `0a0fd24`.
  - **Preuve :** la sortie.
  - **Si `reason_code` apparaît :** le VPS roule déjà `479b990` ou plus. La cause n° 1 devient moins probable ; passer directement à la Phase 1.

## Phase 1 — Codex (OpenAI Codex CLI)

Doc : [CLI reference](https://developers.openai.com/codex/cli/reference), [Authentication](https://developers.openai.com/codex/auth), [Non-interactive](https://developers.openai.com/codex/noninteractive), [Config reference](https://developers.openai.com/codex/config-reference), [Pricing et limites](https://developers.openai.com/codex/pricing), [Slash commands](https://developers.openai.com/codex/cli/slash-commands).

- [ ] **1.1 Version, et installation isolée**
  - **Commande :** `codex --version`. Pour une install jetable : `npm install --prefix /tmp/cx @openai/codex@latest && /tmp/cx/node_modules/.bin/codex --version`. Refaire avec `@openai/codex@<version de l'image>` si tu la connais.
  - **Attendu :** `codex-cli 0.166.0` ou plus récent.
  - **Preuve :** la ligne de version.
  - **Si `command not found` ou erreur npm :** `node -v` doit donner 22 ou plus ; réinstaller Node.
- [ ] **1.2 Diagnostic officiel**
  - **Commande :** `codex doctor`, puis `codex doctor --json > /tmp/codex-doctor.json`. La sortie JSON est caviardée par Codex : relis-la quand même avant de la partager.
  - **Attendu :** `✓` partout sauf avertissements bénins (`TERM`).
  - **Preuve :** le fichier `/tmp/codex-doctor.json`.
  - **Si `✗ auth` :** étape 1.4. **Si `⚠ websocket` :** Codex retombe en HTTPS, mais ajoute des reconnexions ; lancer `codex doctor --network-only`.
- [ ] **1.3 Contrat des drapeaux utilisés par le contrôleur**
  - **Commande :**
    ```bash
    C=${C:-codex}
    for f in --ignore-user-config --ignore-rules --sandbox --ephemeral --skip-git-repo-check --output-schema; do
      $C exec --help | grep -q -- "$f" && echo "OK $f" || echo "MANQUE $f"; done
    $C --ignore-user-config --ignore-rules exec --help >/dev/null 2>&1; echo "ordre main: exit=$?"
    $C features list | grep -E '^(shell_tool|multi_agent|hooks|apps) '
    ```
  - **Attendu :** six lignes `OK` et `ordre main: exit=2`. L'ordre de `main` est refusé ; celui de #3 est bon. Les quatre fonctions apparaissent (`stable`).
  - **Preuve :** la sortie collée.
  - **Si `MANQUE` :** la version est trop vieille ; relancer avec `@latest`. **Si `exit=0` :** la CLI accepte les deux ordres ; noter la version.
- [ ] **1.4 Connexion par abonnement (ta machine)**
  - **Commande :** `codex login status; echo "exit=$?"`
  - **Attendu :** `Logged in using ChatGPT`, `exit=0`. La doc précise : « exit with 0 when logged in ».
  - **Preuve :** ces deux lignes. Jamais le contenu de `~/.codex/auth.json`.
  - **Si `Not logged in` :** `codex login` (navigateur) ou `codex login --device-auth` (machine sans navigateur ; activer d'abord le *device code login* dans les réglages de sécurité ChatGPT). **Si on voit « API key » :** `codex logout` puis reconnexion ChatGPT ; une clé API = facturation à l'usage, interdit ici.
- [ ] **1.5 Plan et quota**
  - **Commande :** `codex`, puis taper `/status` dans la session interactive.
  - **Attendu :** les limites restantes de la fenêtre de 5 h et de la semaine.
  - **Preuve :** capture sans courriel.
  - **Si 0 % restant ou limite atteinte :** c'est la cause n° 1 côté Codex. Attendre la remise à zéro indiquée. Ne pas acheter de crédits.
- [ ] **1.6 Accès au modèle**
  - **Commande :** `grep -nE '^\s*(model|profile|forced_login_method)\s*=' ~/.codex/config.toml`
  - **Attendu :** aucun modèle retiré. GPT-5.5 est retiré de Codex avec connexion ChatGPT depuis le 14 oct. 2026 ([pricing](https://developers.openai.com/codex/pricing)).
  - **Preuve :** la sortie, ou « aucune ligne ».
  - **Si `model = "gpt-5.5"` :** retirer la ligne (copie de sauvegarde d'abord) et relancer 1.7. Note : le contrôleur passe `--ignore-user-config`, donc il n'est pas touché par ta config locale.
- [ ] **1.7 Analyse des drapeaux `-c` sans connexion ni coût**
  - **Commande :**
    ```bash
    mkdir -p /tmp/cxh && cp scripts/decision.schema.json /tmp/ds.json
    echo 'Return {}' | CODEX_HOME=/tmp/cxh timeout 90 codex exec --ignore-user-config --ignore-rules --sandbox read-only --ephemeral --skip-git-repo-check --output-schema /tmp/ds.json -c forced_login_method='"chatgpt"' -c approval_policy='"never"' -c features.shell_tool=false -c web_search='"disabled"' -c tools.view_image=false -c features.multi_agent=false -c apps._default.enabled=false -c features.hooks=false -c 'mcp_servers={}' - 2>&1 | tail -3
    ```
  - **Attendu :** `401 Unauthorized: Missing bearer` (environ 13 s). Les drapeaux sont acceptés ; seul le login manque, puisque `CODEX_HOME` est vide.
  - **Preuve :** les 3 lignes.
  - **Si erreur de config (`invalid value`, `unknown key`) :** le drapeau fautif est cassé pour cette version ; ouvrir un correctif sur #3 avec un test.
- [ ] **1.8 Réseau et sandbox Docker** (si Docker est installé sur ta machine)
  - **Commande :** `docker run --rm --network none node:22-bookworm node -e "fetch('https://api.openai.com').then(()=>console.log('net'),()=>console.log('pas de reseau'))"`
  - **Attendu :** `pas de reseau`. C'est le comportement voulu des boîtes `EXEC` (`scripts/tools.py` utilise `--network none`). Le conteneur cerveau, lui, n'a **pas** `--network` et doit garder le réseau.
  - **Preuve :** `git grep -n -- "'--network'" origin/feature/cursor-subscription -- scripts/controller.py` ne donne aucune ligne.
  - **Si une ligne apparaît dans `controller.py` :** c'est bloquant ; Codex ne peut pas joindre l'API.

## Phase 2 — Cursor (IDE, CLI `agent`, Cloud Agents)

Doc : [CLI parameters](https://cursor.com/docs/cli/reference/parameters), [Authentication](https://cursor.com/docs/cli/reference/authentication), [Configuration](https://cursor.com/docs/cli/reference/configuration), [Headless](https://cursor.com/docs/cli/headless), [Output format](https://cursor.com/docs/cli/reference/output-format), [Rules](https://cursor.com/docs/context/rules), [Plugins](https://cursor.com/docs/plugins), [GitHub integration](https://cursor.com/docs/integrations/github), [Cloud Agents](https://cursor.com/docs/cloud-agent).

- [ ] **2.1 Version et drapeaux de la CLI**
  - **Commande :** `curl https://cursor.com/install -fsS | bash`, puis `agent --version` et `agent --help | grep -E -- '--(print|trust|mode|output-format)'`.
  - **Attendu :** version `2026.10.22-…` ou plus, et quatre lignes. Note : `cursor-agent` est un alias de `agent`.
  - **Preuve :** la sortie.
  - **Si `--trust` manque :** `agent update`.
- [ ] **2.2 Connexion (sortie JSON)**
  - **Commande :** `agent status --format json`
  - **Attendu :** `"isAuthenticated": true`.
  - **Preuve :** les champs `status` et `isAuthenticated` seulement.
  - **Si `unauthenticated` :** lancer `agent login`, ou `NO_OPEN_BROWSER=1 agent login` sans navigateur. ⚠️ `agent status` **sort en code 0 même non connecté** (vérifié) : ne jamais se fier au code de sortie seul. Le contrôleur de #3 lit le texte ; proposer `--format json` dans un correctif.
- [ ] **2.3 Plan et quota**
  - **Commande :** `agent about --format json`, puis le tableau de bord Cursor, section Usage ([pricing](https://cursor.com/docs/account/pricing)).
  - **Attendu :** `subscriptionTier` non nul, et de l'usage disponible dans le tableau de bord.
  - **Preuve :** `cliVersion` et `subscriptionTier` (pas le courriel).
  - **Si `subscriptionTier: null` connecté :** le compte connecté n'est pas celui qui paie. `agent logout`, puis `agent login` avec le bon compte.
- [ ] **2.4 Accès aux modèles**
  - **Commande :** `agent models` ou `agent --list-models`.
  - **Attendu :** une liste non vide.
  - **Preuve :** les 5 premières lignes.
  - **Si vide ou erreur :** retour à 2.3 (plan ou compte).
- [ ] **2.5 Réécriture de `cli-config.json` (reproduction locale, sans compte)**
  - **Commande :**
    ```bash
    H=/tmp/cuh; rm -rf $H; mkdir -p $H/.cursor /tmp/wsx
    echo '{"version":1,"permissions":{"allow":[],"deny":["Shell(*)","Write(**)"]}}' > $H/.cursor/cli-config.json
    chmod 444 $H/.cursor/cli-config.json; stat -c '%s %A' $H/.cursor/cli-config.json
    (cd /tmp/wsx && HOME=$H CURSOR_CONFIG_DIR=$H/.cursor agent -p --trust --mode ask --output-format json "ok"; echo "exit=$?")
    stat -c '%s %A' $H/.cursor/cli-config.json
    ```
  - **Attendu (observé) :** `73 -r--r--r--`, puis `Authentication required`, puis `855 -rw-r--r--`. La CLI a remplacé le fichier en lecture seule.
  - **Preuve :** les trois lignes.
  - **Si Docker est dispo :** refaire avec `--mount type=bind,src=$H/.cursor/cli-config.json,dst=/home/node/.cursor/cli-config.json,readonly` dans `node:22-bookworm` et la CLI installée. Si on obtient `EBUSY` ou `EROFS`, c'est la cause probable des échecs Cursor. Correctif à proposer sur #3 : monter un **dossier** de config jetable, recopié à chaque tour, au lieu d'un fichier en lecture seule.
- [ ] **2.6 Confiance du dossier (workspace trust)**
  - **Commande :** `(cd /tmp/wsx && HOME=/tmp/cuh agent -p --mode ask "ok"; echo "exit=$?")`, sans `--trust`.
  - **Attendu :** connecté, cela donne `Workspace Trust Required` ; avec `--trust`, la réponse passe. C'est le comportement documenté de `--trust` (« headless mode only »).
  - **Preuve :** la sortie.
  - **Si `--trust` ne suffit pas :** ne **jamais** ajouter `--force` ou `--yolo` (ces drapeaux autorisent les commandes) ; noter le message exact.
- [ ] **2.7 Règles et plugins de l'IDE**
  - **Check :** le dépôt n'a pas de `.cursor/` ; Cursor charge `AGENTS.md` (voir [Rules](https://cursor.com/docs/context/rules)) et ici aussi `CLAUDE.md`. Dans Cursor → Settings → Rules et Plugins, lister les règles `alwaysApply` actives.
  - **Attendu :** seulement les règles de GlobalLand.
  - **Preuve :** capture de la liste.
  - **Si des dizaines de règles de plugins sans rapport apparaissent** (Zscaler, Harness, Opsera, Zapier, Aikido « scanner avant de finir », Plain « confirmer avant d'agir »…) : les désactiver ou désinstaller. Ces règles poussent l'agent à demander confirmation ou à lancer des scans, ce qui fige le travail autonome. C'est observé dans le contexte de l'agent qui a écrit ce plan.
- [ ] **2.8 Cloud Agents et GitHub (le 403 sur les pushs)**
  - **Check 1, qui pousse :** cette PR a été poussée sans erreur par un Cloud Agent, sur `cursor/plan-deblocage-outils-f040`. L'intégration marche donc pour le compte Cursor qui a lancé cet agent.
  - **Check 2, quel compte :** cursor.com → Dashboard → Integrations → GitHub doit être connecté au **même** compte ou à la même équipe Cursor que l'abonnement payé. L'erreur documentée « GitHub installation is already connected to another Cursor target » veut dire que l'installation appartient à un autre compte.
  - **Check 3, accès au dépôt :** github.com/settings/installations → Cursor → *Repository access* doit inclure `GlobalLand.si`. La doc exige des droits lecture-écriture ([Cloud Agents](https://cursor.com/docs/cloud-agent)).
  - **Check 4, quelle commande a fait le 403 :** dans les Cloud Agents, la CLI `gh` est en **lecture seule** par conception. `gh pr create`, `gh issue create` ou un push via l'API donnent un 403 normal. Les PR passent par l'outil Cursor, pas par `gh`.
  - **Attendu :** les quatre checks verts. Un agent de test qui crée une branche `cursor/test-…` la pousse.
  - **Preuve :** URL de la branche poussée.
  - **Si 403 sur un `git push` vers une branche `cursor/*` :** réinstaller l'app depuis github.com/apps/cursor (section Troubleshooting de la doc GitHub).

## Phase 3 — Corriger dans le dépôt (PR sur la pile #3 → #5, jamais fusionnées par un agent)

- [ ] **3.1 Test de contrat contre les vraies CLI.** Créer un test optionnel, sur le modèle de `test_docker_smoke.py` (activé par variable d'environnement), qui lance `codex exec --help` et `agent --help` installés et vérifie chaque drapeau de `brain_command`, ordre compris. **Preuve :** le test échoue sur l'ordre de `main` et passe sur #3. **Si la CLI est absente :** le test est ignoré, pas vert.
- [ ] **3.2 Cursor : dossier de config jetable** au lieu d'un fichier `readonly` (suite de 2.5). **Preuve :** un test unitaire sur l'argv et la reproduction 2.5 sans erreur.
- [ ] **3.3 Cursor : `status --format json`** pour la vérification de connexion. Le code de sortie seul ment (2.2). **Preuve :** des tests avec les sorties `unauthenticated` et `authenticated` en fixtures.
- [ ] **3.4 Délai du cerveau configurable.** Aujourd'hui, c'est 120 s fixes via `bounded_run`. Ajouter une clé `controller.timeout_seconds` dans la config, avec 120 par défaut et une borne maximale. **Preuve :** un test avec une fausse commande lente. **Pas d'augmentation des CPU ou de la mémoire** sans décision.
- [ ] **3.5 Vérifier que la bascule de `479b990` couvre le scénario observé** : succès, succès, puis échec du même fournisseur à répétition. **Commande :** `python3 -m unittest tests.test_provider_failover -v` sur #3. **Preuve :** vert.
- [ ] **3.6 Mettre `CLAUDE.md` à jour :** il dit « Le dépôt est public », alors que l'API GitHub répond `private: true`. Cela change la facturation Actions (Phase 0).

## Remise au boss — VPS (hors périmètre, pas de cases)

Ce que le local ne peut pas trancher, et que toi seul peux lire sans exposer de secret : `state/private/controller-failure.json`, qui contient le type d'exception et la raison ; le nombre de fichiers `state/controller/THINK-*.json`, qui confirme quel fournisseur est rechoisi ; et la version de Codex et de Cursor dans l'image épinglée. Les correctifs de la Phase 3 ne prennent effet qu'après ton installation administrateur.

---

## Prompt Claude Code prêt à coller

> Note : si Claude Code répond d'emblée par une limite d'usage, c'est en soi une preuve pour la cause n° 1.

```text
Tu travailles dans le dépôt GlobalLand.si. Lis docs/PLAN-DEBLOCAGE-OUTILS.md, CLAUDE.md et AGENTS.md.
Exécute UNIQUEMENT les étapes locales 0.1, 0.3, 0.4, 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5 et 2.6.
Règles strictes :
- Aucune action sur le VPS, aucun ssh, aucun docker sur un hôte distant.
- Ne lis, n'affiche et ne copie jamais ~/.codex/auth.json, ~/.cursor/ (sauf les fichiers jetables de /tmp/cuh), credentials/, ni aucune variable *_KEY ou *_TOKEN.
- Aucune dépense : pas de clé API, pas de --with-api-key, pas d'achat de crédits.
- Installe les CLI seulement dans /tmp (npm --prefix /tmp/cx ; installateur Cursor officiel).
- N'utilise jamais --force ou --yolo avec agent.
- Pas de git push, pas de merge.
Pour chaque étape : affiche la commande, la sortie tronquée à 20 lignes, puis le verdict OK/ÉCHEC selon le « résultat attendu » du plan.
Termine par un tableau étape | verdict | preuve, et par les cases du plan que je peux cocher.
Écris ce rapport dans /tmp/diag-local.md (pas dans le dépôt).
```

---

## Sources officielles

- Codex : [CLI reference](https://developers.openai.com/codex/cli/reference) · [Authentication](https://developers.openai.com/codex/auth) · [Non-interactive](https://developers.openai.com/codex/noninteractive) · [Config reference](https://developers.openai.com/codex/config-reference) · [Pricing et limites](https://developers.openai.com/codex/pricing) · [Slash commands](https://developers.openai.com/codex/cli/slash-commands)
- Cursor : [CLI parameters](https://cursor.com/docs/cli/reference/parameters) · [Authentication](https://cursor.com/docs/cli/reference/authentication) · [Configuration](https://cursor.com/docs/cli/reference/configuration) · [Headless](https://cursor.com/docs/cli/headless) · [Output format](https://cursor.com/docs/cli/reference/output-format) · [Rules](https://cursor.com/docs/context/rules) · [Plugins](https://cursor.com/docs/plugins) · [GitHub](https://cursor.com/docs/integrations/github) · [Cloud Agents](https://cursor.com/docs/cloud-agent) · [Pricing](https://cursor.com/docs/account/pricing)
- GitHub : [Billing Actions](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) · [Re-run workflows](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/re-running-workflows-and-jobs) · [`gh run rerun`](https://cli.github.com/manual/gh_run_rerun)

Tous les drapeaux cités ont été vérifiés dans l'aide des CLI installées (Codex 0.166.0, Cursor Agent 2026.10.22) et dans les pages ci-dessus, le 2026-11-01.
