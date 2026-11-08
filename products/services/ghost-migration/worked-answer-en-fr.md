# Worked answer: blockquotes with <br> lose text on Ghost universal import

Produced by autonomous AI agents (GlobalLand). Not posted anywhere. Source request: https://forum.ghost.org/t/60053 (2025-09-08, unanswered as of 2026-11-08).

## EN
**Problem reported:** in the universal-import JSON `html` field, `<blockquote>a<br>b</blockquote>` imports as a quote that contains only the `<br>` tags.

**Suggested workaround (untested against Ghost):** before importing, wrap the inline content of those quotes in one `<p>`: `<blockquote><p>a<br>b</p></blockquote>`. Ghost's quote converter (Koenig `ExtendedQuoteNode.ts`) has an explicit path for paragraph children. `wrap_blockquote_br.py in.json out.json` does this for every post and leaves quotes without `<br>` or with block children unchanged. Test it with a single post first.

**Fallback reported by another forum user (t/59100):** wrap the HTML in `<!--kg-card-begin: html-->` ... `<!--kg-card-end: html-->`. This imports it as an HTML card, which is not an editable quote.

**Verification:** `python3 acceptance_check.py` passed 10/10 on synthetic fixtures. It checks wrapping, untouched cases, preserved text and `<br>` count, and idempotence. Ghost import itself was NOT tested.

## FR
**Problème signalé :** dans le champ `html` du JSON d’import universel, `<blockquote>a<br>b</blockquote>` est importé comme une citation ne contenant que les balises `<br>`.

**Contournement proposé (non testé dans Ghost) :** avant l’import, envelopper le contenu de ces citations dans un seul `<p>`. Le convertisseur de citations de Ghost traite explicitement les paragraphes enfants. Le script `wrap_blockquote_br.py` le fait pour chaque article. Testez d’abord avec un seul article.

**Solution de repli signalée (t/59100) :** encadrer le HTML de `<!--kg-card-begin: html-->` et `<!--kg-card-end: html-->`. On obtient une carte HTML, pas une citation modifiable.

**Vérification :** 10/10 sur des données synthétiques ; l’import dans Ghost n’a PAS été testé.

## Limits
No paid offer, price, customer or revenue. Regex-based. Nested blockquotes are skipped.
