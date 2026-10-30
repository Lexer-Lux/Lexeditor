"""Prebuilt, relocatable native mods; builders and game runtime share one layout.

LXD1MOD wraps an ordinary LXD1PAT with its link fixups and state claims.
The payload contains ready-to-run machine code, never Python or assembly.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import zlib

from . import exe_patches as patches

MAGIC = b'LXD1MOD\0'
VERSION = 1
FILENAME = 'runtime.lxd'
MAX_SIZE = 16 * 1024 * 1024
MAX_FIXUPS = 65536
HEADER = struct.Struct('<8s6I')
# signed displacement += delta, signed displacement -= delta, RVA += delta
REL_PLUS, REL_MINUS, RVA_PLUS = 1, 2, 3


def read(folder: Path) -> bytes:
    with (Path(folder)/FILENAME).open('rb') as stream:
        data = stream.read(MAX_SIZE + 1)
    inspect(data)
    return data


def build(vanilla: bytes, specs: list[dict], *, requires_data=False) -> bytes | None:
    layout = patches._layout(vanilla, specs)
    if layout is None:
        return None
    patch = patches._runtime_patch(vanilla, layout)
    offsets, at = {}, 24
    for kind, rva, length, payload in patches.read_runtime_patch(patch)['records']:
        offsets[(kind, rva)] = (at, at + 12, length)
        at += 12 + len(payload)
    fixups = []
    if layout['codes']:
        block = layout['codes'][0][0]
        record_at, payload_at, _ = offsets[(patches.BLOCK, block)]
        fixups.append((record_at + 4, RVA_PLUS))
        for rva, island in layout['placed']:
            for offset, _target in island['relocations']:
                fixups.append((payload_at + rva - block + offset, REL_MINUS))
    if layout['functions']:
        _, payload_at, count = offsets[(patches.FUNCTIONS, 0)]
        fixups.extend((payload_at + i * 4, RVA_PLUS) for i in range(count * 3))
    for spec in specs:
        for hook in spec['hooks']:
            _, payload_at, length = offsets[(patches.HOOK, hook['rva'])]
            if hook['replacement'][0] == 'branch':
                fixups.append((payload_at + length + 1, REL_PLUS))
            fixups.extend((payload_at + length + offset, REL_PLUS)
                          for offset, _name, _target in hook['relocations'])
    claims = [claim for spec in specs for claim in spec['state']]
    for spec in specs:
        if not spec['state']:
            for name, size in spec['sectionVirtualSize'].items():
                section = next(section for section in layout['pe'].sections if section['name'] == name)
                if size > section['vsize']:
                    claims.append((section['rva'] + section['vsize'], size - section['vsize']))
    fixed = int(any(island['rva'] is not None for _rva, island in layout['placed']))
    data = (HEADER.pack(MAGIC, VERSION, len(patch), len(fixups), len(claims), fixed, int(requires_data)) + patch
            + b''.join(struct.pack('<2I', *item) for item in fixups + claims))
    data += struct.pack('<I', zlib.crc32(data))
    inspect(data)
    return data


def inspect(data: bytes) -> dict:
    if len(data) < HEADER.size + 4 or len(data) > MAX_SIZE:
        raise patches.PatchError('The prebuilt mod has an invalid size')
    magic, version, size, count, claimed, fixed, reserved = HEADER.unpack_from(data)
    if (magic != MAGIC or version != VERSION or fixed not in (0, 1) or reserved not in (0, 1)
            or count > MAX_FIXUPS or claimed > 4096
            or HEADER.size + size + (count + claimed) * 8 + 4 != len(data)
            or zlib.crc32(data[:-4]) != struct.unpack_from('<I', data, len(data)-4)[0]):
        raise patches.PatchError('The prebuilt mod is damaged or unsupported')
    patch = data[HEADER.size:HEADER.size+size]
    if len(patch) < 24 or struct.unpack_from('<I',patch,20)[0] > 4096:
        raise patches.PatchError('The prebuilt mod has too many patch records')
    try:
        decoded = patches.read_runtime_patch(patch)
    except (struct.error, ValueError) as error:
        raise patches.PatchError('The prebuilt mod contains a damaged patch') from error
    at = HEADER.size + size
    fixups = [struct.unpack_from('<2I', data, at + i * 8) for i in range(count)]
    claims = [struct.unpack_from('<2I', data, at + (count+i) * 8) for i in range(claimed)]
    occupied = set()
    for offset, kind in fixups:
        if kind not in (REL_PLUS, REL_MINUS, RVA_PLUS) or offset + 4 > size:
            raise patches.PatchError('The prebuilt mod has an invalid relocation')
        span = set(range(offset, offset+4))
        if span & occupied:
            raise patches.PatchError('The prebuilt mod repeats a relocation')
        occupied.update(span)
    if any(not size or rva + size > decoded['imageSize'] for rva, size in claims):
        raise patches.PatchError('The prebuilt mod has invalid state claims')
    return {**decoded, 'patch': patch, 'fixups': fixups, 'claims': claims, 'fixed': bool(fixed),
            'requiresData': bool(reserved)}


def link(data: bytes, base: int) -> bytes:
    """Reference implementation of the runtime link step, used by checks."""
    module = inspect(data)
    blocks = [rva for kind, rva, _size, _payload in module['records'] if kind == patches.BLOCK]
    delta = base - blocks[0] if blocks else 0
    if module['fixed'] and delta:
        raise patches.PatchError('This mod requires its fixed code address')
    result = bytearray(module['patch'])
    for offset, kind in module['fixups']:
        dtype = '<I' if kind == RVA_PLUS else '<i'
        value = struct.unpack_from(dtype, result, offset)[0] + (-delta if kind == REL_MINUS else delta)
        try:
            struct.pack_into(dtype, result, offset, value)
        except struct.error as error:
            raise patches.PatchError('The prebuilt mod cannot link at this address') from error
    return bytes(result)


def write_release(folder: Path, destination: Path, vanilla: bytes) -> Path:
    """Export built contributions without developer files or local paths."""
    from core import mod_metadata, mod_requires
    from core.mod_library import relative_path
    from . import assets, menu_dim, mod_loader, tweak_mods
    folder, destination = Path(folder), Path(destination)
    tweak_mods.checked(folder)
    metadata = json.loads((folder/'mod.json').read_text(encoding='utf-8'))
    mod_id = str(metadata.get('id') or folder.name)
    if len(relative_path(mod_id).parts) != 1:
        raise ValueError('The mod needs a valid ID')
    if mod_id.casefold() in set(assets.ASSET_ROOTS) | {'param','paramdef','mods'}:
        raise ValueError('The mod ID must not use a reserved game folder name')
    source = tweak_mods.checked(folder/'native'/f'{mod_id}.json')
    spec = patches.validate(json.loads(source.read_text(encoding='utf-8')), metadata.get('name') or mod_id) if source.is_file() else None
    contributions = list(mod_loader.content_files(folder,metadata.get('name') or mod_id))
    for kind in ('layout','esd',menu_dim.FOLDER):
        path = tweak_mods.checked(folder/kind/f'{mod_id}.json')
        if path.is_file():
            contributions.append((path.relative_to(folder),path))
    payload = build(vanilla, [spec], requires_data=bool(contributions)) if spec else None
    if payload is None:
        if not contributions:
            raise ValueError('This mod has no built contributions to export')
        pe = patches._checked_pe(vanilla,patches.VANILLA_SIZE,patches.VANILLA_SHA256)
        patch = patches.RUNTIME_MAGIC+struct.pack('<4I',1,struct.unpack_from('<I',vanilla,pe.size_of_image)[0],
                                                struct.unpack_from('<I',vanilla,pe.nt+8)[0],0)
        payload = HEADER.pack(MAGIC,VERSION,len(patch),0,0,0,1)+patch
        payload += struct.pack('<I',zlib.crc32(payload))
    target = destination/mod_id
    target.mkdir(parents=True, exist_ok=False)
    try:
        public = {key: metadata[key] for key in (*mod_metadata.FIELDS, 'id', 'version', 'requires') if key in metadata}
        public.update(id=mod_id, name=metadata.get('name') or mod_id, enabled=True, order=metadata.get('order', 1000),
                      requires=mod_requires.needs(folder))
        encoded = (json.dumps(public, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
        if len(encoded) > 65536:
            raise ValueError('The release metadata exceeds the loader size limit')
        (target/'mod.json').write_bytes(encoded)
        (target/FILENAME).write_bytes(payload)
        for relative, source in contributions:
            relative = relative_path(relative.as_posix())
            output = target/relative
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(source.read_bytes())
    except Exception:
        import shutil
        if target.resolve().parent != destination.resolve():
            raise ValueError('The release folder is outside its destination')
        shutil.rmtree(target)
        raise
    return target
