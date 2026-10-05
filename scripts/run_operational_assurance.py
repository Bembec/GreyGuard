"""Run fixed recovery, kill-switch, and deployment assurance exercises."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMANDS=([sys.executable,"-m","pytest","backend/tests/test_production_readiness.py","backend/tests/test_execution_isolation.py","backend/tests/test_isolation_operations.py","backend/tests/test_policy_governance.py","-q"],[sys.executable,"scripts/generate_sbom.py"])
def main():
 for command in COMMANDS:
  result=subprocess.run(command,cwd=ROOT,check=False)
  if result.returncode:raise SystemExit(result.returncode)
 print("GreyGuard operational assurance exercises passed.")
if __name__=="__main__":main()
