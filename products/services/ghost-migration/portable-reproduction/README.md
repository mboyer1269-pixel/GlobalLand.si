# Portable reproduction: Ghost blockquote `<br>` report (forum t/60053)

Built by autonomous AI agents (GlobalLand). **STATUS: UNVALIDATED.** Its authors have NOT run this harness against the upstream package or against Ghost. Their sandbox had no registry access (`sandbox-default-run.json`: exit 2, DEPENDENCY_ABSENT). No defect is claimed to be reproduced, and the `<p>`-wrapping workaround is not endorsed.

## EN
**What it tests:** converter-level behaviour of `@tryghost/kg-html-to-lexical` (direct dependency pinned to **1.4.4**) on 8 synthetic inputs (`fixtures.json`), covering questions Q1-Q4 of `../diagnostic-handoff.md`.

**Not locked:** no `package-lock.json` is supplied. Transitive dependencies (jsdom, lexical, @lexical/*, `@tryghost/kg-default-nodes ~2.3.0`, `@tryghost/kg-default-transforms ~1.3.9`) resolve when you install. Record them with `npm ls --all > tree.txt` and attach that file to any report.

**Run** (Node ^22.22.2 or ^24.15.0):
```
npm install
node harness.cjs --out result.json; echo $?
npm ls --all > tree.txt
```
**Exit codes:** 0 all assertions passed; 1 at least one FAIL or ERROR; 2 package or a dependency missing; 3 no `htmlToLexical` export (API mismatch); 4 fixtures unreadable. A `version_warning` field appears if the installed version is not 1.4.4.

**Reading `result.json`:** each case lists extracted `texts`, `quote_types`, `linebreaks`, `missing_tokens`, `checks` and the raw `lexical` output.
- Q1 `q1-before`: FAIL with `a`/`b` in `missing_tokens` while a linebreak remains would match the report. PASS means it was not reproduced at this converter version.
- Q2 `q2-after`: PASS is consistent with the `<p>` hypothesis for this converter only.
- Q3 pair: compares normalized text and linebreak count. `raw_text_equal_observation` records whether leading/trailing whitespace bytes survived. It is an observation, not an assertion.
- Q4 nested cases: only token presence and order are asserted. Inspect `lexical` to see how nesting was handled.
- Q5 (real Ghost universal import) is **not covered**. We have not verified which converter version, options or pre-processing Ghost's importer applies. A converter result is not an import result.

**Harness self-test (stubs only):** `node tests/run-stub-tests.cjs` runs the harness against stub converters in `tests/stubs/`. These imitate success, the reported loss, exceptions, a missing export and string output. Results are in `stub-test-results.json` (12/12). They test control flow only and say nothing about Ghost.

## FR
**Objet :** comportement du convertisseur `@tryghost/kg-html-to-lexical` (dépendance directe épinglée en **1.4.4**) sur 8 entrées synthétiques (`fixtures.json`), pour les questions Q1-Q4 de `../diagnostic-handoff.md`.

**Non verrouillé :** aucun `package-lock.json` n'est fourni ; les dépendances transitives sont résolues à l'installation. Enregistrez-les avec `npm ls --all > tree.txt`.

**Exécution** (Node ^22.22.2 ou ^24.15.0) : `npm install`, puis `node harness.cjs --out result.json`.

**Codes de sortie :** 0 tout réussi ; 1 au moins un FAIL ou ERROR ; 2 paquet ou dépendance absent ; 3 export `htmlToLexical` absent ; 4 fixtures illisibles.

**Interprétation :** un FAIL de Q1 (`a`/`b` manquants, saut de ligne présent) correspondrait au signalement. Un PASS de Q2 est compatible avec l'hypothèse `<p>` pour ce convertisseur seulement. Pour Q3, les espaces bruts sont observés sans être imposés. Pour Q4, seuls la présence et l'ordre des jetons sont vérifiés. **Q5 (import Ghost réel) n'est pas couvert** : un résultat du convertisseur n'est pas un résultat d'import.

**Auto-test :** `node tests/run-stub-tests.cjs` utilise uniquement des convertisseurs factices (12/12). Ce n'est pas une exécution de l'amont.

## Limits / Limites
No price, offer, customer, delivery, outreach or revenue. Not published. Any publication requires an independent exact-digest review.
