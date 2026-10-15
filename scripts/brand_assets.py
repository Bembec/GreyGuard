"""Brand asset slots: validate the manifest, resolve fallbacks, and keep the apps' copies in step.

config/brand-assets.json names every logo and icon slot GreyGuard uses (lockups, symbol, favicons,
PWA icons, social preview, document logo, splash), the stable path each final file belongs at, its
size and its status: "final", "provisional" (the current approved artwork, in use until the
designer's masters arrive) or "missing" (resolved through its fallback to a provisional asset).

Components never name a file. They ask for a slot, so replacing an asset means putting the new file
at the slot's path, updating its size and status here, and re-running sync.

    python scripts/brand_assets.py check
    python scripts/brand_assets.py sync     # writes frontend/src/config/brandAssets.generated.json and docs/brand/ASSET_MANIFEST.md
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "brand-assets.json"
FRONTEND_MAP = ROOT / "frontend" / "src" / "config" / "brandAssets.generated.json"
FRONTEND_CSS = ROOT / "frontend" / "src" / "styles" / "brand-slots.generated.css"
ASSET_DOC = ROOT / "docs" / "brand" / "ASSET_MANIFEST.md"
STATUSES = ("final", "provisional", "missing")
REQUIRED_SLOTS = ("lockup-dark", "lockup-horizontal-dark", "lockup-light", "symbol", "symbol-mono", "favicon-16", "favicon-32", "favicon-48",
                  "favicon-ico", "apple-touch-180", "pwa-192", "pwa-512", "pwa-maskable-512", "social-preview", "document-logo", "splash")


def load(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def check_manifest(manifest: dict, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    if manifest.get("format") != "greyguard-brand-assets/1":
        return ["the manifest's format must be greyguard-brand-assets/1"]
    slots = manifest.get("slots", {})
    source = root / manifest["source_root"]
    for name in REQUIRED_SLOTS:
        if name not in slots:
            problems.append(f"{name}: required slot is missing from the manifest")
    for name, slot in slots.items():
        def problem(message: str) -> None:
            problems.append(f"{name}: {message}")
        for field in ("use", "path", "status", "final_requirement"):
            if not slot.get(field):
                problem(f"needs {field}")
        if slot.get("status") not in STATUSES:
            problem(f"has an unknown status {slot.get('status')!r}")
            continue
        file = source / slot["path"]
        if slot["status"] == "missing":
            if file.exists():
                problem("is marked missing but its file exists; set its size and status")
            if not slot.get("fallback"):
                problem("is missing and has no fallback, so nothing would render")
            continue
        if not file.exists():
            problem(f"file {slot['path']} does not exist")
            continue
        if slot.get("webp") and not (source / slot["webp"]).exists():
            problem(f"webp {slot['webp']} does not exist")
        size = png_size(file) if file.suffix == ".png" else None
        if size and (slot.get("width"), slot.get("height")) != size:
            problem(f"is {size[0]}x{size[1]} but the manifest says {slot.get('width')}x{slot.get('height')}")
        target = slot.get("target_size")
        if target and size and f"{size[0]}x{size[1]}" != target and slot["status"] == "final":
            problem(f"final asset must be {target}")
    for name in slots:
        try:
            resolve(manifest, name)
        except ValueError as error:
            problems.append(f"{name}: {error}")
    return problems


def resolve(manifest: dict, name: str) -> dict:
    """The asset that renders for a slot, following fallbacks past missing slots."""
    slots = manifest["slots"]
    seen = []
    current = name
    while True:
        if current not in slots:
            raise ValueError(f"falls back to unknown slot {current}")
        if current in seen:
            raise ValueError(f"has a fallback loop: {' -> '.join(seen + [current])}")
        seen.append(current)
        slot = slots[current]
        if slot["status"] != "missing":
            return {
                "slot": name, "resolvedFrom": current, "path": "/" + slot["path"], "webp": "/" + slot["webp"] if slot.get("webp") else None,
                "width": slot.get("width"), "height": slot.get("height"),
                # Internal only: never rendered as a label to visitors.
                "provisional": slot["status"] != "final" or current != name,
            }
        current = slot["fallback"]


def frontend_map(manifest: dict) -> dict:
    return {"generatedFrom": "config/brand-assets.json", "slots": {name: resolve(manifest, name) for name in manifest["slots"]}}


def frontend_css(manifest: dict) -> str:
    """Each slot as a CSS custom property, so stylesheets use a slot rather than a file path."""
    lines = ["/* Generated from config/brand-assets.json by scripts/brand_assets.py sync. Do not edit by hand. */", ":root {"]
    for name in manifest["slots"]:
        lines.append(f'  --gg-brand-{name}: url("{resolve(manifest, name)["path"]}");')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_doc(manifest: dict) -> str:
    lines = [
        "# Brand asset manifest",
        "",
        "<!-- Generated from config/brand-assets.json by `python scripts/brand_assets.py sync`. Do not edit by hand. -->",
        "",
        manifest["how_to_replace"],
        "",
        "Status: **final** = approved master in place; **provisional** = the current approved artwork, in use until the",
        "designer's masters arrive (decisions BRAND-01 and BRAND-02); **missing** = no file yet, so the fallback renders.",
        "Paths are relative to `frontend/public/`. The website derives its web-sized copies with `npm run brand`.",
        "",
        "| Slot | Use | Path | Size now | Status | Falls back to | Final requirement |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, slot in manifest["slots"].items():
        size = f"{slot['width']}×{slot['height']}" if slot.get("width") else "—"
        lines.append(f"| `{name}` | {slot['use']} | `{slot['path']}` | {size} | {slot['status']} | {slot.get('fallback') or '—'} | {slot['final_requirement']} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    command = (argv if argv is not None else sys.argv[1:] or ["check"])[0]
    manifest = load()
    problems = check_manifest(manifest)
    if problems:
        print(f"Brand asset manifest: {len(problems)} problem(s)")
        for item in problems:
            print(f"  - {item}")
        return 1
    if command == "sync":
        FRONTEND_MAP.write_text(json.dumps(frontend_map(manifest), indent=2) + "\n", encoding="utf-8")
        FRONTEND_CSS.write_text(frontend_css(manifest), encoding="utf-8")
        ASSET_DOC.write_text(render_doc(manifest), encoding="utf-8")
        print(f"Wrote {FRONTEND_MAP.relative_to(ROOT)} and {ASSET_DOC.relative_to(ROOT)}")
        return 0
    counts = {status: sum(1 for slot in manifest["slots"].values() if slot["status"] == status) for status in STATUSES}
    print(f"Brand asset manifest OK: {len(manifest['slots'])} slots ({counts['final']} final, {counts['provisional']} provisional, {counts['missing']} missing with fallbacks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
