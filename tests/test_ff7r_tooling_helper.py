from types import SimpleNamespace

import pytest

from games.ff7r import pak_reader, tooling


def test_upstream_release_is_information_only_and_keeps_the_pin():
    result = tooling.upstream_release(lambda _url: {
        "tag_name": "v0.2.3",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-01-02T03:14:46Z",
        "html_url": "https://github.com/trumank/repak/releases/tag/v0.2.3",
    })

    assert result["pinned"] == "v0.2.3"
    assert result["latest"] == "v0.2.3"
    assert result["behind"] is False
    assert result["autoUpdate"] is False


def test_upstream_release_reports_newer_version_without_installing_it():
    result = tooling.upstream_release(lambda _url: {
        "tag_name": "v0.2.4",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-09-01T00:00:00Z",
    })

    assert result["latest"] == "v0.2.4"
    assert result["pinned"] == "v0.2.3"
    assert result["behind"] is True
    assert result["autoUpdate"] is False


def test_repak_fallback_never_triggers_oodle_autodownload(monkeypatch, tmp_path):
    def reject(_pak, _path):
        raise pak_reader.PakError("fixture direct-reader rejection")

    calls = []
    monkeypatch.setattr(pak_reader, "read_file", reject)
    monkeypatch.setattr(pak_reader, "repak_oodle_library", lambda: None)
    monkeypatch.setattr(tooling, "_command", lambda *args, **kwargs: calls.append((args, kwargs)))

    with pytest.raises(RuntimeError, match="download Oodle automatically"):
        tooling.get_file(tmp_path / "fixture.pak", "A/B.uasset")

    assert calls == []


def test_repak_fallback_is_allowed_when_oodle_is_already_explicit(monkeypatch, tmp_path):
    def reject(_pak, _path):
        raise pak_reader.PakError("fixture direct-reader rejection")

    explicit = tmp_path / "oo2core_9_win64.dll"
    explicit.write_bytes(b"fixture")
    monkeypatch.setattr(pak_reader, "read_file", reject)
    monkeypatch.setattr(pak_reader, "repak_oodle_library", lambda: explicit)
    monkeypatch.setattr(
        tooling,
        "_command",
        lambda *args, **kwargs: SimpleNamespace(stdout=b"fallback-bytes"),
    )

    assert tooling.get_file(tmp_path / "fixture.pak", "A/B.uasset") == b"fallback-bytes"


def test_helper_status_declares_no_automatic_updates(monkeypatch, tmp_path):
    executable = tmp_path / "repak"
    executable.write_bytes(b"fixture")
    monkeypatch.setattr(tooling, "repak_path", lambda: executable)

    status = tooling.helper_status()

    assert status["installed"] is True
    assert status["pinned"] == "v0.2.3"
    assert status["autoUpdate"] is False
    assert status["source"] == "https://github.com/trumank/repak"


def test_direct_reader_finds_the_game_owned_oodle_library(monkeypatch, tmp_path):
    game = tmp_path / "game"
    pak = game / "End" / "Content" / "Paks" / "pakchunk0.pak"
    pak.parent.mkdir(parents=True)
    pak.write_bytes(b"fixture")
    shipped = (
        game / "Engine" / "Binaries" / "ThirdParty" / "Oodle" / "Win64"
        / "oo2core_7_win64.dll"
    )
    shipped.parent.mkdir(parents=True)
    shipped.write_bytes(b"fixture-oodle")
    monkeypatch.setattr(pak_reader, "repak_oodle_library", lambda: None)

    assert pak_reader.oodle_library(pak) == shipped
