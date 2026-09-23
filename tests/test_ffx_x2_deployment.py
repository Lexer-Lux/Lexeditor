from __future__ import annotations

from pathlib import Path

import pytest

from games.ffx_x2 import deployment


def setup_fahrenheit(root: Path):
    (root / "fahrenheit" / "bin").mkdir(parents=True)
    (root / "fahrenheit" / "bin" / "fhstage0.exe").write_bytes(b"fixture")
    (root / "fahrenheit" / "mods").mkdir(parents=True)
    (root / "fahrenheit" / "mods" / "loadorder").write_text("existing\n", encoding="utf-8")


def test_deploy_and_revert_preserve_other_loadorder_entries(tmp_path: Path):
    game, project = tmp_path / "game", tmp_path / "project"
    setup_fahrenheit(game)
    source = project / "efl" / "x" / "FFX_Data" / "test.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"replacement")

    result = deployment.deploy(game, project)
    deployed = game / "fahrenheit" / "mods" / deployment.MOD_ID
    assert result["deployed"] is True
    assert (deployed / "efl" / "x" / "FFX_Data" / "test.bin").read_bytes() == b"replacement"
    assert (deployed / deployment.MANIFEST_NAME).is_file()
    assert (game / "fahrenheit" / "mods" / "loadorder").read_text().splitlines() == ["existing", deployment.MOD_ID]

    result = deployment.revert(game, project)
    assert result["deployed"] is False
    assert not deployed.exists()
    assert (game / "fahrenheit" / "mods" / "loadorder").read_text().splitlines() == ["existing"]


def test_revert_refuses_externally_changed_deployment(tmp_path: Path):
    game, project = tmp_path / "game", tmp_path / "project"
    setup_fahrenheit(game)
    source = project / "efl" / "x2" / "FFX2_Data" / "test.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"replacement")
    deployment.deploy(game, project)
    deployed_file = game / "fahrenheit" / "mods" / deployment.MOD_ID / "efl" / "x2" / "FFX2_Data" / "test.bin"
    deployed_file.write_bytes(b"external edit")
    with pytest.raises(RuntimeError, match="changed externally"):
        deployment.revert(game, project)


def test_deploy_refuses_foreign_mod_directory(tmp_path: Path):
    game, project = tmp_path / "game", tmp_path / "project"
    setup_fahrenheit(game)
    source = project / "efl" / "x" / "FFX_Data" / "test.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"replacement")
    foreign = game / "fahrenheit" / "mods" / deployment.MOD_ID
    foreign.mkdir(parents=True)
    (foreign / "foreign.txt").write_text("not ours")
    with pytest.raises(RuntimeError, match="not owned"):
        deployment.deploy(game, project)
