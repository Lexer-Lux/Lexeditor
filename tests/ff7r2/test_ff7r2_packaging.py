from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

import pytest

from plugins.ff7r2 import packaging


def _fixture(root: Path):
    project = root / "project"
    game = root / "game"
    staged = project / packaging.STAGED_PLAYER
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"synthetic-playerparameter")
    paks = game / "End/Content/Paks"
    paks.mkdir(parents=True)
    (paks / "pakchunk3-WindowsNoEditor.utoc").write_bytes(b"utoc")
    (paks / "pakchunk3-WindowsNoEditor.ucas").write_bytes(b"ucas")
    tool = root / "tool"
    tool.mkdir()
    packer = tool / "UnrealReZen.exe"
    packer.write_bytes(b"explicit-packer")
    packer.with_name("UnrealReZen.deps.json").write_text(
        json.dumps({"libraries": {f"CUE4Parse/{packaging.CUE4PARSE_VERSION}": {}}}),
        encoding="utf-8",
    )
    oodle = tool / packaging.OODLE_NAME
    oodle.write_bytes(b"explicit-oodle")
    env = {
        packaging.UNREALREZEN_ENV: str(packer),
        packaging.OODLE_ENV: str(oodle),
    }
    return project, game, packer, oodle, env


def test_packaging_status_refuses_implicit_dependencies():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-status-") as temp_name:
        project, game, _packer, _oodle, _env = _fixture(Path(temp_name))
        state = packaging.status(project, game, {})
        assert state["ready"] is False
        assert state["downloadsDependencies"] is False
        assert any(packaging.UNREALREZEN_ENV in item for item in state["missing"])
        assert any(packaging.OODLE_ENV in item for item in state["missing"])



def test_packaging_status_rejects_unknown_cue4parse_distribution():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-version-") as temp_name:
        project, game, packer, _oodle, env = _fixture(Path(temp_name))
        packer.with_name("UnrealReZen.deps.json").write_text(
            json.dumps({"libraries": {"CUE4Parse/9.9.9": {}}}),
            encoding="utf-8",
        )
        state = packaging.status(project, game, env)
        assert state["ready"] is False
        assert state["packerPresent"] is True
        assert state["packerDependencyOk"] is False
        assert any("CUE4Parse/1.1.1" in item for item in state["missing"])


def test_packaging_status_requires_oodle_beside_packer():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-oodle-") as temp_name:
        root = Path(temp_name)
        project, game, _packer, oodle, env = _fixture(root)
        elsewhere = root / "elsewhere" / packaging.OODLE_NAME
        elsewhere.parent.mkdir()
        elsewhere.write_bytes(oodle.read_bytes())
        env[packaging.OODLE_ENV] = str(elsewhere)
        state = packaging.status(project, game, env)
        assert state["ready"] is False
        assert state["oodlePresent"] is True
        assert state["oodleInToolDirectory"] is False
        assert any("beside the explicit UnrealReZen executable" in item for item in state["missing"])

def test_candidate_builder_is_isolated_and_never_installs():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-build-") as temp_name:
        project, game, packer, oodle, env = _fixture(Path(temp_name))
        paks_before = sorted(path.name for path in (game / "End/Content/Paks").iterdir())
        observed = {}

        def fake_runner(command, **kwargs):
            observed["command"] = list(command)
            observed["cwd"] = kwargs["cwd"]
            observed["env"] = dict(kwargs["env"])
            assert Path(kwargs["cwd"]).resolve() == packer.parent.resolve()
            runtime_oodle = Path(kwargs["cwd"]) / packaging.OODLE_NAME
            assert runtime_oodle.resolve() == oodle.resolve()
            assert runtime_oodle.read_bytes() == oodle.read_bytes()
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="Done", stderr="")

        result = packaging.build_candidate(project, game, env, runner=fake_runner)
        candidate = Path(result["candidateDirectory"])
        assert candidate.is_dir()
        assert candidate.parent == project / "build"
        assert result["installed"] is False
        assert result["acceptedInGame"] is False
        assert sorted(path.name for path in (game / "End/Content/Paks").iterdir()) == paks_before
        assert oodle.read_bytes() == b"explicit-oodle"

        command = observed["command"]
        assert command[0] == str(packer.resolve())
        assert command[command.index("--game-dir") + 1] == str((game / "End/Content/Paks").resolve())
        assert command[command.index("--content-path") + 1] == str((project / "content/End/Content").resolve())
        assert command[command.index("--engine-version") + 1] == packaging.ENGINE_VERSION
        assert command[command.index("--compression-format") + 1] == "Zlib"
        assert command[command.index("--mount-point") + 1] == packaging.MOUNT_POINT
        assert "--game-dir-top-only" in command
        assert observed["env"][packaging.UNREALREZEN_ENV] == str(packer)

        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        assert manifest["schema"] == 2
        assert manifest["inputs"] == [{
            "path": packaging.STAGED_PLAYER.as_posix(),
            "sha256": packaging._sha256(project / packaging.STAGED_PLAYER),
            "bytes": len(b"synthetic-playerparameter"),
        }]
        assert manifest["acceptedInGame"] is False
        assert manifest["installed"] is False
        assert manifest["tooling"]["dependencyDownloadInvokedByLexeditor"] is False
        assert manifest["tooling"]["unrealReZen"]["requiredCUE4Parse"] == packaging.CUE4PARSE_VERSION
        assert manifest["tooling"]["oodle"]["requiredName"] == packaging.OODLE_NAME
        assert manifest["tooling"]["oodle"]["alreadyInToolDirectory"] is True
        assert manifest["loadOrder"]["candidate"] == {
            "package": "Lexeditor-FF7R2_P.pak",
            "patchLevel": 0,
            "effectiveOrder": 100,
        }
        assert manifest["loadOrder"]["contentsCompared"] is False
        assert manifest["loadOrder"]["observedNativeMods"]["ranked"] == []
        assert {item["file"] for item in manifest["outputs"]} == {
            "Lexeditor-FF7R2_P.utoc",
            "Lexeditor-FF7R2_P.ucas",
            "Lexeditor-FF7R2_P.pak",
        }


def test_candidate_builder_rejects_oodle_mutation_and_cleans_output():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-mutation-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))

        def mutating_runner(command, **kwargs):
            runtime_oodle = Path(kwargs["cwd"]) / packaging.OODLE_NAME
            runtime_oodle.write_bytes(b"changed")
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with pytest.raises(packaging.PackagingError, match="Supplied Oodle DLL changed"):
            packaging.build_candidate(project, game, env, runner=mutating_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))



@pytest.mark.parametrize(
    ("target_env", "expected"),
    [
        (packaging.UNREALREZEN_ENV, "UnrealReZen executable changed"),
        (packaging.OODLE_ENV, "Supplied Oodle DLL changed"),
    ],
)
def test_candidate_builder_rejects_dependency_race(target_env, expected):
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-race-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))

        def mutating_runner(command, **kwargs):
            Path(kwargs["env"][target_env]).write_bytes(b"changed-during-build")
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with pytest.raises(packaging.PackagingError, match=expected):
            packaging.build_candidate(project, game, env, runner=mutating_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))


def test_candidate_builder_rejects_dependency_manifest_race():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-deps-race-") as temp_name:
        project, game, packer, _oodle, env = _fixture(Path(temp_name))
        deps = packer.with_name("UnrealReZen.deps.json")

        def mutating_runner(command, **kwargs):
            deps.write_text('{"libraries": {}}', encoding="utf-8")
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with pytest.raises(packaging.PackagingError, match="dependency manifest changed"):
            packaging.build_candidate(project, game, env, runner=mutating_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))


def test_candidate_builder_timeout_is_bounded_and_cleans_output():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-timeout-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))

        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        with pytest.raises(packaging.PackagingError, match="timed out after 300 seconds"):
            packaging.build_candidate(project, game, env, runner=timeout_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))

def test_candidate_builder_refuses_missing_staged_output_before_execution():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-missing-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        (project / packaging.STAGED_PLAYER).unlink()
        called = False

        def should_not_run(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("runner should not execute")

        with pytest.raises(packaging.PackagingError, match="not ready"):
            packaging.build_candidate(project, game, env, runner=should_not_run)
        assert called is False

def test_candidate_builder_tracks_all_staged_inputs():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-inputs-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        extra = project / packaging.CONTENT_ROOT / "DataObject/Resident/CardGameCommonParameter.uasset"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"synthetic-card-game")

        state = packaging.status(project, game, env)
        assert state["ready"] is True
        assert state["stagedFileCount"] == 2
        expected_inputs = sorted([
            packaging.STAGED_PLAYER.as_posix(),
            (packaging.CONTENT_ROOT / "DataObject/Resident/CardGameCommonParameter.uasset").as_posix(),
        ])
        assert state["stagedFiles"] == expected_inputs

        def fake_runner(command, **_kwargs):
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        result = packaging.build_candidate(project, game, env, runner=fake_runner)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        assert [item["path"] for item in manifest["inputs"]] == state["stagedFiles"]
        assert {item["bytes"] for item in manifest["inputs"]} == {
            len(b"synthetic-playerparameter"),
            len(b"synthetic-card-game"),
        }


def test_candidate_builder_rejects_staged_input_mutation():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-input-mutation-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        extra = project / packaging.CONTENT_ROOT / "DataObject/Resident/CardGameCommonParameter.uasset"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_bytes(b"before")

        def mutating_runner(command, **_kwargs):
            extra.write_bytes(b"after")
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with pytest.raises(packaging.PackagingError, match="Staged input changed"):
            packaging.build_candidate(project, game, env, runner=mutating_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))


def test_candidate_builder_rejects_staged_set_mutation():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-packaging-set-mutation-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        added = project / packaging.CONTENT_ROOT / "DataObject/Resident/ResidentParameter.uasset"

        def mutating_runner(command, **_kwargs):
            added.parent.mkdir(parents=True, exist_ok=True)
            added.write_bytes(b"appeared-during-build")
            output = Path(command[command.index("--output-path") + 1])
            output.write_bytes(b"candidate-utoc")
            output.with_suffix(".ucas").write_bytes(b"candidate-ucas")
            output.with_suffix(".pak").write_bytes(b"candidate-pak")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with pytest.raises(packaging.PackagingError, match="Staged content set changed"):
            packaging.build_candidate(project, game, env, runner=mutating_runner)
        assert not list((project / "build").glob("ff7r2-candidate-*"))



def test_native_mod_precedence_reports_numeric_patch_levels_and_path_order():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-load-order-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        mods = game / "End/Content/Paks/~mods"
        mods.mkdir()

        def triple(relative: str) -> None:
            pak = mods / relative
            pak.parent.mkdir(parents=True, exist_ok=True)
            for suffix in (".pak", ".utoc", ".ucas"):
                pak.with_suffix(suffix).write_bytes(b"synthetic-mod")

        triple("ZMod_2_P.pak")
        triple("A_Mod/Other_P.pak")
        triple("ZMod_P.pak")
        triple("!Mod_P.pak")
        triple("LooseName.pak")
        incomplete = mods / "Broken_P.pak"
        incomplete.write_bytes(b"pak-only")

        state = packaging.status(project, game, env)["loadOrder"]
        assert state["present"] is True
        ranked = state["ranked"]
        assert [item["package"] for item in ranked] == [
            "ZMod_2_P.pak",
            "!Mod_P.pak",
            "A_Mod/Other_P.pak",
            "ZMod_P.pak",
        ]
        assert ranked[0]["patchLevel"] == 2
        assert ranked[0]["effectiveOrder"] == 300
        assert [item["winnerRank"] for item in ranked] == [1, 2, 3, 4]
        assert state["unranked"][0]["package"] == "LooseName.pak"
        assert state["incomplete"][0]["package"] == "Broken_P.pak"
        assert set(state["incomplete"][0]["missing"]) == {
            "Broken_P.utoc", "Broken_P.ucas"
        }
        assert "package contents are not inspected" in state["scope"].lower()


def test_native_mod_precedence_rejects_symlinked_sidecars():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-load-order-link-") as temp_name:
        project, game, _packer, _oodle, env = _fixture(Path(temp_name))
        mods = game / "End/Content/Paks/~mods"
        mods.mkdir()
        (mods / "Linked_P.pak").write_bytes(b"pak")
        target = mods / "real.utoc"
        target.write_bytes(b"utoc")
        try:
            (mods / "Linked_P.utoc").symlink_to(target)
        except OSError:
            pytest.skip("File symlinks are unavailable in this test environment")
        (mods / "Linked_P.ucas").write_bytes(b"ucas")

        state = packaging.status(project, game, env)["loadOrder"]
        assert state["ranked"] == []
        assert state["incomplete"] == [{
            "package": "Linked_P.pak",
            "missing": ["Linked_P.utoc"],
        }]
