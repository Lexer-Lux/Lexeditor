from types import SimpleNamespace
import hashlib
import json
import tarfile
import zipfile

import pytest

from plugins.ff7r import pak_reader, tooling


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
    monkeypatch.setenv("LEXEDITOR_REPAK", str(executable))

    status = tooling.helper_status()

    assert status["installed"] is True
    assert status["integrity"] == "external"
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


def test_bundled_repak_release_matches_published_archive_and_executable_hashes():
    manifest = json.loads(
        (tooling.BUNDLE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["tag"] == tooling.REPAK_TAG
    assert manifest["commit"] == "e215472c51db69328b1ce77be2db24d24c1d646b"
    assert (tooling.BUNDLE_ROOT / "LICENSE-MIT").is_file()
    assert (tooling.BUNDLE_ROOT / "LICENSE-APACHE").is_file()

    for platform, (archive, archive_sha, kind, member_name, executable_sha) in tooling.BUNDLES.items():
        assert archive.is_file(), platform
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_sha
        row = manifest["platforms"][platform]
        assert row["archiveSha256"] == archive_sha
        assert row["executableSha256"] == executable_sha
        if kind == "zip":
            with zipfile.ZipFile(archive) as package:
                matches = [name for name in package.namelist()
                           if name.rsplit("/", 1)[-1] == member_name]
                assert len(matches) == 1
                executable = package.read(matches[0])
        else:
            with tarfile.open(archive, "r:xz") as package:
                matches = [member for member in package.getmembers()
                           if member.isfile() and member.name.rsplit("/", 1)[-1] == member_name]
                assert len(matches) == 1
                source = package.extractfile(matches[0])
                assert source is not None
                executable = source.read()
        assert hashlib.sha256(executable).hexdigest() == executable_sha


def test_helper_install_uses_only_the_bundled_archive(monkeypatch, tmp_path):
    monkeypatch.delenv("LEXEDITOR_REPAK", raising=False)
    root = tmp_path / "repak-install"
    monkeypatch.setattr(tooling, "helper_root", lambda: root)

    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("helper_install must not use the network")

    monkeypatch.setattr(tooling.urllib.request, "urlopen", network_forbidden)
    result = tooling.helper_install()

    assert result["installed"] is True
    assert result["integrity"] == "verified"
    assert result["packageIntegrity"] == "verified"
    _, _, _, _, expected_executable_sha = tooling._bundle_spec()
    assert tooling._sha256_file(tooling.repak_path()) == expected_executable_sha


def test_modified_managed_repak_is_rejected(monkeypatch, tmp_path):
    monkeypatch.delenv("LEXEDITOR_REPAK", raising=False)
    root = tmp_path / "repak-install"
    root.mkdir(parents=True)
    name = "repak.exe" if tooling.os.name == "nt" else "repak"
    (root / name).write_bytes(b"modified")
    monkeypatch.setattr(tooling, "helper_root", lambda: root)

    status = tooling.helper_status()

    assert status["installed"] is False
    assert status["integrity"] == "mismatch"
    assert "Install/Repair" in status["message"]

def test_distribution_bundles_repak_archives_manifest_and_licenses():
    from tools import build_distribution

    required = {
        "plugins/ff7r/runtime/repak/v0.2.3/manifest.json",
        "plugins/ff7r/runtime/repak/v0.2.3/LICENSE-MIT",
        "plugins/ff7r/runtime/repak/v0.2.3/LICENSE-APACHE",
        "plugins/ff7r/runtime/repak/v0.2.3/repak_cli-x86_64-pc-windows-msvc.zip",
        "plugins/ff7r/runtime/repak/v0.2.3/repak_cli-x86_64-unknown-linux-gnu.tar.xz",
    }
    assert required <= set(build_distribution.VENDORED_HELPERS)

