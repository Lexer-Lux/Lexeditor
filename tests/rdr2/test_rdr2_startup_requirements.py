"""Startup validates the plugin without requiring or creating a local mod."""
from plugins.rdr2 import paths


def test_startup_without_mod_project(tmp_path, monkeypatch):
    project = tmp_path / 'uncreated-mod'
    monkeypatch.setattr(paths, 'PROJECT_ROOT', project)
    assert paths.check() == []
    assert not project.exists()


def test_missing_plugin_files_still_fail_startup(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PLUGIN_ROOT', tmp_path / 'missing-plugin')
    problems = paths.check()
    assert any('RDR2 plugin service' in problem for problem in problems)
    assert any('RDR2 plugin interface' in problem for problem in problems)
    assert any('RDR2 YDR model decoder' in problem for problem in problems)
