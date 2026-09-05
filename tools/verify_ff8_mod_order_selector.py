"""Focused contract for FF8 managed-mod order, state, and conflict display."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import runtime_layout


def write_mod(root: Path, mod_id: str, name: str, order: int, enabled: bool) -> None:
    (root / "hext" / "ff8").mkdir(parents=True)
    (root / "hext" / "ff8" / "shared.txt").write_text(name, encoding="utf-8")
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": mod_id, "name": name, "order": order, "enabled": enabled,
    }), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-mod-order-") as name:
        root = Path(name)
        project, mods, active = root / "editable", root / "mods", root / "active"
        write_mod(project, "editable", "Editable", 20, True)
        write_mod(mods / "red", "red", "Red", 10, True)
        write_mod(mods / "blue", "blue", "Blue", 30, False)

        rows = runtime_layout.catalog(project, mods)
        assert [row["id"] for row in rows] == ["red", "editable", "blue"]
        rows = runtime_layout.configure(
            project, mods, ["blue", "editable", "red"],
            {"blue": True, "editable": True, "red": True},
        )
        assert [row["id"] for row in rows] == ["blue", "editable", "red"]
        assert next(row for row in rows if row["id"] == "editable")["enabled"] is True
        assert next(row for row in rows if row["id"] == "blue")["enabled"] is True
        persisted = json.loads((mods / "blue" / runtime_layout.MOD_FILE).read_text())
        assert persisted["order"] == 0 and persisted["enabled"] is True

        result = runtime_layout.compose(project, active, rows)
        conflict = result["conflicts"][0]
        assert conflict == {
            "path": "hext/ff8/shared.txt", "winner": "ordered runtime patches",
            "claimants": ["blue", "editable", "red"],
            "mode": "low-to-high patch stream",
        }
        patches = sorted((active / "hext" / "ff8").iterdir())
        assert [path.name for path in patches] == [
            "000000__blue__shared.txt",
            "000001__editable__shared.txt",
            "000002__red__shared.txt",
        ]
        assert [path.read_text() for path in patches] == ["Blue", "Editable", "Red"]

        empty = root / "empty-active"
        disabled = runtime_layout.configure(
            project, mods, ["blue", "editable", "red"],
            {"blue": False, "editable": False, "red": False},
        )
        assert not any(row["enabled"] for row in disabled)
        result = runtime_layout.compose(project, empty, disabled)
        assert result["fileCount"] == 0
        manifest = json.loads((empty / runtime_layout.COMPOSITION_FILE).read_text())
        assert manifest["mods"] == [] and manifest["conflicts"] == []

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    server = (ROOT / "games" / "ff8" / "server.py").read_text(encoding="utf-8")
    assert "FF8 MOD LOAD ORDER" in editor
    assert "Claimants, low to high:" in editor
    assert "sourcesReplaceProjects:true" in editor
    assert "manageProjectSources:openModOrder" in editor
    assert "mod.selected?\"mine\":`mod:${mod.id}`" in editor
    assert "Load Order…" in framework
    assert 'path == "/api/mods/configure"' in server
    assert 'path == "/api/mods/import"' in server
    assert '"Import IROJ…"' in editor
    assert "junction" not in editor[editor.index("function projectSources"):editor.index("function discardAll")].casefold()
    print("FF8 managed-mod selector, persistence, empty order, and conflicts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
