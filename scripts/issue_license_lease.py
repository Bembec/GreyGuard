"""Vendor side of self-hosted licensing: create a licensing key pair, or sign a lease for one install.

  python -m scripts.issue_license_lease keygen
  python -m scripts.issue_license_lease issue --install-id ins_... --licensee "Example Ltd" \\
      --plan ENTERPRISE --days 30 --grace-days 14

`issue` reads the private key from GREYGUARD_LICENSE_PRIVATE_KEY. The private key never belongs on
a customer install; the install only gets the public key (GREYGUARD_LICENSE_PUBLIC_KEY) and the
lease, which an install operator installs with PUT /license.
"""
import argparse
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from backend.app.licensing import MAX_GRACE_DAYS, MAX_LEASE_DAYS, _b64encode, issue_lease


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("keygen", help="Print a new licensing key pair.")
    issue = commands.add_parser("issue", help="Print a signed lease.")
    issue.add_argument("--install-id", required=True)
    issue.add_argument("--licensee", required=True)
    issue.add_argument("--plan", required=True, choices=["FOUNDATION", "ENTERPRISE", "DEDICATED"])
    issue.add_argument("--days", type=int, required=True)
    issue.add_argument("--grace-days", type=int, default=14)
    args = parser.parse_args()

    if args.command == "keygen":
        key = Ed25519PrivateKey.generate()
        print("GREYGUARD_LICENSE_PRIVATE_KEY=" + _b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())))
        print("GREYGUARD_LICENSE_PUBLIC_KEY=" + _b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))
        return
    private_key = os.getenv("GREYGUARD_LICENSE_PRIVATE_KEY", "")
    if not private_key:
        sys.exit("GREYGUARD_LICENSE_PRIVATE_KEY is not set.")
    if not 1 <= args.days <= MAX_LEASE_DAYS or not 0 <= args.grace_days <= MAX_GRACE_DAYS:
        sys.exit(f"--days must be 1-{MAX_LEASE_DAYS} and --grace-days 0-{MAX_GRACE_DAYS}.")
    print(issue_lease(private_key, licensee=args.licensee, install=args.install_id, plan=args.plan,
                      days=args.days, grace_days=args.grace_days))


if __name__ == "__main__":
    main()
