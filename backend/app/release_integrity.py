"""Create and verify signed GreyGuard release manifests."""
from __future__ import annotations
import base64,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey

def sha256(path: Path) -> str:return hashlib.sha256(path.read_bytes()).hexdigest()

def create_manifest(root: Path,version: str,commit: str,files: list[str]) -> dict:
 if not version or not commit:raise ValueError("Release version and commit are required.")
 artifacts=[]
 for relative in sorted(set(files)):
  path=root/relative
  if not path.is_file():raise FileNotFoundError(relative)
  artifacts.append({"path":relative.replace("\\","/"),"sha256":sha256(path),"size_bytes":path.stat().st_size})
 return {"schema":"greyguard.release.v1","version":version,"commit":commit,"created_at":datetime.now(timezone.utc).isoformat(),"artifacts":artifacts}

def canonical(manifest: dict) -> bytes:return json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()

def _private(value: str | None=None) -> Ed25519PrivateKey:
 encoded=value or os.environ.get("GREYGUARD_RELEASE_SIGNING_KEY","")
 try:key=base64.urlsafe_b64decode(encoded)
 except Exception as error:raise ValueError("Release signing key must be URL-safe base64.") from error
 if len(key)!=32:raise ValueError("Release signing key must decode to 32 bytes.")
 return Ed25519PrivateKey.from_private_bytes(key)

def sign_manifest(manifest: dict,key_value: str | None=None) -> dict:
 private=_private(key_value);public=private.public_key().public_bytes_raw();signature=private.sign(canonical(manifest))
 return {"algorithm":"Ed25519","public_key":base64.urlsafe_b64encode(public).decode(),"signature":base64.urlsafe_b64encode(signature).decode(),"manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest()}

def verify_manifest(manifest: dict,signature: dict,root: Path | None=None) -> bool:
 if signature.get("algorithm")!="Ed25519":raise ValueError("Unsupported release signature algorithm.")
 if hashlib.sha256(canonical(manifest)).hexdigest()!=signature.get("manifest_sha256"):raise ValueError("Release manifest checksum mismatch.")
 public=Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(signature["public_key"]));public.verify(base64.urlsafe_b64decode(signature["signature"]),canonical(manifest))
 if root:
  for artifact in manifest["artifacts"]:
   path=root/artifact["path"]
   if not path.is_file() or sha256(path)!=artifact["sha256"]:raise ValueError(f"Release artifact verification failed: {artifact['path']}")
 return True
