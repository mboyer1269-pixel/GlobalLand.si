import csv, io

def check(text, delimiter=",", required_columns=None):
    """Structural CSV check. Returns stable JSON-able dict."""
    issues = []
    had_bom = text.startswith("\ufeff")
    text = text.lstrip("\ufeff")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error as exc:
        return {"ok": False, "issues": [{"kind": "invalid_csv", "detail": str(exc)}], "data_rows": 0, "columns": 0, "headers": [], "had_bom": had_bom}
    if not rows:
        return {"ok": False, "issues": [{"kind": "empty_file"}], "data_rows": 0, "columns": 0, "headers": [], "had_bom": had_bom}
    headers = rows[0]
    for i, h in enumerate(headers, 1):
        if not h.strip():
            issues.append({"kind": "blank_header", "column": i})
    seen = {}
    for i, h in enumerate(headers, 1):
        k = h.strip().casefold()
        if k and k in seen:
            issues.append({"kind": "duplicate_header", "column": i, "header": h, "first_column": seen[k]})
        seen.setdefault(k, i)
    for col in (required_columns or []):
        if col.strip().casefold() not in seen:
            issues.append({"kind": "missing_required_column", "header": col})
    for line, row in enumerate(rows[1:], 2):
        if len(row) == 1 and row[0] == "":
            issues.append({"kind": "blank_row", "record": line})
        elif len(row) != len(headers):
            issues.append({"kind": "column_count", "record": line, "expected": len(headers), "actual": len(row)})
    return {"ok": not issues, "issues": issues, "data_rows": len(rows) - 1, "columns": len(headers), "headers": headers, "had_bom": had_bom}
