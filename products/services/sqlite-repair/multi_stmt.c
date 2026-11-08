#include <stdio.h>
#include <sqlite3.h>
/* Reproduction and fix for https://stackoverflow.com/q/79919860 (CC BY-SA 4.0, asked by LUN).
   Synthetic data only. Made by autonomous AI agents (GlobalLand). */
static sqlite3 *open_seeded(const char *seed){sqlite3 *db=0;char *e=0;sqlite3_open(":memory:",&db);
 if(sqlite3_exec(db,seed,0,0,&e)!=SQLITE_OK){printf("SEED_ERR %s\n",e);sqlite3_free(e);}return db;}
/* Original pattern from the question: one prepare, one step. */
static void before(sqlite3 *db,const char *sql){sqlite3_stmt *st=0;const char *tail=0;
 int rc=sqlite3_prepare_v2(db,sql,-1,&st,&tail);printf("BEFORE prepare=%d\n",rc);
 rc=sqlite3_step(st);printf("BEFORE step=%d (SQLITE_ROW=%d SQLITE_DONE=%d) tail=\"%s\"\n",rc,SQLITE_ROW,SQLITE_DONE,tail);
 sqlite3_finalize(st);}
/* Fix: prepare_v2 compiles only the FIRST statement; loop on pzTail. */
static int run_all(sqlite3 *db,const char *sql){const char *p=sql;int n=0;
 while(p && *p){sqlite3_stmt *st=0;const char *tail=0;
  int rc=sqlite3_prepare_v2(db,p,-1,&st,&tail);
  if(rc!=SQLITE_OK){printf("ERROR prepare stmt%d: %s\n",n+1,sqlite3_errmsg(db));return rc;}
  p=tail; if(!st) continue; /* only whitespace/comments left */
  n++; int cols=sqlite3_column_count(st),rows=0;
  while((rc=sqlite3_step(st))==SQLITE_ROW){rows++;printf("stmt%d row:",n);
   for(int i=0;i<cols;i++){const unsigned char *v=sqlite3_column_text(st,i);printf(" %s",v?(const char*)v:"NULL");}printf("\n");}
  if(rc!=SQLITE_DONE){printf("ERROR step stmt%d: %s\n",n,sqlite3_errmsg(db));sqlite3_finalize(st);return rc;}
  printf("stmt%d done cols=%d rows=%d\n",n,cols,rows);sqlite3_finalize(st);}
 printf("statements=%d\n",n);return SQLITE_OK;}
int main(void){printf("sqlite_version=%s\n",sqlite3_libversion());
 const char *Q="CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM T1";
 const char *S="CREATE TABLE TABLE1(id INTEGER, name TEXT); INSERT INTO TABLE1 VALUES(1,'a'),(2,'b'),(3,'c');";
 sqlite3 *db;
 printf("== case1 reproduce (question SQL, original code)\n");db=open_seeded(S);before(db,Q);sqlite3_close(db);
 printf("== case2 fixed loop, question SQL\n");db=open_seeded(S);run_all(db,Q);sqlite3_close(db);
 printf("== case3 duplicates + NULL + ORDER BY\n");
 db=open_seeded("CREATE TABLE TABLE1(id INTEGER, name TEXT); INSERT INTO TABLE1 VALUES(2,NULL),(1,'a'),(1,'a'),(3,'z');");
 run_all(db,"CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM T1 ORDER BY id, name");sqlite3_close(db);
 printf("== case4 trailing semicolon, whitespace and comment\n");db=open_seeded(S);
 run_all(db,"CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM T1;  -- end\n  ");sqlite3_close(db);
 printf("== case5 empty TABLE1\n");db=open_seeded("CREATE TABLE TABLE1(id INTEGER, name TEXT);");run_all(db,Q);sqlite3_close(db);
 printf("== case6 error in second statement stops loop\n");db=open_seeded(S);
 int rc=run_all(db,"CREATE TEMPORARY TABLE T1 AS SELECT * FROM TABLE1 ; SELECT * FROM missing; SELECT 1");printf("rc=%d\n",rc);sqlite3_close(db);
 return 0;}
