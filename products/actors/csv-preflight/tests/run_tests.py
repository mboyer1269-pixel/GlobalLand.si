"""Offline CSV core contract; any failed check produces a nonzero process exit."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import core


def main():
    cases = [
        ('valid', 'A,B\n1,2', ',', [], True, []),
        ('bom', '\ufeffA,B\n1,2', ',', [], True, []),
        ('short_row', 'A,B\n1', ',', [], False, ['column_count']),
        ('duplicate_header', 'A,a\n1,2', ',', [], False, ['duplicate_header']),
        ('blank_header', 'A,\n1,2', ',', [], False, ['blank_header']),
        ('unclosed_quote', 'A,B\n"1,2', ',', [], False, ['invalid_csv']),
        ('empty', '', ',', [], False, ['empty_file']),
        ('missing_required', 'A,B\n1,2', ',', ['C'], False, ['missing_required_column']),
        ('semicolon', 'A;B\n1;2', ';', [], True, []),
        ('quoted_delimiter', 'A,B\n"1,2",3', ',', [], True, []),
    ]
    failed = 0
    for name, text, delimiter, required, ok, issues in cases:
        try:
            row = core.check(text, delimiter, required)
            assert row['ok'] is ok, row
            assert [issue['kind'] for issue in row['issues']] == issues, row
            if name == 'bom':
                assert row['had_bom'] is True and row['headers'] == ['A', 'B'], row
            if ok:
                assert row['data_rows'] == 1 and row['columns'] == 2, row
        except Exception as exc:
            failed += 1
            print('FAIL', name, str(exc)[:300])
    print('passed %d/%d' % (len(cases) - failed, len(cases)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
