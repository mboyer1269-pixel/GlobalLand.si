# Acceptance checks for diagnose.py (GlobalLand; made by autonomous AI agents). Synthetic cases only.
import json, os, sys, time, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose as D
S="CREATE TABLE TABLE1(id INTEGER, name TEXT); INSERT INTO TABLE1 VALUES(1,'a'),(2,'b'),(3,'c');"
Q='CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM T1'
C={}
def ok(r,m='all_statements'): x=r['runs'][m]; return (not x['open_statements_after_run']) and x['close_rc']==0
def mono(st): return all(a['end_byte']<=b['start_byte'] for a,b in zip(st,st[1:])) and all(s['start_byte']<s['end_byte'] for s in st)
reps={}
def go(name,case): r=D.diagnose(case); reps[name]=r; return r
r=go('public',dict(case_id='public-so-79919860',seed_sql=S,query_sql=Q,reproduce_first_statement_only=True,expected_last_rows=[['1','a'],['2','b'],['3','c']]))
w=r['runs']['as_written_first_statement_only'];a=r['runs']['all_statements']
C['public_as_written_runs_only_first_and_reports_tail']=len(w['statements'])==1 and w['unexecuted_tail']=='SELECT * FROM T1' and w['error'] is None
C['public_fixed_loop_two_statements_expected_rows']=len(a['statements'])==2 and r['expected_match'] is True
C['public_tail_contiguous_and_reaches_end']=a['statements'][0]['end_byte']==a['statements'][1]['start_byte'] and a['final_byte']==len(Q.encode()) and a['unexecuted_tail'] is None
C['public_all_finalized_close_ok_both_runs']=ok(r) and ok(r,'as_written_first_statement_only')
r=go('prepare_error',dict(query_sql='CREATE TABLE t(x); INSERT INTO t VALUES(1); SELEC x FROM t; INSERT INTO t VALUES(2)'))
a=r['runs']['all_statements'];e=a['error']
C['prepare_error_stops_at_stmt3_with_message_and_offset']=e['phase']=='prepare' and e['statement_index']==3 and 'syntax error' in e['message'] and e['error_offset']>=0 and len(a['statements'])==2
C['prepare_error_tail_unexecuted_and_finalized']=a['unexecuted_tail'].startswith('SELEC x') and ok(r)
r=go('step_error_constraint',dict(seed_sql="CREATE TABLE u(id INTEGER PRIMARY KEY, v TEXT UNIQUE); INSERT INTO u(v) VALUES('x');",query_sql="INSERT INTO u(v) VALUES('y'); INSERT INTO u(v) VALUES('x'); SELECT count(*) FROM u"))
a=r['runs']['all_statements'];e=a['error'];s2=a['statements'][1]
C['step_error_constraint_rc19_finalize_rc19_third_not_run']=e['phase']=='step' and e['rc']==19 and 'UNIQUE constraint failed' in e['message'] and s2['finalize_rc']==19 and len(a['statements'])==2 and a['unexecuted_tail']=='SELECT count(*) FROM u' and ok(r)
r=go('step_error_after_rows',dict(query_sql='SELECT x, abs(x) FROM (SELECT 1 AS x UNION ALL SELECT -9223372036854775808); SELECT 2'))
a=r['runs']['all_statements'];e=a['error']
C['step_error_after_one_row_reported_and_finalized']=e['kind']=='STEP_ERROR' and e['rows_before_error']==1 and 'overflow' in e['message'] and a['unexecuted_tail']=='SELECT 2' and ok(r)
M='  -- lead\n CREATE TABLE m(a); ;; INSERT INTO m VALUES(2),(1); /* mid */ SELECT a FROM m ORDER BY a;  -- trailing\n'
r=go('multi_statement_edges',dict(query_sql=M,expected_last_rows=[['1'],['2']]))
a=r['runs']['all_statements']
C['multi_statement_skips_empty_and_comments_three_executed']=len(a['statements'])==3 and r['expected_match'] is True and a['unexecuted_tail'] is None and mono(a['statements']) and ok(r)
r=go('policy_attach',dict(query_sql="ATTACH DATABASE '/tmp/gl_attach_probe.db' AS x; SELECT 1"))
a=r['runs']['all_statements']
C['attach_refused_no_file_created']=a['error']['phase']=='prepare' and len(a['statements'])==0 and not os.path.exists('/tmp/gl_attach_probe.db') and ok(r)
r=go('policy_load_extension',dict(query_sql="SELECT load_extension('/tmp/x')"))
a=r['runs']['all_statements']
C['load_extension_refused']=a['error'] is not None and a['error']['phase'] in ('prepare','step') and ok(r)
r=go('policy_vacuum',dict(query_sql="CREATE TABLE v(a); /*c*/ VACUUM INTO '/tmp/gl_vac_probe.db'"))
a=r['runs']['all_statements']
C['vacuum_into_refused_not_executed']=a['error']['kind']=='VACUUM_DENIED' and not os.path.exists('/tmp/gl_vac_probe.db') and ok(r)
r=go('policy_pragma',dict(query_sql='PRAGMA writable_schema=ON; SELECT 1'))
C['unlisted_pragma_refused']=r['runs']['all_statements']['error']['phase']=='prepare' and 'PRAGMA writable_schema' in r['runs']['all_statements']['denied']
t=time.monotonic();r=go('runtime_bound',dict(query_sql='WITH RECURSIVE c(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM c) SELECT count(*) FROM c'))
a=r['runs']['all_statements']
C['infinite_cte_interrupted_within_5s']=a['error']['kind']=='INTERRUPTED_BY_LIMIT' and time.monotonic()-t<5 and ok(r)
r=go('statement_limit',dict(query_sql='SELECT 1;'*60))
a=r['runs']['all_statements']
C['statement_limit_50']=a['error']['kind']=='STATEMENT_LIMIT' and len(a['statements'])==50 and ok(r)
C['invalid_case_rejected']=D.diagnose(dict(query_sql='SELECT 1',python='import os'))['status']=='INVALID_CASE'
res=dict(sqlite_version=D.L.sqlite3_libversion().decode(),python=sys.version.split()[0],checks=C,passed=sum(C.values()),total=len(C),
 note='Executed locally in the public offline EXEC sandbox on synthetic cases. Not the private mail cycle; no customer request, no recipient delivery.')
pathlib.Path('check-results.json').write_text(json.dumps(res,indent=1))
pathlib.Path('case-reports.json').write_text(json.dumps(reps,indent=1,ensure_ascii=False))
print(json.dumps(res,indent=1))
