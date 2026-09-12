from pathlib import Path
import json

import pytest

from games.ff8 import cards


def pair(project):
    first, second = project / cards.MANIFEST, project / cards.HEXT
    second.parent.mkdir(parents=True)
    first.write_bytes(b"old manifest")
    second.write_bytes(b"old patch")
    return [(first, b"new manifest"), (second, b"new patch")], [(first, b"old manifest"), (second, b"old patch")]


def test_pair_commits_and_removes_recovery(tmp_path):
    pending, old = pair(tmp_path)
    cards._commit_project_files(tmp_path, pending, old)
    assert [p.read_bytes() for p, _ in pending] == [b"new manifest", b"new patch"]
    assert not (tmp_path / ".cards-recovery").exists()


@pytest.mark.parametrize("restore_fails", [False, True])
def test_second_install_failure_keeps_originals(tmp_path, monkeypatch, restore_fails):
    pending, old = pair(tmp_path)
    replace = cards.os.replace

    def fail(source, destination):
        if Path(source).name == "1.after":
            raise OSError("disk write failed")
        if restore_fails and Path(source).name.startswith(".cards-"):
            raise OSError("restore failed")
        return replace(source, destination)

    monkeypatch.setattr(cards.os, "replace", fail)
    with pytest.raises(OSError):
        cards._commit_project_files(tmp_path, pending, old)
    assert pending[1][0].read_bytes() == b"old patch"
    stage = tmp_path / ".cards-recovery"
    if restore_fails:
        assert (stage / "0.before").read_bytes() == b"old manifest"
        assert (stage / "1.before").read_bytes() == b"old patch"
        before = {p.name: p.read_bytes() for p in stage.iterdir()}
        for _ in range(3):
            with pytest.raises(OSError, match="pending recovery"):
                cards.save_project(tmp_path, b"not even an executable", [])
            with pytest.raises(OSError, match="pending recovery"):
                cards.project_edits(tmp_path, b"not even an executable")
        assert {p.name: p.read_bytes() for p in stage.iterdir()} == before
    else:
        assert pending[0][0].read_bytes() == b"old manifest"
        assert not stage.exists()


def test_external_change_during_staging_is_preserved(tmp_path, monkeypatch):
    pending, old = pair(tmp_path)
    write = Path.write_bytes

    def change(path, value):
        result = write(path, value)
        if path.name == "1.after":
            write(pending[0][0], b"external edit")
        return result

    monkeypatch.setattr(Path, "write_bytes", change)
    with pytest.raises(ValueError, match="changed during save"):
        cards._commit_project_files(tmp_path, pending, old)
    assert pending[0][0].read_bytes() == b"external edit"
    assert pending[1][0].read_bytes() == b"old patch"
    assert not (tmp_path / ".cards-recovery").exists()


def test_new_project_failure_removes_only_its_first_file(tmp_path, monkeypatch):
    pending = [(tmp_path / cards.MANIFEST, b"manifest"), (tmp_path / cards.HEXT, b"patch")]
    replace = cards.os.replace

    def fail(source, destination):
        if Path(source).name == "1.after":
            raise OSError("failure")
        return replace(source, destination)

    monkeypatch.setattr(cards.os, "replace", fail)
    with pytest.raises(OSError):
        cards._commit_project_files(tmp_path, pending, [(p, None) for p, _ in pending])
    assert all(not p.exists() for p, _ in pending)
    assert not (tmp_path / ".cards-recovery").exists()


def test_save_merges_edits_and_keeps_patch_consistent(tmp_path, monkeypatch):
    baseline = bytes(cards.COUNT * cards.RECORD_SIZE)
    monkeypatch.setattr(cards, "read_tables", lambda exe: (baseline, baseline))
    monkeypatch.setattr(cards, "build_hext", lambda exe, edits: json.dumps(edits))
    assert cards.save_project(tmp_path, b"fixture", [{"id": 0, "field": "top", "value": 5}])["saved"] == 1
    assert cards.save_project(tmp_path, b"fixture", [{"id": 0, "field": "bottom", "value": 4}])["saved"] == 1
    edits = cards.project_edits(tmp_path, b"fixture")
    assert edits == [{"id": 0, "field": "top", "value": 5}, {"id": 0, "field": "bottom", "value": 4}]
    assert not (tmp_path / ".cards-recovery").exists()


def test_save_rejects_change_between_snapshot_and_validation(tmp_path, monkeypatch):
    pending, old = pair(tmp_path)
    baseline = bytes(cards.COUNT * cards.RECORD_SIZE)
    monkeypatch.setattr(cards, "read_tables", lambda exe: (baseline, baseline))
    monkeypatch.setattr(cards, "build_hext", lambda exe, edits: json.dumps(edits))

    def read_changed(project, exe):
        pending[0][0].write_bytes(b"concurrent edit")
        return []

    monkeypatch.setattr(cards, "project_edits", read_changed)
    with pytest.raises(ValueError, match="changed during save"):
        cards.save_project(tmp_path, b"fixture", [{"id": 0, "field": "top", "value": 5}])
    assert pending[0][0].read_bytes() == b"concurrent edit"
    assert pending[1][0].read_bytes() == old[1][1]


def test_oversized_project_is_not_copied_into_recovery(tmp_path):
    (tmp_path / cards.MANIFEST).write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="1 MiB limit"):
        cards.save_project(tmp_path, b"unused", [])
    assert not (tmp_path / ".cards-recovery").exists()
