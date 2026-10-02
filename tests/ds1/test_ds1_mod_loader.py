"""Profile export and snapshot tests; no native loader/game is executed."""
from hashlib import sha256
from pathlib import Path
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.composition import CompositionError, ConflictError
from plugins.ds1.formats import ItemDocument
from plugins.ds1.mod_loader import Mod, RELATIVE, ProfileConflictError, prepare_profile, verify_profile


def files(tmp_path):
    game = tmp_path / "game"
    base = game / RELATIVE
    base.parent.mkdir(parents=True)
    raw = make_archive()
    base.write_bytes(raw)
    mods = []
    for index, name in enumerate(("a", "b")):
        mod = tmp_path / name
        target = mod / RELATIVE
        target.parent.mkdir(parents=True)
        document = ItemDocument(raw)
        document.edit("EquipParamGoods", 100 + index, "sellValue", 42 + index)
        target.write_bytes(document.export())
        mods.append(Mod(name, mod))
    return game, base, raw, mods


def prepare(tmp_path, *, policy="error"):
    game, base, raw, mods = files(tmp_path)
    destination = tmp_path / "profile"
    report = prepare_profile(game, base, destination, mods, expected_base_sha256=sha256(raw).hexdigest(), policy=policy)
    return game, base, raw, mods, destination, report


def test_profile_isolated_and_modengine_order_is_reversed(tmp_path):
    game, base, raw, mods, destination, report = prepare(tmp_path)
    assert base.read_bytes() == raw
    merged = ItemDocument((destination / "merged" / RELATIVE).read_bytes())
    assert merged.value("EquipParamGoods", 100, "sellValue") == 42
    assert merged.value("EquipParamGoods", 101, "sellValue") == 43
    for index, mod in enumerate(mods):
        original = ItemDocument((mod.root / RELATIVE).read_bytes())
        assert original.value("EquipParamGoods", 100 + index, "sellValue") == 42 + index
        assert original.value("EquipParamGoods", 101 - index, "sellValue") == 0
    config = tomllib.loads((destination / "config_darksoulsremastered.toml").read_text("utf-8"))
    assert [row["name"] for row in config["extension"]["mod_loader"]["mods"]] == ["lexeditor-composed", "b", "a"]
    assert config["modengine"]["external_dlls"] == []
    assert report["runtimeBundled"] is False
    assert verify_profile(destination) == report


def test_bad_baseline_and_dependencies_do_not_create_output(tmp_path):
    game, base, raw, mods = files(tmp_path)
    destination = tmp_path / "profile"
    with pytest.raises(CompositionError, match="Baseline hash"):
        prepare_profile(game, base, destination, mods, expected_base_sha256="0" * 64)
    assert not destination.exists()
    invalid = [Mod("a", mods[0].root, requires=("b",)), mods[1]]
    with pytest.raises(CompositionError, match="dependencies"):
        prepare_profile(game, base, destination, invalid, expected_base_sha256=sha256(raw).hexdigest())
    assert not destination.exists()


def test_declared_wrong_baseline_rejected(tmp_path):
    game, base, raw, mods = files(tmp_path)
    with pytest.raises(CompositionError, match="baseline version mismatch"):
        prepare_profile(game, base, tmp_path / "profile",
                        [Mod("a", mods[0].root, base_sha256="0" * 64)],
                        expected_base_sha256=sha256(raw).hexdigest())


def test_disabled_missing_mod_is_not_loaded(tmp_path):
    game, base, raw, mods = files(tmp_path)
    mods.append(Mod("disabled", tmp_path / "not-installed", enabled=False))
    destination = tmp_path / "profile"
    report = prepare_profile(game, base, destination, mods, expected_base_sha256=sha256(raw).hexdigest())
    assert [entry["id"] for entry in report["mods"]] == ["a", "b"]


def test_nonparam_file_conflicts_require_explicit_order(tmp_path):
    game, base, raw, mods = files(tmp_path)
    for mod in mods:
        asset = mod.root / "chr" / "example.bin"
        asset.parent.mkdir()
        asset.write_bytes(mod.id.encode())
    destination = tmp_path / "profile"
    with pytest.raises(ProfileConflictError, match="conflicting files") as failure:
        prepare_profile(game, base, destination, mods, expected_base_sha256=sha256(raw).hexdigest())
    assert failure.value.report["fileConflicts"][0]["winner"] == "b"
    assert not destination.exists()
    result = prepare_profile(game, base, destination, mods, expected_base_sha256=sha256(raw).hexdigest(), policy="last-wins")
    assert result["composition"]["fileConflicts"] == [
        {"path": "chr/example.bin", "loser": "a", "winner": "b", "granularity": "file"}]
    assert not (destination / "merged" / "chr").exists()


@pytest.mark.parametrize("location", ["game", "mod", "existing"])
def test_existing_or_overlapping_output_refused(tmp_path, location):
    game, base, raw, mods = files(tmp_path)
    destination = game / "output" if location == "game" else mods[0].root / "output" if location == "mod" else tmp_path / "existing"
    if location == "existing":
        destination.mkdir()
        (destination / "keep.txt").write_text("preserve")
    with pytest.raises(CompositionError):
        prepare_profile(game, base, destination, mods, expected_base_sha256=sha256(raw).hexdigest())
    assert base.read_bytes() == raw
    if location == "existing":
        assert (destination / "keep.txt").read_text() == "preserve"


@pytest.mark.parametrize("change", ["mod", "base", "config", "merged", "added-file"])
def test_stale_profiles_are_rejected(tmp_path, change):
    game, base, raw, mods, destination, report = prepare(tmp_path)
    paths = {"mod": mods[0].root / RELATIVE, "base": base,
             "config": destination / "config_darksoulsremastered.toml",
             "merged": destination / "merged" / RELATIVE,
             "added-file": mods[0].root / "new-file.bin"}
    paths[change].write_bytes(b"changed")
    with pytest.raises(CompositionError, match="changed"):
        verify_profile(destination)


def test_symlink_mod_input_refused(tmp_path):
    game, base, raw, mods = files(tmp_path)
    link = tmp_path / "link"
    try:
        link.symlink_to(mods[0].root, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink permission unavailable")
    with pytest.raises(CompositionError, match="Symlinks"):
        prepare_profile(game, base, tmp_path / "profile", [Mod("a", link)],
                        expected_base_sha256=sha256(raw).hexdigest())


def test_reserved_mod_id_and_missing_game_refused(tmp_path):
    game, base, raw, mods = files(tmp_path)
    with pytest.raises(CompositionError, match="reserved"):
        prepare_profile(game, base, tmp_path / "profile", [Mod("lexeditor-composed", mods[0].root)],
                        expected_base_sha256=sha256(raw).hexdigest())
    with pytest.raises(CompositionError, match="Game root"):
        prepare_profile(tmp_path / "missing-game", base, tmp_path / "profile", mods,
                        expected_base_sha256=sha256(raw).hexdigest())
