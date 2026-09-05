"""Contracts for FF8 private game assets and shared provenance controls."""

from pathlib import Path
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, game_icons, paths  # noqa: E402


framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
rdr2_editor = (ROOT / "games" / "rdr2" / "editor.html").read_text(encoding="utf-8")
rdr_editor = (ROOT / "games" / "rdr" / "editor.html").read_text(encoding="utf-8")
ff7_editor = (ROOT / "games" / "ff7" / "editor.html").read_text(encoding="utf-8")
blank_editor = (ROOT / "games" / "blank" / "editor.html").read_text(encoding="utf-8")
extractor = (ROOT / "games" / "ff8" / "extractor.py").read_text(encoding="utf-8")

assert "provenanceControl" in framework
assert "referenceDisplay" in framework
assert 'shortName: options.vanillaShortName || "V"' in framework
assert "!same(options.current, source.value)" in framework
assert 'className:"ref refstack"' in rdr2_editor
assert "LexeditorUI.referenceDisplay" in rdr2_editor
assert 'class: "allsame"' not in rdr2_editor
assert "LexeditorUI.provenanceControl" in editor
assert "provenanceControl" in rdr_editor
assert "state.vanilla.items" in rdr_editor and "state.vanilla.shops" in rdr_editor
assert "mission.baseRewards" in rdr_editor
assert "provenanceControl" in ff7_editor
assert "provenanceControl" in blank_editor and "referenceDisplay" in blank_editor
assert '"icon.sp1", "icon.TEX"' in extractor
assert "BASELINE_FORMAT = 3" in extractor
assert "conceptIcon" in editor and "/assets/icons/" in editor

manifest = game_icons.ensure_icons()
assert manifest["available"] and len(manifest["icons"]) == len(game_icons.ICON_NAMES)
for icon_id in (272, 277, 278, 279, 280, 292):
    target = game_icons.icon_path(icon_id)
    assert target and target.is_file()
    with Image.open(target) as image:
        assert image.width > 0 and image.height > 0
        assert image.getbbox(), f"icon {icon_id} is blank"

vanilla = formats.item_rows("vanilla")
assert vanilla["rows"] and vanilla["rows"][0]["name"]
with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-reference-", ignore_cleanup_errors=True) as temp_name:
    previous = paths.PROJECT_ROOT
    try:
        paths.PROJECT_ROOT = Path(temp_name)
        reference = paths.PROJECT_ROOT / "references" / "Example" / "direct" / "menu"
        reference.mkdir(parents=True)
        source = paths.BASELINE_ROOT / "menu" / "price.bin"
        (reference / "price.bin").write_bytes(source.read_bytes())
        assert formats.reference_roots()[0]["id"] == "Example"
        assert formats.item_rows("reference:Example")["rows"] == vanilla["rows"]
    finally:
        paths.PROJECT_ROOT = previous

print("Installed FF8 icons, vanilla reads, reference discovery, and shared provenance contracts passed")
