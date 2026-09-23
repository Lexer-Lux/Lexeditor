"""Explicit local FF8 testing only; does not change official package trust pins."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .ffnx_issue_51 import runtime_package


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".local-candidate-", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(value)
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


def _closed() -> None:
    from .ffnx_manager import running_processes
    if running_processes():
        raise RuntimeError("Close FF8 and its launcher before changing the local candidate")


def install(candidate: Path, game_root: Path, expected_sha256: str) -> dict:
    """Install one explicitly selected, already tested build with one rollback."""
    candidate, game_root = Path(candidate).resolve(), Path(game_root).resolve()
    driver = candidate / "AF3DN.P"
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or digest(driver) != expected_sha256:
        raise ValueError("Local candidate does not match the explicitly selected SHA-256")
    runtime_package.verify_game_installation(game_root)
    image, _ = runtime_package._pe_exports(driver)
    runtime_package._reject_unloadable_manifest(image)
    provenance = {name: digest(candidate / name) for name in (
        "ISSUE51_DERIVATIVE_SOURCE.patch", "SOURCE_INPUTS.sha256", "BUILD.txt", "LICENSE")}
    _closed()
    target = game_root / "AF3DN.P"
    saved = candidate / "local-install"
    receipt = saved / "receipt.json"
    if receipt.exists():
        record = json.loads(receipt.read_text(encoding="utf-8"))
        if record["gameRoot"] != str(game_root) or record["candidateSha256"] != expected_sha256:
            raise RuntimeError("This candidate already has a rollback for a different installation")
        if digest(target) == expected_sha256:
            return record
        if record.get("state") not in {"restored", "prepared"} or digest(target) != record["originalSha256"]:
            raise RuntimeError("Restore or inspect the previous local install before reinstalling")
    original = target.read_bytes()
    record = {"kind": "local-test-candidate", "gameRoot": str(game_root),
              "candidateSha256": expected_sha256, "originalSha256": digest(target),
              "provenance": provenance, "settingsChanged": False, "state": "prepared"}
    _write(saved / "AF3DN.P", original)
    config = game_root / "FFNx.toml"
    if config.exists():
        _write(saved / "FFNx.toml", config.read_bytes())
        record["settingsSha256"] = digest(config)
    _write(receipt, json.dumps(record, indent=2).encode())
    _closed()
    try:
        _write(target, driver.read_bytes())
        if digest(target) != expected_sha256:
            raise OSError("Installed local candidate failed readback")
        record["state"] = "installed"
        _write(receipt, json.dumps(record, indent=2).encode())
    except Exception:
        _write(target, original)
        raise
    return record


def rollback(candidate: Path) -> dict:
    saved = Path(candidate).resolve() / "local-install"
    receipt = saved / "receipt.json"
    record = json.loads(receipt.read_text(encoding="utf-8"))
    game_root = Path(record["gameRoot"]).resolve()
    runtime_package.verify_game_installation(game_root)
    _closed()
    target = game_root / "AF3DN.P"
    backup = saved / "AF3DN.P"
    if digest(backup) != record["originalSha256"]:
        raise ValueError("Local rollback backup has changed")
    if digest(target) == record["originalSha256"]:
        return record
    if digest(target) != record["candidateSha256"]:
        raise RuntimeError("Installed DLL changed after this test; refusing to overwrite it")
    _write(target, backup.read_bytes())
    if digest(target) != record["originalSha256"]:
        raise OSError("Local rollback failed readback")
    record["state"] = "restored"
    _write(receipt, json.dumps(record, indent=2).encode())
    # Settings were never changed; retain any edits made while testing.
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("install", "rollback"))
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.operation == "install":
        if args.game_root is None or args.sha256 is None:
            parser.error("install requires --game-root and --sha256")
        result = install(args.candidate, args.game_root, args.sha256)
    else:
        result = rollback(args.candidate)
    print(json.dumps(result, indent=2))
