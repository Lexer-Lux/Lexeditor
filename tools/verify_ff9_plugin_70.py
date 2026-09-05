"""Issue-local static and API checks for the real FF9 plugin (GitHub #70)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff9 import paths  # noqa: E402
from games.ff9.memoria_csv import MemoriaCsvDocument, MemoriaDataStore  # noqa: E402
from games.ff9.plugin import PLUGIN, smoke  # noqa: E402
from app import discover_plugins  # noqa: E402
from project_manager import ProjectManager  # noqa: E402


FIXTURE = """#! IncludeId
# Item data.
# Id;Price;SellingPrice;Usable;Name;Abilities
# Int32;UInt32;Int32;Bit;String;Int32[]
0;250;125;1;Potion;1, 2;# 000 - Potion
1;320;160;0;Dagger;3;# 001 - Dagger
"""


def main() -> int:
    plugins = discover_plugins()
    assert plugins.get("ff9") is PLUGIN
    assert PLUGIN.projects is not None
    assert PLUGIN.projects.template_root == paths.PROJECT_TEMPLATE_ROOT
    assert PLUGIN.projects.required_paths == ("StreamingAssets/Data",)
    editor = (paths.PLUGIN_ROOT / "editor.html").read_text(encoding="utf-8")
    assert "projectSnapshot:" not in editor, "FF9 bypasses the shared project manager"

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff9-contract-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        manager = ProjectManager({"ff9": PLUGIN}, root / "projects.json")
        snapshot = manager.snapshot("ff9")
        assert snapshot["canCreate"] is True
        assert next(row for row in snapshot["projects"] if row["current"])["valid"] is True
        parent = root / "mods"
        parent.mkdir()
        created = manager.create("ff9", str(parent), "My FF9 Mod")
        assert created["current"] == str((parent / "My FF9 Mod").resolve())
        assert (parent / "My FF9 Mod" / "StreamingAssets" / "Data").is_dir()
        assert (parent / "My FF9 Mod" / "README.txt").is_file()

        game = root / "game"
        project = root / "project"
        baseline = game / "StreamingAssets" / "Data" / "Items" / "Items.csv"
        baseline.parent.mkdir(parents=True)
        baseline.write_text(FIXTURE, encoding="utf-8")
        original = baseline.read_bytes()

        document = MemoriaCsvDocument(baseline)
        fields = {field["key"]: field for field in document.fields}
        assert len(document.rows) == 2
        assert fields["Price"] == {
            "key": "Price", "label": "Price", "declaredType": "UInt32",
            "editable": True, "kind": "integer", "min": 0, "max": 4294967295,
        }
        assert fields["Usable"]["kind"] == "boolean" and fields["Usable"]["editable"]
        assert fields["Abilities"]["kind"] == "stored" and not fields["Abilities"]["editable"]
        assert not fields["Id"]["editable"]
        public = document.public_rows(next(value for value in __import__(
            "games.ff9.memoria_csv", fromlist=["DATASETS"]
        ).DATASETS if value.key == "items"))
        assert public[0]["name"] == "Potion"
        assert public[0]["values"]["Price"] == 250
        assert public[0]["values"]["Usable"] is True

        windows_csv = root / "windows-encoded.csv"
        windows_csv.write_bytes(FIXTURE.replace("Potion", "Potion’s", 1).encode("cp1252"))
        windows_document = MemoriaCsvDocument(windows_csv)
        assert windows_document.encoding == "cp1252"
        windows_document.write_atomic(root / "windows-roundtrip.csv")
        assert (root / "windows-roundtrip.csv").read_bytes().decode("cp1252").find("Potion’s") >= 0

        old = paths.GAME_ROOT, paths.DATA_ROOT, paths.PROJECT_ROOT
        paths.GAME_ROOT, paths.DATA_ROOT, paths.PROJECT_ROOT = game, root / "data", project
        try:
            store = MemoriaDataStore()
            loaded = store.load("items")
            saved = store.save("items", loaded["sha256"], [{
                "line": loaded["rows"][0]["line"],
                "values": {"Price": 999, "Usable": False, "Name": "Hi-Potion"},
            }])
            assert saved["source"] == "project"
            assert saved["rows"][0]["values"]["Price"] == 999
            assert saved["rows"][0]["values"]["Usable"] is False
            assert baseline.read_bytes() == original, "a save changed the game baseline"
            target = project / "StreamingAssets" / "Data" / "Items" / "Items.csv"
            assert target.is_file() and "0;999;125;0;Hi-Potion;1, 2;# 000 - Potion" in target.read_text(encoding="utf-8")

            try:
                store.save("items", loaded["sha256"], [])
            except RuntimeError as error:
                assert "changed outside Lexeditor" in str(error)
            else:
                raise AssertionError("stale data was overwritten")

            current = store.load("items")
            try:
                store.save("items", current["sha256"], [{
                    "line": current["rows"][0]["line"], "values": {"Price": -1},
                }])
            except ValueError as error:
                assert "must be from 0" in str(error)
            else:
                raise AssertionError("an out-of-range UInt32 value was saved")
        finally:
            paths.GAME_ROOT, paths.DATA_ROOT, paths.PROJECT_ROOT = old

    messages = smoke()
    assert "bounded field edit saved to a project overlay and reloaded" in messages
    print("FF9 plugin issue #70 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
