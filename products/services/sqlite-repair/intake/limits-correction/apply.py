# Narrow wording correction of pending SQLite intake limits. Made by autonomous AI agents.
import hashlib,json,pathlib
S=pathlib.Path('products/sites/sqlite-statement-diagnostic')
D=pathlib.Path('products/services/sqlite-repair/intake/limits-correction');D.mkdir(parents=True,exist_ok=True)
h=lambda b:hashlib.sha256(b).hexdigest()
EN_OLD='never your application code, Python, shell, extensions, <code>ATTACH</code>, <code>VACUUM</code> or file paths, with at most 50 statements, 64 KiB of SQL and 2 seconds per run.'
EN_NEW=('never your application code, Python, shell, extensions, <code>ATTACH</code>, <code>VACUUM</code> or file paths. '
'Limits apply per phase, not to the whole request: <code>seed_sql</code> and <code>query_sql</code> may each contain at most 50 statements and 64 KiB of SQL (so up to 100 statements and 128 KiB in total), and each phase has its own 2-second deadline. '
'That deadline and a budget of about 2,000,000 virtual-machine steps shared by both phases of a run are checked cooperatively by a progress handler every 1,000 steps while SQLite executes, so they are not a hard wall-clock limit and a run can take longer. '
'If you say <code>prepare</code> is called once, a separate first-statement-only run on a fresh in-memory database, with its own budgets, is added to the full prepare/step/finalize loop run. '
'Only the first 50 rows of each statement are kept.')
FR_OLD='(jamais votre code, Python, shell, extensions, ATTACH, VACUUM ni chemins de fichiers ; au plus 50 instructions, 64 Kio et 2 secondes).'
FR_NEW=('(jamais votre code, Python, shell, extensions, ATTACH, VACUUM ni chemins de fichiers). '
'Les limites s&rsquo;appliquent par phase et non à l&rsquo;ensemble de la demande : <code>seed_sql</code> et <code>query_sql</code> peuvent chacun contenir au plus 50 instructions et 64 Kio de SQL (soit jusqu&rsquo;à 100 instructions et 128 Kio au total), et chaque phase a son propre délai de 2 secondes. '
'Ce délai et un budget d&rsquo;environ 2 000 000 étapes de machine virtuelle, partagé par les deux phases d&rsquo;une exécution, sont vérifiés de façon coopérative toutes les 1 000 étapes pendant que SQLite exécute ; ce n&rsquo;est pas une limite stricte de temps réel et une exécution peut durer plus longtemps. '
'Si vous indiquez que <code>prepare</code> n&rsquo;est appelé qu&rsquo;une fois, une exécution distincte limitée à la première instruction, sur une nouvelle base en mémoire et avec ses propres budgets, s&rsquo;ajoute à l&rsquo;exécution de la boucle complète. '
'Seules les 50 premières lignes de chaque instruction sont conservées.')
LL_OLD='Only SQL runs, in-memory, max 50 statements / 64 KiB / 2 s.'
LL_NEW=('Only SQL runs, in-memory. Limits are per phase: seed_sql and query_sql each max 50 statements and 64 KiB (up to 100 statements / 128 KiB total); '
'2 s deadline per phase and ~2,000,000 VM steps per run shared by both phases, checked cooperatively every 1,000 steps (not a hard wall-clock cap). '
'If prepare is called once, a separate first-statement-only run on a fresh database is added. First 50 rows per statement kept.')
res={}
for name,pairs,base in [('index.html',[(EN_OLD,EN_NEW),(FR_OLD,FR_NEW)],'389c137a2782b830dd20bb0ec174bfd2dacea49be1d1663413ba32914209938f'),('llms.txt',[(LL_OLD,LL_NEW)],'1a42a487ef5e7317461d3b333089fa2bf8f61f22f5f904c29e0e7677e702d97b')]:
  p=S/name;orig=p.read_text(encoding='utf-8');assert h(orig.encode())==base,(name,'baseline mismatch')
  new=orig
  for o,n in pairs:
    assert new.count(o)==1,(name,'old count');new=new.replace(o,n)
  rev=new
  for o,n in pairs: rev=rev.replace(n,o)
  p.write_text(new,encoding='utf-8')
  res[name]=dict(before=base,after=h(new.encode()),replacements=len(pairs),reverse_restores_pending_baseline=h(rev.encode())==base)
idx=(S/'index.html').read_text(encoding='utf-8');ll=(S/'llms.txt').read_text(encoding='utf-8')
added=EN_NEW+FR_NEW+LL_NEW
res['checks']=dict(
 mailto_recipient_subject_count=idx.count('mailto:globalland@agentmail.to?subject=site%3Asqlite-statement-diagnostic%20interest'),
 identifier_present=idx.count('site:sqlite-statement-diagnostic')>=3 and 'site:sqlite-statement-diagnostic' in ll,
 ai_disclosure_en=('Made by autonomous AI agents (GlobalLand).' in idx),ai_disclosure_fr=('agents d&rsquo;IA autonomes' in idx),ai_disclosure_llms='Made by autonomous AI agents' in ll,
 no_price_tokens_added=not any(t in added for t in ['$','CAD','USD','EUR','€','prix :','price:']),
 no_script_tag='<script' not in idx.lower(),
 no_time_promise_added=not any(t in added.lower() for t in ['within ','guarantee','garanti','hours','heures']),
 per_phase_en='per phase' in EN_NEW,per_phase_fr='par phase' in FR_NEW,per_phase_llms='per phase' in LL_NEW,
 not_hard_wallclock_en='not a hard wall-clock limit' in EN_NEW,not_hard_wallclock_fr='pas une limite stricte' in FR_NEW,
 separate_mode_en='separate first-statement-only run' in EN_NEW,separate_mode_fr='distincte' in FR_NEW,
 old_aggregate_wording_removed=(EN_OLD not in idx and FR_OLD not in idx and LL_OLD not in ll))
res['hashes']=dict(index=h(idx.encode()),llms=h(ll.encode()),sample=h((S/'repro/sample-inline-response.txt').read_bytes()))
json.dump(res,open(D/'apply-result.json','w'),indent=1)
print(json.dumps(res,indent=1))
