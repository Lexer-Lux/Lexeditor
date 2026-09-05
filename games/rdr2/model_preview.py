"""Extract and cache real RDR2 item geometry for the in-window viewer."""

from __future__ import annotations

import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

try:
    from .paths import GAME_ROOT, LEXEDITOR_ROOT, PLUGIN_ROOT
except ImportError:
    from paths import GAME_ROOT, LEXEDITOR_ROOT, PLUGIN_ROOT


CACHE_VERSION = 8
DEFAULT_CACHE_SIZE_MB = 1024
MIN_CACHE_SIZE_MB = 128
MAX_CACHE_SIZE_MB = 10240
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
REQUIRED_WEAPON_TEXTURE_SEMANTICS = frozenset({
    "lyr0diffusetex", "lyr0normaltex", "lyr0materialatex",
    "lyr1diffusetex", "lyr1normaltex", "lyr1materialatex",
    "controltexturetex",
})
RENDERED_WEAPON_TEXTURE_SEMANTICS = REQUIRED_WEAPON_TEXTURE_SEMANTICS | {
    "engravingtexturetex", "albedopalettetex",
}
REQUIRED_STANDARD_TEXTURE_SEMANTICS = frozenset({
    "diffusetex", "bumptex",
})
RENDERED_TEXTURE_SEMANTICS = RENDERED_WEAPON_TEXTURE_SEMANTICS | {
    "diffusetex", "diffusetex2", "bumptex", "speculartex", "speculartex2",
    "tintpalettetex",
}
YFT_DRAWABLE_POINTER_OFFSET = 0x20
DRAWABLE_HEADER_SIZE = 0xD0
TEXTURE_DICTIONARY_HEADER_SIZE = 0x40
TEXTURE_MODEL_SUFFIX_RE = re.compile(r"_(?:ab|abal|nm|ma|mb|pal)$", re.I)

_local_app_data = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
).expanduser().resolve()
PREVIEW_DATA_ROOT = Path(
    os.environ.get(
        "LEXEDITOR_RDR2_PREVIEW_DATA_ROOT",
        _local_app_data / "Lexeditor" / "game-data" / "rdr2",
    )
).expanduser().resolve()
CACHE_ROOT = PREVIEW_DATA_ROOT / "model-previews"
SETTINGS_FILE = PREVIEW_DATA_ROOT / "model-preview-settings.json"
MANIFEST_FILE = CACHE_ROOT / "manifest.json"
ASSET_INDEX_FILE = CACHE_ROOT / "asset-index.json"

RPF_TOOL_ROOT = LEXEDITOR_ROOT / "tools" / "rpf-cli" / "bin"
RPF_TOOL = RPF_TOOL_ROOT / "RpfCli.exe"
DECODER_ROOT = PLUGIN_ROOT / "vendor" / "reddead2blend"
DECODER = DECODER_ROOT / "pylibdrawable.pyd"

# Each location below is based on an installed-game archive listing. The
# resolver checks for the requested entry. It does not infer a path from the
# model name.
ASSET_LOCATIONS = (
    {
        "kind": "weapon",
        "outer": "packs_1.rpf",
        "chain": ("packs/base/models/weapons.rpf",),
        "extension": ".ydr",
    },
    {
        "kind": "pickup",
        "outer": "levels_3.rpf",
        "chain": ("levels/rdr3/props/lev_des/s_pickups.rpf",),
        "extension": ".ydr",
    },
    {
        "kind": "pickup-fragment",
        "outer": "levels_3.rpf",
        "chain": ("levels/rdr3/props/lev_des/s_pickups.rpf",),
        "extension": ".yft",
    },
)


class PreviewUnavailable(RuntimeError):
    """The item does not have a model in a format that this viewer supports."""


def model_preview_availability(model: str) -> dict:
    """Check the installed archive index without extracting or decoding a model."""
    model = (model or "").strip()
    if not model:
        return {
            "available": False,
            "reason": "This catalog item does not name a model asset.",
        }
    if not MODEL_NAME_RE.fullmatch(model):
        return {
            "available": False,
            "reason": "The catalog model name contains unsupported characters.",
        }
    if not RPF_TOOL.is_file() or not DECODER.is_file() or not GAME_ROOT.is_dir():
        return {
            "available": False,
            "reason": "The installed-game model tools are not ready.",
        }
    for location in ASSET_LOCATIONS:
        entry = _entry_map(_archive_entries(location)).get(
            model.casefold() + location["extension"]
        )
        if entry is not None:
            return {
                "available": True,
                "format": location["extension"].removeprefix(".").upper(),
                "source": {
                    "outerArchive": location["outer"],
                    "archiveChain": list(location["chain"]),
                    "entry": entry,
                },
            }
    return {
        "available": False,
        "reason": (
            "The installed model is not in an archive that this viewer supports yet."
        ),
    }


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else fallback
    except (OSError, ValueError, TypeError):
        return fallback


def _settings() -> dict:
    raw = _read_json(SETTINGS_FILE, {})
    try:
        cache_size = int(raw.get("cacheSizeMb", DEFAULT_CACHE_SIZE_MB))
    except (TypeError, ValueError):
        cache_size = DEFAULT_CACHE_SIZE_MB
    return {
        "cacheSizeMb": min(MAX_CACHE_SIZE_MB, max(MIN_CACHE_SIZE_MB, cache_size)),
    }


def _manifest() -> dict:
    raw = _read_json(MANIFEST_FILE, {})
    if raw.get("version") != CACHE_VERSION or not isinstance(raw.get("entries"), dict):
        return {"version": CACHE_VERSION, "entries": {}}
    return raw


def _save_manifest(manifest: dict) -> None:
    manifest["version"] = CACHE_VERSION
    _atomic_json(MANIFEST_FILE, manifest)


def _entry_path(key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("Invalid model-preview cache key")
    return CACHE_ROOT / f"{key}.json.gz"


def _entry_assets_path(key: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise ValueError("Invalid model-preview cache key")
    return CACHE_ROOT / f"{key}-textures"


def _entry_size(key: str) -> int:
    total = 0
    geometry = _entry_path(key)
    if geometry.is_file():
        total += geometry.stat().st_size
    assets = _entry_assets_path(key)
    if assets.is_dir() and not (_is_reparse_point(assets) or assets.is_symlink()):
        total += _tree_bytes(assets)
    return total


def _file_stamp(path: Path) -> dict:
    info = path.stat()
    return {"size": info.st_size, "mtimeNs": info.st_mtime_ns}


def _cache_key(model: str, location: dict, component_models: tuple[str, ...] = ()) -> str:
    outer = GAME_ROOT / location["outer"]
    evidence = {
        "version": CACHE_VERSION,
        "model": model.casefold(),
        "outer": str(outer),
        "outerStamp": _file_stamp(outer),
        "chain": location["chain"],
        "extension": location["extension"],
        "componentModels": component_models,
        "decoderStamp": _file_stamp(DECODER),
        "archiveReaderStamp": _file_stamp(RPF_TOOL),
    }
    raw = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_bytes(manifest: dict) -> int:
    total = 0
    for entry in manifest.get("entries", {}).values():
        try:
            total += max(0, int(entry.get("size", 0)))
        except (TypeError, ValueError):
            pass
    return total


def _evict(manifest: dict, protected: str = "") -> list[str]:
    limit = _settings()["cacheSizeMb"] * 1024 * 1024
    removed = []
    entries = manifest.get("entries", {})
    ordered = sorted(
        entries.items(),
        key=lambda pair: (float(pair[1].get("accessed", 0)), pair[0]),
    )
    total = _cache_bytes(manifest)
    for key, entry in ordered:
        if total <= limit:
            break
        if key == protected:
            continue
        path = _entry_path(key)
        try:
            path.unlink(missing_ok=True)
            assets = _entry_assets_path(key)
            if assets.is_dir() and not (_is_reparse_point(assets) or assets.is_symlink()):
                shutil.rmtree(assets)
        except OSError:
            continue
        try:
            total -= max(0, int(entry.get("size", 0)))
        except (TypeError, ValueError):
            pass
        entries.pop(key, None)
        removed.append(key)
    return removed


def _cache_stats(manifest: dict | None = None) -> dict:
    manifest = manifest or _manifest()
    entries = manifest.get("entries", {})
    live_entries = 0
    live_bytes = 0
    stale = []
    for key, entry in entries.items():
        path = _entry_path(key)
        assets = _entry_assets_path(key)
        if (
            not path.is_file() or not assets.is_dir()
            or _is_reparse_point(assets) or assets.is_symlink()
        ):
            stale.append(key)
            continue
        live_entries += 1
        live_bytes += _entry_size(key)
    for key in stale:
        entries.pop(key, None)
    if stale:
        _save_manifest(manifest)
    return {"entries": live_entries, "bytes": live_bytes}


def get_preview_settings() -> dict:
    settings = _settings()
    stats = _cache_stats()
    return {
        **settings,
        "minCacheSizeMb": MIN_CACHE_SIZE_MB,
        "maxCacheSizeMb": MAX_CACHE_SIZE_MB,
        "cacheEntries": stats["entries"],
        "cacheBytes": stats["bytes"],
        "cacheRoot": str(CACHE_ROOT),
        "supportedFormats": ["Textured YDR and YFT previews"],
        "notYetSupported": ["YDD dictionaries, skinned assets, and other shaders"],
    }


def save_preview_settings(payload: dict) -> dict:
    try:
        cache_size = int(payload.get("cacheSizeMb"))
    except (TypeError, ValueError) as error:
        raise ValueError("Cache size must be a whole number of MB") from error
    if not MIN_CACHE_SIZE_MB <= cache_size <= MAX_CACHE_SIZE_MB:
        raise ValueError(
            f"Cache size must be between {MIN_CACHE_SIZE_MB} and {MAX_CACHE_SIZE_MB} MB"
        )
    _atomic_json(SETTINGS_FILE, {"cacheSizeMb": cache_size})
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    _evict(manifest)
    _save_manifest(manifest)
    return get_preview_settings()


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _checked_cache_root() -> Path:
    expected_parent = PREVIEW_DATA_ROOT.resolve()
    if CACHE_ROOT.name != "model-previews" or CACHE_ROOT.parent.resolve() != expected_parent:
        raise RuntimeError("Refusing to clear an unexpected model-preview cache path")
    if CACHE_ROOT.exists() and (_is_reparse_point(CACHE_ROOT) or CACHE_ROOT.is_symlink()):
        raise RuntimeError("Refusing to clear a linked model-preview cache folder")
    return CACHE_ROOT


def _tree_bytes(path: Path) -> int:
    total = 0
    for root, directories, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in directories + files:
            child = root_path / name
            if _is_reparse_point(child) or child.is_symlink():
                raise RuntimeError("Refusing to clear a cache that contains a linked path")
        for name in files:
            try:
                total += (root_path / name).stat().st_size
            except OSError:
                pass
    return total


def clear_preview_cache() -> dict:
    root = _checked_cache_root()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        _save_manifest({"version": CACHE_VERSION, "entries": {}})
        return {"removedBytes": 0, "removedEntries": 0, **get_preview_settings()}
    removed_bytes = _tree_bytes(root)
    removed_entries = _cache_stats().get("entries", 0)
    for child in list(root.iterdir()):
        if _is_reparse_point(child) or child.is_symlink():
            raise RuntimeError("Refusing to clear a cache that contains a linked path")
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    _save_manifest({"version": CACHE_VERSION, "entries": {}})
    return {
        "removedBytes": removed_bytes,
        "removedEntries": removed_entries,
        **get_preview_settings(),
    }


def _decoder_module():
    if not DECODER.is_file():
        raise RuntimeError("The bundled YDR model decoder is missing")
    decoder_dir = str(DECODER_ROOT)
    if decoder_dir not in sys.path:
        sys.path.insert(0, decoder_dir)
    return importlib.import_module("pylibdrawable")


def _archive_index_key(location: dict) -> str:
    evidence = {
        "outer": location["outer"],
        "outerStamp": _file_stamp(GAME_ROOT / location["outer"]),
        "chain": location["chain"],
        "archiveReaderStamp": _file_stamp(RPF_TOOL),
    }
    raw = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _archive_entries(location: dict) -> tuple[str, ...]:
    outer = GAME_ROOT / location["outer"]
    if not outer.is_file():
        return ()
    index = _read_json(ASSET_INDEX_FILE, {"version": 1, "archives": {}})
    if index.get("version") != 1 or not isinstance(index.get("archives"), dict):
        index = {"version": 1, "archives": {}}
    key = _archive_index_key(location)
    cached = index["archives"].get(key)
    if isinstance(cached, list) and all(isinstance(value, str) for value in cached):
        return tuple(cached)
    command = [str(RPF_TOOL), str(outer), "--list-chain", *location["chain"]]
    result = subprocess.run(
        command,
        cwd=RPF_TOOL_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError("The installed model archive could not be indexed")
    entries = tuple(sorted({
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip().casefold().endswith((".ydr", ".ytd", ".yft"))
    }, key=str.casefold))
    if not entries:
        raise RuntimeError("The installed model archive index is empty")
    index["archives"] = {key: list(entries)}
    _atomic_json(ASSET_INDEX_FILE, index)
    return entries


def _entry_map(entries: tuple[str, ...]) -> dict[str, str]:
    return {Path(entry).name.casefold(): entry for entry in entries}


def _ranked_texture_dictionaries(model: str, entries: tuple[str, ...]) -> list[str]:
    model_name = model.casefold()
    family = re.sub(r"\d+$", "", model_name.removeprefix("w_")).rstrip("_")
    model_tokens = set(model_name.removeprefix("w_").split("_"))

    def rank(entry: str) -> tuple[int, int, int, str]:
        stem = Path(entry).stem.casefold()
        plain = re.sub(r"\+(?:hi|hidr|hifr)$", "", stem)
        tokens = set(plain.removeprefix("w_").split("_"))
        if plain == model_name:
            group = 0
        elif plain == family:
            group = 1
        elif plain == "weapon_shared":
            group = 2
        elif plain in {"weapon_small", "weapon_large"}:
            group = 3
        elif model_tokens & tokens:
            group = 4
        else:
            group = 5
        overlap = -len(model_tokens & tokens)
        high_resolution_first = 0 if re.search(r"\+(?:hi|hidr|hifr)$", stem) else 1
        return group, overlap, high_resolution_first, entry.casefold()

    return sorted(
        (entry for entry in entries if entry.casefold().endswith(".ytd")),
        key=rank,
    )


def _materialize_archive(location: dict, working: Path) -> Path:
    outer = GAME_ROOT / location["outer"]
    target = working / "preview-assets.rpf"
    command = [
        str(RPF_TOOL), str(outer), "--extract-chain", *location["chain"], str(target),
    ]
    result = subprocess.run(
        command,
        cwd=RPF_TOOL_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or not target.is_file() or target.stat().st_size < 4:
        raise RuntimeError("The installed model archive could not be opened")
    with target.open("rb") as handle:
        magic = handle.read(4)
    if magic != b"8FPR":
        raise RuntimeError("The installed model archive has an unexpected format")
    return target


def _extract_archive_entry(
    location: dict, entry: str, working: Path, archive: Path | None = None,
) -> Path | None:
    outer = archive or (GAME_ROOT / location["outer"])
    if not outer.is_file():
        return None
    output = working / entry
    command = (
        [str(RPF_TOOL), str(outer), entry, str(output)]
        if archive is not None else
        [str(RPF_TOOL), str(outer), "--extract-chain", *location["chain"], entry, str(output)]
    )
    result = subprocess.run(
        command,
        cwd=RPF_TOOL_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode == 0 and output.is_file() and output.stat().st_size > 16:
        return output
    return None


def _extract_archive_entries(
    location: dict, entries: list[str], working: Path, archive: Path | None = None,
) -> dict[str, Path]:
    wanted = list(dict.fromkeys(entries))
    if not wanted:
        return {}
    if archive is None:
        return {
            entry: output
            for entry in wanted
            if (output := _extract_archive_entry(location, entry, working)) is not None
        }
    command = [
        str(RPF_TOOL), str(archive), "--extract-selected", str(working), *wanted,
    ]
    result = subprocess.run(
        command,
        cwd=RPF_TOOL_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError("The selected model assets could not be extracted")
    outputs = {entry: working / entry for entry in wanted}
    missing = [entry for entry, output in outputs.items()
               if not output.is_file() or output.stat().st_size <= 16]
    if missing:
        raise RuntimeError("The selected model assets are missing: " + ", ".join(missing))
    return outputs


def _extract(
    model: str, component_models: tuple[str, ...], working: Path,
) -> tuple[list[Path], dict, tuple[str, ...], Path]:
    if not RPF_TOOL.is_file():
        raise RuntimeError("The bundled RDR2 archive reader is missing")
    if not GAME_ROOT.is_dir():
        raise RuntimeError(f"The RDR2 game folder is missing: {GAME_ROOT}")
    for location in ASSET_LOCATIONS:
        entries = _archive_entries(location)
        available = _entry_map(entries)
        entry = available.get(model.casefold() + location["extension"])
        if entry is None:
            continue
        archive = _materialize_archive(location, working)
        component_entries = []
        for component_model in component_models:
            component_entry = available.get(
                component_model.casefold() + location["extension"],
            )
            if component_entry is None:
                raise RuntimeError(
                    "The catalog component model is missing from the installed archive: "
                    + component_model
                )
            component_entries.append(component_entry)
        selected = [entry, *component_entries]
        extracted = _extract_archive_entries(location, selected, working, archive)
        sources = [extracted[value] for value in selected]
        return sources, location, entries, archive
    raise PreviewUnavailable(
        "No previewable asset was found for this catalog model in the indexed "
        "installed-game model archives."
    )


def _rounded_rows(rows, width: int) -> list[list[float]]:
    output = []
    for row in rows:
        output.append([round(float(value), 6) for value in row[:width]])
    return output


def _without_yft_anchor_triangles(
    positions: list[list[float]], triangles: list[list[int]],
) -> tuple[list[list[int]], int]:
    """Remove the isolated fragType anchor plane that some pickup YFTs carry."""
    if len(triangles) < 100:
        return triangles, 0

    def span_squared(triangle: list[int]) -> float:
        points = [positions[index] for index in triangle]
        return max(
            sum((points[first][axis] - points[second][axis]) ** 2 for axis in range(3))
            for first, second in ((0, 1), (1, 2), (2, 0))
        )

    spans = sorted(span_squared(triangle) for triangle in triangles)
    typical = spans[len(spans) // 2]
    upper_normal = spans[min(len(spans) - 1, int(len(spans) * 0.99))]
    cutoff = max(typical * 256.0, upper_normal * 16.0)
    if spans[-1] <= cutoff:
        return triangles, 0
    filtered = [triangle for triangle in triangles if span_squared(triangle) <= cutoff]
    return filtered, len(triangles) - len(filtered)


def _shader_info(geometry) -> dict:
    if not hasattr(geometry, "GetShader"):
        raise RuntimeError("The bundled YDR decoder does not expose material data")
    shader = geometry.GetShader()
    texture_names = list(getattr(shader, "Textures", []))
    uniforms = list(getattr(shader, "Uniforms", []))
    textures = {}
    for index, texture_name in enumerate(texture_names):
        if not texture_name or index >= len(uniforms):
            continue
        semantic = str(uniforms[index].Name).casefold()
        textures[semantic] = str(texture_name)
    values = {
        str(uniform.Name).casefold(): [round(float(value), 6) for value in uniform.Data]
        for uniform in uniforms if uniform.Data
    }
    return {"shader": str(shader.Name), "textures": textures, "uniforms": values}


def _texfury_loadable_ytd(source: Path, working: Path) -> Path:
    raw = source.read_bytes()
    if raw[:4] != b"RSC8" or len(raw) <= 16:
        raise RuntimeError(f"The extracted texture dictionary is not RSC8: {source.name}")
    magic, version, virtual_flags, physical_flags = struct.unpack_from("<4I", raw, 0)
    expected = (virtual_flags & 0xFFFFFFF0) + (physical_flags & 0xFFFFFFF0)
    payload = raw[16:]
    if len(payload) != expected:
        raise RuntimeError(f"The archive reader did not return a decoded YTD payload: {source.name}")
    wrapped = struct.pack(
        "<4I", magic, version & 0xFF, virtual_flags, physical_flags,
    ) + zlib.compress(payload)
    target = working / f"{source.stem}-texfury.ytd"
    target.write_bytes(wrapped)
    return target


def _decode_texture_set(
    location: dict,
    working: Path,
    texture_names: set[str],
    model: str,
    archive_entries: tuple[str, ...],
    archive: Path | None = None,
    additional_dictionaries: tuple[Path, ...] = (),
) -> tuple[dict[str, dict], Path]:
    try:
        from texfury import ITD
    except ImportError as error:
        raise RuntimeError("The RDR2 texture decoder is not installed") from error

    requested = {name.casefold(): name for name in texture_names if name}
    decoded = {}
    sources = {}
    for source in additional_dictionaries:
        dictionary = ITD.load(str(_texfury_loadable_ytd(source, working)))
        for texture in dictionary.textures:
            texture_key = str(texture.name).casefold()
            if texture_key in requested and texture_key not in decoded:
                decoded[texture_key] = texture
                sources[texture_key] = source.name
    ranked = _ranked_texture_dictionaries(model, archive_entries)
    offset = 0
    batch_size = 12
    while offset < len(ranked) and not requested.keys() <= decoded.keys():
        batch = ranked[offset:offset + batch_size]
        extracted = _extract_archive_entries(location, batch, working, archive)
        for entry in batch:
            dictionary = ITD.load(str(
                _texfury_loadable_ytd(extracted[entry], working)
            ))
            for texture in dictionary.textures:
                texture_key = str(texture.name).casefold()
                if texture_key in requested and texture_key not in decoded:
                    decoded[texture_key] = texture
                    sources[texture_key] = entry
        offset += len(batch)
        batch_size = 24

    texture_root = working / "decoded-textures"
    texture_root.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for key, requested_name in requested.items():
        texture = decoded.get(key)
        if texture is None:
            continue
        if not MODEL_NAME_RE.fullmatch(requested_name):
            raise RuntimeError(f"The YDR contains an unsafe texture name: {requested_name}")
        filename = requested_name.casefold() + ".png"
        target = texture_root / filename
        texture.to_pil().save(target, format="PNG")
        metadata[key] = {
            "name": requested_name,
            "file": filename,
            "width": int(texture.width),
            "height": int(texture.height),
            "dictionary": sources[key],
        }
    return metadata, texture_root


def _convert_ydr(source: Path, model: str, location: dict, key: str, working: Path) -> tuple[dict, Path]:
    raw = source.read_bytes()
    if raw[:4] != b"RSC8" or len(raw) <= 16:
        raise RuntimeError("The extracted YDR does not have the expected RSC8 payload")
    stripped = source.with_name(source.stem + "-decoded.ydr")
    stripped.write_bytes(raw[16:])
    drawable = _decoder_module().ImportYdr(str(stripped))
    lod_index = next((index for index, lod in enumerate(drawable.Lods) if lod is not None), None)
    if lod_index is None:
        raise RuntimeError("The extracted YDR has no drawable LOD")
    lod = drawable.Lods[lod_index]
    meshes = []
    materials = []
    material_keys = {}
    minimum = [float("inf"), float("inf"), float("inf")]
    maximum = [float("-inf"), float("-inf"), float("-inf")]
    vertex_count = 0
    triangle_count = 0
    for model_index, drawable_model in enumerate(lod.Models):
        for geometry_index, geometry in enumerate(drawable_model.Geometries):
            positions = _rounded_rows(geometry.GetVertexPositionArray(0), 3)
            if not positions:
                continue
            if geometry.NormalsCount:
                normals = _rounded_rows(geometry.GetVertexNormalArray(0), 3)
            else:
                normals = [[0.0, 0.0, 1.0] for _ in positions]
            texcoords0 = _rounded_rows(geometry.GetVertexTexCoordArray(0), 2)
            texcoords1 = (
                _rounded_rows(geometry.GetVertexTexCoordArray(1), 2)
                if geometry.TexCoordsCount > 1 else texcoords0
            )
            colors = (
                _rounded_rows(geometry.GetVertexColorArray(0), 4)
                if geometry.ColorsCount else [[1.0, 1.0, 1.0, 1.0] for _ in positions]
            )
            triangles = [[int(value) for value in triangle[:3]]
                         for triangle in geometry.GetIndexArray()]
            shader = _shader_info(geometry)
            material_signature = json.dumps(shader, sort_keys=True, separators=(",", ":"))
            material_index = material_keys.get(material_signature)
            if material_index is None:
                material_index = len(materials)
                material_keys[material_signature] = material_index
                materials.append(shader)
            for position in positions:
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], position[axis])
                    maximum[axis] = max(maximum[axis], position[axis])
            vertex_count += len(positions)
            triangle_count += len(triangles)
            meshes.append({
                "name": f"model-{model_index}-geometry-{geometry_index}",
                "positions": positions,
                "normals": normals,
                "texCoords0": texcoords0,
                "texCoords1": texcoords1,
                "colors": colors,
                "triangles": triangles,
                "material": material_index,
            })
    if not meshes or not triangle_count:
        raise RuntimeError("The extracted YDR contains no renderable triangles")
    texture_names = {
        texture_name
        for material in materials
        for semantic, texture_name in material["textures"].items()
        if semantic in RENDERED_WEAPON_TEXTURE_SEMANTICS
    }
    decoded_textures, texture_root = _decode_texture_set(
        location, working, texture_names, model, _archive_entries(location),
    )
    for material in materials:
        if material["shader"].casefold() == "standard_weapon_2lyr":
            missing = [
                semantic for semantic in sorted(REQUIRED_WEAPON_TEXTURE_SEMANTICS)
                if semantic not in material["textures"]
                or material["textures"][semantic].casefold() not in decoded_textures
            ]
            if missing:
                raise RuntimeError(
                    "The weapon material is missing required textures: " + ", ".join(missing)
                )
        material["textures"] = {
            semantic: {
                **decoded_textures[texture_name.casefold()],
                "url": (
                    "/api/model-preview/texture?key=" + key
                    + "&name=" + decoded_textures[texture_name.casefold()]["file"]
                ),
            }
            for semantic, texture_name in material["textures"].items()
            if texture_name.casefold() in decoded_textures
        }
    return {
        "schema": 2,
        "model": model,
        "format": "YDR",
        "lod": lod_index,
        "bounds": {"min": minimum, "max": maximum},
        "meshes": meshes,
        "materials": materials,
        "summary": {
            "meshes": len(meshes),
            "vertices": vertex_count,
            "triangles": triangle_count,
        },
        "source": {
            "outerArchive": location["outer"],
            "archiveChain": list(location["chain"]),
            "entry": model.casefold() + location["extension"],
        },
        "material": "installed-game",
        "limitations": [],
    }, texture_root


def _resource_offset(pointer: int, payload_size: int, label: str) -> int:
    segment = pointer & 0xF0000000
    offset = pointer & 0x0FFFFFFF
    if pointer >> 32 or segment not in {0x50000000, 0x60000000}:
        raise RuntimeError(f"The YFT {label} is not an RDR2 resource pointer")
    if offset >= payload_size:
        raise RuntimeError(f"The YFT {label} points outside the decoded resource")
    return offset


def _convert_yft(source: Path, working: Path) -> Path:
    """Expose the embedded YFT drawable to the bundled drawable decoder."""
    raw = source.read_bytes()
    if raw[:4] != b"RSC8" or len(raw) <= 16 + DRAWABLE_HEADER_SIZE:
        raise RuntimeError(f"The extracted YFT is not a decoded RSC8 payload: {source.name}")
    payload = bytearray(raw[16:])

    # RDR2 fragType stores its primary drawable pointer at 0x20. This is
    # verified against the installed s_agedpiraterum01x and s_saltedbeef01x
    # resources. The target is a normal 0xD0 CDrawableData header; its resource
    # pointers continue to address the unchanged YFT payload.
    drawable_pointer = struct.unpack_from("<Q", payload, YFT_DRAWABLE_POINTER_OFFSET)[0]
    drawable_offset = _resource_offset(
        drawable_pointer, len(payload), "primary drawable pointer",
    )
    if drawable_offset + DRAWABLE_HEADER_SIZE > len(payload):
        raise RuntimeError("The YFT primary drawable header is truncated")
    header = payload[drawable_offset:drawable_offset + DRAWABLE_HEADER_SIZE]
    shader_pointer = struct.unpack_from("<Q", header, 0x10)[0]
    _resource_offset(shader_pointer, len(payload), "drawable shader group")
    lod_pointers = [struct.unpack_from("<Q", header, offset)[0]
                    for offset in (0x50, 0x58, 0x60, 0x68)]
    if not any(lod_pointers):
        raise RuntimeError("The YFT primary drawable has no LOD")
    for pointer in lod_pointers:
        if pointer:
            _resource_offset(pointer, len(payload), "drawable LOD")

    payload[:DRAWABLE_HEADER_SIZE] = header
    target = working / f"{source.stem}-embedded-drawable.ydr"
    target.write_bytes(payload)
    return target


def _yft_texture_dictionary(source: Path, working: Path) -> Path | None:
    """Expose a YFT's embedded texture dictionary as a decoded RSC8 YTD."""
    raw = source.read_bytes()
    if raw[:4] != b"RSC8" or len(raw) <= 16 + TEXTURE_DICTIONARY_HEADER_SIZE:
        raise RuntimeError(f"The extracted YFT is not a decoded RSC8 payload: {source.name}")
    payload = bytearray(raw[16:])
    drawable_pointer = struct.unpack_from("<Q", payload, YFT_DRAWABLE_POINTER_OFFSET)[0]
    drawable_offset = _resource_offset(
        drawable_pointer, len(payload), "primary drawable pointer",
    )
    shader_pointer = struct.unpack_from("<Q", payload, drawable_offset + 0x10)[0]
    shader_offset = _resource_offset(shader_pointer, len(payload), "drawable shader group")
    dictionary_pointer = struct.unpack_from("<Q", payload, shader_offset + 0x08)[0]
    if not dictionary_pointer:
        return None
    dictionary_offset = _resource_offset(
        dictionary_pointer, len(payload), "embedded texture dictionary",
    )
    if dictionary_offset + TEXTURE_DICTIONARY_HEADER_SIZE > len(payload):
        raise RuntimeError("The YFT embedded texture dictionary is truncated")
    payload[:TEXTURE_DICTIONARY_HEADER_SIZE] = payload[
        dictionary_offset:dictionary_offset + TEXTURE_DICTIONARY_HEADER_SIZE
    ]
    target = working / f"{source.stem}-embedded-textures.ytd"
    target.write_bytes(raw[:16] + payload)
    return target


def _convert_ydr_assembly(
    sources: list[Path], model: str, location: dict, key: str, working: Path,
    archive_entries: tuple[str, ...], archive: Path, source_format: str = "YDR",
) -> tuple[dict, Path]:
    meshes = []
    materials = []
    material_keys = {}
    minimum = [float("inf"), float("inf"), float("inf")]
    maximum = [float("-inf"), float("-inf"), float("-inf")]
    vertex_count = 0
    triangle_count = 0
    omitted_anchor_triangles = 0
    lod_indices = []
    for source_index, source in enumerate(sources):
        if source_format == "YFT":
            stripped = _convert_yft(source, working)
        else:
            raw = source.read_bytes()
            if raw[:4] != b"RSC8" or len(raw) <= 16:
                raise RuntimeError(
                    f"The extracted YDR is not a decoded RSC8 payload: {source.name}"
                )
            stripped = source.with_name(source.stem + "-decoded.ydr")
            stripped.write_bytes(raw[16:])
        drawable = _decoder_module().ImportYdr(str(stripped))
        if drawable is None:
            raise RuntimeError(f"The extracted {source_format} drawable could not be decoded")
        lod_index = next(
            (index for index, lod in enumerate(drawable.Lods) if lod is not None), None,
        )
        if lod_index is None:
            raise RuntimeError(
                f"The extracted {source_format} has no drawable LOD: {source.name}"
            )
        lod_indices.append(lod_index)
        lod = drawable.Lods[lod_index]
        for model_index, drawable_model in enumerate(lod.Models):
            for geometry_index, geometry in enumerate(drawable_model.Geometries):
                positions = _rounded_rows(geometry.GetVertexPositionArray(0), 3)
                if not positions:
                    continue
                normals = (
                    _rounded_rows(geometry.GetVertexNormalArray(0), 3)
                    if geometry.NormalsCount
                    else [[0.0, 0.0, 1.0] for _ in positions]
                )
                texcoords0 = _rounded_rows(geometry.GetVertexTexCoordArray(0), 2)
                texcoords1 = (
                    _rounded_rows(geometry.GetVertexTexCoordArray(1), 2)
                    if geometry.TexCoordsCount > 1 else texcoords0
                )
                colors = (
                    _rounded_rows(geometry.GetVertexColorArray(0), 4)
                    if geometry.ColorsCount
                    else [[1.0, 1.0, 1.0, 1.0] for _ in positions]
                )
                triangles = [
                    [int(value) for value in triangle[:3]]
                    for triangle in geometry.GetIndexArray()
                ]
                if source_format == "YFT":
                    triangles, omitted = _without_yft_anchor_triangles(
                        positions, triangles,
                    )
                    omitted_anchor_triangles += omitted
                shader = _shader_info(geometry)
                signature = json.dumps(shader, sort_keys=True, separators=(",", ":"))
                material_index = material_keys.get(signature)
                if material_index is None:
                    material_index = len(materials)
                    material_keys[signature] = material_index
                    materials.append(shader)
                used_vertices = {index for triangle in triangles for index in triangle}
                for vertex_index in used_vertices:
                    position = positions[vertex_index]
                    for axis in range(3):
                        minimum[axis] = min(minimum[axis], position[axis])
                        maximum[axis] = max(maximum[axis], position[axis])
                vertex_count += len(positions)
                triangle_count += len(triangles)
                meshes.append({
                    "name": (
                        f"{source.stem}-model-{model_index}-geometry-{geometry_index}"
                    ),
                    "positions": positions,
                    "normals": normals,
                    "texCoords0": texcoords0,
                    "texCoords1": texcoords1,
                    "colors": colors,
                    "triangles": triangles,
                    "material": material_index,
                    "component": source_index > 0,
                })
    if not meshes or not triangle_count:
        raise RuntimeError(
            f"The extracted {source_format} assembly contains no renderable triangles"
        )
    texture_names = {
        texture_name
        for material in materials
        for semantic, texture_name in material["textures"].items()
        if semantic in RENDERED_TEXTURE_SEMANTICS
    }
    available = _entry_map(archive_entries)
    source_by_name = {source.name.casefold(): source for source in sources}
    dependency_entries = sorted({
        entry
        for texture_name in texture_names
        if (entry := available.get(
            TEXTURE_MODEL_SUFFIX_RE.sub("", texture_name.casefold()) + ".yft"
        )) is not None and entry.casefold() not in source_by_name
    }, key=str.casefold)
    dependencies = _extract_archive_entries(
        location, dependency_entries, working, archive,
    )
    yft_sources = {
        source.name.casefold(): source
        for source in (*sources, *dependencies.values())
        if source.suffix.casefold() == ".yft"
    }
    embedded_dictionaries = tuple(
        dictionary
        for source in yft_sources.values()
        if (dictionary := _yft_texture_dictionary(source, working)) is not None
    )
    decoded_textures, texture_root = _decode_texture_set(
        location, working, texture_names, model, archive_entries, archive,
        additional_dictionaries=embedded_dictionaries,
    )
    standard_material_count = 0
    standard_textured_count = 0
    unresolved_maps = set()
    for material in materials:
        shader_name = material["shader"].casefold()
        if shader_name == "standard_weapon_2lyr":
            missing = [
                semantic for semantic in sorted(REQUIRED_WEAPON_TEXTURE_SEMANTICS)
                if semantic not in material["textures"]
                or material["textures"][semantic].casefold() not in decoded_textures
            ]
            if missing:
                raise RuntimeError(
                    "The weapon material is missing required textures: "
                    + ", ".join(missing)
                )
        elif shader_name in {"standard", "standard_dirt", "standard_glass"}:
            standard_material_count += 1
            resolved_semantics = {
                semantic for semantic, texture_name in material["textures"].items()
                if texture_name.casefold() in decoded_textures
            }
            if REQUIRED_STANDARD_TEXTURE_SEMANTICS <= resolved_semantics:
                standard_textured_count += 1
        else:
            raise RuntimeError(
                f"The {material['shader']} game material is not rendered yet"
            )
        material_missing = {
            texture_name for texture_name in material["textures"].values()
            if texture_name.casefold() not in decoded_textures
        }
        unresolved_maps.update(material_missing)
        material["missingTextures"] = sorted(material_missing, key=str.casefold)
        material["textures"] = {
            semantic: {
                **decoded_textures[texture_name.casefold()],
                "url": (
                    "/api/model-preview/texture?key=" + key
                    + "&name=" + decoded_textures[texture_name.casefold()]["file"]
                ),
            }
            for semantic, texture_name in material["textures"].items()
            if texture_name.casefold() in decoded_textures
        }
    if standard_material_count and not standard_textured_count:
        raise RuntimeError(
            "The installed standard material has no decoded diffuse and normal maps"
        )
    limitations = []
    if unresolved_maps:
        limitations.append(
            "Some optional or shared material maps were not present in the indexed "
            "archive: " + ", ".join(sorted(unresolved_maps, key=str.casefold)) + "."
        )
    return {
        "schema": 2,
        "model": model,
        "format": source_format,
        "lod": lod_indices[0],
        "bounds": {"min": minimum, "max": maximum},
        "meshes": meshes,
        "materials": materials,
        "summary": {
            "meshes": len(meshes),
            "vertices": vertex_count,
            "triangles": triangle_count,
            "components": max(0, len(sources) - 1),
            "omittedFragmentAnchorTriangles": omitted_anchor_triangles,
        },
        "source": {
            "outerArchive": location["outer"],
            "archiveChain": list(location["chain"]),
            "entry": model.casefold() + location["extension"],
            "components": [source.name for source in sources[1:]],
        },
        "material": "installed-game",
        "limitations": limitations,
    }, texture_root


def _write_cached_geometry(key: str, geometry: dict) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    target = _entry_path(key)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(geometry, handle, separators=(",", ":"))
    temporary.replace(target)
    return target


def _cached_response(key: str, entry: dict, cached: bool) -> dict:
    return {
        "available": True,
        "cached": cached,
        "key": key,
        "geometryUrl": f"/api/model-preview/geometry?key={key}",
        "model": entry["model"],
        "format": entry["format"],
        "summary": entry["summary"],
        "material": entry.get("material", "installed-game"),
        "source": entry["source"],
        "limitations": entry.get("limitations", []),
    }


def prepare_model_preview(
    item_key: str, model: str, component_models: tuple[str, ...] = (),
) -> dict:
    item_key = (item_key or "").strip()
    model = (model or "").strip()
    if not item_key:
        raise ValueError("Catalog item is required")
    if not model:
        raise PreviewUnavailable("This catalog item does not name a model asset.")
    if not MODEL_NAME_RE.fullmatch(model):
        raise ValueError("The catalog model name contains unsupported characters")
    components = tuple(dict.fromkeys(
        value.strip() for value in component_models if value and value.strip()
    ))
    if any(
        not MODEL_NAME_RE.fullmatch(value)
        or not value.casefold().startswith(model.casefold() + "_")
        for value in components
    ):
        raise ValueError("The catalog component model is not part of the base model")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    for location in ASSET_LOCATIONS:
        outer = GAME_ROOT / location["outer"]
        if not outer.is_file() or not DECODER.is_file():
            continue
        key = _cache_key(model, location, components)
        entry = manifest["entries"].get(key)
        target = _entry_path(key)
        texture_root = _entry_assets_path(key)
        if entry and target.is_file() and texture_root.is_dir():
            entry["accessed"] = time.time()
            entry["size"] = _entry_size(key)
            _save_manifest(manifest)
            return _cached_response(key, entry, True)

    working_root = CACHE_ROOT / "working"
    working_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="extract-", dir=working_root) as temporary:
        sources, location, archive_entries, archive = _extract(
            model, components, Path(temporary),
        )
        key = _cache_key(model, location, components)
        geometry, decoded_texture_root = _convert_ydr_assembly(
            sources, model, location, key, Path(temporary), archive_entries, archive,
            source_format=location["extension"].removeprefix(".").upper(),
        )
        target = _write_cached_geometry(key, geometry)
        texture_target = _entry_assets_path(key)
        if texture_target.exists():
            if _is_reparse_point(texture_target) or texture_target.is_symlink():
                raise RuntimeError("Refusing to replace a linked model-preview texture folder")
            shutil.rmtree(texture_target)
        decoded_texture_root.replace(texture_target)
    try:
        working_root.rmdir()
    except OSError:
        pass
    entry = {
        "model": model,
        "item": item_key,
        "format": geometry["format"],
        "summary": geometry["summary"],
        "material": geometry["material"],
        "source": geometry["source"],
        "limitations": geometry["limitations"],
        "size": _entry_size(key),
        "accessed": time.time(),
    }
    manifest["entries"][key] = entry
    _evict(manifest, protected=key)
    _save_manifest(manifest)
    return _cached_response(key, entry, False)


def cached_geometry_path(key: str) -> Path:
    target = _entry_path(key)
    manifest = _manifest()
    entry = manifest.get("entries", {}).get(key)
    if not entry or not target.is_file():
        raise FileNotFoundError("Model-preview geometry is not in the cache")
    entry["accessed"] = time.time()
    entry["size"] = _entry_size(key)
    _save_manifest(manifest)
    return target


def cached_texture_path(key: str, name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_]+\.png", name or ""):
        raise ValueError("Invalid model-preview texture name")
    manifest = _manifest()
    entry = manifest.get("entries", {}).get(key)
    texture_root = _entry_assets_path(key)
    target = texture_root / name
    if not entry or not target.is_file() or texture_root.resolve() not in target.resolve().parents:
        raise FileNotFoundError("Model-preview texture is not in the cache")
    entry["accessed"] = time.time()
    entry["size"] = _entry_size(key)
    _save_manifest(manifest)
    return target
