# Renders an inline EN/FR diagnostic reply from a diagnose.py report. GlobalLand, made by autonomous AI agents.
import json, re, sys, html
def quote(path):
  t=html.unescape(re.sub(r'<[^>]+>',' ',open(path,encoding='utf-8').read()));t=re.sub(r'\s+',' ',t)
  m=re.search(r'If pzTail is not NULL[^.]*\.',t);return m.group(0).strip() if m else None
def render(rep,q):
  w=rep['runs'].get('as_written_first_statement_only');a=rep['runs']['all_statements'];L=[]
  L.append('SQLite diagnosis (synthetic example) / Diagnostic SQLite (exemple synthetique)')
  L.append('Prepared by autonomous AI agents (GlobalLand). / Prepare par des agents IA autonomes (GlobalLand).')
  L.append('Engine: real SQLite %s C API via Python ctypes, in-memory database only.'%rep['sqlite_version'])
  if w:
    L.append('\n[Observed, as written] sqlite3_prepare_v2 compiled %d statement(s); unexecuted tail: %r'%(len(w['statements']),w['unexecuted_tail']))
  ex=[s for s in a['statements'] if s.get('executed')]
  L.append('[Observed, corrected loop] %d statement(s) executed; last statement rows: %s'%(len(ex),json.dumps(ex[-1]['rows'] if ex else None)))
  if 'expected_match' in rep: L.append('Expected rows match: %s'%rep['expected_match'])
  if a.get('error'): L.append('Stopped on error: %s'%json.dumps(a['error'],ensure_ascii=False))
  L.append('All statements finalized: %s; sqlite3_close rc=%d'%(not a['open_statements_after_run'],a['close_rc']))
  L.append('\nCause: sqlite3_prepare_v2 compiles only the first statement of the input.')
  if q: L.append('Official documentation (https://www.sqlite.org/c3ref/prepare.html): "%s"'%q)
  L.append('Correction: loop on pzTail; for each non-NULL statement step until SQLITE_DONE, finalize it, stop on the first error and report sqlite3_errmsg.')
  L.append('''\n  const char *p = sql, *tail;\n  while (p && *p) {\n    sqlite3_stmt *st = NULL;\n    int rc = sqlite3_prepare_v2(db, p, -1, &st, &tail);\n    if (rc != SQLITE_OK) { fprintf(stderr, "%s\\n", sqlite3_errmsg(db)); break; }\n    p = tail;\n    if (!st) continue;            /* whitespace or comment only */\n    while ((rc = sqlite3_step(st)) == SQLITE_ROW) { /* read columns */ }\n    if (rc != SQLITE_DONE) fprintf(stderr, "%s\\n", sqlite3_errmsg(db));\n    sqlite3_finalize(st);\n    if (rc != SQLITE_DONE) break;\n  }''')
  L.append('\nLimits: the C snippet above was not compiled or executed here; the same loop was executed through ctypes. Synthetic data only; your application, driver, build options and real schema were not tested. Not professional advice; no price, order or guarantee implied.')
  L.append('Limites : l\'extrait C n\'a pas ete compile ni execute ici ; la meme boucle a ete executee via ctypes. Donnees synthetiques uniquement ; votre application et votre schema reels n\'ont pas ete testes. Aucun prix, commande ni garantie.')
  L.append('Cause (FR) : sqlite3_prepare_v2 ne compile que la premiere instruction ; il faut boucler sur pzTail, executer puis finaliser chaque instruction et s\'arreter a la premiere erreur.')
  return '\n'.join(L)
if __name__=='__main__':
  rep=json.load(open(sys.argv[1],encoding='utf-8'));rep=rep.get(sys.argv[3],rep) if len(sys.argv)>3 else rep
  print(render(rep,quote(sys.argv[2])))
