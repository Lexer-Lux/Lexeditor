from plugins.ff7r import server
from plugins.ff7r.plugin import DEFAULT_PROJECT


def test_default_project_is_cross_platform_absolute():
    assert DEFAULT_PROJECT.is_absolute()
    assert "C:/FF7R-1Mod" not in str(DEFAULT_PROJECT).replace("\\", "/")


def test_data_map_distinguishes_virtual_research_from_editable_project_resources(monkeypatch):
    monkeypatch.setattr(server, "catalog", lambda: {
        "assets": [
            {
                "asset": "End/Content/GameContents/DataObject/Item",
                "name": "Item",
                "group": "DataObject",
            },
            {
                "asset": "Lexeditor/RuntimeProbe",
                "name": "Native Hook Probe",
                "group": "Lexeditor Runtime",
                "synthetic": "runtime-probe",
            },
            {
                "asset": "Lexeditor/GraphicsTweaks",
                "name": "Graphics Tweaks",
                "group": "Lexeditor Graphics",
                "synthetic": "graphics-tweaks",
            },
        ],
        "textAssets": [],
    })

    rows = server.data_map_payload()["rows"]
    cooked = next(row for row in rows if row["target"] == "End/Content/GameContents/DataObject/Item")
    probe = next(row for row in rows if row["target"] == "Lexeditor/RuntimeProbe")
    graphics = next(row for row in rows if row["target"] == "Lexeditor/GraphicsTweaks")
    runtime = next(row for row in rows if row["filename"].startswith("runtime/LexeditorFF7RRuntime"))

    assert cooked["coverage"] == "structured"
    assert ".uasset / .uexp" in cooked["filename"]

    assert probe["coverage"] == "view"
    assert probe["status"] == "partial"
    assert "Read-only" in probe["controls"]
    assert ".uasset" not in probe["filename"]

    assert graphics["coverage"] == "structured"
    assert graphics["status"] == "partial"
    assert "Engine.ini" in graphics["controls"]

    assert "minimap" not in runtime["controls"].casefold()
    assert "retired" in runtime["notes"].casefold()


def test_data_map_uses_only_shared_coverage_states(monkeypatch):
    monkeypatch.setattr(server, "catalog", lambda: {"assets": [], "textAssets": []})
    rows = server.data_map_payload()["rows"]
    allowed = {"structured", "view", "source", "unavailable"}
    assert rows
    assert {row["coverage"] for row in rows} <= allowed
    runtime = next(row for row in rows if row["filename"].startswith("runtime/LexeditorFF7RRuntime"))
    assert runtime["coverage"] == "view"
