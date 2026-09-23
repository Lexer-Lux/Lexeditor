from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

import pytest

from games.ff7r2 import packaging


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
        assert manifest["acceptedInGame"] is False
        assert manifest["installed"] is False
        assert manifest["tooling"]["dependencyDownloadInvokedByLexeditor"] is False
        assert manifest["tooling"]["unrealReZen"]["requiredCUE4Parse"] == packaging.CUE4PARSE_VERSION
        assert manifest["tooling"]["oodle"]["requiredName"] == packaging.OODLE_NAME
        assert manifest["tooling"]["oodle"]["alreadyInToolDirectory"] is True
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
