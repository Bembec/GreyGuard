"""Inventory SQLite coupling before the controlled PostgreSQL migration."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

SQLITE_PATTERNS={"stdlib_import":r"(?m)^import\s+sqlite3(?:\s|$)","unsupported_replace":r"INSERT\s+OR\s+REPLACE(?!\s+INTO\s+observability_correlations)"}
COMPATIBILITY_FILES={"db_compat.py","database_ops.py","encrypted_backups.py","migration_readiness.py"}

def inventory(source_root: Path) -> dict:
    files=[];totals={name:0 for name in SQLITE_PATTERNS}
    for path in sorted(source_root.glob("*.py")):
        if path.name in COMPATIBILITY_FILES:continue
        text=path.read_text(encoding="utf-8")
        counts={name:len(re.findall(pattern,text,re.IGNORECASE)) for name,pattern in SQLITE_PATTERNS.items()}
        if any(counts.values()):
            files.append({"file":path.name,"counts":counts});
            for name,value in counts.items():totals[name]+=value
    return {"ready_for_postgresql":not any(totals.values()),"files_requiring_conversion":len(files),"totals":totals,"files":files}

def validate_postgresql_url(value: str) -> str:
    if not value.startswith(("postgresql://","postgresql+psycopg://")):
        raise ValueError("PostgreSQL URL must use postgresql:// or postgresql+psycopg://.")
    if "@" not in value or "/" not in value.rsplit("@",1)[-1]:
        raise ValueError("PostgreSQL URL must include credentials, host, and database name.")
    return value

def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--source",default="backend/app");parser.add_argument("--output")
    args=parser.parse_args();result=inventory(Path(args.source));rendered=json.dumps(result,indent=2)
    if args.output:Path(args.output).write_text(rendered+"\n",encoding="utf-8")
    print(rendered)

if __name__=="__main__":main()
