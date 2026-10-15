"""Brand asset slots and public configuration: temporary branding resolves the same everywhere, final
assets replace provisional ones without code changes, and no secret reaches a frontend."""
import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from scripts import brand_assets, decisions

ROOT = Path(__file__).resolve().parents[2]
WEBSITE_MAP = ROOT / "website" / "src" / "lib" / "brand-assets.generated.json"


@pytest.fixture()
def manifest():
    return brand_assets.load()


def test_the_manifest_is_valid_and_every_slot_renders(manifest):
    assert brand_assets.check_manifest(manifest) == []
    for name in brand_assets.REQUIRED_SLOTS:
        assert brand_assets.resolve(manifest, name)["path"].startswith("/brand/")


def test_the_console_map_and_asset_doc_are_generated_from_the_manifest(manifest):
    generated = json.loads(brand_assets.FRONTEND_MAP.read_text(encoding="utf-8"))
    assert generated == brand_assets.frontend_map(manifest), "run: python scripts/brand_assets.py sync"
    assert brand_assets.FRONTEND_CSS.read_text(encoding="utf-8") == brand_assets.frontend_css(manifest)
    assert brand_assets.ASSET_DOC.read_text(encoding="utf-8") == brand_assets.render_doc(manifest)


def test_the_website_resolves_each_slot_exactly_as_the_console_does(manifest):
    website = json.loads(WEBSITE_MAP.read_text(encoding="utf-8"))["slots"]
    for slot, asset in website.items():
        expected = brand_assets.resolve(manifest, slot)
        assert asset["resolvedFrom"] == expected["resolvedFrom"], f"{slot}: run npm run brand in website/"
        assert asset["provisional"] == expected["provisional"]
        assert (ROOT / "website" / "public" / asset["path"].lstrip("/")).exists()


def test_missing_slots_fall_back_to_the_current_approved_artwork(manifest):
    light = brand_assets.resolve(manifest, "lockup-light")
    assert light["resolvedFrom"] == "lockup-dark" and light["provisional"] is True
    assert brand_assets.resolve(manifest, "symbol-mono")["resolvedFrom"] == "symbol"


def test_a_final_asset_replaces_its_fallback_without_code_changes(manifest, tmp_path):
    # Simulate the designer's light lockup arriving: copy a file to the slot's path and mark it final.
    root = tmp_path / "repo"
    source = root / manifest["source_root"]
    shutil.copytree(ROOT / manifest["source_root"] / "brand", source / "brand")
    updated = copy.deepcopy(manifest)
    slot = updated["slots"]["lockup-light"]
    target = source / slot["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / manifest["source_root"] / manifest["slots"]["lockup-dark"]["path"], target)
    slot.update(status="final", width=1839, height=855)
    assert brand_assets.check_manifest(updated, root=root) == []
    resolved = brand_assets.resolve(updated, "lockup-light")
    assert resolved["resolvedFrom"] == "lockup-light" and resolved["provisional"] is False


def test_a_fallback_loop_or_dangling_fallback_is_rejected(manifest):
    looped = copy.deepcopy(manifest)
    looped["slots"]["lockup-dark"].update(status="missing", fallback="lockup-light")
    assert any("loop" in problem or "missing" in problem for problem in brand_assets.check_manifest(looped))


def _source_files():
    for folder, patterns in ((ROOT / "frontend" / "src", ("*.ts", "*.tsx", "*.css")), (ROOT / "website" / "src", ("*.ts", "*.astro", "*.css"))):
        for pattern in patterns:
            yield from folder.rglob(pattern)


def test_no_component_names_a_brand_file_directly():
    # Pages ask for a slot; only the generated maps and the manifest name files.
    offenders = []
    for path in _source_files():
        if ".generated." in path.name:
            continue
        for match in re.finditer(r"""["'`]/brand/[^"'`]+["'`]""", path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert offenders == []


def test_html_and_pwa_icon_paths_are_manifest_slot_paths(manifest):
    slot_paths = {"/" + slot["path"] for slot in manifest["slots"].values()} | {"/" + slot["webp"] for slot in manifest["slots"].values() if slot.get("webp")}
    for path in (ROOT / "frontend" / "index.html", ROOT / "frontend" / "vite.config.ts"):
        for referenced in re.findall(r"""/?brand/[\w/.-]+\.(?:png|ico|webp)""", path.read_text(encoding="utf-8")):
            assert "/" + referenced.lstrip("/") in slot_paths, f"{path.name} uses {referenced}, which is not a manifest slot path"


def test_no_secret_reaches_frontend_or_public_configuration():
    files = [ROOT / "config" / "decisions.json", ROOT / "config" / "brand-assets.json", brand_assets.FRONTEND_MAP, WEBSITE_MAP,
             ROOT / "website" / "content" / "claims.json", ROOT / "website" / "public" / "_headers"]
    for path in files:
        problems = []
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            decisions._scan_for_secrets(json.loads(text), path.name, problems)
        elif decisions.SECRET_VALUE.search(text):
            problems.append(path.name)
        assert problems == [], problems
    # The console only ever reads one build-time variable, the API base URL.
    variables = set()
    for path in (ROOT / "frontend" / "src").rglob("*.ts*"):
        variables |= set(re.findall(r"import\.meta\.env\.(VITE_[A-Z_]+)", path.read_text(encoding="utf-8")))
    assert variables <= {"VITE_API_BASE_URL"}


def test_security_txt_publishes_the_decided_security_contact():
    registry = {item["id"]: item for item in decisions.load(decisions.REGISTRY)["decisions"]}
    contact = registry["CO-03"]["value"]
    text = (ROOT / "frontend" / "public" / ".well-known" / "security.txt").read_text(encoding="utf-8")
    assert f"Contact: {contact}" in text
