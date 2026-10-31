"""Whole-file and binder-member asset overrides, with texture previews.

A mod replaces a game asset by carrying the file at its game-relative path
(movies, sounds, models, textures) or, for binders the loader combines, by
carrying the rebuilt binder with a replaced member. Structured editors own
their files (parameters, item text, .msb maps, .anibnd.dcx animations); every
other file under the game's data roots is an asset and merges whole, or
member-by-member for binders.

Texture previews decode TPF containers (binder members, standalone .tpf,
BDF3 .chrtpfbdt character archives and .dds files) and render each DDS
through Pillow, which already reads every compressed format the game
ships, BC7 included. Split .tpfbhd/.tpfbdt pairs list their member
textures under the header file; the .tpfbdt data half replaces as a
whole file.
"""
import hashlib
import io
import os
import re
import struct
import time
from pathlib import Path

from . import fsb
from .formats import FormatError, MAX_ARCHIVE, inflate, members  # noqa: F401

MOD_ID = "lexeditor-ds1"
# Every top-level game folder an override may land in. param/ holds the
# structured archives; paramdef/ is tooling the game never reads.
ASSET_ROOTS = ("chr", "event", "facegen", "font", "map", "menu", "movww", "msg",
               "mtd", "obj", "other", "parts", "remo", "script", "sfx", "shader", "sound")
# The installed game's biggest asset is a 380 MB movie.
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_ASSET_FILES = 2000
MAX_ASSET_NODES = 32000
MAX_ASSET_TOTAL = 4 * 1024 * 1024 * 1024
MAX_PREVIEW_DIM = 512
MAX_PREVIEW_BYTES = 256 * 1024 * 1024
# One upload piece after base64 decoding; the browser sends sequentially.
MAX_UPLOAD_CHUNK = 1024 * 1024
UPLOAD_PART_PREFIX = ".lexeditor-upload-"
UPLOAD_ID = re.compile(r"[A-Za-z0-9-]{1,64}\Z")

# Inner extensions (past .dcx) that hold geometry, and ones that hold images.
# Cutscene binders carry character meshes, so they list with the models.
MODEL_EXTENSIONS = frozenset({'.flver', '.chrbnd', '.objbnd', '.partsbnd', '.fgbnd',
                              '.remobnd', '.hkx', '.hkxbhd', '.hkxbdt'})
# Geometry extensions mapped to the model kind they carry for the Models
# tab; Havok files hold collision and navigation, never a visible mesh.
MODEL_KINDS = {'.flver': 'piece', '.chrbnd': 'character', '.objbnd': 'object',
               '.partsbnd': 'part', '.fgbnd': 'face', '.remobnd': 'cutscene'}
COLLISION_EXTENSIONS = frozenset({'.hkx', '.hkxbhd', '.hkxbdt'})
TEXTURE_EXTENSIONS = frozenset({'.tpf', '.tpfbhd', '.tpfbdt', '.chrtpfbdt', '.dds', '.png', '.ccm'})
SPLIT_ARCHIVE_EXTENSIONS = frozenset({'.tpfbdt'})
SOUND_EXTENSIONS = frozenset({'.fev', '.fsb', '.itl', '.mix', '.mch', '.rpc'})
BUILD_INPUT_SUFFIXES = frozenset({'.py', '.pyc', '.pyo'})
# FMOD bank name tags that mark music: area themes (m), streamed themes
# (sm) and the mix setup. Every other bank is sound effects.
MUSIC_TAGS = ('_sm', '_m', 'main', 'mixer', 'multi')


def kind_of(relative):
    """models, textures, sound, music or other, by folder and inner extension."""
    lowered = str(relative).replace(chr(92), '/').lower()
    inner = lowered[:-4] if lowered.endswith('.dcx') else lowered
    leaf = inner.rsplit('/', 1)[-1]
    extension = '.' + leaf.rsplit('.', 1)[-1] if '.' in leaf else ''
    if lowered.startswith('sound/'):
        stem = leaf.split('.')[0]
        return 'music' if any(tag in stem for tag in MUSIC_TAGS) else 'sound'
    if extension in MODEL_EXTENSIONS:
        return 'models'
    if extension in TEXTURE_EXTENSIONS:
        return 'textures'
    if extension in SOUND_EXTENSIONS:
        return 'sound'
    return 'other'


def is_split_archive(relative):
    """Split texture data halves (.tpfbdt) replace as whole files; their
    .tpfbhd headers list the pair's member textures."""
    lowered = str(relative).replace(chr(92), '/').lower()
    inner = lowered[:-4] if lowered.endswith('.dcx') else lowered
    leaf = inner.rsplit('/', 1)[-1]
    return '.' in leaf and '.' + leaf.rsplit('.', 1)[-1] in SPLIT_ARCHIVE_EXTENSIONS


DXGI_FORMATS = {70: "BC1", 71: "BC1", 72: "BC1", 73: "BC1", 74: "BC2", 75: "BC2",
                76: "BC2", 77: "BC3", 78: "BC4", 79: "BC4", 80: "BC5", 81: "BC5",
                83: "BC5", 95: "BC6H", 96: "BC6H", 97: "BC7", 98: "BC7",
                99: "BC7", 28: "RGBA8", 87: "BGRA8"}


class AssetError(FormatError):
    """An asset override or preview the editor refuses."""


def _checked(path):
    from .tweak_mods import checked
    return checked(Path(path))


def is_character_file(relative):
    """Character archives and loose state machines handled by the composer."""
    from .tae import CHR_DIR
    return relative.parent == CHR_DIR and relative.name.casefold().endswith((".anibnd.dcx", ".esd.dcx"))


def is_owned(relative):
    """Structured editors own parameters, item and menu text, maps and animations."""
    from .store import RELATIVE
    from . import texts
    from .msb import MAP_DIR
    text = relative.as_posix()
    if relative in (RELATIVE, texts.RELATIVE, texts.MENU_RELATIVE):
        return True
    if text.startswith(MAP_DIR.as_posix() + "/") and relative.suffix == ".msb":
        return True
    return is_character_file(relative)


def check_relative(value):
    """A game-relative override path, contained and within the asset roots."""
    from core.mod_library import relative_path
    try:
        relative = relative_path(str(value))
    except ValueError as error:
        raise AssetError(str(error)) from error
    if relative.parts[0] not in ASSET_ROOTS:
        raise AssetError(f"The {relative.parts[0]} folder holds no replaceable game files")
    if relative.suffix.casefold() == '.exe':
        raise AssetError('Executable files are not mod data; Lexeditor never writes game executables')
    if relative.suffix.casefold() in BUILD_INPUT_SUFFIXES:
        raise AssetError('Python files are build inputs, not Dark Souls game assets')
    if is_owned(relative):
        raise AssetError("That file has its own editor; change it there instead")
    if '.lexeditor-' in relative.name.casefold():
        raise AssetError("That name is reserved for Lexeditor's own bookkeeping")
    return relative


def _project_files(root, strict):
    """Stream a bounded tree; refuse links before entering directories."""
    count = 0
    for top in ASSET_ROOTS:
        stack = [root/top]
        while stack:
            directory = stack.pop()
            try:
                directory = _checked(directory)
                if not directory.is_dir():
                    continue
                with os.scandir(directory) as entries:
                    for entry in entries:
                        count += 1
                        if count > MAX_ASSET_NODES:
                            if strict:
                                raise AssetError(f'The asset tree contains more than {MAX_ASSET_NODES} files or folders')
                            return
                        if entry.name.casefold() == '__pycache__' or '.lexeditor-' in entry.name.casefold():
                            continue
                        try:
                            path = _checked(Path(entry.path))
                            if path.is_dir():
                                stack.append(path)
                            elif path.suffix.casefold() not in BUILD_INPUT_SUFFIXES:
                                yield path
                        except (OSError, ValueError) as error:
                            if strict:
                                raise AssetError(f'{entry.name}: {error}') from error
            except (OSError, ValueError) as error:
                if strict:
                    raise AssetError(f'{directory.name}: {error}') from error


def scan_project(project, strict=True, game_root=None):
    """The mod's asset overrides: game-relative paths with sizes.

    Soft mode stops at the caps instead of raising, for status checks
    that must report on a project rather than refuse it.

    Against the installed game an override reads 'modified' (it replaces a
    game file) or 'new' (nothing sits at its path); without the game its
    status stays unknown. Tweak scripts are code, not overrides.
    """
    from core import script_mods
    from .store import MARKER
    root = _checked(project)
    tweak_mod = script_mods.is_script_mod(root)
    found, total = [], 0
    for path in _project_files(root,strict):
        if path.name == MARKER or path.name == 'mod.json':
            continue
        relative = path.relative_to(root)
        if is_owned(relative) or tweak_mod and script_mods.owns(relative.as_posix()):
            continue
        try:
            relative = check_relative(relative)
        except AssetError:
            if strict:
                raise
            continue
        if len(found) >= MAX_ASSET_FILES:
            if strict:
                raise AssetError(f'A mod carries at most {MAX_ASSET_FILES} asset overrides')
            break
        size = path.stat().st_size
        if size > MAX_ASSET_BYTES:
            if strict:
                raise AssetError(f'{relative.as_posix()} is too large to carry as an override')
            continue
        total += size
        if total > MAX_ASSET_TOTAL:
            if strict:
                raise AssetError('The mod\'s asset overrides are too large in total')
            break
        status = None if game_root is None else 'modified' if (Path(game_root)/relative).is_file() else 'new'
        found.append({'relative':relative.as_posix(),'size':size,'kind':kind_of(relative.as_posix()),
                      'archive':is_split_archive(relative.as_posix()),'status':status})
    return sorted(found,key=lambda row:row['relative'].casefold())


def scan_game(game_root, project=None):
    """Every replaceable installed file: game-relative paths with sizes.

    Game files the mod shadows read 'modified'; without a mod project
    nothing is marked.
    """
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
            if project is None:
                status = None
            else:
                status = 'modified' if (Path(project) / relative).is_file() else None
            found.append({"relative": relative.as_posix(), "size": path.stat().st_size,
                          "kind": kind_of(relative.as_posix()),
                          "archive": is_split_archive(relative.as_posix()),
                          "status": status})
    return found


def scan_merged(game_root, project=None):
    """One list for the asset tabs: game files plus mod-only extras.

    A game file the mod shadows reads 'modified' and wears the mod
    file's size (it is what the game loads); a mod file with no game
    counterpart reads 'new'. Without the installed game only the
    mod's files list, unmarked. Sorted by path, like each scan.
    """
    if game_root is None:
        return scan_project(project, strict=False) if project is not None else []
    merged = {entry["relative"]: entry for entry in scan_game(game_root, project)}
    if project is not None:
        for entry in scan_project(project, strict=False, game_root=game_root):
            if entry["relative"] in merged:
                merged[entry["relative"]] = {**merged[entry["relative"]],
                                            "size": entry["size"], "status": "modified"}
            else:
                merged[entry["relative"]] = entry
    return [merged[key] for key in sorted(merged)]


_SOUNDS_CACHE = {}


def clear_sound_cache():
    """Forget flattened bank streams; uploads and removals change them."""
    _SOUNDS_CACHE.clear()


def list_streams(game_root, project=None):
    """Every FSB bank's streams, split by kind.

    {"sound": [...], "music": [...], "unreadable": [...]}; each stream
    carries its bank path, name, duration in seconds, payload size,
    and whether the mod overrides its bank.
    The table reads headers only, so the whole game scans in about a
    second; the result is cached per game root and mod project. The
    mod's bank wins over the installed one. Banks that fail to parse
    list under "unreadable" instead of breaking the scan.
    """
    key = (str(game_root), str(project))
    cached = _SOUNDS_CACHE.get(key)
    if cached is not None:
        return cached
    found = {"sound": [], "music": [], "unreadable": []}
    for entry in scan_merged(game_root, project):
        if entry["kind"] not in ("sound", "music"):
            continue
        relative = entry["relative"]
        if not relative.lower().endswith(".fsb"):
            continue
        path = None
        overridden = False
        if project is not None:
            own = Path(project) / relative
            if own.is_file():
                path = own
                overridden = True
        if path is None:
            if game_root is None:
                continue
            path = Path(game_root) / relative
        try:
            streams = fsb.parse_table(path)
        except fsb.FsbError:
            found["unreadable"].append(relative)
            continue
        for stream in streams:
            found[entry["kind"]].append({"bank": relative, "name": stream["name"],
                                        "duration": round(stream["duration"], 2),
                                        "size": stream["size"],
                                        "overridden": overridden})
    _SOUNDS_CACHE[key] = found
    return found


def stream_number(name):
    """The TAE sound ID a stream answers to, or None.

    Bank streams carry their event number after a letter tag
    (o7230.wav answers 7230, v713000400.wav answers 713000400);
    names without a bare number (birds.wav, o1201open.wav,
    CURSOL_MOVE.wav) answer nothing.
    """
    match = re.fullmatch(r"[A-Za-z]*(\d+)\.[Ww][Aa][Vv]", str(name or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def find_sound(game_root, project, sound_id):
    """Installed banks holding stream number `sound_id`.

    [{bank, stream, sub, duration, size, overridden}], sound-effect
    banks before music ones. The bank derives by search: a TAE
    Play-sound event stores only the number, and the bank holding
    that stream is where it plays from. Reads the cached stream
    list, so resolving costs no bank scan of its own.
    """
    if isinstance(sound_id, bool):
        return []
    try:
        wanted = int(sound_id)
    except (TypeError, ValueError):
        return []
    streams = list_streams(game_root, project)
    found = []
    for kind, sub in (("sound", "sfx"), ("music", "music")):
        for entry in streams.get(kind, []):
            if stream_number(entry["name"]) == wanted:
                found.append({"bank": entry["bank"], "stream": entry["name"],
                              "sub": sub, "duration": entry["duration"],
                              "size": entry["size"],
                              "overridden": entry["overridden"]})
    return found


def store_bytes(project, relative, data):
    """Carry `data` as the mod's override of a game file."""
    relative = check_relative(relative)
    if len(data) > MAX_ASSET_BYTES:
        raise AssetError("That file is too large to carry as an override")
    target = _checked(Path(project) / relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    from core.plugin_files import atomic_write
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


BDF_MAGIC = b'BDF307D7R6\x00\x00\x00\x00\x00\x00'
BDF_HEADER_SIZE = 16
BDF_ALIGN = 16
BDF_MAX_MEMBERS = 10000


def parse_bdf(data):
    """A .chrtpfbdt character archive's DCX members: (offset, size) slots.

    BDF3 is a 16-byte magic header followed by standard DCX blobs, each
    holding one TPF, packed back to back on 16-byte boundaries with zero
    padding. Sizes include the 76-byte DCX header.
    """
    raw = bytes(data)
    if len(raw) < BDF_HEADER_SIZE or raw[:BDF_HEADER_SIZE] != BDF_MAGIC:
        raise AssetError('That is not a Dark Souls character texture archive')
    slots = []
    at = BDF_HEADER_SIZE
    while True:
        if at >= len(raw):
            break
        end = (at + BDF_ALIGN - 1) // BDF_ALIGN * BDF_ALIGN
        if raw[at:end] != b'\x00' * (end - at):
            raise AssetError('That character texture archive has dirt between members')
        at = end
        if at >= len(raw):
            break
        if len(slots) >= BDF_MAX_MEMBERS:
            raise AssetError('That character texture archive names too many members')
        blob = raw[at:]
        if len(blob) < 76 or blob[:4] != b'DCX\0':
            raise AssetError('That character texture archive holds a non-DCX member')
        _length, compressed = struct.unpack_from('>II', blob, 28)
        size = 76 + compressed
        if not 76 < size <= MAX_ARCHIVE or at + size > len(raw):
            raise AssetError('That character texture archive ends inside a member')
        slots.append((at, size))
        at += size
    if not slots:
        raise AssetError('That character texture archive holds no members')
    return slots


def _bdf_textures(payload):
    """Every texture in a BDF3 character archive, with member slots."""
    found = []
    for slot, (offset, size) in enumerate(parse_bdf(payload)):
        try:
            tpf = bytes(inflate(payload[offset:offset + size]))
        except FormatError as error:
            raise AssetError(f'Character texture member {slot} does not open: {error}') from error
        for texture in parse_tpf(tpf):
            blob = tpf[texture["offset"]:texture["offset"] + texture["size"]]
            info = dds_info(blob)
            found.append({"member": str(slot), "index": texture["index"], "name": texture["name"],
                          "width": info["width"], "height": info["height"], "format": info["format"]})
    return found


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


# Diffuse and lightmap texture types, mirrored from viewport (which
# renders them); assets cannot import viewport.
MODEL_TEXTURE_TYPES = frozenset({'g_diffuse', 'gdiffuse', 'g_lightmap'})


def _material_maps(material):
    """Diffuse and lightmap stems one mesh material names."""
    found = []
    for texture in material.get('textures', []):
        if texture.get('type', '').lower() not in MODEL_TEXTURE_TYPES:
            continue
        path = texture.get('path') or ''
        if not path:
            continue
        stem = path.replace(chr(92), '/').rsplit('/', 1)[-1]
        found.append(stem.rsplit('.', 1)[0] if '.' in stem else stem)
    return found


def open_container(raw):
    """Plain bytes and binder members, or (None, {}) for other files.

    Unwrapped binders open too: the game's FaceGen archive never got
    a DCX wrapper.
    """
    try:
        plain = bytes(inflate(raw))
    except FormatError:
        plain = None
    candidate = plain if plain is not None else bytes(raw)
    try:
        found = members(candidate)
    except FormatError:
        return plain, {}
    owned = found if isinstance(found, dict) else {entry.name: entry for entry in found}
    return candidate, owned


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
    if plain is not None and lowered.endswith(".dcx"):
        # The bytes already came out of the wrapper; read the inner type.
        # Without this the menu icon sheets (menu_1.tpf.dcx and kin) list
        # no textures and their records show no thumbnail or preview.
        lowered = lowered[:-len(".dcx")]
    if lowered.endswith(".tpf"):
        for texture in parse_tpf(payload):
            info = dds_info(payload[texture["offset"]:texture["offset"] + texture["size"]])
            found.append({"member": "", "index": texture["index"], "name": texture["name"],
                          "width": info["width"], "height": info["height"], "format": info["format"]})
    elif lowered.endswith(".chrtpfbdt"):
        found.extend(_bdf_textures(payload))
    elif lowered.endswith(".tpfbhd"):
        # Pair headers list through their data sibling, which bare bytes
        # cannot see; the path reader below resolves it.
        raise AssetError("That split header lists through its data file")
    elif lowered.endswith(".tpfbdt"):
        # The data half of a split pair replaces as a whole file; its
        # textures list under the .tpfbhd header file.
        raise AssetError("Split texture archives replace as whole files")
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
    if plain is not None and lowered.endswith(".dcx"):
        # The bytes already came out of the wrapper; read the inner type.
        # Without this the menu icon sheets (menu_1.tpf.dcx and kin) list
        # no textures and their records show no thumbnail or preview.
        lowered = lowered[:-len(".dcx")]
    if lowered.endswith(".chrtpfbdt"):
        slots = parse_bdf(payload)
        try:
            slot = int(member)
        except (TypeError, ValueError):
            raise AssetError("That character texture archive has no such member") from None
        if not 0 <= slot < len(slots):
            raise AssetError("That character texture archive has no such member")
        offset, size = slots[slot]
        try:
            payload = bytes(inflate(payload[offset:offset + size]))
        except FormatError as error:
            raise AssetError(f"Character texture member {slot} does not open: {error}") from error
        textures = parse_tpf(payload)
    elif lowered.endswith(".tpf"):
        textures = parse_tpf(payload)
    elif lowered.endswith(".tpfbhd"):
        raise AssetError("That split header previews through its data file")
    elif lowered.endswith(".tpfbdt"):
        raise AssetError("Split texture archives replace as whole files")
    elif lowered.endswith(".dds"):
        return render_png(payload)
    else:
        raise AssetError("That file carries no previewable textures")
    match = next((item for item in textures if item["index"] == index), None)
    if match is None:
        raise AssetError("That file has no such texture")
    return render_png(payload[match["offset"]:match["offset"] + match["size"]])


# Texture lists and previews by disk seeks, not full reads: the Textures
# tab expands hundreds of containers on open, and every selection and
# preview strip re-reads its file. Plain .tpf, .dds and BDF3 members
# read only their headers; DCX-wrapped and binder files still inflate
# whole, because their bytes are a stream. Caches key by path, size and
# mtime, so an upload or removal (new bytes, new stamp) never reads
# stale. List hits return copies: the model strip appends companion
# tiles to the list it gets, which must not pollute the cache.
_TEXTURE_LIST_CACHE = {}
_TEXTURE_LIST_CACHE_SIZE = 256
_TEXTURE_PNG_CACHE = {}
_TEXTURE_PNG_CACHE_SIZE = 64


def _cache_store(cache, cap, key, value):
    # Lock-free reads share these caches across request threads: concurrent
    # computes of one key are benign (last write wins), and a lost eviction
    # race just retries instead of raising.
    cache.pop(key, None)
    while len(cache) >= cap:
        try:
            cache.pop(next(iter(cache)))
        except (KeyError, StopIteration):
            break
    cache[key] = value
    return value


def _read_at(handle, offset, size, total, what):
    if not 0 <= offset <= total - size:
        raise AssetError(f"That texture container ends inside its {what}")
    handle.seek(offset)
    blob = handle.read(size)
    if len(blob) != size:
        raise AssetError(f"That texture container ends inside its {what}")
    return blob


def _tpf_entries_from_file(handle, total):
    """A plain .tpf file's table via seeks: parse_tpf without the read."""
    head = _read_at(handle, 0, 16, total, "header")
    if head[:4] != b"TPF\x00":
        raise AssetError("That is not a Dark Souls texture container")
    count = struct.unpack_from("<I", head, 8)[0]
    if count > 10000:
        raise AssetError("That texture container names too many textures")
    table = _read_at(handle, 16, count * 20, total, "table") if count else b""
    entries = []
    for index in range(count):
        offset, size, _unknown, name_off, _other = struct.unpack_from("<5I", table, index * 20)
        if offset + size > total:
            raise AssetError("That texture container points outside its pixels")
        if not 0 <= name_off < total:
            raise AssetError("That texture container has a nameless texture")
        raw_name = _read_at(handle, name_off, min(128, total - name_off), total, "names")
        end = raw_name.find(b"\x00")
        if end <= 0:
            raise AssetError("That texture container has a nameless texture")
        entries.append({"index": index, "name": raw_name[:end].decode("shift_jis", "replace"),
                        "offset": offset, "size": size})
    return entries


def _bdf_slots_from_file(handle, total):
    """BDF3 DCX slots via header seeks: parse_bdf without the read."""
    if _read_at(handle, 0, BDF_HEADER_SIZE, total, "header") != BDF_MAGIC:
        raise AssetError("That is not a Dark Souls character texture archive")
    slots, at = [], BDF_HEADER_SIZE
    while True:
        if at >= total:
            break
        end = (at + BDF_ALIGN - 1) // BDF_ALIGN * BDF_ALIGN
        if _read_at(handle, at, end - at, total, "padding") != b"\x00" * (end - at):
            raise AssetError("That character texture archive has dirt between members")
        at = end
        if at >= total:
            break
        if len(slots) >= BDF_MAX_MEMBERS:
            raise AssetError("That character texture archive names too many members")
        head = _read_at(handle, at, 76, total, "member")
        if head[:4] != b"DCX\0":
            raise AssetError("That character texture archive holds a non-DCX member")
        _length, compressed = struct.unpack_from(">II", head, 28)
        size = 76 + compressed
        if not 76 < size <= MAX_ARCHIVE or at + size > total:
            raise AssetError("That character texture archive ends inside a member")
        slots.append((at, size))
        at += size
    if not slots:
        raise AssetError("That character texture archive holds no members")
    return slots


def _bdf_textures_from_file(handle, total):
    """Every texture in a BDF3 file, inflating one member at a time."""
    found = []
    for slot, (offset, size) in enumerate(_bdf_slots_from_file(handle, total)):
        handle.seek(offset)
        blob = handle.read(size)
        if len(blob) != size:
            raise AssetError("That character texture archive ends inside a member")
        try:
            tpf = bytes(inflate(blob))
        except FormatError as error:
            raise AssetError(f"Character texture member {slot} does not open: {error}") from error
        for texture in parse_tpf(tpf):
            info = dds_info(tpf[texture["offset"]:texture["offset"] + texture["size"]])
            found.append({"member": str(slot), "index": texture["index"], "name": texture["name"],
                          "width": info["width"], "height": info["height"], "format": info["format"]})
    return found


def _texture_file_key(path):
    try:
        stat = Path(path).stat()
    except OSError as error:
        raise AssetError(f"Cannot read {Path(path).name}") from error
    return (str(path), stat.st_size, stat.st_mtime_ns)


def _pair_data_path(path):
    """A .tpfbhd header path's .tpfbdt data sibling, wrapped or plain."""
    plain = str(path)[:-len(".dcx")] if str(path).lower().endswith(".dcx") else str(path)
    sibling = str(Path(plain).with_suffix(".tpfbdt"))
    if str(path).lower().endswith(".dcx"):
        sibling += ".dcx"
    return Path(sibling)


def _pair_textures(header_bytes, data_path):
    """Every texture in a split pair: header slots seek-read from data."""
    from . import bhf
    try:
        table = bhf.parse_bhf(header_bytes)
    except FormatError as error:
        raise AssetError(str(error)) from error
    found = []
    for stem in sorted(table):
        offset, size = table[stem]
        try:
            tpf = bytes(bhf.inflate_member(data_path, offset, size))
        except FormatError as error:
            raise AssetError(str(error)) from error
        for texture in parse_tpf(tpf):
            info = dds_info(tpf[texture["offset"]:texture["offset"] + texture["size"]])
            found.append({"member": stem, "index": texture["index"], "name": texture["name"],
                          "width": info["width"], "height": info["height"], "format": info["format"]})
    return found


def list_textures_from_path(path, filename):
    """list_textures by disk seeks for plain containers; cached by stamp."""
    lowered = str(filename).lower()
    inner = lowered[:-4] if lowered.endswith(".dcx") else lowered
    key = _texture_file_key(path)
    if inner.endswith(".tpfbhd"):
        # The list also depends on the data sibling's bytes: a replaced
        # data half must invalidate the header's cached list.
        key = key + _texture_file_key(_pair_data_path(path))[1:]
    total = key[1]
    hit = _TEXTURE_LIST_CACHE.get(key)
    if hit is not None:
        return [dict(entry) for entry in hit]
    found = None
    if inner.endswith(".tpfbhd") and not lowered.endswith(".dcx"):
        if total > 8 * 1024 * 1024:
            raise AssetError("That split header is too large to list")
        with open(path, "rb") as handle:
            found = _pair_textures(handle.read(), _pair_data_path(path))
    if found is None and not lowered.endswith(".dcx"):
        with open(path, "rb") as handle:
            magic = handle.read(BDF_HEADER_SIZE)
            if inner.endswith(".tpf") and magic[:4] == b"TPF\x00":
                found = []
                for entry in _tpf_entries_from_file(handle, total):
                    head = _read_at(handle, entry["offset"], min(entry["size"], 132), total, "pixels")
                    info = dds_info(head)
                    found.append({"member": "", "index": entry["index"], "name": entry["name"],
                                  "width": info["width"], "height": info["height"], "format": info["format"]})
            elif inner.endswith(".chrtpfbdt") and magic == BDF_MAGIC:
                found = _bdf_textures_from_file(handle, total)
            elif inner.endswith(".dds") and magic[:4] == b"DDS ":
                info = dds_info(_read_at(handle, 0, min(132, total), total, "pixels"))
                found = [{"member": "", "index": 0, "name": str(filename).rsplit("/", 1)[-1],
                          "width": info["width"], "height": info["height"], "format": info["format"]}]
    if found is None:
        with open(path, "rb") as handle:
            found = list_textures(handle.read(), filename)
    _cache_store(_TEXTURE_LIST_CACHE, _TEXTURE_LIST_CACHE_SIZE, key, [dict(entry) for entry in found])
    return [dict(entry) for entry in found]


def texture_png_from_path(path, filename, member="", index=0):
    """texture_png by disk seeks for plain containers; cached by stamp."""
    lowered = str(filename).lower()
    inner = lowered[:-4] if lowered.endswith(".dcx") else lowered
    key = _texture_file_key(path)
    if inner.endswith(".tpfbhd"):
        key = key + _texture_file_key(_pair_data_path(path))[1:]
    key = key + (member, index)
    hit = _TEXTURE_PNG_CACHE.get(key)
    if hit is not None:
        return hit
    total = _texture_file_key(path)[1]
    png = None
    if inner.endswith(".tpfbhd") and not lowered.endswith(".dcx"):
        from . import bhf
        if total > 8 * 1024 * 1024:
            raise AssetError("That split header is too large to preview")
        try:
            with open(path, "rb") as handle:
                table = bhf.parse_bhf(handle.read())
        except FormatError as error:
            raise AssetError(str(error)) from error
        slot = table.get((member or "").lower())
        if slot is None:
            raise AssetError("That split archive has no such member")
        try:
            tpf = bytes(bhf.inflate_member(_pair_data_path(path), slot[0], slot[1]))
        except FormatError as error:
            raise AssetError(str(error)) from error
        match = next((item for item in parse_tpf(tpf) if item["index"] == index), None)
        if match is None:
            raise AssetError("That file has no such texture")
        png = render_png(tpf[match["offset"]:match["offset"] + match["size"]])
    if not lowered.endswith(".dcx"):
        with open(path, "rb") as handle:
            magic = handle.read(BDF_HEADER_SIZE)
            if inner.endswith(".tpf") and magic[:4] == b"TPF\x00":
                match = next((entry for entry in _tpf_entries_from_file(handle, total)
                              if entry["index"] == index), None)
                if match is None:
                    raise AssetError("That file has no such texture")
                png = render_png(_read_at(handle, match["offset"], match["size"], total, "pixels"))
            elif inner.endswith(".chrtpfbdt") and magic == BDF_MAGIC:
                slots = _bdf_slots_from_file(handle, total)
                try:
                    slot = int(member)
                except (TypeError, ValueError):
                    raise AssetError("That character texture archive has no such member") from None
                if not 0 <= slot < len(slots):
                    raise AssetError("That character texture archive has no such member")
                offset, size = slots[slot]
                handle.seek(offset)
                blob = handle.read(size)
                if len(blob) != size:
                    raise AssetError("That character texture archive ends inside a member")
                try:
                    tpf = bytes(inflate(blob))
                except FormatError as error:
                    raise AssetError(f"Character texture member {slot} does not open: {error}") from error
                match = next((item for item in parse_tpf(tpf) if item["index"] == index), None)
                if match is None:
                    raise AssetError("That file has no such texture")
                png = render_png(tpf[match["offset"]:match["offset"] + match["size"]])
    if png is None:
        with open(path, "rb") as handle:
            png = texture_png(handle.read(), filename, member, index)
    return _cache_store(_TEXTURE_PNG_CACHE, _TEXTURE_PNG_CACHE_SIZE, key, png)


# Model inventories by content hash: selecting two copies of one file, or
# coming back to it, must not re-decode its meshes. Digests key it, so the
# bytes themselves are never retained.
_MODEL_INFO_CACHE = {}
_MODEL_INFO_CACHE_SIZE = 32


def _inner_extension(filename):
    lowered = str(filename).replace(chr(92), '/').lower()
    inner = lowered[:-4] if lowered.endswith('.dcx') else lowered
    leaf = inner.rsplit('/', 1)[-1]
    return '.' + leaf.rsplit('.', 1)[-1] if '.' in leaf else ''


def _default_flver(stem, names):
    wanted = stem + '.flver'
    if wanted in names:
        return wanted
    ordered = sorted(names)
    return ordered[0] if ordered else ''


def model_info(data, filename):
    """A model file's inventory for the Models tab: kind, mesh members,
    mesh and bone counts. Object binders count their member objects;
    character models count bones; collision files carry neither and say
    so. Best-effort throughout: an unreadable member is skipped, and a
    file with no readable mesh reports why instead of raising."""
    from .flver import FlverDocument
    digest = (sha_short(data), str(filename).lower())
    hit = _MODEL_INFO_CACHE.get(digest)
    if hit is not None:
        return dict(hit, members=list(hit['members']), maps=list(hit['maps']))
    extension = _inner_extension(filename)
    if extension in COLLISION_EXTENSIONS:
        info = {'kind': 'collision', 'previewable': False, 'members': [], 'member': '',
                'objects': None, 'meshes': 0, 'bones': 0, 'reason': 'collision',
                'maps': []}
    else:
        plain, owned = open_container(bytes(data))
        if owned:
            blobs = sorted(name for name in owned if name.lower().endswith('.flver'))
            leaf = str(filename).replace(chr(92), '/').rsplit('/', 1)[-1]
            inner = leaf[:-4] if leaf.lower().endswith('.dcx') else leaf
            meshes = bones = 0
            broken = set()
            docs = {}
            for name in blobs:
                entry = owned[name]
                try:
                    doc = FlverDocument(plain[entry.offset:entry.offset + entry.size])
                except Exception:
                    # Counts must never break a selection: a corrupt member
                    # is skipped, and only the preview member's failure
                    # marks the file unreadable.
                    broken.add(name)
                    continue
                docs[name] = doc
                meshes += len(doc.meshes)
                bones += len(doc.bones)
            with_mesh = [name for name in blobs if name in docs and any(
                len(mesh['positions']) for mesh in docs[name].meshes)]
            if not blobs:
                reason = 'no-mesh'
                default = ''
            elif with_mesh:
                # The preview member holds visible geometry: the stem
                # match when it has meshes, else the first that does.
                # A skeleton-only default used to preview an empty stage.
                default = _default_flver(inner.rsplit('.', 1)[0], with_mesh)
                reason = None
            elif len(broken) == len(blobs):
                reason = 'unreadable'
                default = ''
            else:
                reason = 'no-mesh'
                default = ''
            maps = sorted({stem for mesh in docs[default].meshes
                           for stem in _material_maps(mesh['material'])}
                          ) if reason is None else []
            info = {'kind': MODEL_KINDS.get(extension, 'model'),
                    'previewable': reason is None,
                    'members': blobs, 'member': default if reason is None else '',
                    'objects': len(blobs) if extension == '.objbnd' else None,
                    'meshes': meshes, 'bones': bones, 'reason': reason,
                    'maps': maps}
        else:
            payload = plain if plain is not None else bytes(data)
            if extension == '.flver':
                try:
                    doc = FlverDocument(payload)
                except Exception:
                    doc = None
                if doc is None:
                    info = {'kind': 'piece', 'previewable': False, 'members': [],
                            'member': '', 'objects': None, 'meshes': 0, 'bones': 0,
                            'reason': 'unreadable', 'maps': []}
                elif not any(len(mesh['positions']) for mesh in doc.meshes):
                    info = {'kind': 'piece', 'previewable': False, 'members': [],
                            'member': '', 'objects': None, 'meshes': 0,
                            'bones': len(doc.bones), 'reason': 'no-mesh', 'maps': []}
                else:
                    info = {'kind': 'piece', 'previewable': True, 'members': [],
                            'member': '', 'objects': None,
                            'meshes': len(doc.meshes), 'bones': len(doc.bones),
                            'reason': None,
                            'maps': sorted({stem for mesh in doc.meshes
                                            for stem in _material_maps(mesh['material'])})}
            else:
                info = {'kind': MODEL_KINDS.get(extension, 'model'),
                        'previewable': False, 'members': [], 'member': '',
                        'objects': None, 'meshes': 0, 'bones': 0,
                        'reason': 'unreadable', 'maps': []}
    _MODEL_INFO_CACHE[digest] = dict(info, members=list(info['members']),
                                          maps=list(info['maps']))
    while len(_MODEL_INFO_CACHE) > _MODEL_INFO_CACHE_SIZE:
        _MODEL_INFO_CACHE.pop(next(iter(_MODEL_INFO_CACHE)))
    return info


def sha_short(data):
    return hashlib.sha256(bytes(data)).hexdigest()[:12]
