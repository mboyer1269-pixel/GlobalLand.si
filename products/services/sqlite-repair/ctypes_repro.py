# Exercises the real C API (libsqlite3.so.0) via ctypes because compiled binaries cannot execute in this sandbox (noexec).
# Source question: https://stackoverflow.com/q/79919860 (CC BY-SA 4.0, LUN). Synthetic data. Made by autonomous AI agents (GlobalLand).
import ctypes as C, ctypes.util as U
L=C.CDLL('libsqlite3.so.0')
P=C.c_void_p
L.sqlite3_libversion.restype=C.c_char_p
L.sqlite3_open.argtypes=[C.c_char_p,C.POINTER(P)]
L.sqlite3_exec.argtypes=[P,C.c_char_p,P,P,P]
L.sqlite3_prepare_v2.argtypes=[P,C.c_void_p,C.c_int,C.POINTER(P),C.POINTER(C.c_void_p)]
L.sqlite3_step.argtypes=[P];L.sqlite3_finalize.argtypes=[P];L.sqlite3_close.argtypes=[P]
L.sqlite3_column_count.argtypes=[P];L.sqlite3_column_text.argtypes=[P,C.c_int];L.sqlite3_column_text.restype=C.c_char_p
L.sqlite3_errmsg.argtypes=[P];L.sqlite3_errmsg.restype=C.c_char_p
ROW,DONE=100,101
out=[]
def pr(*a):
  s=' '.join(str(x) for x in a);print(s);out.append(s)
def opendb(seed):
  db=P();L.sqlite3_open(b':memory:',C.byref(db));rc=L.sqlite3_exec(db,seed.encode(),None,None,None);assert rc==0,rc;return db
def before(db,sql):
  buf=C.create_string_buffer(sql.encode());st=P();tail=C.c_void_p()
  rc=L.sqlite3_prepare_v2(db,C.cast(buf,C.c_void_p),-1,C.byref(st),C.byref(tail));pr('BEFORE prepare=',rc)
  rc=L.sqlite3_step(st);pr('BEFORE step=',rc,'tail=',repr(C.string_at(tail.value).decode()));L.sqlite3_finalize(st);return rc
def run_all(db,sql):
  # the fix: prepare_v2 compiles only the first statement; loop on pzTail
  buf=C.create_string_buffer(sql.encode());p=C.cast(buf,C.c_void_p).value;n=0;res=[]
  while p and C.string_at(p,1)!=b'\x00':
    st=P();tail=C.c_void_p()
    rc=L.sqlite3_prepare_v2(db,p,-1,C.byref(st),C.byref(tail))
    if rc!=0: pr('ERROR prepare stmt%d:'%(n+1),L.sqlite3_errmsg(db).decode());return rc,res
    p=tail.value
    if not st.value: continue
    n+=1;cols=L.sqlite3_column_count(st);rows=[]
    while (rc:=L.sqlite3_step(st))==ROW:
      r=tuple((lambda v:None if v is None else v.decode())(L.sqlite3_column_text(st,i)) for i in range(cols));rows.append(r);pr('stmt%d row:'%n,r)
    L.sqlite3_finalize(st)
    if rc!=DONE: pr('ERROR step stmt%d:'%n,rc);return rc,res
    pr('stmt%d done cols=%d rows=%d'%(n,cols,len(rows)));res.append(rows)
  pr('statements=%d'%n);return 0,res
pr('sqlite_version=',L.sqlite3_libversion().decode())
Q='CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM T1'
S="CREATE TABLE TABLE1(id INTEGER, name TEXT); INSERT INTO TABLE1 VALUES(1,'a'),(2,'b'),(3,'c');"
checks={}
pr('== case1 reproduce original code');db=opendb(S);rc=before(db,Q);checks['case1_step_is_SQLITE_DONE_and_tail_unexecuted']=(rc==DONE);L.sqlite3_close(db)
pr('== case2 fixed loop');db=opendb(S);rc,res=run_all(db,Q);checks['case2_second_stmt_returns_3_rows']=(rc==0 and res[-1]==[('1','a'),('2','b'),('3','c')]);L.sqlite3_close(db)
pr('== case3 duplicates+NULL+ORDER BY');db=opendb("CREATE TABLE TABLE1(id INTEGER, name TEXT); INSERT INTO TABLE1 VALUES(2,NULL),(1,'a'),(1,'a'),(3,'z');")
rc,res=run_all(db,Q+' ORDER BY id, name');checks['case3_dups_kept_null_preserved_ordered']=(rc==0 and res[-1]==[('1','a'),('1','a'),('2',None),('3','z')]);L.sqlite3_close(db)
pr('== case4 trailing ; whitespace comment');db=opendb(S);rc,res=run_all(db,Q+';  -- end\n  ');checks['case4_terminates_two_statements']=(rc==0 and len(res)==2 and len(res[-1])==3);L.sqlite3_close(db)
pr('== case5 empty TABLE1');db=opendb('CREATE TABLE TABLE1(id INTEGER, name TEXT);');rc,res=run_all(db,Q);checks['case5_zero_rows']=(rc==0 and res[-1]==[]);L.sqlite3_close(db)
pr('== case6 error in 2nd stmt stops');db=opendb(S);rc,res=run_all(db,'CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM missing; SELECT 1');checks['case6_error_reported_third_not_run']=(rc!=0 and len(res)==1);L.sqlite3_close(db)
import json,pathlib
r={'checks':checks,'passed':sum(checks.values()),'total':len(checks),'transcript':out,'note':'C API exercised via ctypes on system libsqlite3; compiled C binary could not execute (noexec)'}
pathlib.Path('products/services/sqlite-repair/acceptance.json').write_text(json.dumps(r,indent=1))
pr('PASSED %d/%d'%(r['passed'],r['total']))
