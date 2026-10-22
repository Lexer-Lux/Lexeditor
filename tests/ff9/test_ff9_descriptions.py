"""FF9 US description help text attaches to rows and saves to an overlay.

The installed .mes TextAssets (read through mainData's ResourceManager) give
each item, action, support ability and command its help text; edits land in a
project FF9_Data overlay the install never sees. Synthetic Unity archives
only: no game bytes.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ff9_message_fixture import make_message_archives
from plugins.ff9 import message_text

ENTRIES = {
    "items": ["Potion heals.[FF0000]Red", "Ether restores."],
    "abilities": ["Support zero.", "Auto-Reflect help."],
}


@pytest.fixture
def game_project(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    data_dir = game / "x64" / "FF9_Data"
    data_dir.mkdir(parents=True)
    main, resources = make_message_archives(ENTRIES)
    (data_dir / "mainData").write_bytes(main)
    (data_dir / "resources.assets").write_bytes(resources)
    return game, project


def test_installed_entries_read_through_main_data(game_project):
    game, _project = game_project
    entries = message_text.messages(game)
    assert entries["items"] == ENTRIES["items"]
    assert entries["abilities"] == ENTRIES["abilities"]


def test_missing_install_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        message_text.messages(tmp_path / "empty")


def test_rows_gain_description_and_vanilla_text(game_project):
    game, project = game_project
    payload = {"key": "items",
               "rows": [{"id": 0, "line": 3}, {"id": 1, "line": 4}, {"id": 9, "line": 5}]}
    out = message_text.add_descriptions(payload, game, project)
    assert "descriptionError" not in out
    assert out["rows"][0]["description"] == "Potion heals.[FF0000]Red"
    assert out["rows"][0]["vanillaText"] == "Potion heals.[FF0000]Red"
    assert out["rows"][0]["vanillaDescription"] == "Potion heals.Red"
    assert out["rows"][1]["description"] == "Ether restores."
    assert "description" not in out["rows"][2]
    assert out["textSource"] == "vanilla"
    assert out["textSha256"] == message_text.text_sha256(ENTRIES["items"])


def test_other_datasets_pass_through_undescribed(game_project):
    game, project = game_project
    payload = {"key": "weapons", "rows": [{"id": 0, "line": 3}]}
    assert message_text.add_descriptions(payload, game, project) is payload


def test_save_writes_the_overlay_and_reloads_it(game_project):
    game, project = game_project
    sha = message_text.text_sha256(ENTRIES["items"])
    result = message_text.save_descriptions(game, project, "items", sha, {"1": "Ether restores lots."})
    assert result[1] == "Ether restores lots."
    overlay = project / "FF9_Data" / "EmbeddedAsset" / "Text" / "US" / "item" / "itm_help.mes"
    assert overlay.is_file()
    assert overlay.read_bytes() == message_text.join_messages(result).encode("utf-8")
    current, source = message_text.current_entries(game, project, "items")
    assert source == "project" and current[1] == "Ether restores lots."
    out = message_text.add_descriptions({"key": "items", "rows": [{"id": 1, "line": 4}]}, game, project)
    assert out["rows"][0]["description"] == "Ether restores lots."
    assert out["rows"][0]["vanillaText"] == "Ether restores."
    assert out["textSource"] == "project"


def test_save_rejects_bad_updates(game_project):
    game, project = game_project
    sha = message_text.text_sha256(ENTRIES["items"])
    with pytest.raises(ValueError, match="Unknown FF9 description table"):
        message_text.save_descriptions(game, project, "weapons", sha, {})
    with pytest.raises(ValueError, match="must be an object"):
        message_text.save_descriptions(game, project, "items", sha, [])
    with pytest.raises(ValueError, match="Invalid FF9 description index"):
        message_text.save_descriptions(game, project, "items", sha, {"x": "words"})
    with pytest.raises(ValueError, match="out of range"):
        message_text.save_descriptions(game, project, "items", sha, {"9": "words"})
    with pytest.raises(ValueError, match="must be text"):
        message_text.save_descriptions(game, project, "items", sha, {"1": 5})
    with pytest.raises(ValueError, match="must not contain \\[ENDN\\]"):
        message_text.save_descriptions(game, project, "items", sha, {"1": "a[ENDN]b"})
    with pytest.raises(ValueError, match="must not contain NUL"):
        message_text.save_descriptions(game, project, "items", sha, {"1": "a\x00b"})
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        message_text.save_descriptions(game, project, "items", "0" * 64, {"1": "words"})
