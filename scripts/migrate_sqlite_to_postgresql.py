"""One-way, evidenced SQLite-to-PostgreSQL migration rehearsal."""
import argparse,hashlib,json,os,sqlite3
from datetime import datetime,timezone
from pathlib import Path
import psycopg

def quote(name):
 if not name.replace("_","").isalnum():raise ValueError(f"Unsafe identifier: {name}")
 return '"'+name+'"'

def migrate(source: Path,url: str,confirm: bool=False) -> dict:
 if not confirm:raise ValueError("Migration requires explicit confirmation.")
 if not url.startswith(("postgresql://","postgresql+psycopg://")):raise ValueError("A PostgreSQL URL is required.")
 source_hash=hashlib.sha256(source.read_bytes()).hexdigest();evidence={"started_at":datetime.now(timezone.utc).isoformat(),"source_sha256":source_hash,"tables":{}}
 sqlite=sqlite3.connect(source);sqlite.row_factory=sqlite3.Row;postgres=psycopg.connect(url.replace("postgresql+psycopg://","postgresql://"))
 try:
  source_tables=[row[0] for row in sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
  target_tables={row[0] for row in postgres.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
  missing=[name for name in source_tables if name not in target_tables]
  if missing:raise RuntimeError("PostgreSQL schema is missing tables: "+", ".join(missing))
  postgres.execute("SET session_replication_role = replica")
  for table in source_tables:postgres.execute(f"TRUNCATE TABLE {quote(table)} CASCADE")
  for table in source_tables:
   columns=[row[1] for row in sqlite.execute(f"PRAGMA table_info({quote(table)})")];rows=sqlite.execute(f"SELECT * FROM {quote(table)}").fetchall()
   if rows:
    placeholders=",".join(["%s"]*len(columns));column_sql=",".join(quote(value) for value in columns)
    postgres.executemany(f"INSERT INTO {quote(table)} ({column_sql}) VALUES ({placeholders})",[tuple(row) for row in rows])
   evidence["tables"][table]={"rows":len(rows),"columns":len(columns)}
  postgres.execute("SET session_replication_role = DEFAULT");postgres.commit()
  for table,detail in evidence["tables"].items():
   target_count=postgres.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]
   if target_count!=detail["rows"]:raise RuntimeError(f"Row-count mismatch for {table}")
  evidence["completed_at"]=datetime.now(timezone.utc).isoformat();evidence["verified"]=True;return evidence
 except Exception:postgres.rollback();raise
 finally:sqlite.close();postgres.close()

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--source",required=True);parser.add_argument("--database-url",default=os.environ.get("GREYGUARD_DATABASE_URL"));parser.add_argument("--evidence",default="artifacts/postgresql-migration-evidence.json");parser.add_argument("--confirm",action="store_true");args=parser.parse_args()
 evidence=migrate(Path(args.source),args.database_url or "",args.confirm);output=Path(args.evidence);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8");print(output)
if __name__=="__main__":main()
