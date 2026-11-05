import csv, io
import http.client
import socket
import ssl
from urllib.parse import urljoin

from .public_http import request, PublicHTTPError

MAX_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 5


def _error(source, code, message):
    return {'source': source, 'ok': False, 'issues': [], 'data_rows': 0, 'columns': 0,
            'headers': [], 'had_bom': False, 'error_code': code, 'error': message}


def check_text(text, delimiter=',', required_columns=None, source='pasted_text'):
    if not isinstance(text, str):
        return _error(source, 'invalid_text', 'CSV text must be a string')
    if not isinstance(delimiter, str) or len(delimiter) != 1 or (required_columns is not None and (
            not isinstance(required_columns, list) or not all(isinstance(col, str) for col in required_columns))):
        return _error(source, 'invalid_input', 'Provide a single delimiter and a list of column names')
    # Check characters first to avoid allocating another copy of oversized input.
    if len(text) > MAX_BYTES or len(text.encode('utf-8')) > MAX_BYTES:
        return _error(source, 'too_large', 'file larger than 10 MiB')
    return {'source': source, **check(text, delimiter, required_columns), 'error_code': None, 'error': None}


def read_csv(url, delimiter=',', required_columns=None, timeout=30):
    target = url
    try:
        for hop in range(MAX_REDIRECTS + 1):
            status, location, body = request(target, 'GET', timeout, read_bytes=MAX_BYTES + 1,
                headers={'Accept': 'text/csv, text/plain;q=0.9',
                         'User-Agent': 'GlobalLand-csv-preflight/0.1 (autonomous AI agents)'})
            if status in (301, 302, 303, 307, 308) and location:
                if hop == MAX_REDIRECTS:
                    raise PublicHTTPError('too_many_redirects', 'redirect limit exceeded')
                target = urljoin(target, location)
                continue
            if not 200 <= status < 300:
                raise PublicHTTPError('http_error', 'HTTP %d' % status)
            if len(body) > MAX_BYTES:
                raise PublicHTTPError('too_large', 'file larger than 10 MiB')
            return check_text(body.decode('utf-8'), delimiter, required_columns, source=url)
    except PublicHTTPError as exc:
        return _error(url, exc.code, str(exc))
    except UnicodeError:
        return _error(url, 'invalid_encoding', 'file is not valid UTF-8')
    except (socket.timeout, TimeoutError):
        return _error(url, 'timeout', 'CSV request timed out')
    except ssl.SSLError:
        return _error(url, 'tls_error', 'TLS verification or connection failed')
    except (OSError, ValueError, http.client.HTTPException):
        return _error(url, 'network_error', 'could not complete the CSV request')

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
