"""scripts.generate_sbom must report a package's real version, not its extras bracket.

Regression for a bug that silently affected every extras-using dependency (psycopg,
PyJWT, and now fastapi/uvicorn) since the requirements-line parser matched the package
name but then captured "[extras]==version" as a single invalid version string instead
of skipping the extras bracket - e.g. uvicorn[standard]==0.53.0 produced
version="[standard]==0.53.0" rather than "0.53.0".
"""
from scripts.generate_sbom import python_components


def _write(tmp_path, lines):
    directory = tmp_path / "backend"
    directory.mkdir()
    (directory / "requirements.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def test_extras_bracket_is_not_captured_as_part_of_the_version(tmp_path, monkeypatch):
    _write(tmp_path, ["uvicorn[standard]==0.53.0"])
    monkeypatch.setattr("scripts.generate_sbom.ROOT", tmp_path)
    components = python_components()
    assert components == [{"type": "library", "name": "uvicorn", "version": "0.53.0", "purl": "pkg:pypi/uvicorn"}]


def test_extras_bracket_with_no_version_pin_is_unspecified(tmp_path, monkeypatch):
    _write(tmp_path, ["uvicorn[standard]"])
    monkeypatch.setattr("scripts.generate_sbom.ROOT", tmp_path)
    components = python_components()
    assert components[0]["version"] == "unspecified"


def test_plain_pin_without_extras_is_unaffected(tmp_path, monkeypatch):
    _write(tmp_path, ["fastapi==0.141.1"])
    monkeypatch.setattr("scripts.generate_sbom.ROOT", tmp_path)
    components = python_components()
    assert components == [{"type": "library", "name": "fastapi", "version": "0.141.1", "purl": "pkg:pypi/fastapi"}]
