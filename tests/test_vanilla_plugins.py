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
