"""Synthetic RDR1 mod compatibility checks using documented PC package shapes.

No game assets are used. The fixtures mirror public installation layouts:
whole-archive update/game/content.rpf, loose WSC merge inputs, root ASI/.red
plugins, and game/patchN.rpf layers. This verifies Lexeditor ownership,
collision and restoration only; it does not claim third-party loader execution.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.rdr.archive_deployment import ArchiveSpec, deploy_archives, revert_archives, sha256_file


def build_fixture(_tool: Path, source: Path, output: Path, manifest: Path) -> None:
    payload = bytearray(source.read_bytes())
    for row in manifest.read_text(encoding="utf-8").splitlines():
        if not row:
            continue
        archive_path, replacement = row.split("\t", 1)
        payload += b"\nLEXEDITOR:" + archive_path.encode("utf-8") + b"\n"
        payload += Path(replacement).read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)


def no_process(_names):
    return []


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rdr-mod-compat-") as name:
        root = Path(name)
        game = root / "RDR"
        project = root / "project" / "content"
        tool = root / "Rpf6ReadCli.exe"
        tool.write_bytes(b"synthetic builder")
        (game / "winmm.dll").parent.mkdir(parents=True, exist_ok=True)
        (game / "winmm.dll").write_bytes(b"synthetic Ultimate ASI Loader / RedHook proxy")

        source = game / "game" / "content.rpf"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"RPF6STOCK-CONTENT")
        source_hash = sha256_file(source)

        unmanaged = {
            game / "RDRFix.asi": b"synthetic root ASI plugin",
            game / "ExampleMod.red": b"synthetic RedHook plugin",
            game / "rpf_patch.asi": b"synthetic patch-layer loader",
            game / "game" / "patch0.rpf": b"RPF6PATCH-ZERO",
            game / "game" / "patch9.rpf": b"RPF6PATCH-NINE",
        }
        for path, payload in unmanaged.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        unmanaged_hashes = {path: sha256_file(path) for path in unmanaged}

        external_archive = game / "update" / "game" / "content.rpf"
        external_archive.parent.mkdir(parents=True, exist_ok=True)
        external_archive.write_bytes(b"RPF6EXTERNAL-WHOLE-CONTENT-MOD")
        external_hash = sha256_file(external_archive)

        inventory = project / "content" / "init" / "inventory" / "inventory.xml"
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_text('<inventory source="lexeditor"/>', encoding="utf-8")
        script = project / "content" / "release64" / "scripting" / "gringo" / "commonscripts" / "loot.wsc"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_bytes(b"synthetic loose WSC replacement")

        spec = (ArchiveSpec("content", Path("game/content.rpf"), project),)
        result = deploy_archives(game, tool, spec, builder=build_fixture, running_check=no_process)
        assert result["active"] and result["changed"] == 1
        deployed = external_archive.read_bytes()
        assert b'<inventory source="lexeditor"/>' in deployed
        assert b"synthetic loose WSC replacement" in deployed
        assert b"EXTERNAL-WHOLE-CONTENT-MOD" not in deployed
        deployed_bytes = deployed
        assert sha256_file(source) == source_hash
        for path, digest in unmanaged_hashes.items():
            assert sha256_file(path) == digest, f"unmanaged mod was changed: {path}"

        reverted = revert_archives(game, spec, running_check=no_process)
        assert reverted["changed"] == 1 and not reverted["active"]
        assert sha256_file(external_archive) == external_hash
        for path, digest in unmanaged_hashes.items():
            assert sha256_file(path) == digest, f"unmanaged mod changed during revert: {path}"

        deploy_archives(game, tool, spec, builder=build_fixture, running_check=no_process)
        external_archive.write_bytes(b"RPF6EXTERNAL-CHANGED-AFTER-LEXEDITOR")
        try:
            deploy_archives(game, tool, spec, builder=build_fixture, running_check=no_process)
        except RuntimeError as error:
            assert "changed outside Lexeditor" in str(error)
        else:
            raise AssertionError("redeploy overwrote an externally changed archive")
        try:
            revert_archives(game, spec, running_check=no_process)
        except RuntimeError as error:
            assert "changed outside Lexeditor" in str(error)
        else:
            raise AssertionError("revert overwrote an externally changed archive")

        external_archive.write_bytes(deployed_bytes)
        revert_archives(game, spec, running_check=no_process)
        assert sha256_file(external_archive) == external_hash

    print("PASS RDR public-mod-shaped compatibility: whole-archive overlap is non-merged and reversible; loose WSC + inventory overrides combine; root ASI/.red and patchN files remain untouched; external post-deploy changes block overwrite")
    print("NOTE patchN priority and RedHook plugin execution remain runtime-loader evidence, not synthetic claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
