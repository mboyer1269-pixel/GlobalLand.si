#!/usr/bin/env python3
"""Workaround candidate for forum.ghost.org/t/60053 (built by autonomous AI agents).
Wraps the inline content of <blockquote> elements that contain <br> but no block
children in a single <p>, inside the "html" field of every post in a Ghost
universal-import JSON file. Stdlib only. Ghost importer effect is UNTESTED.
Usage: python3 wrap_blockquote_br.py in.json out.json"""
import json, re, sys
BQ = re.compile(r'(<blockquote\b[^>]*>)(.*?)(</blockquote>)', re.I | re.S)
BLOCK = re.compile(r'<(p|div|ul|ol|h[1-6]|blockquote|figure|pre|table)\b', re.I)
BR = re.compile(r'<br\s*/?>', re.I)
def fix_html(h):
    def rep(m):
        inner = m.group(2)
        if not BR.search(inner) or BLOCK.search(inner):
            return m.group(0)
        return m.group(1) + '<p>' + inner.strip() + '</p>' + m.group(3)
    return BQ.sub(rep, h)
def fix_doc(doc):
    n = 0
    dbs = doc.get('db', [doc]) if isinstance(doc, dict) else []
    for db in dbs:
        for post in (db.get('data', {}) or {}).get('posts', []) or []:
            h = post.get('html')
            if isinstance(h, str):
                new = fix_html(h)
                if new != h:
                    n += 1
                    post['html'] = new
    return n
if __name__ == '__main__':
    doc = json.load(open(sys.argv[1], encoding='utf-8'))
    n = fix_doc(doc)
    json.dump(doc, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'posts changed: {n}')
