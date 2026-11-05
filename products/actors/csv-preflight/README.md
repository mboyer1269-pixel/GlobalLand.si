# CSV Preflight Validator

**Built and maintained by autonomous AI agents (GlobalLand).**

One job: check a CSV file's *structure* before you import it somewhere, and return machine-readable JSON errors.

## Checks performed
- Parse errors (unclosed or stray quotes) via Python csv strict mode
- Blank and duplicate headers (case-insensitive)
- Missing required columns you list
- Rows whose column count differs from the header; blank rows
- UTF-8 BOM presence (reported, not an error)

## Not checked
Amounts, dates, tax, encodings other than UTF-8, or compatibility with any accounting or import platform. Passing this check does not guarantee an import will succeed.

## Input
`csvText` (string) and/or `csvUrls` (list of public URLs), optional `delimiter`, optional `requiredColumns`.

Example: `{"csvUrls":["https://example.com/invoices.csv"],"requiredColumns":["Invoice","Amount"]}`

## Output (one dataset item per file)
`source`, `ok` (bool), `issues` (list of `{kind, record?, column?, header?, expected?, actual?, detail?}`), `data_rows`, `columns`, `headers`, `had_bom`, `error_code`, `error` (both null for a completed check; `issues` is empty when input or fetching fails).

## Pricing
Pay per event: `file-checked`, charged once per file successfully parsed and checked. Files that fail to download are not charged.

## Limits
UTF-8 only, 10 MiB per file including pasted text. Downloads read at most 10 MiB plus one byte before rejecting oversized files. Public HTTP(S) URLs only (no logins): every DNS answer and redirect is validated, the socket connects to a validated IP, and HTTPS verifies the original hostname. At most five redirects are followed. Private/local/metadata destinations and URL credentials are rejected.

## Local verification
Run `python3 products/actors/csv-preflight/tests/run_tests.py` for the CSV core, and `python3 -m unittest discover -s tests -p 'test_actor*.py'` from the repository root for transport restrictions, byte limits and test-runner failure contracts.

With the pinned requirements installed, `python3 tests/actor_sdk_smoke.py --actor csv-preflight` executes the real Apify SDK wrapper using synthetic sockets and local test charging. This covers input, output and billing decisions, including blocked redirects and oversized inputs. It does not test a deployed Actor, live downloads or real Apify billing; publication still requires the configured account and authorization.
