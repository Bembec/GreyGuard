"""Non-destructive encrypted-backup recovery drill using temporary storage."""
import base64,os,sqlite3,tempfile,time
from pathlib import Path
from backend.app.database import database_path
from backend.app.encrypted_backups import create_encrypted_backup,restore_encrypted_backup
def main():
 source=Path(database_path)
 if not source.is_file():raise SystemExit(f"Database does not exist: {source}")
 key=os.environ.get("GREYGUARD_BACKUP_KEY") or base64.urlsafe_b64encode(os.urandom(32)).decode();started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix="greyguard-dr-") as folder:
  root=Path(folder);encrypted=root/"dr-backup.ggb";restored=root/"restored.db";manifest=create_encrypted_backup(source,encrypted,key);restore_encrypted_backup(encrypted,restored,key,confirm=True)
  connection=sqlite3.connect(restored)
  try:tables=connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
  finally:connection.close()
  if tables<1:raise RuntimeError("Recovery drill restored no database tables.")
 print(f"Disaster recovery drill passed: {tables} tables, {manifest['plaintext_size']} bytes, {time.monotonic()-started:.2f}s RTO rehearsal")
if __name__=="__main__":main()
