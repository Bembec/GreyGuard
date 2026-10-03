"""Keep GreyGuard SDK documentation complete and credential-safe."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "sdk"
EXAMPLES = ROOT / "examples" / "sdk"


def test_sdk_guide_links_are_complete():
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    for filename in (
        "quickstart.md",
        "security.md",
        "api-reference.md",
        "troubleshooting.md",
    ):
        assert (DOCS / filename).is_file()
        assert f"]({filename})" in index


def test_examples_use_environment_credentials_and_dry_runs():
    python_example = (EXAMPLES / "python_dry_run.py").read_text(encoding="utf-8")
    javascript_example = (EXAMPLES / "javascript-dry-run.mjs").read_text(
        encoding="utf-8"
    )

    assert 'required_environment("GREYGUARD_AGENT_KEY")' in python_example
    assert "dry_run=True" in python_example
    assert 'requiredEnvironment("GREYGUARD_AGENT_KEY")' in javascript_example
    assert "dryRun: true" in javascript_example


def test_documentation_warns_against_public_browser_credentials():
    security = (DOCS / "security.md").read_text(encoding="utf-8").lower()

    assert "must not be embedded in frontend code" in security
    assert "fail closed" in security


def test_examples_contain_no_credential_literal():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in EXAMPLES.iterdir()
        if path.is_file()
    )

    assert "gg_" not in combined
    assert 'GREYGUARD_AGENT_KEY="' not in combined
    assert "GREYGUARD_AGENT_KEY='" not in combined
