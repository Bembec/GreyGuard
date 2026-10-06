"""Verify core API behavior against the configured PostgreSQL database."""
import os,subprocess,sys
if not os.environ.get("GREYGUARD_DATABASE_URL","").startswith("postgresql"):raise SystemExit("GREYGUARD_DATABASE_URL must select PostgreSQL.")
tests=["backend/tests/test_security_foundation.py","backend/tests/test_database_compatibility.py"]
result=subprocess.run([sys.executable,"-m","pytest",*tests,"-q"],check=False);raise SystemExit(result.returncode)

