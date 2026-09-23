"""Shader Injector for Rebirth: vendored, pinned, and careful with what it touches."""
import hashlib
import io
import json
import os
from pathlib import Path
import time
import zipfile

import pytest

from plugins.ff7r2 import shader_injector as si


ROOT = Path(__file__).resolve().parents[1]
TOP = "fake-injector/"


def _package(tmp_path, extra=None):
    files = {
        "dsound.dll": b"MZ this is the injector",
        "ShaderInjector/ModifiedShaders/Includes/Library.hlsl": b"// library",
        "ShaderInjector/Tools/dxc.exe": b"MZ compiler",
        **(extra or {}),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(TOP, b"")
        for directory in ("ShaderInjector/", "ShaderInjector/Logs/", "ShaderInjector/Dumps/"):
            archive.writestr(TOP + directory, b"")
        for name, content in files.items():
            archive.writestr(TOP + name, content)
    path = tmp_path / "injector.zip"
    path.write_bytes(buffer.getvalue())
    return si.load_package(path, hashlib.sha256(buffer.getvalue()).hexdigest(), TOP)


@pytest.fixture
def game(tmp_path):
    folder = tmp_path / "Win64"
    folder.mkdir()
    (folder / "ff7rebirth_.exe").write_bytes(b"MZ game")
    return folder


# ---- the vendored release ----------------------------------------------------

def test_the_vendored_archive_is_upstreams_release_byte_for_byte():
    digest = hashlib.sha256(si.ARCHIVE.read_bytes()).hexdigest()
    assert digest == si.ARCHIVE_SHA256
    package = si.load_package()
    assert si.DLL in package.files
    assert any(name.startswith("ShaderInjector/ModifiedShaders/") for name in package.files)


def test_its_licence_travels_with_it_and_is_credited():
    text = si.LICENSE.read_text(encoding="utf-8")
    assert text.startswith("MIT License") and "David Matos" in text
    credits = json.loads((ROOT / "ui/credits.json").read_text(encoding="utf-8"))["plugins"]["ff7r2"]
    rows = [row for row in credits["licenses"] if "Shader Injector" in row["name"]]
    assert rows and rows[0]["text"] == si.LICENSE.read_text(encoding="utf-8-sig")


def test_a_different_archive_is_refused(tmp_path):
    other = tmp_path / "other.zip"
    other.write_bytes(b"not the release")
    with pytest.raises(ValueError, match="not the pinned"):
        si.load_package(other)


# ---- install, switch, remove --------------------------------------------------

def test_install_puts_everything_beside_the_executable(tmp_path, game):
    package = _package(tmp_path)
    si.install(game, package)
    assert (game / "dsound.dll").read_bytes() == b"MZ this is the injector"
    assert (game / "ShaderInjector/Tools/dxc.exe").is_file()
    assert (game / "ShaderInjector/Logs").is_dir(), "empty folders the mod expects are made"
    state = si.status(game, package, documents=tmp_path)
    assert state["installed"] and state["enabled"]
    assert not state["missingFiles"] and not state["modifiedFiles"]


def test_a_hand_install_from_the_same_release_is_adopted(tmp_path, game):
    package = _package(tmp_path)
    for name, content in package.files.items():
        (game / name).parent.mkdir(parents=True, exist_ok=True)
        (game / name).write_bytes(content)
    assert si.install(game, package)["written"] == []
    assert si.status(game, package, documents=tmp_path)["installed"]


def test_someone_elses_dsound_dll_is_never_overwritten(tmp_path, game):
    package = _package(tmp_path)
    (game / "dsound.dll").write_bytes(b"MZ an audio fix")
    with pytest.raises(ValueError, match="will not overwrite"):
        si.install(game, package)
    assert (game / "dsound.dll").read_bytes() == b"MZ an audio fix"
    state = si.status(game, package, documents=tmp_path)
    assert state["foreignDll"] and not state["installed"]


def test_off_parks_the_dll_and_on_brings_it_back(tmp_path, game):
    package = _package(tmp_path)
    si.install(game, package)
    si.set_enabled(game, False, package)
    assert not (game / "dsound.dll").exists() and (game / si.DISABLED_DLL).is_file()
    state = si.status(game, package, documents=tmp_path)
    assert state["installed"] and not state["enabled"]
    si.install(game, package)
    assert not (game / "dsound.dll").exists(), "reinstalling does not quietly switch it back on"
    si.set_enabled(game, True, package)
    assert (game / "dsound.dll").is_file() and not (game / si.DISABLED_DLL).exists()


def test_switching_needs_an_install(tmp_path, game):
    with pytest.raises(ValueError, match="not installed"):
        si.set_enabled(game, True, _package(tmp_path))


def test_the_players_shader_edits_survive_reinstall_and_removal(tmp_path, game):
    package = _package(tmp_path)
    si.install(game, package)
    edited = game / "ShaderInjector/ModifiedShaders/Includes/Library.hlsl"
    edited.write_bytes(b"// my brighter lighting")
    assert si.install(game, package)["kept"] == ["ShaderInjector/ModifiedShaders/Includes/Library.hlsl"]
    assert edited.read_bytes() == b"// my brighter lighting"
    (game / "ShaderInjector/Logs/ShaderInjector.log").write_text("generated", encoding="utf-8")
    result = si.uninstall(game, package)
    assert "dsound.dll" in result["removed"]
    assert not (game / "dsound.dll").exists()
    assert not (game / "ShaderInjector/Tools/dxc.exe").exists()
    assert edited.read_bytes() == b"// my brighter lighting"
    assert "ShaderInjector/Logs/ShaderInjector.log" in result["leftovers"]


def test_uninstall_leaves_a_foreign_dsound_dll(tmp_path, game):
    (game / "dsound.dll").write_bytes(b"MZ an audio fix")
    si.uninstall(game, _package(tmp_path))
    assert (game / "dsound.dll").read_bytes() == b"MZ an audio fix"


# ---- ShaderInjector.ini ---------------------------------------------------------

def test_defaults_are_the_pinned_sources_when_there_is_no_file(game):
    settings = si.read_settings(game)
    assert not settings["exists"]
    injector = settings["values"]["InjectorSettings"]
    assert injector == {"InjectorEnabled": True, "MenuOpen": True, "MenuScale": 1.0,
                        "OpenMenuKey": 45, "ToggleInjectorKey": 46}
    assert settings["values"]["ShaderDiscovery"]["MinimumSimilarityScore"] == 0.90


def test_writing_validates_and_writes_every_key_once(game):
    (game / si.INI).write_text("[InjectorSettings]\nMenuScale=1.0\n[Custom]\nMine=1\n", encoding="utf-8")
    result = si.write_settings(game, {"InjectorSettings": {"MenuScale": 2.0, "OpenMenuKey": 145}})
    assert result["values"]["InjectorSettings"]["MenuScale"] == 2.0
    text = (game / si.INI).read_text(encoding="utf-8")
    for setting in si.SETTINGS:
        assert text.count(f"\n{setting.key}=") + text.startswith(f"{setting.key}=") >= 1
    assert text.count("MenuScale=") == 1, "a duplicate key makes the injector ignore the file"
    assert "[Custom]\nMine=1" in text, "sections Lexeditor does not know are kept"
    assert not result["problems"]


@pytest.mark.parametrize("changes", [
    {"InjectorSettings": {"MenuScale": 5}},
    {"InjectorSettings": {"InjectorEnabled": "maybe"}},
    {"InjectorSettings": {"OpenMenuKey": 999}},
    {"ShaderDiscovery": {"Mode": 7}},
    {"Nope": {"Nothing": 1}},
])
def test_bad_values_are_refused_before_anything_is_written(game, changes):
    with pytest.raises(ValueError):
        si.write_settings(game, changes)
    assert not (game / si.INI).exists()


def test_a_file_the_injector_would_reject_is_reported(game):
    (game / si.INI).write_text("[InjectorSettings]\nMenuScale=1.0\nMenuScale=2.0\n", encoding="utf-8")
    assert any("twice" in problem for problem in si.read_settings(game)["problems"])


# ---- neighbours -------------------------------------------------------------------

def test_a_key_reshade_also_answers_is_reported(game):
    (game / "ReShade.ini").write_text(
        "[INPUT]\nKeyEffects=45,0,0,0\nKeyOverlay=36,0,0,0\nKeyReload=46,1,0,0\n", encoding="utf-8")
    conflicts = si.hotkey_conflicts(game)
    assert [(item["injectorKey"], item["reshadeKey"]) for item in conflicts] == [("OpenMenuKey", "KeyEffects")]
    assert "Insert" in conflicts[0]["message"]


def test_clearing_the_shader_cache_removes_only_the_cache(tmp_path):
    saved = tmp_path.joinpath(*si.CACHE_FOLDER)
    saved.mkdir(parents=True)
    (saved / "D3DDriverByteCodeBlob_V1_D2_S3_R4.ushaderprecache").write_bytes(b"x" * 10)
    (saved / "SaveData.sav").write_bytes(b"precious")
    assert si.shader_cache(tmp_path)["bytes"] == 10
    assert si.clear_shader_cache(tmp_path)["removed"] == ["D3DDriverByteCodeBlob_V1_D2_S3_R4.ushaderprecache"]
    assert (saved / "SaveData.sav").read_bytes() == b"precious"
    assert si.shader_cache(tmp_path)["files"] == []


# ---- first-time setup ----------------------------------------------------------------

def _cache(tmp_path, age_seconds):
    saved = tmp_path.joinpath(*si.CACHE_FOLDER)
    saved.mkdir(parents=True, exist_ok=True)
    cache = saved / "D3DDriverByteCodeBlob_V1_D2_S3_R4.ushaderprecache"
    cache.write_bytes(b"x" * 10)
    stamp = time.time() - age_seconds
    os.utime(cache, (stamp, stamp))
    return cache


def test_first_time_setup_asks_to_purge_a_cache_older_than_the_install(tmp_path, game):
    package = _package(tmp_path)
    cache = _cache(tmp_path, age_seconds=86400)
    si.install(game, package)
    notice = si.status(game, package, documents=tmp_path)["setupNotice"]
    assert notice and notice["action"] == "clear_shader_cache"
    assert notice["actionLabel"] == "Clear shader cache"
    si.clear_shader_cache(tmp_path)
    assert si.status(game, package, documents=tmp_path)["setupNotice"] is None
    # The game rebuilt the cache after the install: nothing more to ask.
    cache.write_bytes(b"rebuilt")
    assert si.status(game, package, documents=tmp_path)["setupNotice"] is None


def test_nothing_is_asked_before_it_is_installed(tmp_path, game):
    _cache(tmp_path, age_seconds=86400)
    assert si.status(game, _package(tmp_path), documents=tmp_path)["setupNotice"] is None


def test_a_repair_keeps_the_original_install_time(tmp_path, game):
    package = _package(tmp_path)
    si.install(game, package)
    first = json.loads((game / si.MANIFEST).read_text(encoding="utf-8"))["installedAt"]
    si.install(game, package)
    assert json.loads((game / si.MANIFEST).read_text(encoding="utf-8"))["installedAt"] == first


def test_a_hand_install_is_dated_by_its_dll(tmp_path, game):
    package = _package(tmp_path)
    (game / si.DLL).write_bytes(package.files[si.DLL])
    assert si.install_time(game) == (game / si.DLL).stat().st_mtime


def test_the_shell_sees_it_as_rebirths_helper(tmp_path):
    root = tmp_path / "Rebirth"
    (root / si.INSTALL_FOLDER).mkdir(parents=True)
    package = _package(tmp_path)
    before = si.helper_status(root, package, documents=tmp_path)
    assert not before["installed"] and before["pinned"] == si.VERSION
    si.install(root / si.INSTALL_FOLDER, package)
    after = si.helper_status(root, package, documents=tmp_path)
    assert after["installed"] and after["version"] == si.VERSION and after["integrity"] == "verified"
    si.set_enabled(root / si.INSTALL_FOLDER, False, package)
    assert si.helper_status(root, package, documents=tmp_path)["installed"], "switched off is still set up"
    assert si.helper_status(None)["message"]


def test_upstream_is_information_not_an_install_target():
    newer = si.upstream_release(lambda url: {"tag_name": "2.3.0", "published_at": "2026-10-01"})
    assert newer["behind"] and newer["latest"] == "2.3.0" and newer["pinned"] == si.VERSION
    assert not si.upstream_release(lambda url: {"tag_name": "2.2.1.0"})["behind"]

    def offline(url):
        raise OSError("offline")

    broken = si.upstream_release(offline)
    assert broken["error"] and not broken["behind"]


def test_the_plugin_puts_it_into_first_time_setup_and_the_updates_drawer():
    from plugins.ff7r2.plugin import PLUGIN
    assert PLUGIN.helper_name == "Shader Injector"
    assert PLUGIN.helper_pinned == si.VERSION
    assert PLUGIN.helper_status_for_root is si.helper_status
    assert PLUGIN.helper_install_for_root is si.helper_install
    assert PLUGIN.helper_upstream is si.upstream_release
    assert PLUGIN.helper_actions["clear_shader_cache"] is si.clear_cache_action
