"""Controlled clean-install probe for Lexeditor issue #16.

The parent verifier copies the minimum RDR2 preparation runtime to an isolated
directory before it starts this script.  This script must therefore import and
exercise only that copied runtime.  It replaces external archive reads with a
deterministic tool stub; it does not weaken the extractor's validation or
installation-state behavior.
"""

from __future__ import annotations

import json
import hashlib
import sys
import time
from dataclasses import replace
from pathlib import Path


def _wait(manager, plugin_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.snapshot(plugin_id)
        if not state["scanInProgress"]:
            return state
        time.sleep(0.01)
    raise AssertionError(("clean-install scan did not finish", manager.snapshot(plugin_id)))


def _xml_fixture(root: str) -> bytes:
    return (
        f"<{root}><Item><Name>LEXEDITOR_ISSUE_16_FIXTURE</Name>"
        f"<Value value=\"1\" /></Item></{root}>"
    ).encode("utf-8")


def _raw_fixture(output: str) -> bytes:
    return b"PSIN" + output.encode("utf-8") + b"\x00LEXEDITOR_ISSUE_16"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: issue16_clean_install_probe.py COPIED_ROOT")
    copied_root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(copied_root))

    from games.rdr2 import extractor  # pylint: disable=import-outside-toplevel
    from games.rdr2 import plugin as rdr2_plugin  # pylint: disable=import-outside-toplevel
    from game_installation import GameInstallationManager  # pylint: disable=import-outside-toplevel

    PLUGIN = rdr2_plugin.PLUGIN
    assert Path(extractor.__file__).resolve().is_relative_to(copied_root), extractor.__file__
    assert Path(rdr2_plugin.__file__).resolve().is_relative_to(copied_root)
    assert rdr2_plugin.project_root().resolve().is_relative_to(copied_root)
    assert extractor.TOOL_ROOT.resolve().is_relative_to(copied_root), extractor.TOOL_ROOT
    assert all((extractor.TOOL_ROOT / name).is_file() for name in extractor.TOOL_FILES)

    # Small deterministic payloads retain every real path, method, and root
    # contract while avoiding large throwaway files in this isolated probe.
    extractor.ENTRIES = tuple(
        replace(
            entry,
            minimum_size=min(entry.minimum_size, 512),
            source_sha256=(
                hashlib.sha256(_raw_fixture(entry.output)).hexdigest().upper()
                if entry.kind == "pso-xml" else entry.source_sha256
            ),
        )
        for entry in extractor.ENTRIES
    )
    by_output = {entry.output: entry for entry in extractor.ENTRIES}
    failure = {"output": ""}

    def controlled_tool(command: list[str], _log_file: Path, label: str) -> None:
        assert Path(command[0]).resolve().is_relative_to(copied_root), command
        for argument in command:
            candidate = Path(argument)
            if candidate.is_absolute():
                assert candidate.resolve().is_relative_to(copied_root), command
        is_source = label.endswith(" source")
        output_label = label.removesuffix(" source")
        if not is_source and output_label == failure["output"]:
            raise RuntimeError(f"Controlled PSIN conversion failure: {label}")
        entry = by_output[output_label]
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if is_source:
            output.write_bytes(_raw_fixture(entry.output))
            return
        if entry.kind == "text-json":
            values = {f"0x{index:08X}": f"Fixture {index}" for index in range(10_001)}
            values["0x5DE85D64"] = "Irish Whiskey Bottle"
            output.write_text(json.dumps(values), encoding="utf-8")
            return
        payload = _xml_fixture(entry.expected_root or "LexeditorFixture")
        padding = max(0, entry.minimum_size - len(payload))
        closing = payload.rfind(b"</")
        output.write_bytes(payload[:closing] + (b" " * padding) + payload[closing:])

    extractor._run = controlled_tool

    private_root = extractor.PRIVATE_DATA_ROOT.resolve()
    private_root.mkdir(parents=True, exist_ok=True)
    game_root = copied_root / "fixture-game"
    game_root.mkdir(parents=True, exist_ok=True)
    (game_root / "RDR2.exe").write_bytes(b"fixture executable")
    for archive in {entry.archive for entry in extractor.ENTRIES}:
        (game_root / archive).write_bytes(("fixture " + archive).encode("utf-8"))

    plugin = replace(PLUGIN, check=lambda: [])
    success_root = private_root / "success"
    manager = GameInstallationManager(
        {plugin.plugin_id: plugin},
        config_path=copied_root / "success-installations.json",
        data_root=success_root,
        auto_scan=False,
    )
    manager.configure_directory(plugin.plugin_id, game_root)
    ready = _wait(manager, plugin.plugin_id)
    assert ready["status"] == "added" and ready["statusText"] == "Ready", ready
    assert ready["canOpen"] is True and not ready["problems"], ready
    cache = success_root / plugin.plugin_id
    manifest = json.loads((cache / "extraction-manifest.json").read_text("utf-8"))
    assert set(manifest["outputs"]) == set(by_output), manifest["outputs"].keys()
    serialized_manifest = json.dumps(manifest).casefold()
    assert "snapshot" not in serialized_manifest
    assert r"c:\rdr2mod".casefold() not in serialized_manifest
    assert all(
        extractor._valid_output(entry, cache / entry.output)
        for entry in extractor.ENTRIES
    )
    assert all(
        (cache / entry.output).stat().st_size > 0
        for entry in extractor.ENTRIES
    )
    assert extractor.ensure_rdr2_data(game_root, cache, lambda *_: None)["extracted"] == 0

    converter = next(
        entry for entry in extractor.ENTRIES if entry.output == "catalog_sp.ymt"
    )
    assert converter.kind not in {"xml", "rbf-xml", "text-json"}, converter.kind
    failure["output"] = converter.output
    failure_root = private_root / "failure"
    failed_manager = GameInstallationManager(
        {plugin.plugin_id: plugin},
        config_path=copied_root / "failure-installations.json",
        data_root=failure_root,
        auto_scan=False,
    )
    failed_manager.configure_directory(plugin.plugin_id, game_root)
    failed = _wait(failed_manager, plugin.plugin_id)
    expected_error = f"Controlled PSIN conversion failure: {converter.output}"
    assert failed["status"] == "warning", failed
    assert failed["statusText"] == "Game data preparation failed.", failed
    assert failed["scanStatus"] == "error" and failed["scanInProgress"] is False, failed
    assert failed["canOpen"] is False, failed
    assert failed["problems"] == [expected_error], failed
    assert not list((failure_root / plugin.plugin_id).rglob("*.lexeditor-part*"))

    print("Controlled copied-install preparation and conversion failure verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
