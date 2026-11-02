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
`source`, `ok` (bool), `issues` (list of `{kind, record?, column?, header?, expected?, actual?, detail?}`), `data_rows`, `columns`, `headers`, `had_bom`, `error` (null unless the file could not be fetched/decoded; `issues` is then empty).

## Pricing
Pay per event: `file-checked`, charged once per file successfully parsed and checked. Files that fail to download are not charged.

## Limits
UTF-8 only, 10 MiB per file, public URLs only (no logins).
