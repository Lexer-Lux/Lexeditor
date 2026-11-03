"""Play observes the installed FFNx runtime; only Save builds or deploys."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from plugins.ff8 import gameplay_settings


@pytest.mark.parametrize("damaged_report", [False, True])
def test_launch_never_builds_or_saves(tmp_path, monkeypatch, damaged_report):
    game, project, runtime = [tmp_path / name for name in ("game", "project", "runtime")]
    for folder in (game, project, runtime):
        folder.mkdir()
    (game / "FFNx.log").write_text("last session")
    patch = runtime / "hext/FF8_EN/test.txt"
    patch.parent.mkdir(parents=True)
    patch.write_text("installed patch")
    rows = {"files": [{"path": "hext/FF8_EN/test.txt", "winner": "installed-mod"}]}
    monkeypatch.setattr(gameplay_settings.runtime_layout, "read",
                        Mock(side_effect=ValueError("broken report")) if damaged_report else Mock(return_value=rows))
    build = Mock(side_effect=AssertionError("Play must not build"))
    monkeypatch.setattr(gameplay_settings, "save", build)
    monkeypatch.setattr(gameplay_settings, "ensure", build)
    before = {path: path.read_bytes() for folder in (project, runtime) for path in folder.rglob("*") if path.is_file()}
    result = gameplay_settings.begin_launch(game, project, runtime)
    assert result["observing"]
    build.assert_not_called()
    assert (game / "FFNx.previous.log").read_text() == "last session"
    assert all(path.read_bytes() == content for path, content in before.items())
    assert gameplay_settings._last_patches == ([] if damaged_report else [patch.resolve()])


def test_save_passes_settings_to_one_build_and_deploy(tmp_path, monkeypatch):
    game, project, runtime = [tmp_path / name for name in ("game", "project", "runtime")]
    for folder in (game, project, runtime):
        folder.mkdir()
    (game / "FFNx.toml").write_text('hext_patching_path = "' + (runtime / "hext").as_posix() + '"\n')
    save = Mock(return_value={"tweaks": []})
    monkeypatch.setattr(gameplay_settings, "save", save)
    monkeypatch.setattr(gameplay_settings, "_validate_shared_magic_launch", lambda *args: None)
    monkeypatch.setattr(gameplay_settings, "materialized_tweak_patches", lambda *args: [])
    data = {"tweaks": {"one": {"enabled": True}}}
    assert gameplay_settings.activate(game, project, runtime, data=data)["ready"]
    save.assert_called_once_with(data, game.resolve(), project.resolve(), install_runtime=True,
                                 runtime_root=runtime.resolve())
