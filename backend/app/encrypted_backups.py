"""Authenticated encryption for verified GreyGuard database backups."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"GREYGUARD-BACKUP-V1\n"

def _key(value: str | None = None) -> bytes:
    encoded = value or os.environ.get("GREYGUARD_BACKUP_KEY", "")
    try:
        key = base64.urlsafe_b64decode(encoded.encode())
    except Exception as error:
        raise ValueError("GREYGUARD_BACKUP_KEY must be URL-safe base64.") from error
    if len(key) != 32:
        raise ValueError("GREYGUARD_BACKUP_KEY must decode to exactly 32 bytes.")
    return key

def _verify_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    if result != "ok":
        raise RuntimeError(f"Database integrity check failed: {result}")

def create_encrypted_backup(source, destination, key_value: str | None = None) -> dict:
    source, destination = Path(source), Path(destination)
    _verify_sqlite(source); destination.parent.mkdir(parents=True, exist_ok=True)
    plaintext = source.read_bytes(); nonce = os.urandom(12)
    metadata = {"format":"GREYGUARD-BACKUP-V1","created_at":datetime.now(timezone.utc).isoformat(),"source":source.name,"plaintext_sha256":hashlib.sha256(plaintext).hexdigest(),"plaintext_size":len(plaintext)}
    aad = json.dumps(metadata,sort_keys=True,separators=(",",":")).encode()
    ciphertext = AESGCM(_key(key_value)).encrypt(nonce, plaintext, aad)
    destination.write_bytes(MAGIC + len(aad).to_bytes(4,"big") + aad + nonce + ciphertext)
    manifest = {**metadata,"encrypted_file":destination.name,"encrypted_sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),"algorithm":"AES-256-GCM"}
    destination.with_suffix(destination.suffix+".manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest

def restore_encrypted_backup(source, destination, key_value: str | None = None, confirm: bool = False) -> Path:
    if not confirm:
        raise ValueError("Encrypted restore requires explicit confirmation.")
    source, destination = Path(source), Path(destination); payload = source.read_bytes()
    if not payload.startswith(MAGIC):
        raise ValueError("Backup format is not recognized.")
    offset=len(MAGIC); aad_size=int.from_bytes(payload[offset:offset+4],"big"); offset+=4
    aad=payload[offset:offset+aad_size];offset+=aad_size;nonce=payload[offset:offset+12];ciphertext=payload[offset+12:]
    plaintext=AESGCM(_key(key_value)).decrypt(nonce,ciphertext,aad)
    metadata=json.loads(aad)
    if hashlib.sha256(plaintext).hexdigest()!=metadata["plaintext_sha256"]:
        raise RuntimeError("Decrypted backup checksum does not match its authenticated metadata.")
    destination.parent.mkdir(parents=True,exist_ok=True)
    handle,path=tempfile.mkstemp(prefix="greyguard-restore-",suffix=".db",dir=destination.parent);os.close(handle)
    temporary=Path(path)
    try:
        temporary.write_bytes(plaintext);_verify_sqlite(temporary);temporary.replace(destination)
    finally:
        if temporary.exists():temporary.unlink()
    return destination

def main() -> None:
    parser=argparse.ArgumentParser(description="GreyGuard encrypted backup operations");commands=parser.add_subparsers(dest="command",required=True)
    create=commands.add_parser("create");create.add_argument("source");create.add_argument("destination")
    restore=commands.add_parser("restore");restore.add_argument("source");restore.add_argument("destination");restore.add_argument("--confirm",action="store_true")
    args=parser.parse_args()
    if args.command=="create":print(json.dumps(create_encrypted_backup(args.source,args.destination),indent=2))
    else:print(f"Restored database to {restore_encrypted_backup(args.source,args.destination,confirm=args.confirm)}")

if __name__=="__main__":main()
