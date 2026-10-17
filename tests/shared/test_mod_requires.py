"""One mod requiring other mods, for every game: the shared helper.

A mod's mod.json may list the mod ids it needs. Switching such a mod on
with a need missing or off is refused, as is switching off a mod a
switched-on one needs; only the switched mods are judged, so an already
broken state never jams an unrelated switch. Builds judge the whole set,
and the Mods tab flags what is left unmet.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import mod_requires
from core.desktop_host import HostApi


def write_mod(root: Path, folder: str, data: dict, schema: dict | None = None) -> Path:
    mod = root / folder
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "mod.json").write_text(json.dumps({"name": folder, **data}), "utf-8")
    if schema is not None:
        (mod / "script").mkdir(exist_ok=True)
        (mod / "script" / "__init__.py").write_text("", "utf-8")
        (mod / "script" / "tweak.py").write_text("def build(settings, context):\n    return {}\n", "utf-8")
        (mod / "settings.schema.json").write_text(json.dumps(schema), "utf-8")
    return mod


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "library"
    write_mod(root, "Alpha", {"enabled": False, "requires": ["Beta"]})
    write_mod(root, "Beta", {"enabled": False})
    write_mod(root, "Gamma", {"enabled": False})
    return root


def enabled_of(library: Path, folder: str) -> bool:
    return json.loads((library / folder / "mod.json").read_text("utf-8"))["enabled"]


def host(library: Path):
    return SimpleNamespace(_game_mods=lambda _plugin: library, _mod_adapter=lambda _plugin: None,
                           mod_library_status=lambda _plugin: {"canManage": False})


def test_id_is_the_stored_id_or_the_folder_name(library):
    assert mod_requires.mod_id(library / "Alpha") == "Alpha"
    write_mod(library, "Beta", {"id": "beta-id", "enabled": False})
    assert mod_requires.mod_id(library / "Beta") == "beta-id"


def test_declared_needs_a_list_of_ids(library):
    assert mod_requires.declared(library / "Beta") == []
    assert mod_requires.declared(library / "Alpha") == ["Beta"]
    write_mod(library, "Gamma", {"enabled": False, "requires": "Beta"})
    with pytest.raises(ValueError, match="requires must list mod ids"):
        mod_requires.declared(library / "Gamma")
    write_mod(library, "Gamma", {"enabled": False, "requires": ["Gamma"]})
    assert mod_requires.declared(library / "Gamma") == []


def test_needs_folds_the_tweak_schema_in(library):
    write_mod(library, "Alpha", {"enabled": False, "requires": ["Beta"]},
              {"fields": [], "requires": ["Gamma", "Beta"]})
    assert mod_requires.needs(library / "Alpha") == ["Beta", "Gamma"]
    (library / "Alpha" / "settings.schema.json").write_text("{broken", "utf-8")
    assert mod_requires.needs(library / "Alpha") == ["Beta"]


def test_enabling_names_a_need_that_is_off_or_missing(library):
    with pytest.raises(ValueError, match=r"Alpha requires Beta, which is switched off"):
        mod_requires.check_changes(library, {"Alpha": True})
    (library / "Beta").rename(library / "Beta2")
    with pytest.raises(ValueError, match=r"Alpha requires Beta, which is not installed"):
        mod_requires.check_changes(library, {"Alpha": True})


def test_enabling_together_passes_and_disabling_a_need_is_refused(library):
    mod_requires.check_changes(library, {"Alpha": True, "Beta": True})
    write_mod(library, "Alpha", {"enabled": True, "requires": ["Beta"]})
    write_mod(library, "Beta", {"enabled": True})
    with pytest.raises(ValueError, match="Alpha requires Beta. Switch Alpha off first"):
        mod_requires.check_changes(library, {"Beta": False})
    mod_requires.check_changes(library, {"Alpha": False})


def test_an_unrelated_switch_ignores_an_already_broken_state(library):
    write_mod(library, "Alpha", {"enabled": True, "requires": ["Beta"]})
    mod_requires.check_changes(library, {"Gamma": True})
    with pytest.raises(ValueError, match="Alpha requires Beta"):
        mod_requires.check_enabled(library)


def test_unmet_lines_flag_only_switched_on_mods(library):
    write_mod(library, "Alpha", {"enabled": True, "requires": ["Beta", "ghost"]})
    assert mod_requires.unmet_lines(library) == {
        str((library / "Alpha").resolve()): ["Requires Beta, which is switched off.",
                                             "Requires ghost, which is not installed."]}
    write_mod(library, "Alpha", {"enabled": True, "requires": ["Beta"]})
    write_mod(library, "Gamma", {"enabled": True, "requires": [7]})
    assert mod_requires.unmet_lines(library) == {
        str((library / "Alpha").resolve()): ["Requires Beta, which is switched off."],
        str((library / "Gamma").resolve()): ["Its list of required mods is not valid."]}


def test_the_mods_tab_switch_refuses_both_directions(library):
    fake = host(library)
    with pytest.raises(ValueError, match="requires Beta"):
        HostApi.set_mod_enabled(fake, "game", str(library / "Alpha"), True)
    assert enabled_of(library, "Alpha") is False
    assert HostApi.set_mod_enabled(fake, "game", str(library / "Beta"), True)["enabled"] is True
    assert HostApi.set_mod_enabled(fake, "game", str(library / "Alpha"), True)["enabled"] is True
    with pytest.raises(ValueError, match="Alpha requires Beta"):
        HostApi.set_mod_enabled(fake, "game", str(library / "Beta"), False)
    assert enabled_of(library, "Beta") is True
    assert HostApi.set_mod_enabled(fake, "game", str(library / "Alpha"), False)["enabled"] is False
    assert HostApi.set_mod_enabled(fake, "game", str(library / "Beta"), False)["enabled"] is False
