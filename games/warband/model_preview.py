"""Resolve Warband inventory meshes from installed BRF and DDS resources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from PIL import Image

from . import paths


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(paths.MOD_PROJECT)
GAME_ROOT = Path(paths.WARBAND_ROOT)
MODULE_ROOT = PROJECT / "Module"
MODULE_INI = MODULE_ROOT / "module.ini"
COMMON_RES = GAME_ROOT / "CommonRes"
MODULE_RES = MODULE_ROOT / "Resource"
GAME_TEXTURES = GAME_ROOT / "Textures"
MODULE_TEXTURES = MODULE_ROOT / "Textures"
BRF_SYNC = LEXEDITOR_ROOT / "tools" / "brf-sync" / "bin" / "brf_sync.exe"
LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
CACHE_ROOT = LOCAL_DATA / "Lexeditor" / "game-data" / "warband" / "model-previews"
_LOCK = threading.RLock()
_RESOURCE_RE = re.compile(r"^\s*(load_resource|load_mod_resource)\s*=\s*([^#;\s]+)", re.I)


class PreviewUnavailable(RuntimeError):
    """The selected item does not resolve to a previewable installed mesh."""


def _resource_paths() -> list[Path]:
    if not MODULE_INI.is_file():
        return []
    ordered = []
    for line in MODULE_INI.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _RESOURCE_RE.match(line)
        if not match:
            continue
        folder = COMMON_RES if match.group(1).casefold() == "load_resource" else MODULE_RES
        candidate = folder / (match.group(2) + ".brf")
        if candidate.is_file():
            ordered.append(candidate.resolve())
    return ordered


def _stamp(path: Path) -> str:
    info = path.stat()
    raw = f"{path}|{info.st_size}|{info.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _run_tool(command: str, source: Path, destination: Path) -> None:
    if not BRF_SYNC.is_file():
        raise PreviewUnavailable("The bundled Warband BRF reader is missing.")
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(BRF_SYNC), command, str(source), str(destination)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise PreviewUnavailable((result.stderr or result.stdout or "BRF read failed").strip())


def _metadata(resource: Path) -> dict:
    destination = CACHE_ROOT / "brf-info" / _stamp(resource)
    data_file = destination / "data.json"
    if not data_file.is_file():
        _run_tool("info", resource, destination)
    return json.loads(data_file.read_text(encoding="utf-8"))


def _find_record(kind: str, name: str) -> tuple[Path, dict] | None:
    target = name.casefold()
    # Later module.ini resources replace earlier resources with the same name.
    for resource in reversed(_resource_paths()):
        records = _metadata(resource).get(kind, [])
        match = next((row for row in records if str(row.get("name", "")).casefold() == target), None)
        if match is not None:
            return resource, match
    return None


def _texture_file(name: str) -> Path | None:
    if not name or name.casefold() == "none":
        return None
    filename = name if name.casefold().endswith(".dds") else name + ".dds"
    for root in (MODULE_TEXTURES, GAME_TEXTURES):
        direct = root / filename
        if direct.is_file():
            return direct.resolve()
        if root.is_dir():
            match = next((path for path in root.glob("*.dds") if path.name.casefold() == filename.casefold()), None)
            if match:
                return match.resolve()
    return None


def _export_mesh(resource: Path, mesh: str) -> Path:
    destination = CACHE_ROOT / "brf-export" / _stamp(resource)
    target = destination / "Meshes" / f"{mesh}.obj"
    if not target.is_file():
        _run_tool("export", resource, destination)
    if target.is_file():
        return target
    # The BRF record match is case-insensitive, but the exporter preserves case.
    match = next((path for path in (destination / "Meshes").glob("*.obj") if path.stem.casefold() == mesh.casefold()), None)
    if match is None:
        raise PreviewUnavailable(f"The BRF exporter did not produce mesh {mesh}.")
    return match


def _parse_obj(path: Path) -> dict:
    source_positions: list[list[float]] = []
    source_normals: list[list[float]] = []
    source_uvs: list[list[float]] = []
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    uvs: list[list[float]] = []
    triangles: list[list[int]] = []
    vertices: dict[tuple[int, int, int], int] = {}

    def index_of(token: str) -> int:
        parts = (token.split("/") + ["", ""])[:3]
        key = tuple(int(value) if value else 0 for value in parts)
        if key in vertices:
            return vertices[key]
        position_index, uv_index, normal_index = key
        if position_index <= 0:
            raise PreviewUnavailable("The exported Warband mesh has an invalid vertex index.")
        index = len(positions)
        vertices[key] = index
        positions.append(source_positions[position_index - 1])
        uvs.append(source_uvs[uv_index - 1] if uv_index > 0 else [0.0, 0.0])
        normals.append(source_normals[normal_index - 1] if normal_index > 0 else [0.0, 0.0, 1.0])
        return index

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("v "):
            source_positions.append([float(value) for value in raw.split()[1:4]])
        elif raw.startswith("vn "):
            source_normals.append([float(value) for value in raw.split()[1:4]])
        elif raw.startswith("vt "):
            values = [float(value) for value in raw.split()[1:3]]
            # OpenBRF exports OBJ UVs with a bottom-left origin. The browser
            # flips decoded images during upload, so preserve the OBJ value.
            source_uvs.append(values)
        elif raw.startswith("f "):
            face = [index_of(token) for token in raw.split()[1:]]
            for offset in range(1, len(face) - 1):
                triangles.append([face[0], face[offset], face[offset + 1]])
    if not positions or not triangles:
        raise PreviewUnavailable("The installed BRF mesh has no renderable triangles.")
    minimum = [min(row[axis] for row in positions) for axis in range(3)]
    maximum = [max(row[axis] for row in positions) for axis in range(3)]
    return {
        "positions": positions, "normals": normals, "texCoords": uvs,
        "triangles": triangles, "bounds": {"min": minimum, "max": maximum},
    }


def _png_texture(texture: Path | None, key: str) -> Path | None:
    if texture is None:
        return None
    destination = CACHE_ROOT / "textures" / f"{key}.png"
    if not destination.is_file() or destination.stat().st_mtime_ns < texture.stat().st_mtime_ns:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(texture) as image:
            image.convert("RGBA").save(destination, "PNG", optimize=True)
    return destination


def preview(mesh: str) -> dict:
    mesh = str(mesh or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", mesh):
        raise PreviewUnavailable("This item does not name a valid Warband mesh.")
    with _LOCK:
        found = _find_record("meshes", mesh)
        if found is None:
            raise PreviewUnavailable(f"The installed module does not load mesh {mesh}.")
        resource, mesh_record = found
        material_name = str(mesh_record.get("material", ""))
        material_match = _find_record("materials", material_name) if material_name else None
        material = material_match[1] if material_match else {}
        diffuse = _texture_file(str(material.get("diffuseA", "")))
        evidence = {
            "version": 2, "mesh": mesh.casefold(), "resource": _stamp(resource),
            "material": material_name, "texture": _stamp(diffuse) if diffuse else "",
            "tool": _stamp(BRF_SYNC),
        }
        key = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
        cached = CACHE_ROOT / f"{key}.json"
        texture_png = _png_texture(diffuse, key)
        if cached.is_file():
            geometry = json.loads(cached.read_text(encoding="utf-8"))
        else:
            geometry = _parse_obj(_export_mesh(resource, str(mesh_record.get("name", mesh))))
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(geometry, separators=(",", ":")), encoding="utf-8")
        return {
            "mesh": mesh, "material": material_name, "resource": resource.name,
            "texture": f"/api/item-preview/texture?key={key}" if texture_png else "",
            "summary": {"vertices": len(geometry["positions"]), "triangles": len(geometry["triangles"])},
            "geometry": geometry,
        }


def texture_path(key: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        return None
    path = CACHE_ROOT / "textures" / f"{key}.png"
    return path if path.is_file() else None
