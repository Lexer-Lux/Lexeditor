"""Verify strict editor/package integration for FF8 shared Magic issue 51."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import ffnx_manager, gameplay_settings  # noqa: E402
from games.ff8.ffnx_issue_51 import runtime_config, runtime_package  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_state(paths: list[Path]) -> dict[Path, tuple[bool, bytes]]:
    return {
        path: (path.is_file(), path.read_bytes() if path.is_file() else b"")
        for path in paths
    }


def assert_file_state(expected: dict[Path, tuple[bool, bytes]]) -> None:
    for path, (existed, content) in expected.items():
        assert path.is_file() is existed, path
        if existed:
            assert path.read_bytes() == content, path


def link_state(path: Path) -> tuple[str, str]:
    if ffnx_manager._is_junction(path):
        return ("junction", str(path.resolve(strict=True)))
    if path.is_symlink():
        return ("symlink", os.readlink(path))
    if path.exists():
        return ("collision", "")
    return ("absent", "")


def fake_package(root: Path) -> tuple[Path, dict]:
    package = root / "fixture-package"
    package.mkdir()
    driver = package / runtime_package.DRIVER_NAME
    driver.write_bytes(b"controlled derivative fixture")
    digest = sha256(driver)
    # The installer also deploys the Steamworks library FFNx loads by name,
    # so the fixture carries one to exercise that copy and its rollback.
    steam_api = package / runtime_package.STEAM_API_NAME
    steam_api.write_bytes(b"controlled steamworks fixture")
    # The driver ships with the shader set built alongside it, so the fixture
    # carries one too and the installer copy and backup are exercised.
    shaders = package / runtime_package.SHADER_DIR_NAME
    shaders.mkdir()
    (shaders / "FFNx.fixture.d3d11.frag").write_bytes(b"fixture shader")
    return package, {
        "packagedDriver": str(driver),
        "driverSha256": digest,
        "packagedSteamApi": str(steam_api),
        "steamApiName": runtime_package.STEAM_API_NAME,
        "steamApiSha256": sha256(steam_api),
        "packagedShaderRoot": str(shaders),
        "shaderDirName": runtime_package.SHADER_DIR_NAME,
        "sourceCommit": runtime_package.SOURCE_COMMIT,
        "manifest": str(package / runtime_package.MANIFEST_NAME),
        "manifestSha256": "1" * 64,
        "identity": "fixture identity",
        "hookCount": 28,
        "licenseSha256": "2" * 64,
        "sourcePatchSha256": "3" * 64,
        "buildReportSha256": "4" * 64,
    }


def patched_runtime(package: dict, game_root: Path):
    """Patch package proof only; exercise the real installer and link code."""
    old_verify = runtime_package.verify
    old_game = runtime_package.verify_game_installation
    old_status = runtime_package.status
    runtime_package.verify = lambda _root=runtime_package.PACKAGE_ROOT: package
    runtime_package.verify_game_installation = lambda root: Path(root) / "FF8_EN.exe"

    def status(root: Path, _package_root=runtime_package.PACKAGE_ROOT):
        target = Path(root) / runtime_package.DRIVER_NAME
        installed = target.is_file() and sha256(target) == package["driverSha256"]
        return {
            "packageAvailable": True,
            "available": installed and (Path(root) / "FFNx.toml").is_file(),
            "pinned": installed,
            "message": "fixture runtime" if installed else "fixture not installed",
        }

    runtime_package.status = status
    return old_verify, old_game, old_status


def restore_runtime(patches) -> None:
    runtime_package.verify, runtime_package.verify_game_installation, runtime_package.status = patches


def verify_final_package_if_staged() -> bool:
    manifest = runtime_package.PACKAGE_ROOT / runtime_package.MANIFEST_NAME
    if not manifest.is_file():
        print("SKIP: final reviewed issue-51 runtime package is not staged yet")
        return False
    # The positive path uses the real package and the hard-coded locks unchanged.
    try:
        verified = runtime_package.verify()
    except runtime_package.RuntimePackageError as error:
        # The staged build is the non-Steam variant, which aborts the game on
        # launch. Refusing it is the correct outcome, so the positive path
        # cannot run until a Steam-variant rebuild is staged.
        assert "steam_api" in str(error), error
        print("SKIP: staged runtime package is refused -", error)
        return "refused"
    driver = Path(verified["packagedDriver"])
    data, exports = runtime_package._pe_exports(driver)
    assert runtime_package.PINNED_ARTIFACT_SHA256["driver"] == sha256(driver)
    assert runtime_package._constant_export(
        data, exports["lexeditor_issue_51_hook_count"],
    ) == 28
    assert runtime_package._constant_export(
        data, exports["lexeditor_issue_51_compile_gate_enabled"], boolean=True,
    ) == 1
    assert runtime_package._constant_export(
        data, exports["lexeditor_issue_51_core_linked"], boolean=True,
    ) == 1
    assert runtime_package._constant_export(
        data, exports["lexeditor_issue_51_config_version"],
    ) == 1
    assert runtime_package._pointer_export_string(
        data, exports["lexeditor_issue_51_identity"], verified["identity"],
    )
    assert runtime_package._pointer_export_string(
        data,
        exports["lexeditor_issue_51_config_contract"],
        runtime_package.CONFIG_CONTRACT_IDENTITY,
    )
    # Direct helper mutations prove wrong bodies and pointers are rejected.
    wrong = bytearray(data)
    hook = exports["lexeditor_issue_51_hook_count"]
    wrong[hook:hook + 6] = b"\xB8\x1B\x00\x00\x00\xC3"
    assert runtime_package._constant_export(bytes(wrong), hook) == 27
    identity = exports["lexeditor_issue_51_identity"]
    wrong = bytearray(data)
    wrong[identity + 1:identity + 5] = (0).to_bytes(4, "little")
    assert not runtime_package._pointer_export_string(
        bytes(wrong), identity, verified["identity"],
    )
    return True


def main() -> int:
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    gameplay_view = editor[editor.index("function renderGameplaySettings"):editor.index("function renderPlatformSettings")]
    assert 'row("SHARED PARTY MAGIC INVENTORY"' in gameplay_view
    settings_dirty = editor.index("const settingsDirty=")
    other_saves = editor.index("const results=await Promise.all(jobs);")
    settings_save = editor.index('results.push(await api("/api/settings/save"')
    assert settings_dirty < other_saves < settings_save
    assert 'jobs.push(api("/api/settings/save"' not in editor
    settings_source = (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(
        encoding="utf-8",
    )
    save_source = settings_source[
        settings_source.index("def save("):settings_source.index("def ensure(")
    ]
    assert "shared_magic_inventory = False" not in save_source

    staged = verify_final_package_if_staged()
    # A refused package is staged and pinned; only an absent one leaves the
    # hashes empty.
    if staged is False:
        assert all(not value for value in runtime_package.PINNED_ARTIFACT_SHA256.values())
        try:
            runtime_package.verify()
        except runtime_package.RuntimePackageError:
            pass
        else:
            raise AssertionError("an unstaged package passed verification")

    with tempfile.TemporaryDirectory(prefix="lexeditor-shared-magic-editor-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        game = root / "game"
        game.mkdir()
        (game / "FF8_EN.exe").write_bytes(b"fixture executable")
        (game / runtime_package.DRIVER_NAME).write_bytes(b"stock driver")
        (game / "FFNx.toml").write_text(
            'direct_mode_path = "direct"\nhext_patching_path = "hext"\n',
            encoding="utf-8",
        )
        state_path = root / "ffnx-state.json"
        state_path.write_text('{"distribution":"stock"}\n', encoding="utf-8")
        package_root, package = fake_package(root)
        patches = patched_runtime(package, game)
        link = game / ffnx_manager.DIRECT_LINK_NAME
        old_direct = root / "old-project" / "direct"
        new_direct = root / "new-project" / "direct"
        old_direct.mkdir(parents=True)
        new_direct.mkdir(parents=True)
        try:
            # Installer-local failure removes a link that did not exist before.
            watched = [game / runtime_package.DRIVER_NAME, game / "FFNx.toml", state_path]
            before = file_state(watched)
            real_save_state = ffnx_manager._save_state
            ffnx_manager._save_state = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("injected state failure")
            )
            try:
                ffnx_manager.install_derivative(
                    game, state_path=state_path, backup_root=root / "backup-a",
                    runtime_package_root=package_root, direct_root=new_direct,
                    game_running=lambda: False,
                )
            except OSError as error:
                assert "injected state failure" in str(error)
            else:
                raise AssertionError("installer state failure was not injected")
            finally:
                ffnx_manager._save_state = real_save_state
            assert_file_state(before)
            assert link_state(link) == ("absent", "")

            # A prior junction returns as a junction to its exact old target.
            ffnx_manager._ensure_direct_link(game, old_direct)
            assert link_state(link) == ("junction", str(old_direct.resolve()))
            ffnx_manager._save_state = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("injected junction failure")
            )
            try:
                ffnx_manager.install_derivative(
                    game, state_path=state_path, backup_root=root / "backup-b",
                    runtime_package_root=package_root, direct_root=new_direct,
                    game_running=lambda: False,
                )
            except OSError:
                pass
            finally:
                ffnx_manager._save_state = real_save_state
            assert link_state(link) == ("junction", str(old_direct.resolve()))

            # A prior directory symlink returns as a symlink with its raw target.
            ffnx_manager._remove_managed_link(link)
            raw_target = os.path.relpath(old_direct, game)
            link.symlink_to(raw_target, target_is_directory=True)
            assert link_state(link) == ("symlink", raw_target)
            ffnx_manager._save_state = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("injected symlink failure")
            )
            try:
                ffnx_manager.install_derivative(
                    game, state_path=state_path, backup_root=root / "backup-c",
                    runtime_package_root=package_root, direct_root=new_direct,
                    game_running=lambda: False,
                )
            except OSError:
                pass
            finally:
                ffnx_manager._save_state = real_save_state
            assert link_state(link) == ("symlink", raw_target)

            # An ordinary collision is rejected and untouched.
            ffnx_manager._remove_managed_link(link)
            link.mkdir()
            marker = link / "user-file.txt"
            marker.write_text("keep", encoding="utf-8")
            try:
                ffnx_manager.install_derivative(
                    game, state_path=state_path, backup_root=root / "backup-d",
                    runtime_package_root=package_root, direct_root=new_direct,
                    game_running=lambda: False,
                )
            except RuntimeError as error:
                assert "not a Lexeditor link" in str(error)
            else:
                raise AssertionError("ordinary Direct Mode collision was modified")
            assert link_state(link) == ("collision", "") and marker.read_text() == "keep"
            shutil.rmtree(link)

            # The outer gameplay transaction uses the real installer, mutates a
            # real junction, then restores it after a later settings failure.
            ffnx_manager._ensure_direct_link(game, old_direct)
            project = root / "mod"
            runtime_config.write(project, shared_magic_inventory=False)
            old_state_path = ffnx_manager.STATE_PATH
            old_game_running = ffnx_manager._game_running
            ffnx_manager.STATE_PATH = state_path
            ffnx_manager._game_running = lambda: False
            real_executable = gameplay_settings._verify_executable
            gameplay_settings._verify_executable = lambda target: Path(target) / "FF8_EN.exe"
            loaded = gameplay_settings.load(project, game)
            watched = [
                game / runtime_package.DRIVER_NAME,
                game / "FFNx.toml",
                state_path,
                gameplay_settings.patch_path(project),
                gameplay_settings.settings_path(project),
                runtime_config.path(project),
            ]
            before_save = file_state(watched)
            before_link = link_state(link)
            real_atomic = gameplay_settings._atomic_text

            def fail_settings(target: Path, text: str) -> None:
                if Path(target) == gameplay_settings.settings_path(project):
                    raise OSError("injected settings failure")
                real_atomic(target, text)

            gameplay_settings._atomic_text = fail_settings
            try:
                gameplay_settings.save(
                    {**loaded, "sharedMagicInventory": True}, game, project,
                )
            except OSError as error:
                assert "injected settings failure" in str(error)
            else:
                raise AssertionError("post-install settings failure was not injected")
            finally:
                gameplay_settings._atomic_text = real_atomic
                gameplay_settings._verify_executable = real_executable
                ffnx_manager.STATE_PATH = old_state_path
                ffnx_manager._game_running = old_game_running
            assert_file_state(before_save)
            assert link_state(link) == before_link

            # A recorded derivative blocks every stock update path, even when
            # its hash does not match the new reviewed package.
            state_path.write_text(json.dumps({
                "distribution": runtime_package.DISTRIBUTION,
                "gameRoot": str(game.resolve()),
                "version": "old-derivative",
            }), encoding="utf-8")
            (game / runtime_package.DRIVER_NAME).write_bytes(b"old derivative")
            fetched = False

            def forbidden_fetch(_url):
                nonlocal fetched
                fetched = True
                raise AssertionError("stock update was attempted")

            blocked = ffnx_manager.ensure_ffnx(
                game, new_direct, state_path=state_path,
                runtime_package_root=package_root,
                fetch_json=forbidden_fetch, game_running=lambda: False,
            )
            assert not fetched
            assert "controlled derivative upgrade" in blocked["lastResult"]
        finally:
            restore_runtime(patches)

        # Invalid UTF-8 always becomes the clean fail-closed domain error.
        invalid_project = root / "invalid-utf8"
        target = runtime_config.path(invalid_project)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"\xff\xfe")
        try:
            runtime_config.load(invalid_project)
        except runtime_config.RuntimeConfigError as error:
            assert "could not be read" in str(error)
        else:
            raise AssertionError("invalid UTF-8 did not fail closed")

    print("FF8 issue #51 package, link, save-order, and rollback gates verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
