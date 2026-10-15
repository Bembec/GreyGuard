"""The Trust Center source pages (docs/trust) may only say what the repository can show. Every
statement ID on a page must be in the source register, every register ID must be used, every cited
path must exist, and the "no built-in external destination" statement (TC-SUB-1) is checked here."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUST = ROOT / "docs" / "trust"
REGISTER = TRUST / "source-register.md"
STATEMENT_ID = re.compile(r"\bTC-[A-Z]+-\d+\b")
# A backticked repository path: has a slash or a file extension, and is not an API route.
CITED_PATH = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*(?:/[A-Za-z0-9_.-]+|\.(?:md|py|yml|yaml|conf|json|txt|toml|ts|tsx)))`")
EXTERNAL_URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
ALLOWED_HOSTS = ("example.com", "example.org", "example.net", "localhost", "127.0.0.1")


def pages():
    return sorted(path for path in TRUST.glob("*.md") if path != REGISTER)


def register_rows():
    rows = {}
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and STATEMENT_ID.fullmatch(cells[0]):
            rows[cells[0]] = cells
    return rows


def test_every_page_statement_is_registered_and_every_registered_statement_is_used():
    used = {match for page in pages() for match in STATEMENT_ID.findall(page.read_text(encoding="utf-8"))}
    registered = set(register_rows())
    assert used - registered == set(), "IDs used on a page but missing from the register"
    assert registered - used == set(), "IDs in the register that no page uses"


def test_every_register_row_has_evidence_an_owner_and_a_review_date():
    rows = register_rows()
    assert rows
    for statement_id, (_, statement, evidence, owner, reviewed) in rows.items():
        assert statement and CITED_PATH.search(evidence), statement_id
        assert owner in {"Engineering", "Project owner"}, statement_id
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed), statement_id


def test_every_cited_path_exists():
    missing = []
    for document in [*pages(), REGISTER]:
        for cited in CITED_PATH.findall(document.read_text(encoding="utf-8")):
            path = cited.split("::")[0]
            if not (ROOT / path).exists() and not (document.parent / path).exists():
                missing.append(f"{document.name}: {path}")
    assert missing == []


def test_the_backend_has_no_built_in_external_destination():
    """TC-SUB-1: every outbound connection goes to an operator- or customer-configured endpoint."""
    found = []
    for source in (ROOT / "backend" / "app").rglob("*.py"):
        for host in EXTERNAL_URL.findall(source.read_text(encoding="utf-8")):
            if not host.endswith(ALLOWED_HOSTS):
                found.append(f"{source.relative_to(ROOT)}: {host}")
    assert found == []


def test_the_url_check_would_catch_a_hard_coded_destination():
    assert EXTERNAL_URL.findall('send_json("https://telemetry.vendor.io/v1", body)') == ["telemetry.vendor.io"]
    assert EXTERNAL_URL.findall("https://greyguard.example.com/api")[0].endswith(ALLOWED_HOSTS)
