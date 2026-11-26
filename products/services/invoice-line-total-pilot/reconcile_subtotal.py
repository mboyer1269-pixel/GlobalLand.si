import csv
import io
import json
import re
import sys


def cents(value):
    if re.fullmatch(r'[0-9]{1,9}\.[0-9]{2}', value) is None:
        raise ValueError('Use unsigned CAD amounts with 1–9 whole digits and exactly two decimal digits.')
    whole, fraction = value.split('.')
    return int(whole) * 100 + int(fraction)


def money(value):
    whole, fraction = divmod(abs(value), 100)
    sign = '-' if value < 0 else ''
    return f'{sign}{whole}.{fraction:02d}'


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('Pass one declared pre-tax subtotal and pipe a one-column CSV on stdin.')
        declared = cents(sys.argv[1])
        raw = sys.stdin.read(4097)
        if len(raw) > 4096:
            raise ValueError('Input exceeds 4096 characters.')
        rows = list(csv.reader(io.StringIO(raw, newline=''), strict=True))
        if not rows or rows[0] != ['line_amount']:
            raise ValueError('Expected the single CSV header line_amount.')
        amounts = rows[1:]
        if not 1 <= len(amounts) <= 20 or any(len(row) != 1 for row in amounts):
            raise ValueError('Provide 1–20 rows, each containing one line amount.')
        computed = sum(cents(row[0]) for row in amounts)
    except (ValueError, csv.Error) as error:
        print(json.dumps({'verdict': 'INVALID', 'reason': str(error)}))
        return 2
    delta = declared - computed
    print(json.dumps({'currency': 'CAD', 'rows': len(amounts), 'declared_subtotal': money(declared), 'computed_subtotal': money(computed), 'declared_minus_computed': money(delta), 'verdict': 'MATCH' if delta == 0 else 'MISMATCH'}))
    return int(delta != 0)


if __name__ == '__main__':
    sys.exit(main())
