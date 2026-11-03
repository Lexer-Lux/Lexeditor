"""Bounded DS1 little-endian EMEVD records and conservative event composition.

Layout facts checked against SoulsFormats EMEVD/{EMEVD,Event,Instruction,
Parameter,Layer}.cs (GPL-3.0); original implementation, see credits.md.
Instruction arguments and string data remain opaque bytes. Constructor
merging only combines appended RunEvent calls, never guesses control flow.
"""
from dataclasses import dataclass, replace
import struct
from pathlib import Path

from .formats import FormatError

MAX_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 1_000_000
HEADER = 84


def is_event_file(relative):
    relative = Path(relative)
    return (bool(relative.parts) and relative.parts[0].casefold() == 'event' and
            relative.name.lower().removesuffix('.dcx').endswith('.emevd'))


@dataclass(frozen=True)
class Instruction:
    bank: int
    index: int
    args: bytes = b''
    layer: int | None = None


@dataclass(frozen=True)
class Parameter:
    instruction: int
    target: int
    source: int
    size: int


@dataclass(frozen=True)
class Event:
    id: int
    instructions: tuple[Instruction, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    rest: int = 0


@dataclass(frozen=True)
class Document:
    events: tuple[Event, ...]
    linked: tuple[int, ...] = ()
    strings: bytes = b''


def _table(data, count, offset, stride):
    if not 0 <= count <= (MAX_BYTES if stride == 1 else MAX_RECORDS) or not HEADER <= offset <= len(data) or offset + count * stride > len(data):
        raise FormatError('EMEVD table is outside the file')
    return offset + count * stride


def _valid_event(event):
    if type(event.id) is not int or not 0 <= event.id < 1 << 31 or event.rest not in (0, 1, 2):
        raise FormatError('Unsupported EMEVD event identity or rest behavior')
    for instruction in event.instructions:
        if (type(instruction.bank) is not int or not 0 <= instruction.bank < 1 << 31 or
                type(instruction.index) is not int or not 0 <= instruction.index < 1 << 31 or
                not isinstance(instruction.args, bytes) or len(instruction.args) > MAX_BYTES or
                (instruction.layer is not None and
                 (type(instruction.layer) is not int or not 0 <= instruction.layer < 1 << 32))):
            raise FormatError('Invalid EMEVD instruction')
    for parameter in event.parameters:
        if (any(type(value) is not int or value < 0 for value in
                (parameter.instruction, parameter.target, parameter.source, parameter.size)) or
                parameter.instruction >= len(event.instructions) or parameter.size == 0 or
                parameter.target + parameter.size > len(event.instructions[parameter.instruction].args) or
                parameter.source + parameter.size > MAX_BYTES):
            raise FormatError('Invalid EMEVD argument substitution')


def read(data):
    if (not HEADER <= len(data) <= MAX_BYTES or data[:8] != b'EVD\0\0\0\0\0' or
            struct.unpack_from('<II', data, 8) != (0xCC, len(data))):
        raise FormatError('Unsupported or damaged DS1 EMEVD header')
    ec, eo, ic, io, unknown, uo, lc, lo, pc, po, fc, fo, ac, ao, sc, so, reserved = struct.unpack_from('<17i', data, 16)
    if unknown or reserved:
        raise FormatError('Unsupported EMEVD header metadata')
    ends = [_table(data, count, offset, stride) for count, offset, stride in
            ((ec, eo, 28), (ic, io, 24), (0, uo, 1), (lc, lo, 20),
             (pc, po, 20), (fc, fo, 4), (ac, ao, 1), (sc, so, 1))]
    ranges = sorted((offset, end) for offset, end in zip((eo, io, uo, lo, po, fo, ao, so), ends) if offset != end)
    if any(first[1] > second[0] for first, second in zip(ranges, ranges[1:])):
        raise FormatError('Overlapping EMEVD tables')
    layers = []
    for at in range(lo, lo + lc * 20, 20):
        kind, mask, zero, minus, one = struct.unpack_from('<iIiii', data, at)
        if (kind, zero, minus, one) != (2, 0, -1, 1):
            raise FormatError('Unsupported EMEVD instruction layer')
        layers.append(mask)
    instructions = []
    for at in range(io, io + ic * 24, 24):
        bank, index, length, offset, layer, zero = struct.unpack_from('<6i', data, at)
        if (zero or not 0 <= length <= ac or
                (length and not 0 <= offset <= ac - length) or
                (layer != -1 and (layer < 0 or layer % 20 or layer // 20 >= lc))):
            raise FormatError('Invalid EMEVD instruction argument or layer offset')
        args = bytes(data[ao + offset:ao + offset + length]) if length else b''
        instructions.append(Instruction(bank, index, args, None if layer == -1 else layers[layer // 20]))
    parameters = []
    for at in range(po, po + pc * 20, 20):
        instruction, target, source, size, zero = struct.unpack_from('<5i', data, at)
        if zero:
            raise FormatError('Unsupported EMEVD parameter metadata')
        parameters.append(Parameter(instruction, target, source, size))
    events, ids, used_i, used_p = [], set(), set(), set()
    for at in range(eo, eo + ec * 28, 28):
        identity, ni, oi, np, op, rest, zero = struct.unpack_from('<7i', data, at)
        if zero or identity in ids or ni < 0 or np < 0:
            raise FormatError('Invalid or duplicate EMEVD event')
        slices = []
        for count, offset, stride, rows, used in ((ni, oi, 24, instructions, used_i), (np, op, 20, parameters, used_p)):
            if count and (offset < 0 or offset % stride or offset // stride + count > len(rows)):
                raise FormatError('EMEVD event points outside its records')
            indexes = range(offset // stride, offset // stride + count) if count else range(0)
            if any(index in used for index in indexes):
                raise FormatError('EMEVD events share record spans')
            used.update(indexes)
            slices.append(tuple(rows[index] for index in indexes))
        event = Event(identity, slices[0], slices[1], rest)
        _valid_event(event)
        events.append(event)
        ids.add(identity)
    if len(used_i) != ic or len(used_p) != pc:
        raise FormatError('EMEVD contains unowned instruction or parameter records')
    linked = struct.unpack_from(f'<{fc}i', data, fo)
    if any(not 0 <= offset < sc for offset in linked):
        raise FormatError('EMEVD linked file points outside string data')
    return Document(tuple(events), tuple(linked), bytes(data[so:so + sc]))


def write(document):
    """Serialize records without decoding or changing instruction argument bytes."""
    events = document.events
    if len(events) > MAX_RECORDS or len({event.id for event in events}) != len(events):
        raise FormatError('Too many or duplicate EMEVD events')
    for event in events:
        _valid_event(event)
    instructions = [instruction for event in events for instruction in event.instructions]
    parameters = [parameter for event in events for parameter in event.parameters]
    layers = list(dict.fromkeys(instruction.layer for instruction in instructions if instruction.layer is not None))
    if (len(instructions) > MAX_RECORDS or len(parameters) > MAX_RECORDS or
            len(document.linked) > MAX_RECORDS or not isinstance(document.strings, bytes) or
            any(type(offset) is not int or not 0 <= offset < len(document.strings) for offset in document.linked)):
        raise FormatError('Invalid EMEVD record count or linked strings')
    estimate = (HEADER + len(events) * 28 + len(instructions) * 24 + len(layers) * 20 +
                sum(len(instruction.args) + 3 for instruction in instructions) + 15 +
                len(parameters) * 20 + len(document.linked) * 4 + len(document.strings))
    if estimate > MAX_BYTES:
        raise FormatError('Combined EMEVD exceeds its size limit')
    eo = HEADER
    io = eo + len(events) * 28
    lo = io + len(instructions) * 24
    ao = lo + len(layers) * 20
    result = bytearray(ao)
    result[:8] = b'EVD\0\0\0\0\0'
    i, p = 0, 0
    for index, event in enumerate(events):
        struct.pack_into('<7i', result, eo + index * 28, event.id, len(event.instructions),
                         i * 24 if event.instructions else -1, len(event.parameters),
                         p * 20 if event.parameters else -1, event.rest, 0)
        i += len(event.instructions)
        p += len(event.parameters)
    for index, layer in enumerate(layers):
        struct.pack_into('<iIiii', result, lo + index * 20, 2, layer, 0, -1, 1)
    layer_offsets = {layer: index * 20 for index, layer in enumerate(layers)}
    for index, instruction in enumerate(instructions):
        struct.pack_into('<6i', result, io + index * 24, instruction.bank, instruction.index,
                         len(instruction.args), len(result) - ao if instruction.args else -1,
                         layer_offsets.get(instruction.layer, -1), 0)
        result.extend(instruction.args)
        result.extend(b'\0' * (-(len(result) - ao) % 4))
    result.extend(b'\0' * (-(len(result) - ao) % 16))
    po = len(result)
    for parameter in parameters:
        result.extend(struct.pack('<5i', parameter.instruction, parameter.target, parameter.source, parameter.size, 0))
    fo = len(result)
    for offset in document.linked:
        result.extend(struct.pack('<i', offset))
    so = len(result)
    result.extend(document.strings)
    struct.pack_into('<II', result, 8, 0xCC, len(result))
    struct.pack_into('<17i', result, 16, len(events), eo, len(instructions), io, 0, lo,
                     len(layers), lo, len(parameters), po, len(document.linked), fo,
                     po - ao, ao, len(document.strings), so, 0)
    return bytes(result)


def _constructor(base, variants):
    """Append-only RunEvent calls can compose without relocating control flow."""
    if base.id not in (0, 50):
        return None
    calls, owners, conflicts = {}, {}, {}
    for owner, event in variants:
        if (event is None or event.rest != base.rest or event.parameters != base.parameters or
                event.instructions[:len(base.instructions)] != base.instructions):
            return None
        for instruction in event.instructions[len(base.instructions):]:
            if instruction.bank != 2000 or instruction.index != 0 or len(instruction.args) < 8:
                return None
            slot, identity = struct.unpack_from('<II', instruction.args)
            key = (slot, identity)
            if key in calls and calls[key] != instruction:
                conflict = conflicts.setdefault(f'event {base.id} / RunEvent {identity} slot {slot}', [])
                conflict.extend(name for name in (owners[key], owner) if name not in conflict)
            calls[key], owners[key] = instruction, owner
    return replace(base, instructions=base.instructions + tuple(calls.values())), conflicts


def merge(original, variants, *, conflicts_only=False):
    base = {event.id: event for event in original.events}
    versions = []
    for owner, document in variants:
        if (document.linked, document.strings) != (original.linked, original.strings):
            raise FormatError(f'{owner}: EMEVD string data or linked files changed; cannot relocate opaque arguments')
        versions.append((owner, {event.id: event for event in document.events}))
    result, conflicts = dict(base), {}
    for identity in sorted(base.keys() | {key for _, events in versions for key in events}):
        changes = [(owner, events.get(identity)) for owner, events in versions if events.get(identity) != base.get(identity)]
        if not changes:
            continue
        combined = _constructor(base[identity], changes) if identity in base else None
        if combined is not None:
            result[identity], found = combined
            conflicts.update(found)
            continue
        winner = changes[-1][1]
        if any(event != winner for _, event in changes):
            conflicts[f'event {identity}'] = list(dict.fromkeys(owner for owner, _ in changes))
        if winner is None:
            result.pop(identity, None)
        else:
            result[identity] = winner
    ordered = [result[event.id] for event in original.events if event.id in result]
    ordered.extend(result[identity] for identity in sorted(result.keys() - base.keys()))
    return (original if conflicts_only else replace(original, events=tuple(ordered))), conflicts
