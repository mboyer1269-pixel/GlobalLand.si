#!/usr/bin/env python3
"""GlobalLand plain-text CSV structure diagnostic. Stdlib only, offline, no network.
Built and maintained by autonomous AI agents.
Port of the structural rules of the public checker at
https://globalland-invoice-preflight.global-land.workers.dev/ (products/sites/invoice-preflight/index.html).
Usage: python3 -I diagnostic.py < message.txt  -> JSON on stdout.
The CSV must be pasted between the lines ---CSV START--- and ---CSV END---.
It checks structure only: quoting, row widths, empty/duplicate headers, row count.
"""
import json, sys

MAX_DATA_ROWS = 20
MAX_CHARS = 20000
START = '---CSV START---'
END = '---CSV END---'
NOT_CHECKED = ['amounts', 'dates', 'tax', 'currency', 'customer or account mappings',
               'semicolon/tab delimiters', 'encoding beyond UTF-8 text',
               'compatibility with Manager.io or any accounting platform']


def check(text):
    if text.startswith('﻿'):
        text = text[1:]
    rows, row, cell, quoted, closed, errors = [], [], '', False, False, []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quoted:
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    cell += '"'; i += 1
                else:
                    quoted, closed = False, True
            else:
                cell += c
            i += 1
            continue
        if c == '"':
            if cell != '' or closed:
                errors.append('Unexpected quote near character %d' % (i + 1))
            else:
                quoted = True
        elif c == ',':
            row.append(cell); cell = ''; closed = False
        elif c in '\r\n':
            if c == '\r' and i + 1 < n and text[i + 1] == '\n':
                i += 1
            row.append(cell); rows.append(row); row = []; cell = ''; closed = False
        else:
            if closed:
                errors.append('Text after closing quote near character %d' % (i + 1))
            cell += c
        i += 1
    if quoted:
        errors.append('Unclosed quoted field')
    if cell != '' or row or closed:
        row.append(cell); rows.append(row)
    if not rows:
        errors.append('Empty file')
    else:
        width = len(rows[0])
        for k, r in enumerate(rows):
            if len(r) != width:
                errors.append('Row %d has %d columns; expected %d' % (k + 1, len(r), width))
        seen = set()
        for k, h in enumerate(rows[0]):
            if not h.strip():
                errors.append('Empty header at column %d' % (k + 1))
            if h.strip() in seen:
                errors.append('Duplicate header: ' + h)
            seen.add(h.strip())
    return {'dataRows': max(0, len(rows) - 1), 'columns': len(rows[0]) if rows else 0, 'errors': errors}


def extract(body):
    s = body.find(START)
    if s < 0:
        return None
    e = body.find(END, s + len(START))
    if e < 0:
        return None
    return body[s + len(START):e].strip('\r\n')


def diagnose(body):
    if len(body) > MAX_CHARS:
        return {'status': 'DECLINED', 'reason': 'MESSAGE_TOO_LARGE', 'limit_chars': MAX_CHARS}
    csv_text = extract(body)
    if csv_text is None:
        return {'status': 'DECLINED', 'reason': 'MISSING_CSV_MARKERS',
                'hint': 'Paste the CSV between ' + START + ' and ' + END}
    res = check(csv_text)
    if res['dataRows'] > MAX_DATA_ROWS:
        return {'status': 'DECLINED', 'reason': 'TOO_MANY_ROWS', 'dataRows': res['dataRows'],
                'limit_data_rows': MAX_DATA_ROWS}
    out = {'status': 'CHECKED', 'structure_ok': not res['errors']}
    out.update(res)
    out['not_checked'] = NOT_CHECKED
    return out


if __name__ == '__main__':
    print(json.dumps(diagnose(sys.stdin.read()), ensure_ascii=False, indent=2))
