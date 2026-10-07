"""Single source of truth for where GreyGuard stores local data."""

import os
from pathlib import Path

DEFAULT_DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"


def data_directory() -> Path:
    """Return GREYGUARD_DATA_DIR when set, otherwise backend/data.

    Relative values are resolved from the current working directory, which is the
    repository root for development and /app inside the production container.
    """
    configured = os.environ.get("GREYGUARD_DATA_DIR", "").strip()
    return Path(configured).resolve() if configured else DEFAULT_DATA_DIRECTORY
