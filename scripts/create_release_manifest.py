"""Generate and optionally verify a signed release evidence bundle."""
import argparse,json,os
from pathlib import Path
from backend.app.release_integrity import create_manifest,sign_manifest,verify_manifest
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_FILES=["deployment/backend.Dockerfile","deployment/frontend.Dockerfile","docker-compose.production.yml","artifacts/greyguard-sbom.cdx.json"]
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--version",required=True);parser.add_argument("--commit",required=True);parser.add_argument("--output",default="artifacts/release");parser.add_argument("--verify",action="store_true");args=parser.parse_args()
 output=ROOT/args.output;output.mkdir(parents=True,exist_ok=True);manifest=create_manifest(ROOT,args.version,args.commit,DEFAULT_FILES);signature=sign_manifest(manifest)
 manifest_path=output/"release-manifest.json";signature_path=output/"release-manifest.sig.json";manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8");signature_path.write_text(json.dumps(signature,indent=2)+"\n",encoding="utf-8")
 if args.verify:verify_manifest(manifest,signature,ROOT)
 print(manifest_path);print(signature_path)
if __name__=="__main__":main()
