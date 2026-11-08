# Boundary checks supporting the revised per-phase limit wording. Made by autonomous AI agents.
import sys,json,time,pathlib
sys.path.insert(0,'products/services/sqlite-repair/fulfillment')
import diagnose as d
D=pathlib.Path('products/services/sqlite-repair/intake/limits-correction');D.mkdir(parents=True,exist_ok=True)
out={}
def err(r,m='all_statements'):
  x=r['runs'][m];return dict(seed_error=x.get('seed_error'),error=x.get('error'),n=len(x.get('statements') or []),elapsed_s=x.get('elapsed_s'),close_rc=x.get('close_rc'))
seed50=' '.join('CREATE TABLE t%d(x);'%i for i in range(50));q50='SELECT 1;'*50
r=d.diagnose(dict(seed_sql=seed50,query_sql=q50));out['T1_seed50_plus_query50']=dict(result=err(r),accepted=r['runs']['all_statements']['error'] is None and 'seed_error' not in r['runs']['all_statements'])
r=d.diagnose(dict(query_sql='SELECT 1;'*51));e=err(r);out['T2_query51']=dict(result=e,statement_limit=(e['error'] or {}).get('kind')=='STATEMENT_LIMIT' and e['n']==50)
r=d.diagnose(dict(seed_sql='SELECT 2;'*51,query_sql='SELECT 3;'));e=err(r);out['T2b_seed51']=dict(result=e,seed_statement_limit=(e['seed_error'] or {}).get('kind')=='STATEMENT_LIMIT')
pad=lambda s,n:s+' '*(n-len(s.encode()))
r=d.diagnose(dict(seed_sql=pad('SELECT 1;',65536),query_sql=pad('SELECT 2;',65536)));e=err(r)
out['T3_seed64KiB_plus_query64KiB']=dict(status=r.get('status'),result=e,accepted=r.get('status')=='OK' and e['error'] is None and e['seed_error'] is None,total_bytes=131072)
r=d.diagnose(dict(query_sql=pad('SELECT 1;',65537)));out['T4_query_65537']=dict(status=r.get('status'),detail=r.get('detail'),rejected=r.get('status')=='INVALID_CASE')
heavy=lambda n:'WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<%d) SELECT count(*) FROM c;'%n
b=d.Box();db=d.mkdb(b);x=d.run(db,b,heavy(20000),False);d.L.sqlite3_close(db);k=b.ops/20000.0
N=int(1.2e6/k)
b=d.Box();db=d.mkdb(b);alone=d.run(db,b,heavy(N),False);ops_alone=b.ops;d.L.sqlite3_close(db)
r=d.diagnose(dict(seed_sql=heavy(N),query_sql=heavy(N)));e=err(r)
out['T5_vm_budget_shared_across_phases']=dict(N=N,ops_counted_one_phase=ops_alone,alone_error=alone['error'],combined=e,
 shared=alone['error'] is None and e['seed_error'] is None and (e['error'] or {}).get('kind')=='INTERRUPTED_BY_LIMIT')
b=d.Box();db=d.mkdb(b);d.run(db,b,'SELECT 1;',False);d1=b.deadline;time.sleep(0.05);d.run(db,b,'SELECT 2;',False);d2=b.deadline;d.L.sqlite3_close(db)
out['T6_deadline_reset_per_phase']=dict(second_deadline_later_s=round(d2-d1,3),reset=d2>d1)
r=d.diagnose(dict(seed_sql='CREATE TABLE a(x); INSERT INTO a VALUES(1);',query_sql='SELECT 1; SELECT x FROM a;',reproduce_first_statement_only=True))
runs=r['runs'];out['T7_separate_modes']=dict(modes=sorted(runs),first_only_n=len(runs['as_written_first_statement_only']['statements']),full_n=len(runs['all_statements']['statements']),close_rcs=[v['close_rc'] for v in runs.values()],
 separate=sorted(runs)==['all_statements','as_written_first_statement_only'] and len(runs['as_written_first_statement_only']['statements'])==1)
out['T8_cooperative_timing']=dict(basis='code inspection of diagnose.py: progress handler registered with N=1000 VM ops; deadline compared only inside that callback; deadline reset at the start of each run() call. No wall-clock overrun was induced in this test.',progress_interval_ops=1000)
out['all_pass']=all([out['T1_seed50_plus_query50']['accepted'],out['T2_query51']['statement_limit'],out['T2b_seed51']['seed_statement_limit'],out['T3_seed64KiB_plus_query64KiB']['accepted'],out['T4_query_65537']['rejected'],out['T5_vm_budget_shared_across_phases']['shared'],out['T6_deadline_reset_per_phase']['reset'],out['T7_separate_modes']['separate']])
out['sqlite_version']=d.L.sqlite3_libversion().decode();out['limits']=d.LIM
json.dump(out,open(D/'boundary-results.json','w'),indent=1,default=str);print(json.dumps(out,indent=1,default=str))
