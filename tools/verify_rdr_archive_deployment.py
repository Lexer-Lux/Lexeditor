from pathlib import Path
import tempfile

from games.rdr.archive_deployment import (
    ArchiveSpec, deploy_archives, deployment_status, revert_archives, sha256_file,
)


def build_fixture(_tool: Path, source: Path, output: Path, manifest: Path) -> None:
    rows = manifest.read_text(encoding="utf-8").splitlines()
    payload = bytearray(source.read_bytes())
    for row in rows:
        if not row:
            continue
        archive_path, replacement = row.split("\t", 1)
        payload.extend(b"\nLEXEDITOR:" + archive_path.encode() + b"\n")
        payload.extend(Path(replacement).read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(bytes(payload))


def no_process(_names):
    return []


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rdr-deploy-test-") as name:
        root = Path(name)
        game = root / "game-root"
        project = root / "project"
        tool = root / "Rpf6ReadCli.exe"
        tool.write_bytes(b"fixture")
        (game / "winmm.dll").parent.mkdir(parents=True, exist_ok=True)
        (game / "winmm.dll").write_bytes(b"fixture loader")
        specs = []
        for label, archive in (
            ("tuning", "tune_d11generic.rpf"),
            ("content", "content.rpf"),
            ("gringores", "gringores.rpf"),
        ):
            source = game / "game" / archive
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"RPF6" + label.encode() + b"-original")
            override = project / label
            specs.append(ArchiveSpec(label, Path("game") / archive, override))
        specs = tuple(specs)

        external = game / "update" / "game" / "content.rpf"
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_bytes(b"existing-user-update")
        external_hash = sha256_file(external)
        source_hashes = {spec.name: sha256_file(game / spec.source_relative) for spec in specs}

        tune_override = project / "tuning" / "tune" / "ai" / "motives.xml"
        tune_override.parent.mkdir(parents=True, exist_ok=True)
        tune_override.write_text("<motives><value>project</value></motives>", encoding="utf-8")
        content_override = project / "content" / "content" / "init" / "inventory" / "inventory.xml"
        content_override.parent.mkdir(parents=True, exist_ok=True)
        content_override.write_text('<inventory project="1"/>', encoding="utf-8")

        result = deploy_archives(game, tool, specs, builder=build_fixture, running_check=no_process)
        assert result["changed"] == 2 and result["active"]
        for spec in specs:
            assert sha256_file(game / spec.source_relative) == source_hashes[spec.name]
        tune_target = game / "update" / "game" / "tune_d11generic.rpf"
        assert tune_target.is_file() and b"project" in tune_target.read_bytes()
        assert external.is_file() and sha256_file(external) != external_hash
        status = deployment_status(game, specs)
        assert not status["pending"] and sum(row["deployed"] for row in status["rows"]) == 2

        tune_override.write_text("<motives><value>project-two</value></motives>", encoding="utf-8")
        assert deployment_status(game, specs)["pending"]
        second = deploy_archives(game, tool, specs, builder=build_fixture, running_check=no_process)
        assert second["changed"] == 2 and b"project-two" in tune_target.read_bytes()

        reverted = revert_archives(game, specs, running_check=no_process)
        assert reverted["changed"] == 2 and not reverted["active"]
        assert not tune_target.exists()
        assert external.is_file() and sha256_file(external) == external_hash
        for spec in specs:
            assert sha256_file(game / spec.source_relative) == source_hashes[spec.name]

        deploy_archives(game, tool, specs, builder=build_fixture, running_check=no_process)
        tune_target.write_bytes(b"somebody changed this update archive")
        try:
            revert_archives(game, specs, running_check=no_process)
        except RuntimeError as error:
            assert "changed outside Lexeditor" in str(error)
        else:
            raise AssertionError("concurrent update archive change was overwritten")

    print("PASS RDR archive deployment: immutable sources, update-folder ownership, redeploy, revert, concurrent-change refusal")


if __name__ == "__main__":
    main()
