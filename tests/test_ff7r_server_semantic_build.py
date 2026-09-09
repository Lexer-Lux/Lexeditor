from pathlib import Path

from games.ff7r import server


def test_build_composes_better_lockon_over_ordinary_project_content(monkeypatch, tmp_path):
    game = tmp_path / "game"
    data = tmp_path / "data"
    project = tmp_path / "project"
    ordinary = project / "content" / "End" / "Content" / "ordinary.uexp"
    ordinary.parent.mkdir(parents=True, exist_ok=True)
    ordinary.write_bytes(b"ordinary-project-edit")

    monkeypatch.setattr(server, "GAME_ROOT", game)
    monkeypatch.setattr(server, "DATA_ROOT", data)
    monkeypatch.setattr(server, "PROJECT_ROOT", project)
    monkeypatch.setattr(server, "_catalog_cache", {
        "schema": 2,
        "signatureId": "fixture",
        "pakVersions": {},
        "assets": [],
        "textAssets": [],
    })
    monkeypatch.setattr(server, "has_enabled_data_overrides", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_encounter_tweaks", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_no_more_cheats", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_better_lockon", lambda _root: True)
    monkeypatch.setattr(server, "materialize_atb_overrides", lambda *_args: [])
    monkeypatch.setattr(server, "materialize_encounter_tweaks", lambda *_args: [])
    monkeypatch.setattr(server, "materialize_no_more_cheats", lambda *_args: [])

    def materialize_lockon(_game, _data, _project, _index, staging):
        assert (Path(staging) / "End" / "Content" / "ordinary.uexp").read_bytes() == b"ordinary-project-edit"
        generated = Path(staging) / "End" / "Content" / "GameContents" / "Text" / "US" / "Resident_TxtRes.uexp"
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_bytes(b"lockon-staging-edit")
        return [{"asset": "Resident_TxtRes", "textId": "$LockPrompt"}]

    monkeypatch.setattr(server, "materialize_better_lockon", materialize_lockon)
    packed_files = {}

    def pack_directory(staging, target, *, version):
        assert version == ""
        root = Path(staging)
        packed_files.update({
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()
        })
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"pak-fixture")

    monkeypatch.setattr(server, "pack_directory", pack_directory)

    result = server.build_mod()

    assert result["betterLockonMaterialized"] == [
        {"asset": "Resident_TxtRes", "textId": "$LockPrompt"}
    ]
    assert packed_files["End/Content/ordinary.uexp"] == b"ordinary-project-edit"
    assert packed_files[
        "End/Content/GameContents/Text/US/Resident_TxtRes.uexp"
    ] == b"lockon-staging-edit"
    assert Path(result["path"]).read_bytes() == b"pak-fixture"


def test_has_pak_edits_counts_better_lockon_without_project_content(monkeypatch, tmp_path):
    project = tmp_path / "project"
    monkeypatch.setattr(server, "PROJECT_ROOT", project)
    monkeypatch.setattr(server, "has_enabled_data_overrides", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_encounter_tweaks", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_no_more_cheats", lambda _root: False)
    monkeypatch.setattr(server, "has_enabled_better_lockon", lambda _root: True)

    assert server._has_pak_edits() is True
