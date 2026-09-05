"""Compatibility facade for FF8 shared-party Magic inventory.

Shared Magic is implemented by Lexeditor's pinned FFNx derivative. It is not a
Hext patch: FF8 reads and writes character Magic through unrelated field,
battle, Draw, transfer, junction, party-change, scenario, and save paths.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from games.ff8.ffnx_issue_51 import runtime_package


DEFAULT_SHARED_MAGIC_INVENTORY = False
SUPPORTED_EXE_SHA256 = runtime_package.SUPPORTED_GAME_SHA256
SAVEMAP_CHARACTER_BASE = 0x01CFE0E8
SAVEMAP_CHARACTER_STRIDE = 0x98
CHARACTER_MAGIC_OFFSET = 0x10
MAGIC_SLOT_COUNT = 32
MAGIC_STOCK_LIMIT = 100


class SharedMagicUnavailableError(RuntimeError):
    """Raised when the verified derivative or supported game is unavailable."""


@dataclass(frozen=True)
class RuntimeBoundary:
    name: str
    requirement: str
    implementation: str


RUNTIME_BOUNDARIES = (
    RuntimeBoundary("migration", "losslessly merge eight private stocks", "native warning and atomic activation latch"),
    RuntimeBoundary("field-menu", "show and edit one shared stock", "guarded field-controller hooks"),
    RuntimeBoundary("draw", "add Draw gains to shared stock", "guarded Draw transaction hooks"),
    RuntimeBoundary("battle-cast", "read and consume shared stock", "guarded actor and callback hooks"),
    RuntimeBoundary("transfer", "disable private transfer duplication", "guarded transfer-family bypasses"),
    RuntimeBoundary("junction", "use shared quantities for junctions", "live canonical mirror invariant"),
    RuntimeBoundary("party-change", "retain stock across party changes", "guarded redistribution and swap hooks"),
    RuntimeBoundary("serializer", "persist one canonical pool", "canonical save transaction"),
    RuntimeBoundary("scenario", "isolate temporary scenario stock", "scenario suspend and resume transaction"),
    RuntimeBoundary("constructors", "preserve an active pool", "guarded inventory constructors"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_runtime(executable: Path, package_root: Path = runtime_package.PACKAGE_ROOT) -> dict:
    """Return static game and derivative evidence without loading either binary."""
    executable = Path(executable)
    digest = _sha256(executable) if executable.is_file() else ""
    package = None
    package_error = ""
    try:
        package = runtime_package.verify(package_root)
    except runtime_package.RuntimePackageError as error:
        package_error = str(error)
    supported = digest == SUPPORTED_EXE_SHA256
    ready = supported and package is not None
    return {
        "executable": str(executable),
        "sha256": digest,
        "supportedExecutable": supported,
        "ready": ready,
        "runtime": package,
        "runtimeError": package_error,
        "boundaries": [
            {
                "name": boundary.name,
                "requirement": boundary.requirement,
                "implementation": boundary.implementation,
                "covered": package is not None,
            }
            for boundary in RUNTIME_BOUNDARIES
        ],
    }


def build_hext(enabled: bool, executable: Path,
               package_root: Path = runtime_package.PACKAGE_ROOT) -> str:
    """Prove enabled-mode readiness; shared Magic never emits a Hext fragment."""
    if not isinstance(enabled, bool):
        raise TypeError("Shared Party Magic Inventory must be true or false")
    if not enabled:
        return ""
    report = inspect_runtime(executable, package_root)
    if not report["supportedExecutable"]:
        raise SharedMagicUnavailableError(
            "Shared Party Magic Inventory supports only the verified Steam English FF8_EN.exe."
        )
    if not report["ready"]:
        raise SharedMagicUnavailableError(
            "Shared Party Magic Inventory needs the verified Lexeditor FFNx derivative. "
            f"{report['runtimeError']}"
        )
    return ""
