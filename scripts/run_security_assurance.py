"""Run GreyGuard's fixed security assurance matrix without accepting commands."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MATRIX=json.loads((ROOT/"assurance/security-test-matrix.json").read_text(encoding="utf-8"))

def run(command:list[str],cwd=ROOT)->None:
 result=subprocess.run(command,cwd=cwd,check=False)
 if result.returncode:raise SystemExit(result.returncode)

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--group",choices=["all",*MATRIX["backend_groups"]],default="all");parser.add_argument("--skip-frontend",action="store_true");args=parser.parse_args()
 files=[]
 for name,items in MATRIX["backend_groups"].items():
  if args.group in {"all",name}:files.extend(items)
 files=list(dict.fromkeys(files));run([sys.executable,"-m","pytest",*files,"-q"])
 if not args.skip_frontend:
  run(["npm.cmd","test","--","--run"],ROOT/"frontend");run(["npm.cmd","run","build"],ROOT/"frontend")
 print("GreyGuard security assurance matrix passed.")

if __name__=="__main__":main()

