import base64
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from backend.app.release_integrity import create_manifest,sign_manifest,verify_manifest

def signing_key():return base64.urlsafe_b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode()

def test_signed_release_manifest_verifies_artifacts(tmp_path):
 (tmp_path/"artifact.txt").write_text("trusted release",encoding="utf-8")
 manifest=create_manifest(tmp_path,"v1.2.3","a"*40,["artifact.txt"]);signature=sign_manifest(manifest,signing_key())
 assert verify_manifest(manifest,signature,tmp_path)

def test_modified_artifact_is_rejected(tmp_path):
 path=tmp_path/"artifact.txt";path.write_text("original",encoding="utf-8")
 manifest=create_manifest(tmp_path,"v1","b"*40,["artifact.txt"]);signature=sign_manifest(manifest,signing_key());path.write_text("changed",encoding="utf-8")
 with pytest.raises(ValueError,match="artifact verification failed"):verify_manifest(manifest,signature,tmp_path)

def test_modified_manifest_is_rejected(tmp_path):
 path=tmp_path/"artifact.txt";path.write_text("original",encoding="utf-8")
 manifest=create_manifest(tmp_path,"v1","c"*40,["artifact.txt"]);signature=sign_manifest(manifest,signing_key());manifest["version"]="v2"
 with pytest.raises(ValueError,match="checksum mismatch"):verify_manifest(manifest,signature)
