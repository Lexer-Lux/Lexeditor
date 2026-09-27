"""Contract for separate editable-mod and composed FF8 runtime roots."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import kernel_merge, kernel_text, paths, runtime_layout
from tests.ff8.test_ff8_kernel_text import fixture as kernel_fixture


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
        backup = source_hext.with_name("patch.txt.20260912.bak")
        backup.write_text("stale hook\n", encoding="utf-8")

        result = runtime_layout.compose(project, active)
        assert Path(result["projectRoot"]) == project.resolve()
        assert Path(result["runtimeRoot"]) == active.resolve()
        assert (active / "direct" / "menu" / "price.bin").read_bytes() == b"source-price"
        runtime_hext = active / "hext" / "ff8" / "en_nv" / "000000__editable-mod__patch.txt"
        assert runtime_hext.read_text() == "source patch\n"
        assert not list((active / "hext").rglob("*.bak"))
        assert backup.read_text() == "stale hook\n"
        assert source_direct.read_bytes() == b"source-price"
        manifest = json.loads((active / runtime_layout.COMPOSITION_FILE).read_text())
        assert len(manifest["mods"]) == 1
        assert manifest["mods"][0]["id"] == "editable-mod"
        assert Path(manifest["mods"][0]["path"]) == project.resolve()
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
            "mode": "opaque winner",
            "warning": "Only second's direct/menu/price.bin is used; editable-mod's changes to this file are dropped",
        }]

        source_direct.unlink()
        competing.unlink()
        # Keep this composition check runnable on hosted CI: the standalone
        # kernel-merge verifier separately covers the installed retail corpus.
        fixture, definitions = kernel_fixture()
        payloads, _ = kernel_text._split_sections(fixture, len(definitions))
        payloads[1] += bytes(6)
        definitions[2].update(type="data", sub_section_size=8)
        vanilla_kernel = kernel_merge._rebuild(payloads)
        baseline = root / "baseline"
        (baseline / "main").mkdir(parents=True)
        (baseline / "main" / "kernel.bin").write_bytes(vanilla_kernel)
        section2 = int.from_bytes(vanilla_kernel[8:12], "little")
        first = bytearray(vanilla_kernel)
        second = bytearray(vanilla_kernel)
        first[section2 + 4] = (first[section2 + 4] + 1) & 0xFF
        second[section2 + 5] = (second[section2 + 5] + 1) & 0xFF
        (project / "direct" / "kernel.bin").write_bytes(first)
        (managed / "direct" / "kernel.bin").write_bytes(second)
        result = runtime_layout.compose(
            project, active, rows, baseline, definitions)
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

    source = (Path(__file__).resolve().parents[2] / "plugins" / "ff8" / "extractor.py").read_text()
    assert "ensure_ffnx(game_root, paths.RUNTIME_DIRECT_ROOT" in source
    assert "ensure_ffnx(game_root, paths.DIRECT_ROOT" not in source
    print("FF8 editable-mod and active-runtime separation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
