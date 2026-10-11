"""Whole-file and binder-member asset overrides, with texture previews.

A mod replaces a game asset by carrying the file at its game-relative path
(movies, sounds, models, textures) or, for binders the loader combines, by
carrying the rebuilt binder with a replaced member. Structured editors own
their files (parameters, item text, .msb maps, .anibnd.dcx animations); every
other file under the game's data roots is an asset and merges whole, or
member-by-member for binders.

Texture previews decode TPF containers (binder members, standalone .tpf and
.dds files) and render each DDS through Pillow, which already reads every
compressed format the game ships, BC7 included. Split .bhd/.bdt archives
replace as whole files; their member table is not decoded yet.
"""
import hashlib
import io
import os
import re
import struct
import time
from pathlib import Path

from .formats import FormatError, MAX_ARCHIVE, inflate, members  # noqa: F401

MOD_ID = "lexeditor-ds1"
# Every top-level game folder an override may land in. param/ holds the
# structured archives; paramdef/ is tooling the game never reads.
ASSET_ROOTS = ("chr", "event", "facegen", "font", "map", "menu", "movww", "msg",
               "mtd", "obj", "other", "parts", "remo", "script", "sfx", "shader", "sound")
# The installed game's biggest asset is a 380 MB movie.
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_ASSET_FILES = 2000
MAX_ASSET_TOTAL = 4 * 1024 * 1024 * 1024
MAX_PREVIEW_DIM = 512
MAX_PREVIEW_BYTES = 256 * 1024 * 1024
# One upload piece after base64 decoding; the browser sends sequentially.
MAX_UPLOAD_CHUNK = 1024 * 1024
UPLOAD_PART_PREFIX = ".lexeditor-upload-"
UPLOAD_ID = re.compile(r"[A-Za-z0-9-]{1,64}\Z")

DXGI_FORMATS = {70: "BC1", 71: "BC1", 72: "BC1", 73: "BC1", 74: "BC2", 75: "BC2",
                76: "BC2", 77: "BC3", 78: "BC4", 79: "BC4", 80: "BC5", 81: "BC5",
                83: "BC5", 95: "BC6H", 96: "BC6H", 97: "BC7", 98: "BC7",
                99: "BC7", 28: "RGBA8", 87: "BGRA8"}


class AssetError(FormatError):
    """An asset override or preview the editor refuses."""


def _checked(path):
    from .tweak_mods import checked
    return checked(Path(path))


def is_owned(relative):
    """Structured editors own parameters, item text, maps and animations."""
    from .store import RELATIVE
    from . import texts
    from .msb import MAP_DIR
    from .tae_store import CHR_DIR
    text = relative.as_posix()
    if relative in (RELATIVE, texts.RELATIVE):
        return True
    if text.startswith(MAP_DIR.as_posix() + "/") and relative.suffix == ".msb":
        return True
    return text.startswith(CHR_DIR.as_posix() + "/") and relative.name.endswith(".anibnd.dcx")


def check_relative(value):
    """A game-relative override path, contained and within the asset roots."""
    relative = Path(str(value).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise AssetError("An override names a file inside the installed game")
    if relative.parts[0] not in ASSET_ROOTS:
        raise AssetError(f"The {relative.parts[0]} folder holds no replaceable game files")
    if is_owned(relative):
        raise AssetError("That file has its own editor; change it there instead")
    if relative.name.startswith(".lexeditor-") or relative.name.endswith(".lexeditor-original"):
        raise AssetError("That name is reserved for Lexeditor's own bookkeeping")
    return relative


def scan_project(project, strict=True):
    """The mod's asset overrides: game-relative paths with sizes.

    Soft mode stops at the caps instead of raising, for status checks
    that must report on a project rather than refuse it.
    """
    from core import script_mods
    from .store import MARKER
    root = _checked(project)
    tweak_mod = script_mods.is_script_mod(root)
    found, total = [], 0
    for top in ASSET_ROOTS:
        folder = root / top
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_dir() or path.name == MARKER or path.name == "mod.json" \
                    or path.name.startswith(".lexeditor-"):
                continue
            relative = path.relative_to(root)
            if is_owned(relative):
                continue
            # script/ is a game folder and also where a tweak mod keeps its
            # build script, assembly and templates (core/script_mods). In a
            # tweak mod that folder is the mod's own code, never an override:
            # deploying it put tweak.py and its sources into the game.
            if tweak_mod and script_mods.owns(relative.as_posix()):
                continue
            if len(found) >= MAX_ASSET_FILES:
                if strict:
                    raise AssetError(f"A mod carries at most {MAX_ASSET_FILES} asset overrides")
                return found
            size = path.stat().st_size
            if size > MAX_ASSET_BYTES:
                if strict:
                    raise AssetError(f"{relative.as_posix()} is too large to carry as an override")
                continue
            total += size
            if total > MAX_ASSET_TOTAL:
                if strict:
                    raise AssetError("The mod's asset overrides are too large in total")
                return found
            found.append({"relative": relative.as_posix(), "size": size})
    return found


def scan_game(game_root):
    """Every replaceable installed file: game-relative paths with sizes."""
    root = _checked(game_root)
    found = []
    for top in ASSET_ROOTS:
        folder = root / top
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_dir() or path.name.startswith(".lexeditor-") or path.name.endswith(".lexeditor-original"):
                continue
            relative = path.relative_to(root)
            if is_owned(relative):
                continue
            found.append({"relative": relative.as_posix(), "size": path.stat().st_size})
    return found


def store_bytes(project, relative, data):
    """Carry `data` as the mod's override of a game file."""
    relative = check_relative(relative)
    if len(data) > MAX_ASSET_BYTES:
        raise AssetError("That file is too large to carry as an override")
    target = _checked(Path(project) / relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    from .store import atomic_write
    atomic_write(target, bytes(data))
    return {"relative": relative.as_posix(), "size": len(data)}


def remove_override(project, relative):
    """Drop the mod's override of a game file."""
    relative = check_relative(relative)
    target = _checked(Path(project) / relative)
    if not target.is_file():
        raise AssetError("The mod carries no override of that file")
    target.unlink()
    return {"relative": relative.as_posix()}


def _sweep_uploads(root):
    """Drop unfinished uploads older than a day; best effort only."""
    try:
        cutoff = time.time() - 86400
        for part in root.rglob(UPLOAD_PART_PREFIX + "*.part"):
            try:
                if part.is_file() and part.stat().st_mtime < cutoff:
                    part.unlink()
            except OSError:
                pass
    except OSError:
        pass


def receive_chunk(project, upload_id, relative, total, offset, raw, final):
    """Store one upload piece; the last piece becomes the override.

    Pieces arrive in order, each at the offset where the previous one
    ended. A first piece restarts its upload. The finished file lands
    atomically, so an interrupted upload never leaves a half override.
    """
    if not UPLOAD_ID.match(str(upload_id or "")):
        raise AssetError("That upload names no valid transfer")
    relative = check_relative(relative)
    try:
        total, offset = int(total), int(offset)
    except (TypeError, ValueError):
        raise AssetError("That upload names no valid size") from None
    raw = bytes(raw)
    if not 0 < total <= MAX_ASSET_BYTES:
        raise AssetError("That file is too large to carry as an override")
    if offset < 0 or offset > total or offset + len(raw) > total:
        raise AssetError("That upload piece lands outside its own file")
    if len(raw) > MAX_UPLOAD_CHUNK:
        raise AssetError("That upload piece is too large")
    root = _checked(Path(project))
    target = _checked(root / relative)
    part = target.parent / f"{UPLOAD_PART_PREFIX}{upload_id}.part"
    target.parent.mkdir(parents=True, exist_ok=True)
    _sweep_uploads(root)
    if offset == 0 and part.is_file():
        part.unlink()
    have = part.stat().st_size if part.is_file() else 0
    if have != offset:
        raise AssetError("That upload arrived out of order; start it again")
    with open(part, "ab") as handle:
        handle.write(raw)
    received = offset + len(raw)
    if not final:
        return {"relative": relative.as_posix(), "received": received, "total": total}
    if received != total:
        part.unlink(missing_ok=True)
        raise AssetError("That upload ended short of its size")
    os.replace(part, target)
    return {"relative": relative.as_posix(), "size": total}


def parse_tpf(data):
    """A DS1 texture container's textures: names with DDS offsets and sizes."""
    if len(data) < 16 or data[:4] != b"TPF\x00":
        raise AssetError("That is not a Dark Souls texture container")
    count = struct.unpack_from("<I", data, 8)[0]
    if count > 10000:
        raise AssetError("That texture container names too many textures")
    textures = []
    for index in range(count):
        base = 16 + index * 20
        if base + 20 > len(data):
            raise AssetError("That texture container ends inside its own table")
        offset, size, _unknown, name_off, _other = struct.unpack_from("<5I", data, base)
        if offset + size > len(data) or data[offset:offset + 4] != b"DDS ":
            raise AssetError("That texture container points outside its pixels")
        end = data.find(b"\x00", name_off, name_off + 128)
        if end <= name_off:
            raise AssetError("That texture container has a nameless texture")
        textures.append({"index": index, "name": data[name_off:end].decode("shift_jis", "replace"),
                         "offset": offset, "size": size})
    return textures


def dds_info(blob):
    """A DDS blob's dimensions and compression label."""
    if len(blob) < 128 or blob[:4] != b"DDS " or struct.unpack_from("<I", blob, 4)[0] != 124:
        raise AssetError("That is not a readable texture")
    height, width = struct.unpack_from("<2I", blob, 12)
    if not 0 < width <= 16384 and 0 < height <= 16384:
        raise AssetError("That texture has an impossible size")
    fourcc = blob[84:88]
    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", blob, 128)[0]
        label = DXGI_FORMATS.get(dxgi, f"DX10/{dxgi}")
    elif fourcc == b"DXT1":
        label = "DXT1"
    elif fourcc == b"DXT3":
        label = "DXT3"
    elif fourcc == b"DXT5":
        label = "DXT5"
    elif fourcc == b"\x00\x00\x00\x00":
        label = "uncompressed"
    elif fourcc in (b"o\x00\x00\x00", b"p\x00\x00\x00", b"q\x00\x00\x00", b"r\x00\x00\x00",
                    b"s\x00\x00\x00", b"t\x00\x00\x00"):
        label = {"o": "R16F", "p": "RG16F", "q": "RGBA16F", "r": "R32F",
                 "s": "RG32F", "t": "RGBA32F"}[fourcc[:1].decode("ascii")]
    else:
        label = fourcc.decode("ascii", "replace")
    return {"width": width, "height": height, "format": label}


def render_png(blob):
    """A DDS blob as PNG bytes, shrunk to fit the preview pane."""
    if len(blob) > MAX_PREVIEW_BYTES:
        raise AssetError("That texture is too large to preview")
    from PIL import Image
    try:
        with Image.open(io.BytesIO(bytes(blob))) as image:
            image.load()
            image.thumbnail((MAX_PREVIEW_DIM, MAX_PREVIEW_DIM))
            out = io.BytesIO()
            image.save(out, format="PNG")
            return out.getvalue()
    except Exception as error:
        raise AssetError(f"That texture cannot be previewed: {error}") from error


def open_container(raw):
    """Plain bytes and binder members, or (None, {}) for other files."""
    try:
        plain = bytes(inflate(raw))
    except FormatError:
        return None, {}
    try:
        return plain, members(plain)
    except FormatError:
        return plain, {}


def list_textures(file_bytes, filename):
    """The previewable textures in a game file: TPF members, .tpf, .dds."""
    plain, owned = open_container(bytes(file_bytes))
    found = []
    if owned:
        for member, entry in sorted(owned.items()):
            if not member.endswith(".tpf"):
                continue
            for texture in parse_tpf(plain[entry.offset:entry.offset + entry.size]):
                blob = plain[entry.offset + texture["offset"]:entry.offset + texture["offset"] + texture["size"]]
                info = dds_info(blob)
                found.append({"member": member, "index": texture["index"], "name": texture["name"],
                              "width": info["width"], "height": info["height"], "format": info["format"]})
        return found
    payload = plain if plain is not None else bytes(file_bytes)
    lowered = filename.lower()
    if lowered.endswith(".tpf"):
        for texture in parse_tpf(payload):
            info = dds_info(payload[texture["offset"]:texture["offset"] + texture["size"]])
            found.append({"member": "", "index": texture["index"], "name": texture["name"],
                          "width": info["width"], "height": info["height"], "format": info["format"]})
    elif lowered.endswith(".tpfbhd") or lowered.endswith(".tpfbdt"):
        # Split texture archives (BHF3/BDT): their member table is not
        # decoded yet, so they replace only as whole files.
        raise AssetError("Split texture archives cannot be previewed yet; they still replace as whole files")
    elif lowered.endswith(".dds"):
        info = dds_info(payload)
        found.append({"member": "", "index": 0, "name": filename.rsplit("/", 1)[-1],
                      "width": info["width"], "height": info["height"], "format": info["format"]})
    return found


def texture_png(file_bytes, filename, member="", index=0):
    """One texture's PNG preview."""
    plain, owned = open_container(bytes(file_bytes))
    if owned:
        if member not in owned:
            raise AssetError("That binder carries no such texture container")
        entry = owned[member]
        tpf = plain[entry.offset:entry.offset + entry.size]
        textures = parse_tpf(tpf)
        match = next((item for item in textures if item["index"] == index), None)
        if match is None:
            raise AssetError("That texture container has no such texture")
        return render_png(tpf[match["offset"]:match["offset"] + match["size"]])
    payload = plain if plain is not None else bytes(file_bytes)
    lowered = filename.lower()
    if lowered.endswith(".tpf"):
        textures = parse_tpf(payload)
    elif lowered.endswith(".tpfbhd") or lowered.endswith(".tpfbdt"):
        raise AssetError("Split texture archives cannot be previewed yet; they still replace as whole files")
    elif lowered.endswith(".dds"):
        return render_png(payload)
    else:
        raise AssetError("That file carries no previewable textures")
    match = next((item for item in textures if item["index"] == index), None)
    if match is None:
        raise AssetError("That file has no such texture")
    return render_png(payload[match["offset"]:match["offset"] + match["size"]])


def sha_short(data):
    return hashlib.sha256(bytes(data)).hexdigest()[:12]
