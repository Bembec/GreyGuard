import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_assurance_matrix_references_real_tests():
 matrix=json.loads((ROOT/"assurance/security-test-matrix.json").read_text(encoding="utf-8"))
 paths=[path for group in matrix["backend_groups"].values() for path in group]
 paths += [path for group in matrix["frontend_groups"].values() for path in group]
 assert paths and all((ROOT/path).is_file() or (ROOT/path.replace("frontend/","",1)).is_file() for path in paths)

def test_assurance_matrix_covers_critical_regressions():
 controls=set(json.loads((ROOT/"assurance/security-test-matrix.json").read_text(encoding="utf-8"))["required_controls"])
 assert {"authentication","authorization","cross-agent isolation","approval bypass","replay","path traversal","symlink escape","credential redaction","rate limiting","audit integrity"} <= controls

def test_assurance_runner_uses_fixed_subprocess_commands():
 source=(ROOT/"scripts/run_security_assurance.py").read_text(encoding="utf-8")
 assert "shell=True" not in source
 assert "subprocess.run" in source
