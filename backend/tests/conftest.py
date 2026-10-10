"""Test-session safety net: no test may read or write the real data directory.

Every backend module derives its database, state and sandbox paths from paths.data_directory()
when it is first imported. Many tests redirect a module's database_path to a tmp_path, but any
module a test forgets (or reaches only indirectly) would otherwise fall back to backend/data - the
developer's real local database. Pytest loads this file before importing any test module, so
pointing GREYGUARD_DATA_DIR at a throwaway directory here means every module's import-time path
lands inside it. Individual tests still isolate themselves further with tmp_path as before.
"""
import atexit
import os
import shutil
import tempfile

_SESSION_DATA_DIR = tempfile.mkdtemp(prefix="greyguard-test-data-")
os.environ["GREYGUARD_DATA_DIR"] = _SESSION_DATA_DIR
atexit.register(shutil.rmtree, _SESSION_DATA_DIR, ignore_errors=True)
