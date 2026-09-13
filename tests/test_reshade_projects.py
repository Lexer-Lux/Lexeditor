"""A mod's ReShade preset must stay usable without Lexeditor."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import reshade_projects as rp



def _fake_dll(name: str = "ReShade") -> bytes:
    """A Windows binary whose version resource names something.

    is_reshade requires both, because an ASCII mention of ReShade is something
    any wrapper might carry and the cost of being wrong is a deleted game file.
    """
    return b"MZ" + bytes(64) + name.encode("utf-16-le") + bytes(32)


def test_missing_folder_reports_nothing_rather_than_failing(tmp_path):
    snapshot = rp.snapshot(tmp_path)
    assert snapshot["hasFolder"] is False
    assert snapshot["presets"] == []
    assert snapshot["ready"] is False
    assert snapshot["manifest"]["enabled"] is False


def test_manifest_round_trips_as_plain_json(tmp_path):
    rp.write_manifest(tmp_path, {
        "enabled": True, "preset": "Cinematic.ini", "renderer": "dxgi",
        "repositories": [{"name": "qUINT", "version": "3.0"}],
    })
    written = json.loads(rp.manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert written["preset"] == "Cinematic.ini"
    assert written["repositories"] == [{"name": "qUINT", "version": "3.0"}]
    assert rp.read_manifest(tmp_path)["enabled"] is True


def test_repositories_are_named_never_copied(tmp_path):
    """A mod must not carry shaders it is not allowed to redistribute."""
    rp.write_manifest(tmp_path, {"repositories": [
        {"name": "qUINT", "version": "3.0"},
        {"missing_name": True},
    ]})
    manifest = rp.read_manifest(tmp_path)
    assert manifest["repositories"] == [{"name": "qUINT", "version": "3.0"}]


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
    game.mkdir()
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
    game.mkdir()
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


def test_repository_list_is_one_per_machine_and_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0", "https://example.invalid/quint")
    rp.add_repository("iMMERSE", "1.2")
    assert [entry["name"] for entry in rp.repositories()] == ["iMMERSE", "qUINT"]

    # Adding the same name again updates it rather than listing it twice.
    rp.add_repository("qUINT", "4.0")
    assert [entry["version"] for entry in rp.repositories()] == ["1.2", "4.0"]

    rp.remove_repository("iMMERSE")
    assert [entry["name"] for entry in rp.repositories()] == ["qUINT"]


def test_repository_status_separates_missing_from_a_version_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0")
    status = rp.repository_status({"repositories": [
        {"name": "qUINT", "version": "2.0"},
        {"name": "qUINT", "version": "3.0"},
        {"name": "Nowhere", "version": "1"},
    ]})
    assert [entry["state"] for entry in status] == [
        "version-mismatch", "present", "missing"]


def test_export_note_names_the_loader_repositories_and_authored_shaders(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    project = tmp_path / "project"
    rp.write_manifest(project, {
        "enabled": True, "preset": "MyLook.ini", "renderer": "dx12",
        "repositories": [{"name": "qUINT", "version": "3.0"}]})
    (project / "reshade" / "MyLook.ini").write_text("x", encoding="utf-8")
    shaders = project / "reshade" / "shaders"
    shaders.mkdir(parents=True, exist_ok=True)
    (shaders / "MyGrain.fx").write_text("x", encoding="utf-8")

    note = rp.export_note(project)
    assert "d3d12.dll" in note
    assert "qUINT (version 3.0)" in note
    assert "MyLook.ini" in note
    assert "MyGrain.fx" in note
    # The reader may never have used the editor, so the note must not need it.
    assert "Lexeditor" in note and "You do not need Lexeditor" in note

    written = rp.write_export_note(project)
    assert Path(written).name == rp.EXPORT_NOTE_NAME
    assert Path(written).read_text(encoding="utf-8") == note


def test_snapshot_reports_repository_state_for_the_mods_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path / "store")
    rp.add_repository("qUINT", "3.0")
    project = tmp_path / "project"
    rp.write_manifest(project, {"repositories": [{"name": "qUINT", "version": "3.0"}]})
    state = rp.snapshot(project)
    assert [entry["state"] for entry in state["repositoryStatus"]] == ["present"]
    assert [entry["name"] for entry in state["repositories"]] == ["qUINT"]


def test_installing_also_tells_reshade_where_the_shaders_are(tmp_path, monkeypatch):
    # A loader with no search paths in ReShade.ini compiles nothing and shows an
    # empty effect list, which is indistinguishable from the mod not working.
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    (store/rp.STORE_DLL).write_bytes(_fake_dll())
    game = tmp_path/"game"; game.mkdir()
    shaders = tmp_path/"quint"; (shaders/"Shaders").mkdir(parents=True)
    (shaders/"Textures").mkdir()
    rp.write_repositories([
        {"name": "qUINT", "version": "3.0", "path": str(shaders)}])
    result = rp.install(game, "dx11")
    ini = (game/rp.RESHADE_INI).read_text(encoding="utf-8")
    assert "[GENERAL]" in ini
    assert str(shaders/"Shaders") in ini
    assert str(shaders/"Textures") in ini
    assert result["configured"]["effectPaths"]


def test_a_repository_with_no_folder_says_why_nothing_happens(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    game = tmp_path/"game"; game.mkdir()
    # Named but never fetched: this is the state that leaves ReShade empty.
    rp.write_repositories([{"name": "iMMERSE", "version": "1.2"}])
    result = rp.configure(game)
    assert not result["ready"]
    assert "No shader folder" in result["reason"]


def test_configure_keeps_settings_it_does_not_own(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    game = tmp_path/"game"; game.mkdir()
    (game/rp.RESHADE_INI).write_text(
        "[GENERAL]\nEffectSearchPaths=old\nPerformanceMode=1\n", encoding="utf-8")
    shaders = tmp_path/"fx"; shaders.mkdir()
    rp.write_repositories([{"name": "SweetFX", "path": str(shaders)}])
    rp.configure(game)
    ini = (game/rp.RESHADE_INI).read_text(encoding="utf-8")
    assert "PerformanceMode=1" in ini
    assert "EffectSearchPaths=old" not in ini
    assert str(shaders) in ini


def _archive(files):
    """A GitHub-shaped zip: everything under one top folder."""
    import io as _io
    import zipfile
    buffer = _io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in files.items():
            archive.writestr(f"repo-master/{name}", payload)
    return buffer.getvalue()


def test_the_collection_covers_every_effect_it_promises():
    """Each listed effect names a package, and every package is fetchable."""
    for row in rp.coverage():
        assert row["packages"], f"{row['label']} has no package"
        assert row["shaders"], f"{row['label']} names no shader"
    named = {package["name"] for package in rp.CATALOGUE}
    for row in rp.coverage():
        assert set(row["packages"]) <= named


def test_the_collection_names_only_redistributable_packages():
    """The reason these packages and not the usual ones: we may ship them.

    qUINT, Depth3D and iMMERSE are what a preset author reaches for first and
    none of them may be redistributed, so a substitute was found for each role
    instead. A package with no licence recorded here would quietly undo that.
    """
    allowed = ("MIT", "BSD", "CC0")
    for package in rp.CATALOGUE:
        assert package["licence"].startswith(allowed), package["name"]
        assert package["download"].endswith(".zip")


def test_installing_a_package_puts_the_shaders_where_reshade_looks(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    payload = _archive({"Shaders/SMAA.fx": "// smaa",
                        "Textures/noise.png": "png",
                        "README.md": "read me"})
    result = rp.install_repository("SweetFX", fetch=lambda url: payload)
    installed = Path(result["path"])
    assert (installed/"Shaders"/"SMAA.fx").is_file()
    assert (installed/"Textures"/"noise.png").is_file()
    # And the machine's list now carries a folder, not just a name.
    entry = next(row for row in rp.repositories() if row["name"] == "SweetFX")
    assert entry["path"] == str(installed)
    game = tmp_path/"game"; game.mkdir()
    ini = rp.configure(game)
    assert str(installed/"Shaders") in ini["effectPaths"]


def test_installing_replaces_an_older_copy(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    rp.install_repository("SweetFX", fetch=lambda url: _archive({"Shaders/Old.fx": "old"}))
    result = rp.install_repository("SweetFX", fetch=lambda url: _archive({"Shaders/New.fx": "new"}))
    installed = Path(result["path"])
    assert not (installed/"Shaders"/"Old.fx").exists()
    assert (installed/"Shaders"/"New.fx").is_file()


def test_an_unknown_package_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    with pytest.raises(ValueError):
        rp.install_repository("iMMERSE", fetch=lambda url: b"")


def test_coverage_reports_what_is_missing(tmp_path, monkeypatch):
    store = tmp_path/"store"; store.mkdir()
    monkeypatch.setattr(rp, "STORE", store)
    assert not any(row["installed"] for row in rp.coverage())
    rp.install_repository("SweetFX", fetch=lambda url: _archive({"Shaders/SMAA.fx": "x"}))
    covered = {row["label"]: row["installed"] for row in rp.coverage()}
    assert covered["SMAA"]
    assert not covered["Ambient occlusion"]


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
    """Pin the fake builds these tests fetch, the way the real ones are pinned."""
    import hashlib
    import io as _io
    import zipfile
    digests = {}
    for name, payload in payloads.items():
        with zipfile.ZipFile(_io.BytesIO(payload)) as archive:
            digests[name] = hashlib.sha256(archive.read(rp.STORE_DLL)).hexdigest()
    monkeypatch.setattr(rp, "PINNED_LOADER_SHA256", digests)


def test_the_loader_is_taken_out_of_the_setup_program(tmp_path, monkeypatch):
    store = tmp_path/"store"
    monkeypatch.setattr(rp, "STORE", store)
    payload = _setup_exe({rp.STORE_DLL: _fake_dll(),
                          "ReShade32.dll": _fake_dll("ReShade 32")})
    _pin(monkeypatch, {"addon": payload})
    state = rp.install_loader(fetch=lambda url: payload)
    assert state["present"] and state["version"] == rp.PINNED_LOADER
    assert state["variant"] == "addon"
    assert rp.store_dll().read_bytes() == _fake_dll()
    # What arrived is recorded, so the next check can say whether it is behind.
    recorded = rp.loader_state()
    assert recorded["download"].endswith(f"ReShade_Setup_{rp.PINNED_LOADER}_Addon.exe")
    assert recorded["sha256"] == rp.PINNED_LOADER_SHA256["addon"]


def test_only_the_pinned_version_installs(tmp_path, monkeypatch):
    """A helper nobody chose the version of is a helper nobody tested."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe({rp.STORE_DLL: _fake_dll()})
    _pin(monkeypatch, {"addon": payload})
    with pytest.raises(ValueError) as refused:
        rp.install_loader("9.9.9", fetch=lambda url: payload)
    assert rp.PINNED_LOADER in str(refused.value)
    assert not rp.store_dll().is_file()
    # Naming the pin explicitly is the same as asking for the default.
    rp.install_loader(rp.PINNED_LOADER, fetch=lambda url: payload)
    assert rp.store_dll().is_file()


def test_a_build_that_is_not_the_pinned_bytes_is_refused(tmp_path, monkeypatch):
    """The pin is the hash, not the version number in the URL."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    _pin(monkeypatch, {"addon": _setup_exe({rp.STORE_DLL: _fake_dll("ReShade reviewed")})})
    substitute = _setup_exe({rp.STORE_DLL: _fake_dll("ReShade substitute")})
    with pytest.raises(ValueError) as refused:
        rp.install_loader(fetch=lambda url: substitute)
    assert "Nothing was installed" in str(refused.value)
    assert not rp.store_dll().is_file()


def test_the_plain_build_is_a_deliberate_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe({rp.STORE_DLL: _fake_dll()})
    _pin(monkeypatch, {"plain": payload, "addon": payload})
    rp.install_loader(variant="plain", fetch=lambda url: payload)
    assert rp.loader_state()["download"].endswith(f"ReShade_Setup_{rp.PINNED_LOADER}.exe")
    with pytest.raises(ValueError):
        rp.install_loader(variant="nightly", fetch=lambda url: payload)


def test_something_that_is_not_reshade_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    _pin(monkeypatch, {"addon": _setup_exe({rp.STORE_DLL: _fake_dll()})})
    with pytest.raises(ValueError):
        rp.install_loader(fetch=lambda url: b"not a zip at all")
    with pytest.raises(ValueError):
        rp.install_loader(fetch=lambda url: _setup_exe(
            {rp.STORE_DLL: b"MZ some other DLL entirely"}))
    assert not rp.store_dll().is_file()


def test_the_newest_tag_wins_not_the_first_one(monkeypatch):
    listing = json.dumps([{"name": "v6.10.0"}, {"name": "v6.9.1"}, {"name": "v6.8.0"}])
    latest = rp.latest_loader(fetch=lambda url: listing.encode("utf-8"))
    assert latest["latest"] == "6.10.0"
    assert latest["tag"] == "v6.10.0"


def test_the_row_separates_being_behind_the_pin_from_upstream_moving(tmp_path, monkeypatch):
    """Two different facts, and only one of them is this machine's to fix."""
    monkeypatch.setattr(rp, "STORE", tmp_path/"store")
    payload = _setup_exe({rp.STORE_DLL: _fake_dll()})
    _pin(monkeypatch, {"addon": payload})
    listing = json.dumps([{"name": "v99.0.0"}]).encode("utf-8")
    row = rp.loader_upstream(fetch=lambda url: listing)
    assert not row["installed"] and row["pinned"] == rp.PINNED_LOADER
    assert row["upstreamAhead"], "a newer upstream release is still reported"
    rp.install_loader(fetch=lambda url: payload)
    row = rp.loader_upstream(fetch=lambda url: listing)
    # On the pin: nothing to do here, whatever upstream has published.
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
    payload = _setup_exe({rp.STORE_DLL: _fake_dll()})
    _pin(monkeypatch, {"addon": payload})
    rp.install_loader(fetch=lambda url: payload)

    def refuse(url):
        raise OSError("no network")

    row = rp.loader_upstream(fetch=refuse)
    assert row["installed"] and row["installedVersion"] == rp.PINNED_LOADER
    assert row["error"] and not row["behind"]
    assert row["pinned"] == rp.PINNED_LOADER


def test_the_shipped_pin_names_a_hash_for_every_variant():
    """The pin is only a pin if every build it offers has recorded bytes."""
    assert set(rp.PINNED_LOADER_SHA256) == set(rp.LOADER_VARIANTS)
    for name, digest in rp.PINNED_LOADER_SHA256.items():
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), name


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
    game = tmp_path/"game"; game.mkdir()
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


def test_files_upstream_refuses_to_install_are_not_installed(tmp_path, monkeypatch):
    """ReShade's own package list names files a repository ships but excludes.

    GrainSpread is why: it does not compile, and shipping it made every launch
    report a failed effect nobody had asked for.
    """
    store = tmp_path/"store"
    monkeypatch.setattr(rp, "STORE", store)
    payload = _archive({"Shaders/NeoBloom.fx": "// bloom",
                        "Shaders/GrainSpread.fx": "// does not compile",
                        "Shaders/FocalDOF.fx": "// dof"})
    result = rp.install_repository("FXShaders", fetch=lambda url: payload)
    installed = Path(result["path"])
    assert (installed/"Shaders"/"NeoBloom.fx").is_file()
    assert not (installed/"Shaders"/"GrainSpread.fx").exists()
    assert result["skipped"] == ["GrainSpread.fx"]


def test_nothing_a_listed_effect_depends_on_is_denied():
    """A deny list that removed a shader some effect needs would be a bug."""
    named = set()
    for package in rp.CATALOGUE:
        for files in package["effects"].values():
            named.update(name.strip() for name in files.split(",") if ".fx" in name)
    for package_name, denied in rp.DENIED_EFFECTS.items():
        assert package_name in {package["name"] for package in rp.CATALOGUE}
        for name in denied:
            assert name not in named, f"{name} is denied but a listed effect needs it"
