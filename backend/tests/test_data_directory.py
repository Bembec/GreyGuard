"""GREYGUARD_DATA_DIR controls where local data is written."""

from pathlib import Path

from backend.app import paths


def test_defaults_to_backend_data(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DATA_DIR", raising=False)
    assert paths.data_directory() == Path(paths.__file__).resolve().parents[1] / "data"


def test_configured_directory_is_used(monkeypatch, tmp_path):
    monkeypatch.setenv("GREYGUARD_DATA_DIR", str(tmp_path / "isolated"))
    assert paths.data_directory() == (tmp_path / "isolated").resolve()


def test_blank_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATA_DIR", "   ")
    assert paths.data_directory() == paths.DEFAULT_DATA_DIRECTORY
