import json
from pathlib import Path
from scripts import generate_sbom

ROOT=Path(__file__).resolve().parents[2]

def test_sbom_has_supported_format_and_no_secret_values():
 sbom=generate_sbom.build_sbom();serialized=json.dumps(sbom).lower()
 assert sbom["bomFormat"]=="CycloneDX" and sbom["components"]
 assert "password=" not in serialized and "secret=" not in serialized

def test_operational_runner_has_no_shell_execution():
 source=(ROOT/"scripts/run_operational_assurance.py").read_text(encoding="utf-8")
 assert "shell=True" not in source and "subprocess.run" in source

def test_assurance_documents_cover_required_exercises():
 text=" ".join((ROOT/path).read_text(encoding="utf-8").lower() for path in ("assurance/threat-model.md","assurance/abuse-cases.md","assurance/recovery-exercises.md"))
 assert all(term in text for term in ("backup restoration","kill switch","disaster recovery","prompt injection","insider misuse"))
