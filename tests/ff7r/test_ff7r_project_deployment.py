from pathlib import Path

import pytest

from plugins.ff7r.project_deployment import (
    deploy_built_pak,
    deployed_pak_path,
    deployment_status,
    marker_path,
    remove_deployed_pak,
)


def _built(tmp_path: Path, data: bytes) -> Path:
    source = tmp_path / "project" / "build" / "Lexeditor-FF7R_P.pak"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(data)
    return source


def test_deploy_records_ownership_and_allows_verified_redeploy(tmp_path):
    game = tmp_path / "game"
    first = _built(tmp_path, b"first-build")
    result = deploy_built_pak(game, first)

    target = deployed_pak_path(game)
    marker = marker_path(game)
    assert result["managed"] is True
    assert target.read_bytes() == b"first-build"
    assert marker.is_file()

    first.write_bytes(b"second-build-with-new-bytes")
    second = deploy_built_pak(game, first)
    assert second["managed"] is True
    assert target.read_bytes() == b"second-build-with-new-bytes"
    assert second["sha256"] != result["sha256"]


def test_deploy_refuses_unmanaged_existing_target(tmp_path):
    game = tmp_path / "game"
    target = deployed_pak_path(game)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"someone-elses-file")
    built = _built(tmp_path, b"lexeditor-build")

    with pytest.raises(RuntimeError, match="preserve|ownership|proven"):
        deploy_built_pak(game, built)

    assert target.read_bytes() == b"someone-elses-file"
    assert not marker_path(game).exists()


def test_redeploy_and_remove_refuse_externally_changed_managed_target(tmp_path):
    game = tmp_path / "game"
    built = _built(tmp_path, b"owned")
    deploy_built_pak(game, built)
    target = deployed_pak_path(game)
    target.write_bytes(b"changed-outside-lexeditor")

    status = deployment_status(game)
    assert status["managed"] is False
    assert status["state"] == "changed"

    built.write_bytes(b"new-build")
    with pytest.raises(RuntimeError, match="changed"):
        deploy_built_pak(game, built)
    with pytest.raises(RuntimeError, match="changed"):
        remove_deployed_pak(game)
    assert target.read_bytes() == b"changed-outside-lexeditor"


def test_remove_deletes_only_verified_owned_archive_and_marker(tmp_path):
    game = tmp_path / "game"
    built = _built(tmp_path, b"owned")
    deploy_built_pak(game, built)

    result = remove_deployed_pak(game)

    assert result["removed"] is True
    assert result["state"] == "absent"
    assert not deployed_pak_path(game).exists()
    assert not marker_path(game).exists()


def test_missing_pak_with_valid_owned_marker_can_be_cleaned(tmp_path):
    game = tmp_path / "game"
    built = _built(tmp_path, b"owned")
    deploy_built_pak(game, built)
    deployed_pak_path(game).unlink()

    status = deployment_status(game)
    assert status["state"] == "stale-marker"

    result = remove_deployed_pak(game)
    assert result["removed"] is False
    assert result["markerRemoved"] is True
    assert result["state"] == "absent"
