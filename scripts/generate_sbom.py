"""Generate a deterministic CycloneDX-style inventory without exporting secrets."""
from __future__ import annotations
import json,re,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def python_components():
 result=[]
 for file in sorted((ROOT/"backend").glob("requirements*.txt")):
  for raw in file.read_text(encoding="utf-8").splitlines():
   line=raw.strip()
   if not line or line.startswith("#") or line.startswith("-"):continue
   match=re.match(r"([A-Za-z0-9_.-]+)(?:==|>=|~=|<=|>|<)?([^;\s]*)",line)
   if match:result.append({"type":"library","name":match.group(1),"version":match.group(2) or "unspecified","purl":f"pkg:pypi/{match.group(1).lower()}"})
 return result
def javascript_components():
 lock_path=ROOT/"frontend/package-lock.json"
 if not lock_path.is_file():lock_path=ROOT/"package-lock.json"
 lock=json.loads(lock_path.read_text(encoding="utf-8"));result=[]
 for path,meta in sorted(lock.get("packages",{}).items()):
  if not path.startswith("node_modules/"):continue
  name=path.removeprefix("node_modules/");result.append({"type":"library","name":name,"version":meta.get("version","unspecified"),"purl":f"pkg:npm/{name}@{meta.get('version','unspecified')}"})
 return result
def build_sbom():
 components=python_components()+javascript_components();return {"bomFormat":"CycloneDX","specVersion":"1.5","serialNumber":f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL,'https://greyguard.local/sbom')}","version":1,"metadata":{"component":{"type":"application","name":"GreyGuard"}},"components":components}
def main():
 output=ROOT/"artifacts/greyguard-sbom.cdx.json";output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(build_sbom(),indent=2)+"\n",encoding="utf-8");print(output)
if __name__=="__main__":main()
