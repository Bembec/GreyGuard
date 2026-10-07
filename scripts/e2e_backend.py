"""Start an isolated GreyGuard backend for the browser end-to-end tests.

It uses a fresh .e2e-data folder on every run and never touches backend/data,
PostgreSQL or the shared development PIN. Playwright starts and stops it.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".e2e-data"


def main() -> None:
    password = os.environ.get("GREYGUARD_BOOTSTRAP_PASSWORD", "")
    if len(password) < 16:
        sys.exit("The Playwright configuration must provide GREYGUARD_BOOTSTRAP_PASSWORD.")
    shutil.rmtree(DATA, ignore_errors=True)
    DATA.mkdir()
    for unsafe in ("GREYGUARD_DATABASE_URL", "GREYGUARD_ADMIN_PIN"):
        os.environ.pop(unsafe, None)
    os.environ.update({
        "GREYGUARD_ENV": "test",
        "GREYGUARD_DATA_DIR": str(DATA),
        "GREYGUARD_BOOTSTRAP_NAME": "E2E Administrator",
        "GREYGUARD_ALLOWED_ORIGINS": "http://127.0.0.1:4173",
        "GREYGUARD_TRUSTED_HOSTS": "127.0.0.1,localhost",
    })
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import uvicorn  # imported after the environment is set, so every module sees it

    uvicorn.run("backend.app.api:app", host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
