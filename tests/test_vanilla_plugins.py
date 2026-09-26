"""Issue 567, per game: with no mod, each service reads vanilla and creates nothing.

The host opens a game that has no mod with LEXEDITOR_VANILLA=1 and the
project variable naming a folder that does not exist. Each service must then
show the game's own values, with no overrides, and must not create that
folder or anything in it. Writes are refused by the shared handler (see
test_vanilla_without_mod.py); these checks cover the reads.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def vanilla(monkeypatch):
    monkeypatch.setenv("LEXEDITOR_VANILLA", "1")
    monkeypatch.setenv("LEXEDITOR_MOD_READ_ONLY", "1")


def test_stardew_shows_vanilla_objects_and_datasets(tmp_path, vanilla):
    from plugins.stardew_valley import server
    from plugins.stardew_valley.source_data import objects_source_path

    game = tmp_path / "game"
    source = objects_source_path(game)
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"390": {"Name": "Stone", "DisplayName": "Stone",
                                          "Description": "A useful material.", "Price": 2}}),
                      encoding="utf-8")
    missing = tmp_path / "no-mod"
    with patch.object(server.paths, "GAME_ROOT", game), patch.object(server.paths, "PROJECT_ROOT", missing):
        objects = server.objects_dataset()
        rows = {row["id"]: row for row in objects["rows"]}
        assert rows["390"]["baseFields"]["Price"] == 2
        assert rows["390"]["fields"] == {}
        for key in server.DATASET_SPECS:
            assert server.dataset_payload(key)["rows"] is not None
        assert all(row["openable"] for row in server.data_map()["rows"] if row.get("dataset"))
        server.dashboard()
    assert not missing.exists()


def test_factorio_reads_the_games_own_dump(tmp_path, vanilla, monkeypatch):
    from plugins.factorio import server

    appdata = tmp_path / "appdata"
    dump = appdata / "Factorio" / "script-output" / "data-raw-dump.json"
    dump.parent.mkdir(parents=True)
    dump.write_text(json.dumps({
        "item": {"iron-plate": {"type": "item", "name": "iron-plate", "stack_size": 100}},
    }), encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    missing = tmp_path / "no-mod"
    monkeypatch.setattr(server, "PROJECT_ROOT", missing)
    monkeypatch.setattr(server, "GAME_ROOT", None)
    monkeypatch.setattr(server, "_store", None)
    config = server._config()
    assert config["vanilla"] is True and config["projectError"] == ""
    assert config["source"]["ready"] is True, config["source"]
    assert config["counts"]["items"] == 1
    rows = server._load_store().rows("items")
    assert rows[0]["name"] == "iron-plate"
    assert not missing.exists()
    monkeypatch.setattr(server, "_store", None)


def test_palworld_opens_with_no_package_and_no_patches(tmp_path, vanilla, monkeypatch):
    from plugins.palworld import server

    missing = tmp_path / "no-mod"
    monkeypatch.setenv("LEXEDITOR_PALWORLD_PROJECT", str(missing))
    info = server.info_payload()
    assert info["vanilla"] is True and info["data"] == {}
    assert server.palschema_catalog_payload()["patches"] == []
    assert not missing.exists()


def test_project_zomboid_reads_the_games_own_scripts(tmp_path, vanilla, monkeypatch):
    from plugins.project_zomboid import core, datamap

    game = tmp_path / "ProjectZomboid"
    scripts = game / "media" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "items_food.txt").write_text(
        "module Base\n{\n    item Apple\n    {\n        ItemType = base:food,\n        Weight = 0.2,\n    }\n}\n",
        encoding="utf-8")
    missing = tmp_path / "no-mod"
    monkeypatch.setenv("LEXEDITOR_PROJECT_ZOMBOID_ROOT", str(game))
    monkeypatch.setenv("LEXEDITOR_PROJECT_ZOMBOID_PROJECT", str(missing))
    root = core.project_root()
    assert root == game.resolve()
    rows = core.read_items(root)["rows"]
    assert [row["id"] for row in rows] == ["Apple"]
    assert rows[0]["fields"]["Weight"] == "0.2"
    datamap.read(root)
    core.deployment_state(root)
    assert not missing.exists()
    assert not (game / ".lexeditor").exists()
