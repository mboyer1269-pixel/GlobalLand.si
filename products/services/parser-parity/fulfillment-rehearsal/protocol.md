# Parser-port review: private fulfillment protocol (internal, EN/FR delivery)

Made by autonomous AI agents (GlobalLand BUILDER). Status: SYNTHETIC REHEARSAL ONLY. No customer, request, order, payment or delivery to a recipient has been observed. CAD 150 remains an unvalidated price hypothesis; ordering and payment acceptance are unavailable to agents (administrative order creation/acceptance only, see blocker SERVICE-PAYMENT-COLLECTION).

## 1. Scope accepted (matches the live page, unchanged)
One nonconfidential parser port: a date, number or CSV parsing function, about 300 lines at most, in two languages. Runtimes available in the rehearsal: Python 3.11.2 and Node v22.23.4; nothing else was executed. Any other language pair is out of scope until a runtime is shown to be installed.

## 2. Required pasted inputs (plain text in the email body)
1. Reference function source and its language.
2. Port function source and its language.
3. Entry-point names and the expected return convention for invalid input (null/None, exception, sentinel).
4. Confirmation that the code is nonconfidential and may be executed offline.
No attachments (they are not downloaded), no URLs (no retrieval), no confidential code, no personal data. Per docs/AGENTMAIL.md as read in TASK-179466156110: selected sources at most 64 KiB per file; incoming snapshot 256 KiB.

## 3. Scope acceptance questions (ask before any work; unanswered = stop)
- Which implementation is authoritative when they disagree: the reference, or a named specification?
- Is rejection or normalisation expected for out-of-range input?
- Are surrounding whitespace, a leading plus sign, exponent notation, thousands separators and non-ASCII digits intended to be accepted?
- Which runtime versions matter? Results are stated only for versions actually executed.
- Does the code need network, files, third-party packages or a clock? If yes: out of scope (offline standard library only).

## 4. Work steps (each is an offline case-local EXEC)
1. Save both pasted sources unchanged; record their SHA256.
2. Build boundary fixtures for the function type (empty, whitespace, sign, exponent, radix prefix, excess precision, trailing garbage, trailing newline, magnitude limit, non-finite values).
3. Execute reference and port on every fixture; record raw outputs. Never report a result that was not executed.
4. Table every disagreement. A disagreement is a finding, not automatically a port defect: confirm against the authority chosen in section 3.
5. Write one minimal patch to the port, rerun all fixtures, report before/after counts.

## 5. Delivery format (inline UTF-8 text in the reply, EN then FR)
Scope line; executed runtime versions; fixture count; disagreements before; patch as a unified diff; disagreements after; full table; limits; AI disclosure. Budget: 24,000 UTF-8 bytes of files per execution and 32,000 characters for the final reply (docs/AGENTMAIL.md). The rehearsal delivery is 2462 bytes (sha256 40e222f2023a16b5f952426d84f4f7f9ad0f6614ea6a8408096bd7f89c438ea6), so it fits; a 300-line port with a larger table must be truncated to disagreeing rows first.

## 6. Executed synthetic case (products/services/parser-parity/fulfillment-rehearsal/results.json)
Decimal amount string to integer cents. Python reference (strict fullmatch) versus a JavaScript port using parseFloat and Math.round. 25 fixtures. Before repair the port disagreed on 14 inputs (silent acceptance of excess precision, trailing text, exponent, whitespace, hex prefix, leading dot, trailing dot, plus sign, thousands separator, trailing newline, Infinity, over-long magnitude). After the patch in patch.diff: 0 disagreements, 50/50 checks. Side observation executed in the same run: Python re \d matches an Arabic-Indic digit (True) while JavaScript \d does not (False), so the repaired pattern uses [0-9] in both languages.

## 7. What this does not establish
Recipient delivery, the private cycle selecting this protocol, customer demand, accepted orders or revenue. Configured private fulfillment is not observed delivery. Feedback counters remain 0 classified / 5 unclassified: demand unknown.

## FR (resume)
Protocole interne pour la revue d'un portage d'analyseur non confidentiel (environ 300 lignes, deux langages), en texte brut uniquement, sans piece jointe ni URL. Questions prealables : quelle implementation fait autorite, rejet ou normalisation, espaces, signe plus, exposant, separateurs, chiffres non ASCII, versions. Livrable dans le corps du courriel : versions executees, tableau des ecarts, correctif minimal, resultats apres correction, limites, mention IA. Repetition synthetique executee : 14 ecarts avant, 0 apres, 50/50 verifications. Aucun client, aucune commande, aucun paiement; 150 CAD reste une hypothese non validee.
