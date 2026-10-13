"""Warband settings.ini values are typed by the mod's own build.

module_settings.py reads every key in its DEFAULTS table as a whole number
and ignores any other key. The editor reads that table as data (never
running the mod's code), gives known keys whole-number values with their
default, and refuses edits the build would reject or ignore.
"""
import hashlib

import pytest

from plugins.warband import server

MODULE_SETTINGS = '''
import os
raise SystemExit("the editor must never run this file")
DEFAULTS = {
    "raiding": {"loot_base": 50, "prosperity_hit": -60},
    "camera": {"instant_recenter": 1},
}
'''
SETTINGS = "[raiding]\nloot_base = 70 ; gold per raid\nprosperity_hit = -60\n\n[camera]\ninstant_recenter = 1\nmystery = 3\n"


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    (tmp_path / "ModuleSystem").mkdir()
    (tmp_path / "ModuleSystem" / "module_settings.py").write_text(MODULE_SETTINGS, encoding="utf-8")
    path = tmp_path / "settings.ini"
    path.write_text(SETTINGS, encoding="utf-8")
    monkeypatch.setattr(server, "SETTINGS", path)
    return path


def save(edits):
    return server.save_settings(edits, hashlib.sha256(server.SETTINGS.read_bytes()).hexdigest())


def rows():
    return {row["key"]: row for row in server.settings_data()["rows"]}


def test_known_keys_are_whole_numbers_with_their_default(settings):
    listed = rows()
    assert listed["loot_base"]["kind"] == "integer" and listed["loot_base"]["default"] == 50
    assert listed["prosperity_hit"]["default"] == -60
    assert listed["mystery"]["kind"] == "unused"


@pytest.mark.parametrize("value", ["1.5", "lots", "", "7e2"])
def test_a_known_key_takes_only_whole_numbers(settings, value):
    with pytest.raises(ValueError):
        save([{"line": rows()["loot_base"]["line"], "value": value}])
    assert settings.read_text(encoding="utf-8") == SETTINGS


def test_an_unused_key_is_not_edited(settings):
    with pytest.raises(ValueError):
        save([{"line": rows()["mystery"]["line"], "value": "4"}])


def test_a_whole_number_saves_and_keeps_its_comment(settings):
    save([{"line": rows()["loot_base"]["line"], "value": "-25"}])
    assert "loot_base = -25 ; gold per raid" in settings.read_text(encoding="utf-8")
