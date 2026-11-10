#!/usr/bin/env python3
"""Internal fulfillment helper: locate duplicate image URLs within each style.
Built and maintained by autonomous AI agents (GlobalLand). Python 3 stdlib only. Offline.
Usage: python3 locate_dup_images.py IMAGES.csv [--style-col style_id] [--url-col url]
Input: the image CSV (header style_id,color,position,url) as pasted by the client.
Output (stdout JSON): duplicate groups per (style_id, url) with each occurrence's
  record (1 = first data record after the header), transform_line (= record + 1, the
  numbering transform.py uses in its 'images line N' messages), physical_line_start/end
  (actual file lines; differ from records when quoted fields contain newlines) and all fields.
URLs are compared exactly after stripping surrounding whitespace, as transform.py does.
Identifiers stay strings ('007' and '7' are different styles).
Cross-style reuse of a URL is listed separately as information (transform.py does not
flag it). Rows with a blank style or url are listed under skipped_blank.
Exit 0: no within-style duplicates. Exit 1: duplicates found. Exit 2: unreadable input
(missing column, malformed CSV, wrong field count, not UTF-8); details in 'errors'.
"""
import argparse, csv, json, sys


def locate(path, style_col='style_id', url_col='url'):
    out = {'file': path, 'records': 0, 'errors': [], 'duplicate_groups': [],
           'cross_style_reuse': [], 'skipped_blank': []}
    try:
        f = open(path, newline='', encoding='utf-8-sig')
    except OSError as e:
        out['errors'].append('cannot open: %s' % e)
        return out
    with f:
        r = csv.reader(f, strict=True)
        try:
            header = next(r)
        except StopIteration:
            out['errors'].append('empty file: no header')
            return out
        except (csv.Error, UnicodeDecodeError) as e:
            out['errors'].append('header unreadable: %s' % e)
            return out
        header = [h.strip() for h in header]
        miss = [c for c in (style_col, url_col) if c not in header]
        if miss:
            out['errors'].append('missing columns %s; header is %s' % (miss, header))
            return out
        si, ui = header.index(style_col), header.index(url_col)
        seen = {}
        rec, prev_line = 0, r.line_num
        while True:
            try:
                row = next(r)
            except StopIteration:
                break
            except (csv.Error, UnicodeDecodeError) as e:
                out['errors'].append('malformed CSV after physical line %d (record %d): %s' % (prev_line, rec + 1, e))
                return out
            start, end = prev_line + 1, r.line_num
            prev_line = end
            if not row:
                continue
            rec += 1
            if len(row) != len(header):
                out['errors'].append('record %d (physical lines %d-%d): %d fields, header has %d' % (rec, start, end, len(row), len(header)))
                continue
            fields = dict(zip(header, row))
            occ = {'record': rec, 'transform_line': rec + 1, 'physical_line_start': start,
                   'physical_line_end': end, 'fields': fields}
            style, url = row[si].strip(), row[ui].strip()
            if not style or not url:
                occ['blank'] = [c for c, v in ((style_col, style), (url_col, url)) if not v]
                out['skipped_blank'].append(occ)
                continue
            seen.setdefault(url, {}).setdefault(style, []).append(occ)
        out['records'] = rec
    for url, by_style in seen.items():
        for style, occs in by_style.items():
            if len(occs) > 1:
                out['duplicate_groups'].append({'style_id': style, 'url': url, 'count': len(occs), 'occurrences': occs})
        if len(by_style) > 1:
            out['cross_style_reuse'].append({'url': url, 'styles': {s: [o['record'] for o in v] for s, v in by_style.items()}})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('images')
    ap.add_argument('--style-col', default='style_id')
    ap.add_argument('--url-col', default='url')
    a = ap.parse_args(argv)
    res = locate(a.images, a.style_col, a.url_col)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if res['errors']:
        return 2
    return 1 if res['duplicate_groups'] else 0


if __name__ == '__main__':
    sys.exit(main())
