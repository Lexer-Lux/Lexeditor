"""Safe Chrono Trigger project overlays and deterministic CTP export."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from .archive import ResourcesBin


PROJECT_MARKER = "lexeditor-chrono-trigger.json"
ALLOWED_ROOTS = {"Game", "Localize"}


def digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def validate_resource_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] not in ALLOWED_ROOTS:
        raise ValueError("Chrono Trigger project paths must stay under Game/ or Localize/")
    if any(not part or part in {".", ".."} for part in pure.parts):
        raise ValueError("Invalid Chrono Trigger resource path")
    return pure.as_posix()


def initialize_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    marker = root / PROJECT_MARKER
    if not marker.exists():
        marker.write_text(json.dumps({"schema": 1, "game": "chrono-trigger", "edition": "steam"}, indent=2) + "\n", encoding="utf-8")


class OverlayStore:
    def __init__(self, archive: ResourcesBin, project_root: Path | str):
        self.archive = archive
        self.project_root = Path(project_root).resolve()
        initialize_project(self.project_root)

    def _project_path(self, virtual: str) -> Path:
        virtual = validate_resource_path(virtual)
        target = (self.project_root / Path(*PurePosixPath(virtual).parts)).resolve()
        if self.project_root not in target.parents:
            raise ValueError("Project resource escaped the project root")
        return target

    def read(self, virtual: str, source: str = "mine") -> tuple[bytes, str]:
        virtual = validate_resource_path(virtual)
        if source not in {"mine", "vanilla"}:
            raise ValueError("source must be mine or vanilla")
        if source == "mine":
            target = self._project_path(virtual)
            if target.is_file():
                return target.read_bytes(), "project"
        return self.archive.extract(virtual), "vanilla"

    def write(self, virtual: str, expected_sha256: str, payload: bytes) -> Path:
        current, _ = self.read(virtual, "mine")
        if digest(current) != expected_sha256:
            raise RuntimeError(f"{virtual} changed since it was opened; reload before saving")
        target = self._project_path(virtual)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target

    def changes(self) -> list[dict]:
        rows: list[dict] = []
        for root_name in sorted(ALLOWED_ROOTS):
            root = self.project_root / root_name
            if not root.is_dir():
                continue
            for target in sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink()):
                virtual = target.relative_to(self.project_root).as_posix()
                payload = target.read_bytes()
                vanilla = self.archive.extract(virtual) if self.archive.has(virtual) else None
                rows.append({
                    "path": virtual,
                    "size": len(payload),
                    "sha256": digest(payload),
                    "status": "added" if vanilla is None else ("redundant" if payload == vanilla else "modified"),
                })
        return rows

    def revert(self, virtual: str) -> None:
        target = self._project_path(virtual)
        if target.is_file():
            target.unlink()
        parent = target.parent
        while parent != self.project_root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    def export_ctp(self, output: Path | None = None) -> dict:
        inspected = self.changes()
        added = [row["path"] for row in inspected if row["status"] == "added"]
        if added:
            preview = ", ".join(added[:5]) + (" ..." if len(added) > 5 else "")
            raise ValueError(
                "CTP loaders replace existing resources.bin entries and ignore unknown paths; "
                f"remove added project files before export: {preview}"
            )
        changes = [row for row in inspected if row["status"] == "modified"]
        if output is None:
            output = self.project_root / "build" / f"{self.project_root.name}.ctp"
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if self.project_root not in output.parents:
            raise ValueError("CTP export must stay inside the selected project")
        temporary = output.with_suffix(output.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for row in sorted(changes, key=lambda value: value["path"]):
                    path = row["path"]
                    info = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    info.create_system = 3
                    archive.writestr(info, self._project_path(path).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path": str(output), "fileCount": len(changes), "files": [row["path"] for row in changes], "replacementOnly": True}
