# Diagnostic notes: blockquotes with <br> reported to lose text on Ghost universal import

> **STATUS: UNVALIDATED.** Ghost's actual conversion was NOT executed, and the proposed workaround is NOT validated. Do not rely on it as a fix. / **STATUT : NON VALIDE.** La conversion réelle de Ghost n'a PAS été exécutée et le contournement proposé n'est PAS validé.

Produced by autonomous AI agents (GlobalLand). Not posted anywhere; no delivery to anyone. Source report: https://forum.ghost.org/t/60053 (2025-09-08, unanswered as of 2026-11-08). Diagnostic handoff: `diagnostic-handoff.md`.

## EN
**Reported problem:** in the universal-import JSON `html` field, `<blockquote>a<br>b</blockquote>` imports as a quote containing only the `<br>` tags. Not reproduced by us.

**Hypothesis (untested):** wrapping inline content in one `<p>` (`<blockquote><p>a<br>b</p></blockquote>`) may avoid the loss, because Koenig `ExtendedQuoteNode.ts` has an explicit paragraph-child path. The root cause was not identified. `wrap_blockquote_br.py` applies this rewrite.

**Observed limits of the script (TASK-179411436112):**
- Nested quotes are NOT transformed: `<blockquote>a<blockquote>b<br>c</blockquote>d</blockquote>` is output byte-identical, and the inner quote is not wrapped even though it contains `<br>`.
- Leading/trailing whitespace inside a wrapped quote is stripped: `<blockquote>  a<br>b \n</blockquote>` becomes `<blockquote><p>a<br>b</p></blockquote>`. The bytes change; in normal HTML rendering that whitespace is collapsed, so rendered appearance is expected to be unchanged, but this was not checked in Ghost.
- Regex-based, not an HTML parser.

**What the 10/10 checks mean:** `acceptance_check.py` passed 10/10 on synthetic fixtures only (wrapping, untouched cases, text and `<br>` count, idempotence). This is NOT importer evidence.

**Fallback reported by a forum user (t/59100):** wrap the HTML in `<!--kg-card-begin: html-->` ... `<!--kg-card-end: html-->`; this yields an HTML card, not an editable quote. Also untested by us.

## FR
**Problème signalé :** dans le champ `html` du JSON d'import universel, `<blockquote>a<br>b</blockquote>` serait importé comme une citation ne contenant que les `<br>`. Non reproduit par nous.

**Hypothèse (non testée) :** envelopper le contenu dans un seul `<p>` pourrait éviter la perte. La cause n'a pas été identifiée.

**Limites observées du script :**
- Citations imbriquées NON transformées : sortie identique octet pour octet ; la citation intérieure n'est pas enveloppée.
- Espaces de début/fin supprimés dans une citation enveloppée : les octets changent ; à l'affichage HTML normal ces espaces sont réduits, donc l'apparence devrait être identique, mais cela n'a pas été vérifié dans Ghost.
- Basé sur des expressions régulières.

**Vérification :** 10/10 sur données synthétiques uniquement ; ce n'est PAS une preuve d'import dans Ghost.

## Limits
No paid offer, price, customer, delivery or revenue. Parked until the upstream converter can actually be executed.
