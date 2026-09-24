"""SFX, Models, and Textures asset rows for the Final Fantasy VIII plugin.

Audio layout, battle .dat sections, and TIM formats follow the FF8 Modding
Wiki (HobbitDur and contributors). FFNx external SFX names follow FFNx
``src/sfx.cpp`` ``ff8_sfx_play_layered``; external texture base paths follow
FFNx ``src/ff8/vram.cpp``. Only mappings proved by that source are claimed;
mod files that match no verified mapping stay visible as unmapped rows.

Vanilla bytes come from the installed game (``Data/Sound`` for audio, the
extracted baseline for battle models) and are never written. Project saves
go to the editable mod's ``sfx/`` and ``direct/battle/`` folders, which the
normal composer already carries into the runtime tree.
"""

from __future__ import annotations

from datetime import datetime
import base64
from functools import lru_cache
import hashlib
import json
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

from PIL import Image

from core.theme_sounds import entry_wav, read_ff8_entries

from . import formats, paths, runtime_layout, world_textures
from .fs_archive import FsArchive

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 in Lexeditor's bundled environment.
    import tomli as tomllib


SCHEMA_ROOT = Path(__file__).resolve().parent / "schema"
MAX_SFX_BYTES = 16 * 1024 * 1024
MAX_MODEL_BYTES = 16 * 1024 * 1024
SFX_EXTENSIONS = {
    ".ogg": b"OggS",
    ".wav": b"RIFF",
    ".flac": b"fLaC",
    ".mp3": None,  # ID3 tag or raw frame sync; checked separately.
}
# Lexeditor's own sidecar files never count as mod assets.
IGNORED_ASSET_SUFFIXES = (".bak", ".tmp")
CHARACTER_NAMES = {
    0: "Squall", 1: "Zell", 2: "Irvine", 3: "Quistis", 4: "Rinoa",
    5: "Selphie", 6: "Seifer", 7: "Edea", 8: "Laguna", 9: "Kiros",
    10: "Ward",
}
MONSTER_SECTIONS = (
    "Skeleton", "Model geometry", "Model animation", "Dynamic texture data",
    "Animation sequences", "Camera sequence", "Information & stats",
    "Battle scripts / AI", "Sounds", "Sound sample bank", "Textures",
)
NOMODEL_SECTIONS = ("Information & stats", "Battle scripts / AI")
BODY_SECTIONS = (
    "Skeleton", "Model geometry", "Model animation", "Dynamic texture data",
    "Camera sequence", "Textures", "Extra animation block",
)
EDEA_SECTIONS = (
    "Skeleton", "Model geometry", "Model animation", "Dynamic texture data",
    "Camera sequence", "Animation sequences", "Sounds", "Sound sample bank",
    "Textures", "Extra animation block",
)
WEAPON_SECTIONS = (
    "Skeleton", "Model geometry", "Model animation", "Animation sequences",
    "Sounds", "Sound sample bank", "Textures", "Extra animation block",
)
REDUCED_WEAPON_SECTIONS = (
    "Model geometry", "Animation sequences", "Sounds", "Sound sample bank",
    "Textures",
)
MODEL_FILENAME = re.compile(r"[a-z0-9][a-z0-9_.-]*\.(dat|x)", re.IGNORECASE)
CHARACTER_MODEL = re.compile(r"d[0-9a-f][cw][0-9]{3}\.dat")
BODY_FILENAME = re.compile(r"d([0-9a-f])c(\d{3})\.dat", re.IGNORECASE)
WEAPON_FILENAME = re.compile(r"d([0-9a-f])w(\d{3})\.dat", re.IGNORECASE)
MONSTER_FILENAME = re.compile(r"c0m(\d{3})\.dat", re.IGNORECASE)


def _sfx_actor_sounds() -> dict[str, list[str]]:
    try:
        payload = json.loads(
            (SCHEMA_ROOT / "sfx_actor_sounds.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sounds = payload.get("sounds") if isinstance(payload, dict) else None
    return sounds if isinstance(sounds, dict) else {}


ACTOR_SOUNDS = _sfx_actor_sounds()
MONSTER_NAMES = {int(row["com_id"]): str(row["name"]) for row in formats.MONSTERS}


def _managed_root(dataset: str) -> Path:
    return runtime_layout.root_for_mod(
        paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])


def _reference_root(dataset: str) -> Path:
    reference_id = dataset.partition(":")[2]
    reference = next(
        (row for row in formats.reference_roots() if row["id"] == reference_id),
        None)
    if reference is None:
        raise ValueError(f"Unknown reference dataset: {reference_id}")
    return Path(reference["path"])


def _override_folder(folder: str, dataset: str) -> Path | None:
    """Locate a mod-level asset folder, or None when vanilla has no layer."""
    if dataset == "vanilla":
        return None
    if dataset == "current":
        return paths.PROJECT_ROOT / folder
    if dataset.startswith("reference:"):
        return _reference_root(dataset) / folder
    if dataset.startswith("mod:"):
        return _managed_root(dataset) / folder
    raise ValueError(f"Unknown dataset: {dataset}")


def _battle_path(filename: str, dataset: str) -> Path:
    """Resolve one battle file through override, then baseline."""
    wanted = filename.casefold()
    if dataset == "vanilla":
        return paths.BASELINE_ROOT / "battle" / filename
    candidates: tuple[Path, ...]
    if dataset == "current":
        candidates = (paths.DIRECT_ROOT / "battle",)
    elif dataset.startswith("reference:"):
        root = _reference_root(dataset)
        candidates = (root / "direct" / "battle", root / "battle")
    elif dataset.startswith("mod:"):
        root = _managed_root(dataset)
        candidates = (root / "direct" / "battle", root / "battle")
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    for folder in candidates:
        if not folder.is_dir():
            continue
        for child in folder.iterdir():
            if child.is_file() and child.name.casefold() == wanted:
                return child
    return paths.BASELINE_ROOT / "battle" / filename


def _battle_override(filename: str, dataset: str) -> str | None:
    """Report the mod-relative override path when one shadows the baseline."""
    if dataset == "vanilla":
        return None
    if dataset == "current":
        roots = ((paths.PROJECT_ROOT, paths.DIRECT_ROOT / "battle"),)
    elif dataset.startswith("reference:"):
        root = _reference_root(dataset)
        roots = ((root, root / "direct" / "battle"), (root, root / "battle"))
    elif dataset.startswith("mod:"):
        root = _managed_root(dataset)
        roots = ((root, root / "direct" / "battle"), (root, root / "battle"))
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    wanted = filename.casefold()
    for root, folder in roots:
        if not folder.is_dir():
            continue
        for child in folder.iterdir():
            if child.is_file() and child.name.casefold() == wanted:
                return child.relative_to(root).as_posix()
    return None


def _field_names() -> set[str]:
    try:
        rows = json.loads(
            (paths.BASELINE_ROOT / "field" / "index.json").read_text(
                encoding="utf-8"))["rows"]
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    return {str(row.get("name", "")).casefold()
            for row in rows if row.get("name")}


def ensure_character_models() -> int:
    """Extract battle character/weapon models into the baseline on demand.

    The bulk extractor skips these so existing baselines keep working; the
    first Models visit pays one small extraction instead. Returns how many
    files were extracted.
    """
    folder = paths.BASELINE_ROOT / "battle"
    prefix = paths.GAME_ROOT / "Data" / "lang-en" / "battle"
    if not prefix.with_suffix(".fl").is_file():
        return 0
    archive = FsArchive(prefix)
    missing = [entry for entry in archive.entries
               if CHARACTER_MODEL.fullmatch(entry.basename)
               and not (folder / entry.basename).is_file()]
    if not missing:
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    for entry in missing:
        data = archive.extract(entry)
        handle, temporary = tempfile.mkstemp(
            prefix=".model-", suffix=".dat", dir=folder)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            Path(temporary).replace(folder / entry.basename)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return len(missing)


def _audio_paths() -> tuple[Path, Path]:
    fmt = paths.GAME_ROOT / "Data" / "Sound" / "audio.fmt"
    dat = paths.GAME_ROOT / "Data" / "Sound" / "audio.dat"
    if not fmt.is_file() or not dat.is_file():
        raise ValueError("The installed Data/Sound/audio.fmt and audio.dat files are missing")
    return fmt, dat


def _tim_layout(data: bytes, offset: int = 0) -> dict:
    """Parse one PlayStation TIM header at an absolute offset."""
    if offset < 0 or len(data) < offset + 8:
        raise ValueError("TIM header is truncated")
    magic, flags = struct.unpack_from("<II", data, offset)
    if magic != 0x10:
        raise ValueError("Not a PlayStation TIM image")
    depth_bits = flags & 0x03
    if depth_bits == 0:
        depth, per_pixel, colors_per_palette = 4, 0.5, 16
    elif depth_bits == 1:
        depth, per_pixel, colors_per_palette = 8, 1, 256
    elif depth_bits == 2:
        depth, per_pixel, colors_per_palette = 16, 2, 0
    else:
        raise ValueError("24-bit TIM images are not supported")
    position = offset + 8
    palette_count = 0
    if flags & 0x08:
        if len(data) < position + 12:
            raise ValueError("TIM palette header is truncated")
        palette_size, _, _, palette_width, palette_height = struct.unpack_from(
            "<IHHHH", data, position)
        colors = palette_width * palette_height
        if depth == 16 or colors == 0 or colors % colors_per_palette:
            raise ValueError("TIM palette layout is unsupported")
        if palette_size != 12 + colors * 2:
            raise ValueError("TIM palette length does not match its header")
        palette_count = colors // colors_per_palette
        position += palette_size
    if len(data) < position + 12:
        raise ValueError("TIM image header is truncated")
    image_size, _, _, width_words, height = struct.unpack_from(
        "<IHHHH", data, position)
    if image_size != 12 + width_words * 2 * height:
        raise ValueError("TIM image length does not match its header")
    if depth == 4:
        width = width_words * 4
    elif depth == 8:
        width = width_words * 2
    else:
        width = width_words
    total = position + image_size - offset
    if width <= 0 or height <= 0 or len(data) < offset + total:
        raise ValueError("TIM image extends beyond its container")
    return {
        "depth": depth,
        "width": width,
        "height": height,
        "paletteCount": palette_count,
        "size": total,
    }


def _tim_alpha(color: int) -> int:
    if color == 0:
        return 0
    return 128 if color & 0x8000 else 255


def tim_png_bytes(data: bytes, offset: int = 0, palette: int = 0) -> bytes:
    """Render one TIM as PNG bytes with the requested palette."""
    layout = _tim_layout(data, offset)
    depth = layout["depth"]
    try:
        palette = int(palette)
    except (TypeError, ValueError) as error:
        raise ValueError("Palette ID must be an integer") from error
    if depth == 16:
        if palette != 0:
            raise ValueError("16-bit TIM images carry no selectable palette")
        colors: list[tuple[int, int, int, int]] | None = None
    else:
        if not 0 <= palette < layout["paletteCount"]:
            raise ValueError(
                f"Palette ID must be 0 to {layout['paletteCount'] - 1}")
        colors = []
        per_palette = 16 if depth == 4 else 256
        start = offset + 20 + palette * per_palette * 2
        for index in range(per_palette):
            color, = struct.unpack_from("<H", data, start + index * 2)
            colors.append((
                round((color & 0x1F) * 255 / 31),
                round(((color >> 5) & 0x1F) * 255 / 31),
                round(((color >> 10) & 0x1F) * 255 / 31),
                _tim_alpha(color),
            ))
    header = offset + 8
    if layout["paletteCount"]:
        palette_size, = struct.unpack_from("<I", data, header)
        header += palette_size
    width, height = layout["width"], layout["height"]
    if depth == 16:
        pixel_bytes = width * height * 2
    elif depth == 8:
        pixel_bytes = width * height
    else:
        pixel_bytes = (width * height + 1) // 2
    pixels = data[header + 12:header + 12 + pixel_bytes]
    rgba = bytearray(width * height * 4)
    if depth == 16:
        if len(pixels) < width * height * 2:
            raise ValueError("TIM pixels are truncated")
        for index in range(width * height):
            color, = struct.unpack_from("<H", pixels, index * 2)
            rgba[index * 4:index * 4 + 4] = bytes((
                round((color & 0x1F) * 255 / 31),
                round(((color >> 5) & 0x1F) * 255 / 31),
                round(((color >> 10) & 0x1F) * 255 / 31),
                _tim_alpha(color),
            ))
    elif depth == 8:
        if len(pixels) < width * height:
            raise ValueError("TIM pixels are truncated")
        for index, pixel in enumerate(pixels[:width * height]):
            rgba[index * 4:index * 4 + 4] = bytes(colors[pixel])
    else:
        if len(pixels) * 2 < width * height:
            raise ValueError("TIM pixels are truncated")
        for index in range(width * height):
            packed = pixels[index // 2]
            rgba[index * 4:index * 4 + 4] = bytes(
                colors[(packed >> (4 * (index % 2))) & 0x0F])
    image = Image.frombytes("RGBA", (width, height), bytes(rgba))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def parse_dat_sections(data: bytes) -> list[dict] | None:
    """Split a battle model file into its section extents.

    Returns None when the bytes are not a battle-model container instead
    of raising, so mod-supplied files degrade to locked rows.
    """
    if len(data) < 8:
        return None
    raw_count, = struct.unpack_from("<I", data, 0)
    entries = raw_count + 1
    if entries < 2 or entries > 64 or 4 + entries * 4 > len(data):
        return None
    positions = list(struct.unpack_from(f"<{entries}I", data, 4))
    if positions[0] < 4 + entries * 4 or positions[-1] != len(data):
        return None
    # Empty sections (equal neighbors) are legitimate; only going backwards
    # means the table is corrupt.
    if any(bound < lower for lower, bound in zip(positions, positions[1:])):
        return None
    return [{"index": index + 1, "offset": start, "size": end - start}
            for index, (start, end) in enumerate(zip(positions, positions[1:]))]


def _section_names(filename: str, section_count: int) -> tuple[str, tuple[str, ...] | None]:
    """Name a model layout from its filename kind and section count."""
    if MONSTER_FILENAME.fullmatch(filename):
        if section_count == 11:
            return "monster", MONSTER_SECTIONS
        if filename.casefold() == "c0m127.dat" and section_count == 2:
            return "nomodel", NOMODEL_SECTIONS
        return "unmapped", None
    body = BODY_FILENAME.fullmatch(filename)
    if body:
        if section_count == 7:
            return "body", BODY_SECTIONS
        if filename.casefold() == "d7c016.dat" and section_count == 10:
            return "edea", EDEA_SECTIONS
        return "unmapped", None
    weapon = WEAPON_FILENAME.fullmatch(filename)
    if weapon:
        if section_count == 8:
            return "weapon", WEAPON_SECTIONS
        if int(weapon.group(1), 16) in (1, 9) and section_count == 5:
            return "weapon-reduced", REDUCED_WEAPON_SECTIONS
        return "unmapped", None
    return "unmapped", None


def _geometry_section(name: str, sections: list[dict]) -> dict | None:
    wanted = {"monster": 2, "body": 2, "edea": 2, "weapon": 2,
              "weapon-reduced": 1}.get(name)
    if wanted is None or len(sections) < wanted:
        return None
    return sections[wanted - 1]


def _texture_section(name: str, sections: list[dict]) -> dict | None:
    wanted = {"monster": 11, "body": 6, "edea": 9, "weapon": 7,
              "weapon-reduced": 5}.get(name)
    if wanted is None or len(sections) < wanted:
        return None
    return sections[wanted - 1]


def _geometry_counts(data: bytes, section: dict) -> dict | None:
    """Count geometry objects, vertices, and primitives, or None if unsure."""
    start, size = section["offset"], section["size"]
    if size < 8:
        return None
    objects, = struct.unpack_from("<I", data, start)
    if objects > 4096 or start + 4 + objects * 4 + 4 > start + size:
        return None
    positions = struct.unpack_from(f"<{objects}I", data, start + 4)
    if any(position < 4 + objects * 4 or position >= size for position in positions):
        return None
    vertices, = struct.unpack_from("<I", data, start + size - 4)
    triangles = quads = 0
    for position in positions:
        cursor = start + position
        if cursor + 2 > start + size - 4:
            return None
        groups, = struct.unpack_from("<H", data, cursor)
        cursor += 2
        for _ in range(groups):
            if cursor + 4 > start + size - 4:
                return None
            count, = struct.unpack_from("<H", data, cursor + 2)
            cursor += 4 + count * 6
            if cursor > start + size - 4:
                return None
        # Section offsets in shipped files are 4-aligned, so section-relative
        # and file-absolute padding agree here.
        cursor += (4 - (cursor % 4)) % 4
        if cursor + 12 > start + size - 4:
            return None
        textured_triangles, textured_quads, colored_triangles, colored_quads = (
            struct.unpack_from("<HHHH", data, cursor))
        if (textured_triangles > 65535 or textured_quads > 65535
                or colored_triangles > 65535 or colored_quads > 65535):
            return None
        cursor += 12
        cursor += (textured_triangles * 16 + textured_quads * 20
                   + colored_triangles * 20 + colored_quads * 24)
        if cursor > start + size - 4:
            return None
        triangles += textured_triangles + colored_triangles
        quads += textured_quads + colored_quads
    return {"objects": objects, "vertices": vertices,
            "triangles": triangles, "quads": quads}


def _texture_layouts(data: bytes, section: dict) -> list[dict] | None:
    """Describe a model texture section's TIMs, or None if unsure."""
    start, size = section["offset"], section["size"]
    if size < 8:
        return None
    count, = struct.unpack_from("<I", data, start)
    if count > 64 or start + 4 + (count + 1) * 4 > start + size:
        return None
    positions = struct.unpack_from(f"<{count + 1}I", data, start + 4)
    if positions[0] < 4 + (count + 1) * 4 or positions[-1] != size:
        return None
    if any(bound < lower for lower, bound in zip(positions, positions[1:])):
        return None
    layouts = []
    for index in range(count):
        if positions[index + 1] == positions[index]:
            continue
        try:
            layout = _tim_layout(data, start + positions[index])
        except ValueError:
            return None
        layouts.append({"index": index, **layout})
    return layouts


def _model_identity(filename: str, kind: str) -> tuple[str, str, int | None]:
    """Return the display name, note, and linked enemy id for a model file."""
    monster = MONSTER_FILENAME.fullmatch(filename)
    if monster:
        number = int(monster.group(1))
        name = MONSTER_NAMES.get(number)
        if name is not None:
            return name, "", number
        return (f"Unlisted battle model {filename}",
                "This file is beyond the 144-entry enemy list; the Enemies "
                "tab does not reference it.", None)
    body = BODY_FILENAME.fullmatch(filename)
    if body:
        character = CHARACTER_NAMES.get(int(body.group(1), 16), "Unknown")
        if filename.casefold() == "d7c016.dat":
            return ("Edea battle model",
                    "Self-contained body: Edea loads no weapon file.", None)
        return (f"{character} battle body",
                f"One of {character}'s battle body variants; the battle "
                "setup chooses between them.", None)
    weapon = WEAPON_FILENAME.fullmatch(filename)
    if weapon:
        character = CHARACTER_NAMES.get(int(weapon.group(1), 16), "Unknown")
        if kind == "weapon-reduced":
            return (f"{character} attack data",
                    "Reduced weapon file: animation sequences and attack "
                    "sounds only, with no second battle model.", None)
        return (f"{character} weapon model",
                "Which equippable weapon this file holds is not decoded; "
                "only its sections and textures are shown.", None)
    return (f"Battle model {filename}",
            "This file is not a recognized battle-model layout.", None)


def _model_file_info(path: Path) -> dict:
    """Parse one model file's bytes into cacheable inventory facts."""
    data = path.read_bytes()
    sections = parse_dat_sections(data)
    if sections is None:
        return {"sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "parsed": False}
    kind, names = _section_names(path.name, len(sections))
    named = ([{**section, "name": names[section["index"] - 1]}
              for section in sections] if names is not None
             else [{**section, "name": f"Section {section['index']}"}
                   for section in sections])
    geometry = counts = textures = tims = None
    if names is not None:
        geometry = _geometry_section(kind, sections)
        counts = (_geometry_counts(data, geometry)
                  if geometry is not None else None)
        textures = _texture_section(kind, sections)
        tims = _texture_layouts(data, textures) if textures is not None else None
    return {"sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "parsed": True, "kind": kind, "sections": named,
            "counts": counts, "tims": tims if tims is not None else [],
            "geometryVerified": counts is not None,
            "texturesVerified": tims is not None}


@lru_cache(maxsize=512)
def _cached_model_file(path_text: str, size: int, mtime_ns: int) -> dict:
    return _model_file_info(Path(path_text))


def _model_bytes(filename: str, dataset: str) -> tuple[bytes, str | None]:
    """Return resolved model bytes and the mod-relative override path."""
    override = _battle_override(filename, dataset)
    target = _battle_path(filename, dataset)
    if not target.is_file():
        raise ValueError(f"{filename} is not available in this dataset")
    return target.read_bytes(), override


def _sfx_entries() -> list[dict]:
    fmt, _dat = _audio_paths()
    return read_ff8_entries(fmt)


def _sfx_duration_ms(entry: dict) -> int | None:
    rate = int(entry["rate"])
    if rate <= 0:
        return None
    length, channels = int(entry["length"]), int(entry["channels"])
    if int(entry["tag"]) == 2:
        extra = bytes(entry["extra"])
        if len(extra) < 2 or int(entry["alignment"]) <= 0:
            return None
        per_block, = struct.unpack_from("<H", extra, 0)
        if per_block <= 0:
            return None
        blocks = (length + int(entry["alignment"]) - 1) // int(entry["alignment"])
        return round(blocks * per_block / rate * 1000)
    unit = channels * int(entry["bits"]) // 8
    if unit <= 0:
        return None
    return round(length // unit / rate * 1000)


def _sfx_claim_id(stem: str, fields: set[str]) -> tuple[int | None, str | None, bool]:
    """Map an sfx/ filename stem to a sound id, or None when unrecognized.

    Returns the claimed id, the context prefix (or None for a global file),
    and whether the name shape is one FFNx resolves.
    """
    lowered = stem.casefold()
    if lowered.isdigit():
        return int(lowered), None, True
    head, separator, tail = lowered.rpartition("_")
    if not separator or not tail.isdigit():
        return None, None, False
    sound_id = int(tail)
    if head in ("battle", "menu", "world"):
        return sound_id, head, True
    if head in fields:
        return sound_id, head, True
    field, _, _triangle = head.rpartition("_")
    if field in fields:
        return sound_id, head, True
    return None, None, False


def _sfx_mod_files(dataset: str) -> tuple[dict[int, list[dict]], list[dict], dict]:
    """Claim a dataset's sfx/ files against sound ids.

    Returns per-id claims, unrecognized files, and the parsed config flags.
    """
    folder = _override_folder("sfx", dataset)
    if folder is None or not folder.is_dir():
        return {}, [], {}
    try:
        count = len(_sfx_entries())
    except ValueError:
        count = 0
    fields = _field_names()
    claims: dict[int, list[dict]] = {}
    unrecognized: list[dict] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        relative = path.relative_to(folder).as_posix()
        if path.suffix.casefold() in IGNORED_ASSET_SUFFIXES:
            continue
        if path.parent != folder:
            unrecognized.append({"file": relative, "sizeBytes": path.stat().st_size,
                                 "note": "FFNx loads external SFX from the top "
                                         "level of its SFX folder only."})
            continue
        if path.name.casefold() == "config.toml":
            continue
        sound_id, _context, recognized = _sfx_claim_id(path.stem, fields)
        if not recognized or sound_id is None or sound_id >= count:
            unrecognized.append({"file": relative, "sizeBytes": path.stat().st_size,
                                 "note": "This filename matches no FFNx "
                                         "external SFX name for a shipped sound."})
            continue
        claims.setdefault(sound_id, []).append(
            {"file": relative, "sizeBytes": path.stat().st_size})
    config: dict = {}
    config_path = folder / "config.toml"
    if config_path.is_file():
        try:
            raw = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            config = {"error": f"sfx/config.toml could not be parsed: {error}"}
        else:
            for key, value in raw.items():
                if str(key).isdigit() and isinstance(value, dict):
                    kept = {flag: value[flag] for flag in
                            ("loop", "skip", "shuffle", "sequential")
                            if flag in value}
                    if kept:
                        config[str(key)] = kept
    return claims, unrecognized, config


def _external_sfx_enabled() -> bool | None:
    config = paths.GAME_ROOT / "FFNx.toml"
    if not config.is_file():
        return None
    try:
        return bool(tomllib.loads(
            config.read_text(encoding="utf-8-sig")).get("use_external_sfx", False))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError):
        return None


def sfx_rows(dataset: str = "current") -> dict:
    entries = _sfx_entries()
    claims, unrecognized, config = _sfx_mod_files(dataset)
    rows = []
    for sound_id, entry in enumerate(entries):
        valid = int(entry["length"]) > 0
        mod_files = claims.get(sound_id, [])
        rows.append({
            "id": sound_id,
            "kind": "sfx",
            "name": f"Sound {sound_id}",
            "valid": valid,
            "channels": int(entry["channels"]),
            "rate": int(entry["rate"]),
            "bits": int(entry["bits"]),
            "bytes": int(entry["length"]),
            "codec": ("ADPCM" if int(entry["tag"]) == 2
                      else "PCM" if int(entry["tag"]) == 1
                      else f"format {int(entry['tag'])}"),
            "loop": valid and int(entry["flags"]) == 1,
            "durationMs": _sfx_duration_ms(entry) if valid else None,
            "usedBy": ACTOR_SOUNDS.get(str(sound_id), []),
            "modFiles": mod_files,
            "config": config.get(str(sound_id), {}) if isinstance(config, dict) else {},
            "note": "" if valid else "Unused placeholder entry in audio.fmt.",
        })
    for entry in unrecognized:
        rows.append({
            "id": f"file:{entry['file']}",
            "kind": "sfx",
            "name": Path(entry["file"]).name,
            "valid": False,
            "channels": None,
            "rate": None,
            "bits": None,
            "bytes": entry["sizeBytes"],
            "loop": False,
            "durationMs": None,
            "usedBy": [],
            "modFiles": [entry],
            "config": {},
            "note": entry["note"],
        })
    payload: dict = {"rows": rows, "externalSfx": _external_sfx_enabled()}
    if isinstance(config, dict) and config.get("error"):
        payload["configError"] = config["error"]
    return payload


def sfx_audio(sound_id: int, dataset: str = "current") -> tuple[bytes, str]:
    """Return playable audio bytes and a MIME type for one sound."""
    if isinstance(sound_id, bool):
        raise ValueError("Sound ID must be an integer")
    sound_id = int(sound_id)
    entries = _sfx_entries()
    if not 0 <= sound_id < len(entries):
        raise ValueError(f"Sound ID must be 0 to {len(entries) - 1}")
    folder = _override_folder("sfx", dataset)
    if folder is not None and folder.is_dir():
        claims, _unrecognized, _config = _sfx_mod_files(dataset)
        files = claims.get(sound_id, [])
        if files:
            preferred = next((row for row in files
                              if Path(row["file"]).stem.isdigit()), files[0])
            target = folder / Path(*preferred["file"].split("/"))
            data = target.read_bytes()
            suffix = target.suffix.casefold()
            mime = {".ogg": "audio/ogg", ".wav": "audio/wav",
                    ".flac": "audio/flac", ".mp3": "audio/mpeg"}.get(
                        suffix, "application/octet-stream")
            return data, mime
    _fmt, dat = _audio_paths()
    return entry_wav(entries[sound_id], dat), "audio/wav"


def save_sfx(edits: list[dict]) -> dict:
    fmt_entries = _sfx_entries()
    saved = 0
    for edit in edits:
        sound_id = edit.get("id")
        if isinstance(sound_id, bool) or not isinstance(sound_id, int):
            raise ValueError("SFX edits need an integer sound ID")
        if not 0 <= sound_id < len(fmt_entries):
            raise ValueError(f"Sound ID must be 0 to {len(fmt_entries) - 1}")
        folder = paths.PROJECT_ROOT / "sfx"
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob(f"{sound_id}.*"):
            if stale.is_file() and stale.suffix.casefold() not in IGNORED_ASSET_SUFFIXES:
                stale.unlink()
        if edit.get("revert") is True:
            saved += 1
            continue
        encoded = edit.get("audioBase64")
        extension = str(edit.get("ext", "")).casefold()
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        if extension not in SFX_EXTENSIONS:
            raise ValueError(
                f"Sound {sound_id} needs one of: {', '.join(sorted(SFX_EXTENSIONS))}")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f"Sound {sound_id} needs replacement audio data")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError(f"Sound {sound_id} audio data is not valid base64") from error
        if not data or len(data) > MAX_SFX_BYTES:
            raise ValueError(
                f"Sound {sound_id} audio must be 1 byte to {MAX_SFX_BYTES} bytes")
        magic = SFX_EXTENSIONS[extension]
        if magic == b"RIFF":
            if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                raise ValueError(f"Sound {sound_id} is not a WAV file")
        elif magic is not None:
            if not data.startswith(magic):
                raise ValueError(
                    f"Sound {sound_id} is not an {extension[1:].upper()} file")
        elif not (data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF
                                              and data[1] & 0xE0 == 0xE0)):
            raise ValueError(f"Sound {sound_id} is not an MP3 file")
        destination = folder / f"{sound_id}{extension}"
        handle, temporary = tempfile.mkstemp(prefix=f".{sound_id}.", dir=folder)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        saved += 1
    return {"saved": saved}


def _battle_archive_index() -> list[dict]:
    """List battle archive entries from .fl/.fi without extracting bytes."""
    prefix = paths.GAME_ROOT / "Data" / "lang-en" / "battle"
    names = prefix.with_suffix(".fl").read_text(
        encoding="utf-8", errors="strict").splitlines()
    index = prefix.with_suffix(".fi").read_bytes()
    rows = []
    for position, name in enumerate(names):
        basename = Path(name.replace("\\", "/")).name.casefold()
        size = 0
        if (position + 1) * 12 <= len(index):
            size, _, _ = struct.unpack_from("<III", index, position * 12)
        rows.append({"file": basename, "sizeBytes": size})
    return rows


def _model_row(filename: str, dataset: str, archive_sizes: dict[str, int],
               mod_only_files: set[str]) -> dict:
    override = _battle_override(filename, dataset)
    target = _battle_path(filename, dataset)
    info: dict | None = None
    if target.is_file():
        stat = target.stat()
        info = _cached_model_file(str(target), stat.st_size, stat.st_mtime_ns)
    row: dict = {"id": filename, "kind": "model", "file": filename,
                 "override": override, "modOnly": filename in mod_only_files}
    if filename == "scene.out":
        row.update(modelKind="locked", name="Battle formations (scene.out)",
                   sections=None, counts=None, tims=[],
                   sizeBytes=info["sizeBytes"] if info else archive_sizes.get(filename, 0),
                   sha256=info["sha256"] if info else None,
                   note="Battle formations are edited on the Encounters tab.",
                   enemyId=None, editor="encounters")
        return row
    if filename in mod_only_files:
        row["note"] = ("This file is not in the shipped battle archive; only "
                       "this dataset carries it.")
    if info is None:
        row.update(modelKind="locked", name=row.get("name", f"Battle file {filename}"),
                   sections=None, counts=None, tims=[],
                   sizeBytes=archive_sizes.get(filename, 0), sha256=None,
                   enemyId=None)
        if "note" not in row:
            if filename.startswith("a0stg"):
                row["note"] = ("Battle stage geometry is listed but not "
                               "decoded; whole-file replacement only.")
            elif filename.startswith("mag"):
                row["note"] = ("Magic-effect data is listed but not decoded; "
                               "whole-file replacement only.")
            else:
                row["note"] = ("This battle file is listed but not decoded; "
                               "whole-file replacement only.")
        return row
    if not info["parsed"]:
        if info["sizeBytes"] == 0 and filename == "d0w007.dat":
            name, note = ("Squall weapon placeholder",
                          "Empty placeholder weapon file shipped by the game.")
        else:
            name, note, _enemy = _model_identity(filename, "unmapped")
            note = ("These bytes are not a battle-model container; the file "
                    "can only be replaced or reverted as a whole.")
        row.update(modelKind="locked" if info["sizeBytes"] else "empty",
                   name=name, sections=None, counts=None, tims=[],
                   sizeBytes=info["sizeBytes"], sha256=info["sha256"],
                   enemyId=None, note=note)
        return row
    kind = info["kind"]
    name, note, enemy_id = _model_identity(filename, kind)
    if kind == "unmapped":
        note = ("This file parses as a model container but its section "
                "layout is not mapped; whole-file replacement only.")
    elif kind != "nomodel" and (not info["geometryVerified"]
                                or not info["texturesVerified"]):
        note = ((note + " ") if note else "") + (
            "Some sections did not verify; counts and textures below "
            "cover only the verified parts.")
    if filename in mod_only_files:
        note = row["note"] + (f" {note}" if note else "")
    counts = info["counts"] or {}
    row.update(modelKind=kind, name=name, sections=info["sections"],
               counts=info["counts"], tims=info["tims"],
               vertices=counts.get("vertices"), timCount=len(info["tims"]),
               sizeBytes=info["sizeBytes"], sha256=info["sha256"],
               enemyId=enemy_id, note=note)
    return row


def model_rows(dataset: str = "current") -> dict:
    ensure_character_models()
    archive = _battle_archive_index()
    archive_sizes = {entry["file"]: entry["sizeBytes"] for entry in archive}
    filenames = [entry["file"] for entry in archive]
    mod_only_files: set[str] = set()
    if dataset != "vanilla":
        roots: list[Path] = []
        if dataset == "current":
            roots = [paths.DIRECT_ROOT / "battle"]
        elif dataset.startswith("reference:"):
            root = _reference_root(dataset)
            roots = [root / "direct" / "battle", root / "battle"]
        elif dataset.startswith("mod:"):
            root = _managed_root(dataset)
            roots = [root / "direct" / "battle", root / "battle"]
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        for folder in roots:
            if not folder.is_dir():
                continue
            for child in sorted(folder.iterdir()):
                if not child.is_file() or child.name.startswith("."):
                    continue
                if child.suffix.casefold() in IGNORED_ASSET_SUFFIXES:
                    continue
                lowered = child.name.casefold()
                if lowered not in archive_sizes and lowered not in mod_only_files:
                    mod_only_files.add(lowered)
                    filenames.append(lowered)
    rows = [_model_row(filename, dataset, archive_sizes, mod_only_files)
            for filename in filenames]
    return {"rows": rows}


def model_dat_bytes(filename: str, dataset: str = "current") -> bytes:
    if not MODEL_FILENAME.fullmatch(filename) or "/" in filename or "\\" in filename:
        raise ValueError("Model export needs a battle archive filename")
    ensure_character_models()
    data, _override = _model_bytes(filename.casefold(), dataset)
    return data


def save_models(edits: list[dict]) -> dict:
    saved = 0
    for edit in edits:
        filename = str(edit.get("file", "")).casefold()
        if not MODEL_FILENAME.fullmatch(filename):
            raise ValueError(f"{edit.get('file')} is not a battle model filename")
        destination = paths.DIRECT_ROOT / "battle" / filename
        if edit.get("revert") is True:
            destination.unlink(missing_ok=True)
            saved += 1
            continue
        encoded = edit.get("datBase64")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f"{filename} needs replacement file data")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError(f"{filename} file data is not valid base64") from error
        if not data or len(data) > MAX_MODEL_BYTES:
            raise ValueError(
                f"{filename} must be 1 byte to {MAX_MODEL_BYTES} bytes")
        if filename.endswith(".dat") and parse_dat_sections(data) is None:
            raise ValueError(f"{filename} is not a battle-model container")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            # One rolling backup, like field saves: a timestamped copy per
            # save filled mod folders with stale files that never went away.
            shutil.copy2(destination, destination.with_name(f"{destination.name}.bak"))
        handle, temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        saved += 1
    return {"saved": saved}


def _texture_mod_files(dataset: str) -> list[dict]:
    folder = _override_folder("textures", dataset)
    if folder is None or not folder.is_dir():
        return []
    files = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.casefold() in IGNORED_ASSET_SUFFIXES:
            continue
        files.append({"file": path.relative_to(folder).as_posix(),
                      "sizeBytes": path.stat().st_size})
    return files


def _texture_claim(mod_file: str, battle_stems: set[str],
                   texl_count: int) -> tuple[str, str | None]:
    """Attribute a mod texture to a vanilla asset id, or mark it unmapped.

    Returns the asset id (or "file:<path>") and the verified FFNx base path
    (or None). Matching only extends base paths proved by FFNx source.
    """
    normalized = mod_file.casefold()
    if normalized.startswith("battle/"):
        token = re.split(r"[._]", normalized.partition("/")[2], maxsplit=1)[0]
        if token in battle_stems:
            return f"model:{token}.dat", f"battle/{token}.dat"
    match = re.fullmatch(r"world/dat/texl/texture(\d+).*", normalized)
    if match and int(match.group(1)) < texl_count:
        return f"texl:{match.group(1)}", f"world/dat/texl/texture{match.group(1)}"
    return f"file:{mod_file}", None


def texture_rows(dataset: str = "current") -> dict:
    models = model_rows(dataset)["rows"]
    battle_stems = {row["file"][:-4] for row in models
                    if row["file"].endswith(".dat")
                    and (MONSTER_FILENAME.fullmatch(row["file"])
                         or BODY_FILENAME.fullmatch(row["file"])
                         or WEAPON_FILENAME.fullmatch(row["file"]))}
    try:
        texl = world_textures.rows(dataset)["rows"]
    except (OSError, ValueError):
        texl = []
    mod_files = _texture_mod_files(dataset)
    claims: dict[str, list[dict]] = {}
    unmapped: list[dict] = []
    for entry in mod_files:
        asset_id, _base = _texture_claim(entry["file"], battle_stems, len(texl))
        if asset_id.startswith("file:"):
            unmapped.append(entry)
        else:
            claims.setdefault(asset_id, []).append(entry)
    rows: list[dict] = []
    matched: set[str] = set()
    for entry in texl:
        texture_id = int(entry["id"])
        asset_id = f"texl:{texture_id}"
        matched.add(asset_id)
        rows.append({
            "id": f"texl/{texture_id}",
            "kind": "texture",
            "name": f"World Texture {texture_id + 1}",
            "source": "World texl.obj",
            "modelFile": None,
            "timIndex": texture_id,
            "width": entry["width"],
            "height": entry["height"],
            "depth": entry["depth"],
            "paletteCount": entry["paletteCount"],
            "ffnxBase": f"world/dat/texl/texture{texture_id}",
            "modFiles": claims.get(asset_id, []),
            "mapped": True,
            "editor": "world",
            "note": "Replace this texture under Maps > World; this tab previews it.",
        })
    for row in models:
        for tim in row.get("tims") or []:
            asset_id = f"model:{row['file']}"
            matched.add(asset_id)
            rows.append({
                "id": f"battle/{row['file']}#{tim['index']}",
                "kind": "texture",
                "name": f"{row['name']} - texture {tim['index'] + 1}",
                "source": f"Battle {row['file']}",
                "modelFile": row["file"],
                "timIndex": tim["index"],
                "width": tim["width"],
                "height": tim["height"],
                "depth": tim["depth"],
                "paletteCount": tim["paletteCount"],
                "ffnxBase": f"battle/{row['file']}",
                "modFiles": claims.get(asset_id, []),
                "mapped": True,
                "editor": "models",
                "note": ("Replace the whole model file on the Models tab; "
                         "in-place texture swaps inside a model are not supported."),
            })
    for asset_id, entries in sorted(claims.items()):
        if asset_id in matched:
            continue
        base = asset_id.partition(":")[2]
        for entry in entries:
            rows.append({
                "id": f"file:{entry['file']}",
                "kind": "texture",
                "name": Path(entry["file"]).name,
                "source": "Mod file",
                "modelFile": None,
                "timIndex": None,
                "width": None,
                "height": None,
                "depth": None,
                "paletteCount": None,
                "ffnxBase": f"battle/{base}" if asset_id.startswith("model:") else (
                    f"world/dat/texl/{base}"),
                "modFiles": [entry],
                "mapped": False,
                "editor": None,
                "note": (f"Targets {base}, whose textures are not decoded in "
                         "this dataset; kept visible so no mod file is lost."),
            })
    for entry in unmapped:
        rows.append({
            "id": f"file:{entry['file']}",
            "kind": "texture",
            "name": Path(entry["file"]).name,
            "source": "Mod file",
            "modelFile": None,
            "timIndex": None,
            "width": None,
            "height": None,
            "depth": None,
            "paletteCount": None,
            "ffnxBase": None,
            "modFiles": [entry],
            "mapped": False,
            "editor": None,
            "note": ("FFNx resolves this texture while the game runs; "
                     "Lexeditor cannot link it to one vanilla texture."),
        })
    return {"rows": rows}


def texture_png_bytes(texture_id: str, palette: int = 0,
                      dataset: str = "current") -> bytes:
    """Render one Textures-tab row as PNG bytes."""
    value = str(texture_id or "")
    if value.startswith("texl/"):
        try:
            texture_id_number = int(value.partition("/")[2])
        except (TypeError, ValueError) as error:
            raise ValueError("World texture ID must be an integer") from error
        return world_textures.png_bytes(texture_id_number, palette, dataset)
    if value.startswith("battle/"):
        inner, _, index_text = value.partition("/")[2].rpartition("#")
        if not MODEL_FILENAME.fullmatch(inner):
            raise ValueError("Battle texture needs a model file and TIM index")
        try:
            tim_index = int(index_text)
        except (TypeError, ValueError) as error:
            raise ValueError("Battle texture needs a numeric TIM index") from error
        ensure_character_models()
        data, _override = _model_bytes(inner.casefold(), dataset)
        info = _model_file_info_from_bytes(inner.casefold(), data)
        tims = info.get("tims") or []
        if not 0 <= tim_index < len(tims):
            raise ValueError("Battle TIM index is out of range")
        kind = info.get("kind")
        sections = parse_dat_sections(data) or []
        section = _texture_section(kind, sections) if kind else None
        if section is None:
            raise ValueError("This model file exposes no texture section")
        start = section["offset"]
        count, = struct.unpack_from("<I", data, start)
        positions = struct.unpack_from(f"<{count + 1}I", data, start + 4)
        return tim_png_bytes(data, start + positions[tim_index], palette)
    if value.startswith("file:"):
        folder = _override_folder("textures", dataset)
        if folder is None:
            raise ValueError("Mod texture files need a mod dataset")
        relative = value.partition(":")[2]
        target = (folder / Path(*relative.split("/"))).resolve()
        if folder.resolve() not in target.parents or not target.is_file():
            raise ValueError("Mod texture file was not found")
        if target.suffix.casefold() != ".png":
            raise ValueError("Only PNG mod textures can be previewed")
        return target.read_bytes()
    raise ValueError("Unknown texture ID")


def _model_file_info_from_bytes(filename: str, data: bytes) -> dict:
    sections = parse_dat_sections(data)
    if sections is None:
        return {"parsed": False}
    kind, names = _section_names(filename, len(sections))
    textures = (_texture_section(kind, sections) if names is not None else None)
    tims = (_texture_layouts(data, textures)
            if textures is not None else None)
    return {"parsed": True, "kind": kind, "tims": tims if tims is not None else []}

