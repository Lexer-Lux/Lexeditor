"""Contract for separate editable-mod and composed FF8 runtime roots."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, paths, runtime_layout


def main() -> int:
    assert paths.RUNTIME_ROOT.resolve() != paths.PROJECT_ROOT.resolve()
    assert paths.RUNTIME_DIRECT_ROOT.parent == paths.RUNTIME_ROOT
    assert paths.RUNTIME_HEXT_ROOT.parent == paths.RUNTIME_ROOT

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-runtime-") as name:
        root = Path(name)
        project = root / "editable-mod"
        active = root / "runtime" / "active"
        source_direct = project / "direct" / "menu" / "price.bin"
        source_hext = project / "hext" / "ff8" / "en_nv" / "patch.txt"
        source_direct.parent.mkdir(parents=True)
        source_hext.parent.mkdir(parents=True)
        source_direct.write_bytes(b"source-price")
        source_hext.write_text("source patch\n", encoding="utf-8")

        result = runtime_layout.compose(project, active)
        assert Path(result["projectRoot"]) == project
        assert Path(result["runtimeRoot"]) == active
        assert (active / "direct" / "menu" / "price.bin").read_bytes() == b"source-price"
        runtime_hext = active / "hext" / "ff8" / "en_nv" / "000000__editable-mod__patch.txt"
        assert runtime_hext.read_text() == "source patch\n"
        assert source_direct.read_bytes() == b"source-price"
        manifest = json.loads((active / runtime_layout.COMPOSITION_FILE).read_text())
        assert len(manifest["mods"]) == 1
        assert manifest["mods"][0]["id"] == "editable-mod"
        assert manifest["mods"][0]["path"] == str(project)
        assert manifest["conflicts"] == []
        assert all(row["winner"] == "editable-mod" for row in manifest["files"])
        assert all(row["claimants"] == ["editable-mod"] for row in manifest["files"])
        hext_row = next(row for row in manifest["files"] if row["path"].startswith("hext/"))
        assert hext_row["sourcePath"] == "hext/ff8/en_nv/patch.txt"
        assert hext_row["loadOrder"] == 0

        stale = active / "direct" / "stale.bin"
        stale.write_bytes(b"must disappear")
        source_direct.write_bytes(b"new-price")
        runtime_layout.compose(project, active)
        assert not stale.exists(), "composition retained a file absent from the selected mod"
        assert (active / "direct" / "menu" / "price.bin").read_bytes() == b"new-price"

        managed = root / "mods" / "second"
        competing = managed / "direct" / "menu" / "price.bin"
        unique = managed / "direct" / "menu" / "unique.bin"
        competing.parent.mkdir(parents=True)
        competing.write_bytes(b"losing-price")
        unique.write_bytes(b"second-only")
        (managed / runtime_layout.MOD_FILE).write_text(json.dumps({
            "id": "second", "name": "Second Mod", "enabled": True, "order": 10,
        }), encoding="utf-8")
        rows = runtime_layout.catalog(project, root / "mods")
        result = runtime_layout.compose(project, active, rows)
        assert (active / "direct" / "menu" / "price.bin").read_bytes() == b"losing-price"
        assert (active / "direct" / "menu" / "unique.bin").read_bytes() == b"second-only"
        assert result["conflicts"] == [{
            "path": "direct/menu/price.bin",
            "winner": "second",
            "claimants": ["editable-mod", "second"],
        }]

        source_direct.unlink()
        competing.unlink()
        vanilla_kernel = (paths.BASELINE_ROOT / "main" / "kernel.bin").read_bytes()
        section2 = int.from_bytes(vanilla_kernel[8:12], "little")
        first = bytearray(vanilla_kernel)
        second = bytearray(vanilla_kernel)
        first[section2 + 4] = (first[section2 + 4] + 1) & 0xFF
        second[section2 + 5] = (second[section2 + 5] + 1) & 0xFF
        (project / "direct" / "kernel.bin").write_bytes(first)
        (managed / "direct" / "kernel.bin").write_bytes(second)
        result = runtime_layout.compose(
            project, active, rows, paths.BASELINE_ROOT, formats.SECTIONS)
        composed = (active / "direct" / "kernel.bin").read_bytes()
        composed_section2 = int.from_bytes(composed[8:12], "little")
        assert composed[composed_section2 + 4] == first[section2 + 4]
        assert composed[composed_section2 + 5] == second[section2 + 5]
        kernel_conflict = next(row for row in result["conflicts"]
                               if row["path"] == "direct/kernel.bin")
        assert kernel_conflict["winner"] == "semantic merge"

        try:
            runtime_layout.compose(project, project)
        except ValueError as error:
            assert "separate" in str(error)
        else:
            raise AssertionError("editable mod and active runtime were allowed to share one root")

    source = (Path(__file__).resolve().parents[1] / "games" / "ff8" / "extractor.py").read_text()
    assert "ensure_ffnx(game_root, paths.RUNTIME_DIRECT_ROOT" in source
    assert "ensure_ffnx(game_root, paths.DIRECT_ROOT" not in source
    print("FF8 editable-mod and active-runtime separation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
