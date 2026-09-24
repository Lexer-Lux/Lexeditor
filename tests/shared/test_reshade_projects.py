"""A mod's ReShade preset must stay usable without Lexeditor."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hashlib
import pytest

from core import reshade_projects as rp



def _fake_dll(name: str = "ReShade") -> bytes:
    """A Windows binary whose version resource names something.

    is_reshade requires both, because an ASCII mention of ReShade is something
    any wrapper might carry and the cost of being wrong is a deleted game file.
    """
    return b"MZ" + bytes(64) + name.encode("utf-16-le") + bytes(32)


def _exe(folder, bits=64, name="game.exe", imports=()):
    """A Windows executable with a real header and, optionally, an import table.

    Enough of a PE file for executable_bits() and executable_imports() to read
    exactly the way they read a game's: a 32-bit or 64-bit machine field, and
    one section holding import descriptors for the named DLLs.
    """
    pe32 = bits == 32
    optional_size = 224 if pe32 else 240
    optional = 0x58
    table = optional + optional_size
    raw, rva = 0x400, 0x1000
    body = bytearray(20 * (len(imports) + 1))
    for index, dll in enumerate(imports):
        name_rva = rva + len(body)
        body.extend(dll.encode("ascii") + b"\0")
        body[index * 20 + 12:index * 20 + 16] = name_rva.to_bytes(4, "little")
    image = bytearray(raw + len(body))
    image[0:2] = b"MZ"
    image[0x3C:0x40] = (0x40).to_bytes(4, "little")
    image[0x40:0x44] = b"PE\0\0"
    image[0x44:0x46] = (0x014C if pe32 else 0x8664).to_bytes(2, "little")
    image[0x46:0x48] = (1).to_bytes(2, "little")
    image[0x54:0x56] = optional_size.to_bytes(2, "little")
    image[optional:optional + 2] = (0x10B if pe32 else 0x20B).to_bytes(2, "little")
    directory = optional + (96 if pe32 else 112) + 8
    if imports:
        image[directory:directory + 4] = rva.to_bytes(4, "little")
        image[directory + 4:directory + 8] = len(body).to_bytes(4, "little")
    image[table:table + 8] = b".idata\0\0"
    image[table + 8:table + 12] = len(body).to_bytes(4, "little")
    image[table + 12:table + 16] = rva.to_bytes(4, "little")
    image[table + 16:table + 20] = len(body).to_bytes(4, "little")
    image[table + 20:table + 24] = raw.to_bytes(4, "little")
    image[raw:raw + len(body)] = body
    (folder / name).write_bytes(bytes(image))
    return folder / name


def test_missing_folder_reports_nothing_rather_than_failing(tmp_path):
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["hasFolder"] is False
    assert snapshot["presets"] == []
    assert snapshot["ready"] is False
    assert snapshot["manifest"]["enabled"] is False


def test_manifest_round_trips_as_plain_json(tmp_path):
    rp.write_manifest(tmp_path, {
        "enabled": True, "preset": "Cinematic.ini", "renderer": "dxgi",
    })
    written = json.loads(rp.manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert written["preset"] == "Cinematic.ini"
    assert "repositories" not in written
    assert rp.read_manifest(tmp_path)["enabled"] is True


def test_a_preset_that_is_not_there_is_reported_not_silently_ignored(tmp_path):
    (tmp_path / "reshade").mkdir()
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Gone.ini"})
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["presets"] == []
    assert snapshot["ready"] is False


def test_presets_and_authored_shaders_are_listed_separately(tmp_path):
    root = tmp_path / "reshade"
    (root / "shaders").mkdir(parents=True)
    (root / "Cinematic.ini").write_text("[preset]\n", encoding="utf-8")
    (root / "shaders" / "MyGrade.fx").write_text("// authored\n", encoding="utf-8")
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["presets"] == ["Cinematic.ini"]
    assert snapshot["shaders"] == ["MyGrade.fx"]
    # The manifest itself is not a preset.
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Cinematic.ini"})
    assert rp.manifest_path(tmp_path).name not in rp.snapshot(tmp_path)["presets"]


def test_ready_needs_reshade_actually_installed(tmp_path):
    root = tmp_path / "reshade"
    root.mkdir()
    (root / "Cinematic.ini").write_text("[preset]\n", encoding="utf-8")
    rp.write_manifest(tmp_path, {"enabled": True, "preset": "Cinematic.ini"})
    assert rp.snapshot(tmp_path, tmp_path / "nogame")["ready"] is False

    game = tmp_path / "game"
    game.mkdir()
    (game / "dxgi.dll").write_bytes(_fake_dll())
    live = rp.snapshot(tmp_path, game)
    assert live["installedRenderer"] == "dxgi"
    assert live["ready"] is True


def test_a_games_own_loader_dll_is_not_mistaken_for_reshade(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "d3d11.dll").write_bytes(b"\x00" * 256)
    assert rp.installed_renderer(game) == ""


def test_only_a_real_reshade_dll_is_adopted(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    fake = tmp_path / "NotReShade.dll"
    fake.write_bytes(b"\x00" * 128)
    try:
        rp.adopt(fake)
    except ValueError as error:
        assert "does not look like" in str(error)
    else:  # pragma: no cover - the guard must hold
        raise AssertionError("a non-ReShade DLL was adopted")


def test_install_never_overwrites_a_games_own_loader(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    (store / rp.STORE_DLL).write_bytes(_fake_dll())
    monkeypatch.setattr(rp, "STORE", store)

    game = tmp_path / "game"
    game.mkdir(); _exe(game)
    own = game / "d3d11.dll"
    own.write_bytes(b"\x00" * 256)
    try:
        rp.install(game, "dx11")
    except ValueError as error:
        assert "not ReShade" in str(error)
    else:  # pragma: no cover - the guard must hold
        raise AssertionError("a game's own loader was overwritten")
    assert own.read_bytes() == b"\x00" * 256


def test_install_and_uninstall_round_trip(tmp_path, monkeypatch):
    store = tmp_path / "store"
    store.mkdir()
    (store / rp.STORE_DLL).write_bytes(_fake_dll())
    monkeypatch.setattr(rp, "STORE", store)

    game = tmp_path / "game"
    game.mkdir(); _exe(game)
    result = rp.install(game, "dxgi")
    assert result["installed"] is True
    assert (game / "dxgi.dll").is_file()
    assert rp.installed_renderer(game) == "dxgi"

    removed = rp.uninstall(game)
    assert [entry["renderer"] for entry in removed["removed"]] == ["dxgi"]
    assert not (game / "dxgi.dll").exists()


def test_uninstall_leaves_a_games_own_loader_alone(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    own = game / "opengl32.dll"
    own.write_bytes(b"\x00" * 256)
    assert rp.uninstall(game)["removed"] == []
    assert own.is_file()


def test_export_note_names_the_loader_and_carries_the_effects(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    project = tmp_path / "project"
    rp.write_manifest(project, {"enabled": True, "preset": "MyLook.ini", "renderer": "dx12"})
    (project / "reshade" / "MyLook.ini").write_text("x", encoding="utf-8")
    shaders = project / "reshade" / "shaders"
    shaders.mkdir(parents=True, exist_ok=True)
    (shaders / "MyGrain.fx").write_text("x", encoding="utf-8")

    note = rp.export_note(project)
    assert "d3d12.dll" in note
    assert "MyLook.ini" in note
    assert "MyGrain.fx" in note
    # The reader may never have used the editor, so the note must not need it.
    assert "You do not need Lexeditor" in note

    written = rp.write_export_note(project)
    assert Path(written).name == rp.EXPORT_NOTE_NAME
    assert Path(written).read_text(encoding="utf-8") == note
    # The mod carries Lexeditor's effects, which are not listed as its own work
    # and are not searched a second time.
    assert (shaders / rp.BUNDLED_FOLDER_NAME / "Colors.fx").is_file()
    assert rp.snapshot(project)["shaders"] == ["MyGrain.fx"]
    effects, _ = rp.shader_paths(project)
    assert shaders / rp.BUNDLED_FOLDER_NAME not in effects


def test_installing_also_tells_reshade_where_the_shaders_are(tmp_path, monkeypatch):
    # A loader with no search paths in ReShade.ini compiles nothing and shows an
    # empty effect list, which is indistinguishable from the mod not working.
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    (store/rp.STORE_DLL).write_bytes(_fake_dll())
    game = tmp_path/"game"; game.mkdir(); _exe(game)
    result = rp.install(game, "dx11")
    ini = (game/rp.RESHADE_INI).read_text(encoding="utf-8")
    assert "[GENERAL]" in ini
    assert str(rp.BUNDLED_SHADERS) in ini
    assert result["configured"]["effectPaths"]


def test_with_no_shader_folder_configure_says_why_nothing_happens(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    monkeypatch.setattr(rp, "BUNDLED_SHADERS", tmp_path/"no-bundled-shaders")
    game = tmp_path/"game"; game.mkdir()
    result = rp.configure(game)
    assert not result["ready"]
    assert "No shader folder" in result["reason"]


def test_the_hud_addon_matches_the_build_and_leaves_with_reshade(tmp_path):
    game = tmp_path/"game"; game.mkdir()
    for bits in (32, 64):
        result = rp.install_hud_addon(game, bits)
        assert Path(result["path"]).name == rp.HUD_ADDON_FILES[bits]
        assert (game/rp.HUD_ADDON_FILES[bits]).read_bytes()[:2] == b"MZ"
    # A copy that is no longer ours, and the player's saved groups, stay.
    (game/rp.HUD_ADDON_FILES[32]).write_bytes(b"MZ someone else's build")
    (game/"ReshadeEffectShaderToggler.ini").write_text("[General]\n")
    removed = rp.uninstall(game)["removedAddons"]
    assert [entry["addon"] for entry in removed] == [rp.HUD_ADDON_FILES[64]]
    assert (game/rp.HUD_ADDON_FILES[32]).is_file()
    assert (game/"ReshadeEffectShaderToggler.ini").is_file()


def test_every_lexerian_effect_ships():
    from tools.build_distribution import VENDORED_HELPERS
    root = Path(rp.__file__).resolve().parents[1]
    shipped = {(root/path).resolve() for path in VENDORED_HELPERS}
    for effect in rp.BUNDLED_SHADERS.iterdir():
        assert effect.resolve() in shipped, effect.name


def test_lexeditors_own_effects_are_always_searched(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    assert (rp.BUNDLED_SHADERS/"Colors.fx").is_file()
    effects, _ = rp.shader_paths(None)
    assert rp.BUNDLED_SHADERS in effects


def test_configure_keeps_settings_it_does_not_own(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    game = tmp_path/"game"; game.mkdir()
    (game/rp.RESHADE_INI).write_text(
        "[GENERAL]\nEffectSearchPaths=old\nPerformanceMode=1\n", encoding="utf-8")
    rp.configure(game)
    ini = (game/rp.RESHADE_INI).read_text(encoding="utf-8")
    assert "PerformanceMode=1" in ini
    assert "EffectSearchPaths=old" not in ini
    assert str(rp.BUNDLED_SHADERS) in ini


def _setup_exe(files):
    """A ReShade setup: a small executable with a zip stuck on the end."""
    import io as _io
    import zipfile
    buffer = _io.BytesIO()
    buffer.write(b"MZ" + b"\x00" * 4094)  # the installer's own program
    with zipfile.ZipFile(buffer, "a") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_a_real_reshade_dll_is_recognised_past_two_megabytes(tmp_path):
    """ReShade 6.8 names itself 4.3 MB in, which a windowed read missed.

    That is not cosmetic: it made adopt() refuse the real loader, hid an
    installed ReShade from the Tweaks page, and stopped uninstall() removing
    one it had installed itself.
    """
    dll = tmp_path/"d3d11.dll"
    dll.write_bytes(b"MZ" + bytes(3_000_000) + _fake_dll()[2:] + bytes(1000))
    assert rp.is_reshade(dll)
    assert not rp.is_reshade(tmp_path/"missing.dll")
    game = tmp_path/"game"; game.mkdir()
    (game/"d3d11.dll").write_bytes(dll.read_bytes())
    assert rp.installed_renderer(game) == "dx11"


def _pin(monkeypatch, payloads):
    """Pin fake setups the way the real ones are pinned: setup, 64-bit and 32-bit."""
    import io as _io
    import zipfile
    setups, loaders64, loaders32 = {}, {}, {}
    for name, payload in payloads.items():
        setups[name] = hashlib.sha256(payload).hexdigest()
        with zipfile.ZipFile(_io.BytesIO(payload)) as archive:
            loaders64[name] = hashlib.sha256(archive.read(rp.STORE_DLL)).hexdigest()
            loaders32[name] = hashlib.sha256(archive.read(rp.STORE_DLL32)).hexdigest()
    monkeypatch.setattr(rp, "PINNED_SETUP_SHA256", setups)
    monkeypatch.setattr(rp, "PINNED_LOADER_SHA256", loaders64)
    monkeypatch.setattr(rp, "PINNED_LOADER32_SHA256", loaders32)


def _loaders(tag="ReShade"):
    return {rp.STORE_DLL: _fake_dll(tag), rp.STORE_DLL32: _fake_dll(tag + " 32")}


def _setup_file(tmp_path, payload, name="ReShade_Setup.exe"):
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def test_both_loaders_come_out_of_the_bundled_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe(_loaders())
    _pin(monkeypatch, {"addon": payload})
    state = rp.install_loader(setup=_setup_file(tmp_path, payload))
    assert state["present"] and state["present32"]
    assert state["version"] == rp.PINNED_LOADER and state["variant"] == "addon"
    assert rp.store_dll().read_bytes() == _fake_dll()
    assert rp.store_dll(32).read_bytes() == _fake_dll("ReShade 32")
    recorded = rp.loader_state()
    assert recorded["sha256"] == rp.PINNED_LOADER_SHA256["addon"]
    assert recorded["sha256_32"] == rp.PINNED_LOADER32_SHA256["addon"]
    assert recorded["setupSha256"] == rp.PINNED_SETUP_SHA256["addon"]


def test_only_the_pinned_version_installs(tmp_path, monkeypatch):
    """A helper nobody chose the version of is a helper nobody tested."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe(_loaders())
    _pin(monkeypatch, {"addon": payload})
    setup = _setup_file(tmp_path, payload)
    with pytest.raises(ValueError) as refused:
        rp.install_loader("9.9.9", setup=setup)
    assert rp.PINNED_LOADER in str(refused.value)
    assert not rp.store_dll().is_file()
    rp.install_loader(rp.PINNED_LOADER, setup=setup)
    assert rp.store_dll().is_file()


def test_a_setup_that_is_not_the_pinned_bytes_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    _pin(monkeypatch, {"addon": _setup_exe(_loaders("ReShade reviewed"))})
    substitute = _setup_file(tmp_path, _setup_exe(_loaders("ReShade substitute")))
    with pytest.raises(ValueError) as refused:
        rp.install_loader(setup=substitute)
    assert "Nothing was installed" in str(refused.value)
    assert not rp.store_dll().is_file() and not rp.store_dll(32).is_file()


def test_each_loader_inside_the_setup_is_checked_too(tmp_path, monkeypatch):
    """A setup that hashes right but carries a different DLL is still refused."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    _pin(monkeypatch, {"addon": _setup_exe(_loaders("ReShade reviewed"))})
    tampered = _setup_exe(_loaders("ReShade tampered"))
    monkeypatch.setattr(rp, "PINNED_SETUP_SHA256", {"addon": hashlib.sha256(tampered).hexdigest()})
    with pytest.raises(ValueError, match="Nothing was installed"):
        rp.install_loader(setup=_setup_file(tmp_path, tampered))
    assert not rp.store_dll().is_file()


def test_the_plain_build_is_a_deliberate_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe(_loaders())
    _pin(monkeypatch, {"plain": payload, "addon": payload})
    rp.install_loader(variant="plain", setup=_setup_file(tmp_path, payload))
    assert rp.loader_state()["variant"] == "plain"
    with pytest.raises(ValueError):
        rp.install_loader(variant="nightly", setup=_setup_file(tmp_path, payload))


def test_something_that_is_not_reshade_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    junk = b"not a zip at all"
    _pin(monkeypatch, {"addon": _setup_exe(_loaders())})
    monkeypatch.setattr(rp, "PINNED_SETUP_SHA256", {"addon": hashlib.sha256(junk).hexdigest()})
    with pytest.raises(ValueError):
        rp.install_loader(setup=_setup_file(tmp_path, junk))
    assert not rp.store_dll().is_file()


def test_the_newest_tag_wins_not_the_first_one(monkeypatch):
    listing = json.dumps([{"name": "v6.10.0"}, {"name": "v6.9.1"}, {"name": "v6.8.0"}])
    latest = rp.latest_loader(fetch=lambda url: listing.encode("utf-8"))
    assert latest["latest"] == "6.10.0"
    assert latest["tag"] == "v6.10.0"


def test_the_row_separates_being_behind_the_pin_from_upstream_moving(tmp_path, monkeypatch):
    """Two different facts, and only one of them is this machine's to fix."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe(_loaders())
    _pin(monkeypatch, {"addon": payload})
    listing = json.dumps([{"name": "v99.0.0"}]).encode("utf-8")
    row = rp.loader_upstream(fetch=lambda url: listing)
    assert not row["installed"] and row["pinned"] == rp.PINNED_LOADER
    assert row["upstreamAhead"], "a newer upstream release is still reported"
    rp.install_loader(setup=_setup_file(tmp_path, payload))
    row = rp.loader_upstream(fetch=lambda url: listing)
    assert row["installed"] and not row["behind"]
    assert row["installedVersion"] == rp.PINNED_LOADER
    assert row["releaseNotes"] == "https://github.com/crosire/reshade/releases/tag/v99.0.0"


def test_a_copy_that_is_not_the_pin_reads_as_behind(tmp_path, monkeypatch):
    store = tmp_path/"store"
    monkeypatch.setattr(rp, "STORE", store)
    store.mkdir()
    rp.store_dll().write_bytes(_fake_dll())
    (store/rp.LOADER_STATE).write_text(json.dumps({"version": "6.1.0", "variant": "addon"}),
                                       encoding="utf-8")
    row = rp.loader_upstream(fetch=lambda url: json.dumps([{"name": "v6.8.0"}]).encode())
    assert row["installed"] and row["behind"]


def test_a_failed_upstream_check_still_reports_the_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe(_loaders())
    _pin(monkeypatch, {"addon": payload})
    rp.install_loader(setup=_setup_file(tmp_path, payload))

    def refuse(url):
        raise OSError("no network")

    row = rp.loader_upstream(fetch=refuse)
    assert row["installed"] and row["installedVersion"] == rp.PINNED_LOADER
    assert row["error"] and not row["behind"]
    assert row["pinned"] == rp.PINNED_LOADER


def test_the_shipped_pin_names_a_hash_for_every_variant():
    """The pin is only a pin if every build it offers has recorded bytes."""
    for pins in (rp.PINNED_SETUP_SHA256, rp.PINNED_LOADER_SHA256, rp.PINNED_LOADER32_SHA256):
        assert set(pins) == set(rp.LOADER_VARIANTS)
        for name, digest in pins.items():
            assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), name


def test_the_bundled_setups_are_the_pinned_ones_and_carry_their_licence():
    for variant, name in rp.VENDORED_SETUPS.items():
        data = (rp.VENDORED_RESHADE / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == rp.PINNED_SETUP_SHA256[variant], name
    licence = rp.RESHADE_LICENSE.read_text(encoding="utf-8")
    assert "Patrick Mours" in licence and "Redistribution" in licence


def test_the_bundled_setup_installs_without_a_network(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")

    def no_network(*_args, **_kwargs):
        raise AssertionError("installing ReShade reached for the network")

    monkeypatch.setattr(rp, "_fetch", no_network)
    state = rp.install_loader()
    assert state["present"] and state["present32"]
    assert rp.is_reshade(rp.store_dll()) and rp.is_reshade(rp.store_dll(32))


def test_a_32_bit_game_gets_the_32_bit_loader(tmp_path, monkeypatch):
    """FF7, FF8, Chrono Trigger and Warband cannot load ReShade64 at all."""
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    rp.store_dll(64).write_bytes(_fake_dll("ReShade 64"))
    rp.store_dll(32).write_bytes(_fake_dll("ReShade 32"))
    game = tmp_path/"game"; game.mkdir()
    _exe(game, 32, "FF8_EN.exe")
    result = rp.install(game, "dx9")
    assert result["bits"] == 32
    assert (game/"d3d9.dll").read_bytes() == _fake_dll("ReShade 32")


def test_a_folder_with_both_builds_needs_the_declared_executable(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    rp.store_dll(64).write_bytes(_fake_dll("ReShade 64"))
    rp.store_dll(32).write_bytes(_fake_dll("ReShade 32"))
    game = tmp_path/"game"; game.mkdir()
    _exe(game, 32, "mb_warband.exe")
    wse2 = _exe(game, 64, "mb_warband_wse2_x64.exe")
    with pytest.raises(ValueError, match="32-bit and 64-bit"):
        rp.install(game, "dx9")
    assert not (game/"d3d9.dll").exists()
    rp.install(game, "dx9", executable=wse2)
    assert (game/"d3d9.dll").read_bytes() == _fake_dll("ReShade 64")


def test_a_folder_with_no_executable_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    game = tmp_path/"game"; game.mkdir()
    with pytest.raises(ValueError, match="no Windows executable"):
        rp.install(game, "dxgi")


def test_the_loader_is_prepared_from_the_bundle_when_the_store_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    game = tmp_path/"game"; game.mkdir()
    _exe(game, 64)
    rp.install(game, "dxgi")
    assert rp.is_reshade(game/"dxgi.dll")
    assert (game/"dxgi.dll").read_bytes() == rp.store_dll(64).read_bytes()


def test_only_a_windows_binary_naming_reshade_counts(tmp_path):
    """This decides whether a file inside someone's game may be deleted.

    Rebirth ships a d3d12.dll of its own, and an ASCII mention of ReShade is
    something any wrapper or loader might carry. The version resource is the
    discriminator, so the wide form is what is required.
    """
    real = tmp_path/"real.dll"
    real.write_bytes(_fake_dll())
    assert rp.is_reshade(real)

    mentions = tmp_path/"mentions.dll"
    mentions.write_bytes(b"MZ" + b"this wrapper works alongside ReShade" * 8)
    assert not rp.is_reshade(mentions), "an ASCII mention is not the loader"

    not_a_binary = tmp_path/"notes.txt"
    not_a_binary.write_bytes("ReShade".encode("utf-16-le"))
    assert not rp.is_reshade(not_a_binary)
    assert not rp.is_reshade(tmp_path/"absent.dll")


def test_a_game_dll_that_is_not_reshade_is_never_overwritten(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    rp.store_dll().write_bytes(_fake_dll())
    game = tmp_path/"game"; game.mkdir(); _exe(game)
    theirs = b"MZ" + b"the game's own d3d12, which happens to mention ReShade"
    (game/"d3d12.dll").write_bytes(theirs)
    with pytest.raises(ValueError) as refused:
        rp.install(game, "dx12")
    assert "will not overwrite" in str(refused.value)
    assert (game/"d3d12.dll").read_bytes() == theirs
    # And uninstall leaves it alone for the same reason.
    rp.install(game, "dxgi")
    assert [row["renderer"] for row in rp.uninstall(game)["removed"]] == ["dxgi"]
    assert (game/"d3d12.dll").read_bytes() == theirs


def test_imports_are_read_from_the_executable_itself(tmp_path):
    game = _exe(tmp_path, 64, "game.exe", imports=("KERNEL32.dll", "d3d11.dll"))
    assert rp.executable_imports(game) == {"kernel32.dll", "d3d11.dll"}
    assert rp.renders(game)
    launcher = _exe(tmp_path, 32, "launcher.exe", imports=("KERNEL32.dll", "USER32.dll"))
    assert not rp.renders(launcher)
    assert rp.executable_imports(tmp_path / "missing.exe") == set()


def test_a_launcher_hands_over_to_the_game_that_renders(tmp_path):
    """FF7's Steam launcher is 32-bit and draws nothing; the game it starts is 64-bit."""
    launcher = _exe(tmp_path, 32, "FFVII_LAUNCHER.exe", imports=("KERNEL32.dll",))
    _exe(tmp_path, 64, "FFVII.exe", imports=("d3d11.dll",))
    assert rp.loader_bits(tmp_path, launcher) == 64
    assert rp.loader_bits(tmp_path) == 64


def test_the_executable_play_starts_decides_between_two_renderers(tmp_path):
    """Warband ships 32-bit and 64-bit games side by side; Play starts one of them."""
    wse2 = _exe(tmp_path, 32, "mb_warband_wse2.exe", imports=("d3d9.dll",))
    x64 = _exe(tmp_path, 64, "mb_warband_wse2_x64.exe", imports=("d3d9.dll",))
    assert rp.loader_bits(tmp_path, wse2) == 32
    assert rp.loader_bits(tmp_path, x64) == 64
    launcher = _exe(tmp_path, 32, "wse2_launcher.exe", imports=("KERNEL32.dll",))
    with pytest.raises(ValueError, match="32-bit and 64-bit"):
        rp.loader_bits(tmp_path, launcher)


def test_warband_play_names_the_executable_it_starts(tmp_path):
    from plugins.warband.game_launch import WarbandGameController, play_executable
    (tmp_path / "mb_warband.exe").write_bytes(b"MZ")
    assert play_executable(tmp_path).name == "mb_warband.exe"
    (tmp_path / "mb_warband_wse2.exe").write_bytes(b"MZ")
    assert play_executable(tmp_path).name == "mb_warband_wse2.exe"
    assert WarbandGameController().executable(tmp_path).name == "mb_warband_wse2.exe"
