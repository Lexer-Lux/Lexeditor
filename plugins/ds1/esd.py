"""Dark Souls Remastered ESD (EzState state machine) reader and writer.

An ESD file holds one or more state groups (also called machines), each a set
of states keyed by id. Every state carries entry commands (run on entry),
exit commands (run on exit), while commands (run every tick while active;
unused by DS1 but present in the format), and an ordered list of conditions.
Each condition has an evaluator expression (EzState bytecode, see below),
pass commands (run when the evaluator passes), an optional target state id,
and optional subconditions that are checked when the evaluator passes.

File layout (64-bit ``fsSL`` variant that DS1 Remastered ships; the 32-bit
``fSSL`` form is also read and written). All integers are little-endian.
``varint`` below means 8 bytes in the 64-bit form, 4 bytes otherwise::

    magic 'fsSL' (64-bit) or 'fSSL' (32-bit)
    u32 1, u32 dark_souls_count (1 for DS1/DSR), u32 dark_souls_count,
    u32 0x54, u32 data_size (everything after this header),
    u32 6, u32 0x48/0x2C, u32 1, u32 state_group_entry_size,
    u32 state_group_count, u32 state_entry_size, u32 state_count,
    u32 0x38/0x1C, u32 condition_count, u32 0x18/0x10,
    u32 command_count, u32 0x10/0x8, u32 arg_count,
    u32 condition_offsets_offset, u32 condition_offsets_count,
    u32 name_block_offset, u32 name_length (UTF-16 units incl. terminator),
    u32 unk_offset_1, u32 0, u32 unk_offset_2, u32 0
    ---- data section (offsets below are relative to its start) ----
    u32 1, u32 unk0..3 (opaque), [u32 0 pad in 64-bit form]
    varint state_groups_offset, varint state_group_count,
    varint name_offset (-1 when nameless), varint name_length,
    varint 0, varint 0
    per state group, by ascending id:
        varint id, varint states_offset, varint state_count,
        varint states_offset (repeated)
    state headers, group after group, states by ascending id:
        varint id, varint condition_offsets_offset (-1 when none),
        varint condition_count, varint entry_offset (-1 when none),
        varint entry_count, varint exit_offset (-1 when none),
        varint exit_count, varint while_offset (-1 when none),
        varint while_count
        (a group with more than one state is followed by one dummy copy
        of its first state header)
    condition headers, in first-seen order (states first, then
    subconditions depth-first; shared conditions stored once):
        varint target_state_offset (-1 when none),
        varint pass_commands_offset (-1 when none), varint pass_count,
        varint subcondition_offsets_offset (-1 when none),
        varint subcondition_count,
        varint evaluator_offset, varint evaluator_length
    command headers (state entry/exit/while commands, then condition
    pass commands, same order as above):
        u32 bank, u32 id, varint args_offset (-1 when no args),
        varint arg_count
    per-command arg tables: varint bytecode_offset, varint bytecode_length
    condition offset tables (state condition lists, then subcondition
    lists, same order as above)
    evaluator bytecode blobs, then command argument bytecode blobs
    optional UTF-16LE name (padded to 2 bytes first, null-terminated)

The layout above was established against the well-known SoulsFormats ESD
implementation (C#, TKGP) and verified byte-for-byte against every vanilla
DS1R file (see tests). Two details differ from that implementation on
purpose, because the vanilla files do it this way: commands with no args
store args_offset -1 instead of pointing at an empty table, and states
with no conditions store condition_offsets_offset -1 instead of pointing
at an empty table.

Round-trip contract: ``parse(data).to_bytes() == data`` for every vanilla
file. The writer always emits groups/states sorted by id and recomputes
every offset and count, so edited models still produce valid files.

Expression text syntax (``disassemble``/``assemble``)
-----------------------------------------------------
Evaluators and command arguments are tiny stack-machine programs ending in
``0xA1``. The text form is infix with explicit machine tokens, one token
per bytecode op, so ``assemble(disassemble(b)) == b`` for every vanilla
expression::

    5  -3  63              small-int literals (-64..63, one byte)
    i32(1004)             32-bit signed int literal
    f32(0.5) f64(0.1)     single/double float literals
    "text"                UTF-16LE string (JSON-style escapes)
    f22() f38(2, 0)       function call: id, then args (0-7 args)
    1 + 2  a - b  x * y   arithmetic; comparisons <= >= < > == !=;
    a and b  a or c       logic; precedence: or < and < cmp < +- < *//
    (r0 := f22())         save top of stack to register 0..7
    r0                    load register (may come from another condition)
    (f22() == 1)!         `!` = return-if-false marker (0xB7); `...`
    f22()...              similarly = continue-if-false marker (0xA6)
    margs(0)              index into the state machine arguments (0xB8)
    mstat() ongoing()     machine call status / running constant
    neg(x)                unary negation (0x8D; never seen in vanilla DS1R)

Plain ints outside -64..63 assemble to the ``i32`` form. ``f32``/``f64``
double as function ids 32/64: ``f32()`` calls function 32, ``f32(2.5)`` is
a float, and ``f32(2)`` calls function 32 with argument 2 (float
literals always carry a dot, exponent, inf or nan). Markers bind to the
preceding atom, so a marked comparison renders parenthesised
``(f22() == 1)!`` and re-attaches in the same spot. Register saves always
render parenthesised ``(rN := value)`` and re-attach in the same spot, so
shared/continued evaluations survive the round trip. Opcodes the vanilla
files never use in operation position (0x83, 0x97, 0x9A-0xA4, 0xBB-0xFF)
are rejected; 0x8B is accepted as a 7-argument call by extension.
Function ids are plain numbers (``f22``); a name table can be layered on
top later. Operator meanings (``<=`` etc.) and the machine-token names
follow the soulstruct EZL codec and the original Grimrukh ezstate notes;
the container layout follows SoulsFormats.
"""

import re
import struct
from dataclasses import dataclass, field

from .formats import FormatError


class EsdError(FormatError):
    """An ESD file Lexeditor cannot safely read."""


@dataclass
class Command:
    """One command call: a bank/id plus raw argument expressions."""

    bank: int
    id: int
    args: list = field(default_factory=list)


@dataclass
class Condition:
    """One transition: evaluator bytecode, pass commands, target, subs."""

    target_state: object = None
    evaluator: bytes = b""
    pass_commands: list = field(default_factory=list)
    subconditions: list = field(default_factory=list)


@dataclass
class State:
    """One state-machine node with commands and conditions."""

    id: int = 0
    entry_commands: list = field(default_factory=list)
    exit_commands: list = field(default_factory=list)
    while_commands: list = field(default_factory=list)
    conditions: list = field(default_factory=list)


@dataclass
class Esd:
    """A whole ESD file: state groups keyed by id, each states by id."""

    state_groups: dict = field(default_factory=dict)
    name: object = None
    dark_souls_count: int = 1
    long_format: bool = True
    unk: tuple = (0, 0, 0, 0)

    def to_bytes(self):
        """Rebuild the file, recomputing every offset and count."""
        return _write_esd(self)


_HEADER_COUNT = 26
_DATA_START = 4 + _HEADER_COUNT * 4


class _Reader:
    """Bounds-checked cursor over the file bytes."""

    def __init__(self, data, long_format):
        self.data = data
        self.long_format = long_format
        self.varint = "<q" if long_format else "<i"
        self.varsize = 8 if long_format else 4

    def u32(self, pos):
        try:
            return struct.unpack_from("<I", self.data, pos)[0]
        except struct.error:
            raise EsdError("ESD is truncated.")

    def i32(self, pos):
        try:
            return struct.unpack_from("<i", self.data, pos)[0]
        except struct.error:
            raise EsdError("ESD is truncated.")

    def var(self, pos):
        try:
            return struct.unpack_from(self.varint, self.data, pos)[0]
        except struct.error:
            raise EsdError("ESD is truncated.")

    def raw(self, pos, size):
        if size < 0 or pos < 0 or pos + size > len(self.data):
            raise EsdError("ESD offset points outside the file.")
        return bytes(self.data[pos:pos + size])


def parse(data):
    """Read an ESD file, keeping unknown header fields opaque."""
    data = bytes(data)
    if len(data) < _DATA_START or data[:4] not in (b"fsSL", b"fSSL"):
        raise EsdError("Not an ESD file.")
    long_format = data[:4] == b"fsSL"
    reader = _Reader(data, long_format)
    head = struct.unpack_from("<%dI" % _HEADER_COUNT, data, 4)
    (one, dsc, dsc2, magic54, _data_size, six, wide, one_b, group_size,
     group_count, state_size, state_count, cond_size, cond_count,
     cmd_size, cmd_count, arg_size, arg_count, _cond_off, _cond_n,
     _name_off, name_len, _unk_off_1, zero_1, _unk_off_2, zero_2) = head
    if (one, dsc2, magic54, six, one_b, zero_1, zero_2) != (1, dsc, 0x54, 6, 1, 0, 0):
        raise EsdError("Unsupported ESD header.")
    if dsc not in (1, 2, 3):
        raise EsdError("Unsupported ESD header.")
    expect = (0x48, 0x20, 0x48, 0x38, 0x18, 0x10) if long_format else (0x2C, 0x10, 0x24, 0x1C, 0x10, 0x8)
    if (wide, group_size, state_size, cond_size, cmd_size, arg_size) != expect:
        raise EsdError("Unsupported ESD entry sizes.")
    base = _DATA_START
    if reader.u32(base) != 1:
        raise EsdError("Unsupported ESD header.")
    unk = tuple(reader.u32(base + 4 + 4 * i) for i in range(4))
    pos = base + 24 if long_format else base + 20
    _sg_off, sg_n, name_off, name_n, zero_a, zero_b = (
        reader.var(pos + i * reader.varsize) for i in range(6))
    if sg_n != group_count or name_n != name_len or (zero_a, zero_b) != (0, 0):
        raise EsdError("Unsupported ESD header.")
    pos += 6 * reader.varsize
    name = None
    if name_len:
        raw = reader.raw(base + name_off, name_len * 2)
        end = -1
        for at in range(0, len(raw), 2):
            if raw[at:at + 2] == b"\0\0":
                end = at
                break
        if end < 0:
            raise EsdError("ESD name is not null-terminated UTF-16.")
        try:
            name = raw[:end].decode("utf-16-le")
        except UnicodeDecodeError:
            raise EsdError("ESD name is not decodable.")
    groups = []
    for _ in range(group_count):
        gid = reader.var(pos)
        first = reader.var(pos + reader.varsize)
        count = reader.var(pos + 2 * reader.varsize)
        second = reader.var(pos + 3 * reader.varsize)
        if first != second or count < 0:
            raise EsdError("ESD state group is malformed.")
        groups.append((gid, first, count))
        pos += 4 * reader.varsize
    states = {}
    raws = {}
    for _ in range(state_count):
        values = tuple(reader.var(pos + i * reader.varsize) for i in range(9))
        states[pos - base] = values
        raws[pos - base] = reader.raw(pos, 9 * reader.varsize)
        pos += 9 * reader.varsize
    conds = {}
    for _ in range(cond_count):
        values = tuple(reader.var(pos + i * reader.varsize) for i in range(7))
        conds[pos - base] = values
        pos += 7 * reader.varsize

    def read_commands(offset, count):
        if count == 0:
            return []
        if offset < 0:
            raise EsdError("ESD command list offset is missing.")
        found = []
        at = base + offset
        for _ in range(count):
            bank = reader.i32(at)
            cid = reader.i32(at + 4)
            if bank not in (1, 5, 6, 7):
                raise EsdError("Unsupported ESD command bank.")
            arg_off = reader.var(at + 8)
            arg_n = reader.var(at + 8 + reader.varsize)
            if arg_n < 0:
                raise EsdError("ESD command arg count is negative.")
            args = []
            if arg_n:
                if arg_off < 0:
                    raise EsdError("ESD command arg offset is missing.")
                for i in range(arg_n):
                    e_off = reader.var(base + arg_off + i * 2 * reader.varsize)
                    e_len = reader.var(base + arg_off + i * 2 * reader.varsize + reader.varsize)
                    args.append(reader.raw(base + e_off, e_len))
            found.append(Command(bank, cid, args))
            at += 8 + 2 * reader.varsize
        return found

    parsed_states = {}
    for rel, values in states.items():
        (sid, coff, ccnt, enoff, encnt, exoff, excnt, woff, wcnt) = values
        if min(ccnt, encnt, excnt, wcnt) < 0:
            raise EsdError("ESD state counts are negative.")
        parsed_states[rel] = {
            "id": sid,
            "offsets": (coff, ccnt),
            "entry": read_commands(enoff, encnt),
            "exit": read_commands(exoff, excnt),
            "while": read_commands(woff, wcnt),
        }
    parsed_conds = {}
    for rel, values in conds.items():
        (soff, poff, pcnt, coff, ccnt, eoff, elen) = values
        if min(pcnt, ccnt, elen) < 0:
            raise EsdError("ESD condition counts are negative.")
        parsed_conds[rel] = {
            "target": soff,
            "passes": read_commands(poff, pcnt),
            "subs": (coff, ccnt),
            "evaluator": reader.raw(base + eoff, elen),
        }
    state_groups = {}
    for gid, first, count in groups:
        taken = {}
        weird = None
        if count > 1:
            weird = first + count * (9 * reader.varsize)
            if weird not in states:
                raise EsdError("ESD dummy state is missing.")
            if raws[weird] != raws[first]:
                raise EsdError("ESD dummy state does not match.")
            del states[weird]
        members = {}
        for i in range(count):
            rel = first + i * 9 * reader.varsize
            if rel not in states:
                raise EsdError("ESD state is missing.")
            info = parsed_states[rel]
            if info["id"] in members:
                raise EsdError("Duplicate ESD state ID.")
            del states[rel]
            state = State(info["id"], info["entry"], info["exit"], info["while"])
            members[info["id"]] = state
            taken[rel] = info["id"]
        if gid in state_groups:
            raise EsdError("Duplicate ESD state group ID.")
        state_groups[gid] = (members, taken)
    if states:
        raise EsdError("ESD has orphaned states.")
    objects = {}
    for rel, info in parsed_conds.items():
        cond = Condition(None, info["evaluator"], info["passes"])
        cond._cond_offsets = info["subs"]
        objects[rel] = (cond, info["target"])
    resolved = set()

    def resolve(rel, taken):
        cond, target = objects[rel]
        if rel in resolved:
            return cond
        resolved.add(rel)
        if target == -1:
            cond.target_state = None
        elif target in taken:
            cond.target_state = taken[target]
        else:
            raise EsdError("ESD condition target state is missing.")
        coff, ccnt = cond._cond_offsets
        subs = []
        if ccnt:
            if coff < 0:
                raise EsdError("ESD subcondition offset is missing.")
            for i in range(ccnt):
                sub = reader.var(base + coff + i * reader.varsize)
                if sub not in objects:
                    raise EsdError("ESD subcondition is missing.")
                subs.append(resolve(sub, taken))
        cond.subconditions = subs
        del cond._cond_offsets
        return cond

    for _gid, (members, taken) in state_groups.items():
        for rel, sid in taken.items():
            state = members[sid]
            coff, ccnt = parsed_states[rel]["offsets"]
            found = []
            if ccnt:
                if coff < 0:
                    raise EsdError("ESD condition offset is missing.")
                for i in range(ccnt):
                    sub = reader.var(base + coff + i * reader.varsize)
                    if sub not in objects:
                        raise EsdError("ESD condition is missing.")
                    found.append(resolve(sub, taken))
            state.conditions = found
    return Esd({gid: members for gid, (members, _taken) in state_groups.items()},
               name, dsc, long_format, unk)


class _Builder:
    """Byte buffer with named offset reservations filled in later."""

    def __init__(self, long_format):
        self.out = bytearray()
        self.long_format = long_format
        self.varint = "<q" if long_format else "<i"
        self.varsize = 8 if long_format else 4
        self.slots = {}

    @property
    def pos(self):
        return len(self.out)

    def u32(self, value):
        self.out += struct.pack("<I", value)

    def i32(self, value):
        self.out += struct.pack("<i", value)

    def var(self, value):
        self.out += struct.pack(self.varint, value)

    def reserve(self, name):
        if name in self.slots:
            raise EsdError("Duplicate ESD layout slot.")
        self.slots[name] = (self.pos, self.varint)
        self.out += b"\0" * self.varsize

    def reserve32(self, name):
        if name in self.slots:
            raise EsdError("Duplicate ESD layout slot.")
        self.slots[name] = (self.pos, "<I")
        self.out += b"\0" * 4

    def fill(self, name, value):
        try:
            at, fmt = self.slots.pop(name)
        except KeyError:
            raise EsdError("ESD layout slot was never reserved.")
        struct.pack_into(fmt, self.out, at, value)

    def pad(self, align):
        while self.pos % align:
            self.out.append(0)


def _rel(bw, base):
    return bw.pos - base


def validate_writable(esd):
    """Validate the writer's supported ESD model without serializing it."""
    dsc = esd.dark_souls_count
    if dsc not in (1, 2, 3):
        raise EsdError("Unsupported ESD dark souls count.")
    for group in esd.state_groups.values():
        for state in group.values():
            for commands in (state.entry_commands, state.exit_commands,
                             state.while_commands):
                for command in commands:
                    if command.bank not in (1, 5, 6, 7):
                        raise EsdError("Unsupported ESD command bank.")


def _write_esd(esd):
    """Serialize the model, recomputing every offset and count."""
    validate_writable(esd)
    long_format = esd.long_format
    dsc = esd.dark_souls_count
    bw = _Builder(long_format)
    bw.out += b"fsSL" if long_format else b"fSSL"
    bw.u32(1)
    bw.u32(dsc)
    bw.u32(dsc)
    bw.u32(0x54)
    bw.reserve32("DataSize")
    bw.u32(6)
    bw.u32(0x48 if long_format else 0x2C)
    bw.u32(1)
    bw.u32(0x20 if long_format else 0x10)
    bw.u32(len(esd.state_groups))
    state_size = 0x48 if long_format else 0x24
    bw.u32(state_size)
    state_total = sum(len(group) + (1 if len(group) > 1 else 0)
                      for group in esd.state_groups.values())
    bw.u32(state_total)
    bw.u32(0x38 if long_format else 0x1C)
    bw.reserve32("ConditionCount")
    bw.u32(0x18 if long_format else 0x10)
    bw.reserve32("CommandCallCount")
    bw.u32(0x10 if long_format else 0x8)
    bw.reserve32("CommandArgCount")
    bw.reserve32("ConditionOffsetsOffset")
    bw.reserve32("ConditionOffsetsCount")
    bw.reserve32("NameBlockOffset")
    bw.u32(len(esd.name) + 1 if esd.name is not None else 0)
    bw.reserve32("UnkOffset1")
    bw.u32(0)
    bw.reserve32("UnkOffset2")
    bw.u32(0)
    base = bw.pos
    bw.u32(1)
    for value in esd.unk:
        bw.u32(value)
    if len(esd.unk) != 4:
        raise EsdError("ESD opaque header needs four values.")
    if long_format:
        bw.u32(0)
    bw.reserve("StateGroupsOffset")
    bw.var(len(esd.state_groups))
    bw.reserve("NameOffset")
    bw.var(len(esd.name) + 1 if esd.name is not None else 0)
    bw.var(0 if dsc == 1 else -1)
    bw.var(0 if dsc == 1 else -1)
    group_ids = sorted(esd.state_groups)
    state_ids = {gid: sorted(esd.state_groups[gid]) for gid in group_ids}
    if group_ids:
        bw.fill("StateGroupsOffset", _rel(bw, base))
        for gid in group_ids:
            bw.var(gid)
            bw.reserve("Group%d:States1" % gid)
            bw.var(len(state_ids[gid]))
            bw.reserve("Group%d:States2" % gid)
    else:
        bw.fill("StateGroupsOffset", -1)
    state_offsets = {}
    dummies = []
    for gid in group_ids:
        state_offsets[gid] = {}
        bw.fill("Group%d:States1" % gid, _rel(bw, base))
        bw.fill("Group%d:States2" % gid, _rel(bw, base))
        first = bw.pos
        for sid in state_ids[gid]:
            state = esd.state_groups[gid][sid]
            state_offsets[gid][sid] = _rel(bw, base)
            bw.var(sid)
            bw.reserve("State%d-%d:Conds" % (gid, sid))
            bw.var(len(state.conditions))
            bw.reserve("State%d-%d:Entry" % (gid, sid))
            bw.var(len(state.entry_commands))
            bw.reserve("State%d-%d:Exit" % (gid, sid))
            bw.var(len(state.exit_commands))
            bw.reserve("State%d-%d:While" % (gid, sid))
            bw.var(len(state.while_commands))
        if len(state_ids[gid]) > 1:
            dummies.append((first, bw.pos))
            bw.out += b"\0" * state_size
    conditions = {}
    for gid in group_ids:
        ordered = []
        seen = set()

        def collect(cond):
            if id(cond) in seen:
                return
            seen.add(id(cond))
            ordered.append(cond)
            for sub in cond.subconditions:
                collect(sub)

        for sid in state_ids[gid]:
            for cond in esd.state_groups[gid][sid].conditions:
                collect(cond)
        conditions[gid] = ordered
    bw.fill("ConditionCount", sum(len(found) for found in conditions.values()))
    cond_offsets = {}
    for gid in group_ids:
        for index, cond in enumerate(conditions[gid]):
            cond_offsets[id(cond)] = _rel(bw, base)
            if cond.target_state is None:
                bw.var(-1)
            else:
                try:
                    bw.var(state_offsets[gid][cond.target_state])
                except KeyError:
                    raise EsdError("ESD condition target state is missing.")
            bw.reserve("Cond%d-%d:Pass" % (gid, index))
            bw.var(len(cond.pass_commands))
            bw.reserve("Cond%d-%d:Subs" % (gid, index))
            bw.var(len(cond.subconditions))
            bw.reserve("Cond%d-%d:Eval" % (gid, index))
            bw.var(len(cond.evaluator))
    commands = []

    def emit_commands(cmds, slot):
        if not cmds:
            bw.fill(slot, -1)
            return
        bw.fill(slot, _rel(bw, base))
        for command in cmds:
            bw.i32(command.bank)
            bw.i32(command.id)
            bw.reserve("Cmd%d:Args" % len(commands))
            bw.var(len(command.args))
            commands.append(command)

    for gid in group_ids:
        for sid in state_ids[gid]:
            state = esd.state_groups[gid][sid]
            emit_commands(state.entry_commands, "State%d-%d:Entry" % (gid, sid))
            emit_commands(state.exit_commands, "State%d-%d:Exit" % (gid, sid))
            emit_commands(state.while_commands, "State%d-%d:While" % (gid, sid))
        for index, cond in enumerate(conditions[gid]):
            emit_commands(cond.pass_commands, "Cond%d-%d:Pass" % (gid, index))
    bw.fill("CommandCallCount", len(commands))
    bw.fill("CommandArgCount", sum(len(command.args) for command in commands))
    for index, command in enumerate(commands):
        if not command.args:
            bw.fill("Cmd%d:Args" % index, -1)
            continue
        bw.fill("Cmd%d:Args" % index, _rel(bw, base))
        for number, _arg in enumerate(command.args):
            bw.reserve("Cmd%d-%d:Data" % (index, number))
            bw.var(len(_arg))
    bw.fill("ConditionOffsetsOffset", _rel(bw, base))
    offset_count = 0
    for gid in group_ids:
        for sid in state_ids[gid]:
            state = esd.state_groups[gid][sid]
            if not state.conditions:
                bw.fill("State%d-%d:Conds" % (gid, sid), -1)
                continue
            bw.fill("State%d-%d:Conds" % (gid, sid), _rel(bw, base))
            for cond in state.conditions:
                try:
                    bw.var(cond_offsets[id(cond)])
                except KeyError:
                    raise EsdError("ESD condition is unreachable.")
                offset_count += 1
        if len(state_ids[gid]) > 1:
            first = esd.state_groups[gid][state_ids[gid][0]]
            for cond in first.conditions:
                try:
                    bw.var(cond_offsets[id(cond)])
                except KeyError:
                    raise EsdError("ESD condition is unreachable.")
                offset_count += 1
        for index, cond in enumerate(conditions[gid]):
            if not cond.subconditions:
                bw.fill("Cond%d-%d:Subs" % (gid, index), -1)
                continue
            bw.fill("Cond%d-%d:Subs" % (gid, index), _rel(bw, base))
            for sub in cond.subconditions:
                try:
                    bw.var(cond_offsets[id(sub)])
                except KeyError:
                    raise EsdError("ESD subcondition is unreachable.")
                offset_count += 1
    bw.fill("ConditionOffsetsCount", offset_count)
    for gid in group_ids:
        for index, cond in enumerate(conditions[gid]):
            bw.fill("Cond%d-%d:Eval" % (gid, index), _rel(bw, base))
            bw.out += bytes(cond.evaluator)
    for index, command in enumerate(commands):
        for number, arg in enumerate(command.args):
            bw.fill("Cmd%d-%d:Data" % (index, number), _rel(bw, base))
            bw.out += bytes(arg)
    bw.fill("NameBlockOffset", _rel(bw, base))
    if esd.name is None:
        bw.fill("NameOffset", -1)
    else:
        bw.pad(2)
        bw.fill("NameOffset", _rel(bw, base))
        try:
            bw.out += esd.name.encode("utf-16-le") + b"\0\0"
        except UnicodeEncodeError:
            raise EsdError("ESD name is not encodable.")
    bw.fill("UnkOffset1", _rel(bw, base))
    bw.fill("UnkOffset2", _rel(bw, base))
    bw.fill("DataSize", _rel(bw, base))
    for first, dummy in dummies:
        bw.out[dummy:dummy + state_size] = bw.out[first:first + state_size]
    if bw.slots:
        raise EsdError("ESD layout left offsets unfilled.")
    return bytes(bw.out)


_BINOP_TEXT = {
    0x8C: ("+", 4), 0x8E: ("-", 4), 0x8F: ("*", 5), 0x90: ("/", 5),
    0x91: ("<=", 3), 0x92: (">=", 3), 0x93: ("<", 3), 0x94: (">", 3),
    0x95: ("==", 3), 0x96: ("!=", 3), 0x98: ("and", 2), 0x99: ("or", 1),
}
_BINOP_BYTES = {"+": 0x8C, "-": 0x8E, "*": 0x8F, "/": 0x90, "<=": 0x91,
                ">=": 0x92, "<": 0x93, ">": 0x94, "==": 0x95, "!=": 0x96,
                "and": 0x98, "or": 0x99}
_CMP_OPS = frozenset({"<=", ">=", "<", ">", "==", "!="})
_ATOM_PREC = 6
_INT_TEXT = re.compile(r"-?\d+$")


def _quote_string(text):
    parts = ['"']
    for char in text:
        code = ord(char)
        if char == '"':
            parts.append('\\"')
        elif char == "\\":
            parts.append("\\\\")
        elif char == "\n":
            parts.append("\\n")
        elif char == "\t":
            parts.append("\\t")
        elif char == "\r":
            parts.append("\\r")
        elif char == "\b":
            parts.append("\\b")
        elif char == "\f":
            parts.append("\\f")
        elif code < 0x20:
            parts.append("\\u%04x" % code)
        else:
            parts.append(char)
    parts.append('"')
    return "".join(parts)


def _join_binop(symbol, prec, left, left_prec, right, right_prec):
    if left_prec < prec or (left_prec == prec and symbol in _CMP_OPS):
        left = "(%s)" % left
    if right_prec <= prec:
        right = "(%s)" % right
    return "%s %s %s" % (left, symbol, right)


def _parse_call_id(text):
    if _INT_TEXT.match(text):
        return int(text)
    if text.startswith("i32(") and text.endswith(")") and _INT_TEXT.match(text[4:-1]):
        return int(text[4:-1])
    raise EsdError("Expression call id is not an integer.")


def disassemble(expr):
    """Render expression bytecode in the text syntax from the docstring."""
    data = bytes(expr)
    stack = []
    pos = 0
    size = len(data)
    while pos < size:
        op = data[pos]
        if op <= 0x7F:
            stack.append((str(op - 64), _ATOM_PREC, True))
            pos += 1
        elif op == 0x80:
            if pos + 5 > size:
                raise EsdError("Expression float is truncated.")
            value = struct.unpack_from("<f", data, pos + 1)[0]
            stack.append(("f32(%s)" % repr(value), _ATOM_PREC, True))
            pos += 5
        elif op == 0x81:
            if pos + 9 > size:
                raise EsdError("Expression double is truncated.")
            value = struct.unpack_from("<d", data, pos + 1)[0]
            stack.append(("f64(%s)" % repr(value), _ATOM_PREC, True))
            pos += 9
        elif op == 0x82:
            if pos + 5 > size:
                raise EsdError("Expression int is truncated.")
            value = struct.unpack_from("<i", data, pos + 1)[0]
            stack.append(("i32(%d)" % value, _ATOM_PREC, True))
            pos += 5
        elif 0x84 <= op <= 0x8B:
            count = op - 0x84
            if len(stack) < count + 1:
                raise EsdError("Expression call lacks arguments.")
            cells = [stack.pop() for _ in range(count + 1)]
            fid = _parse_call_id(cells[-1][0])
            args = ", ".join(cell[0] for cell in reversed(cells[:-1]))
            stack.append(("f%d(%s)" % (fid, args), _ATOM_PREC, True))
            pos += 1
        elif op in _BINOP_TEXT:
            symbol, prec = _BINOP_TEXT[op]
            if len(stack) < 2:
                raise EsdError("Expression operator lacks operands.")
            right, right_prec, _right_atom = stack.pop()
            left, left_prec, _left_atom = stack.pop()
            stack.append((_join_binop(symbol, prec, left, left_prec,
                                      right, right_prec), prec, False))
            pos += 1
        elif op == 0x8D:
            if not stack:
                raise EsdError("Expression negation lacks an operand.")
            value, _prec, _atom = stack.pop()
            stack.append(("neg(%s)" % value, _ATOM_PREC, True))
            pos += 1
        elif op == 0xA1:
            pos += 1
            if pos != size:
                raise EsdError("Expression end marker is not last.")
            if len(stack) != 1:
                raise EsdError("Expression leaves %d values." % len(stack))
            return stack[0][0]
        elif op == 0xA5:
            end = pos + 1
            while data[end:end + 2] != b"\0\0":
                end += 2
                if end + 1 >= size:
                    raise EsdError("Expression string is unterminated.")
            try:
                text = data[pos + 1:end].decode("utf-16-le")
            except UnicodeDecodeError:
                raise EsdError("Expression string is not decodable.")
            stack.append((_quote_string(text), _ATOM_PREC, True))
            pos = end + 2
        elif op in (0xA6, 0xB7):
            if not stack:
                raise EsdError("Expression marker lacks a value.")
            value, _prec, atomic = stack.pop()
            if not atomic:
                value = "(%s)" % value
            marker = "..." if op == 0xA6 else "!"
            stack.append(("%s%s" % (value, marker), _ATOM_PREC, True))
            pos += 1
        elif 0xA7 <= op <= 0xAE:
            if not stack:
                raise EsdError("Expression save lacks a value.")
            value, _prec, _atom = stack.pop()
            stack.append(("(r%d := %s)" % (op - 0xA7, value), _ATOM_PREC, True))
            pos += 1
        elif 0xAF <= op <= 0xB6:
            stack.append(("r%d" % (op - 0xAF), _ATOM_PREC, True))
            pos += 1
        elif op == 0xB8:
            if not stack:
                raise EsdError("Expression machine arg lacks an index.")
            value, _prec, _atom = stack.pop()
            stack.append(("margs(%s)" % value, _ATOM_PREC, True))
            pos += 1
        elif op == 0xB9:
            stack.append(("mstat()", _ATOM_PREC, True))
            pos += 1
        elif op == 0xBA:
            stack.append(("ongoing()", _ATOM_PREC, True))
            pos += 1
        else:
            raise EsdError("Unknown expression opcode 0x%02X." % op)
    raise EsdError("Expression is missing its end marker.")


_TOKEN_PATTERN = re.compile(r"""
    (?P<dots>\.\.\.)
    | (?P<float>(?:\d+\.\d+|\.\d+)(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+|inf|nan)
    | (?P<num>\d+)
    | (?P<text>"(?:[^"\\]|\\.)*")
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<op><=|>=|==|!=|:=|\(|\)|,|\+|-|\*|/|!|<|>)
""", re.VERBOSE)


def _tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos] in " \t\r\n":
            pos += 1
            continue
        found = _TOKEN_PATTERN.match(text, pos)
        if found is None:
            raise EsdError("Cannot read expression near %r." % text[pos:pos + 12])
        kind = found.lastgroup
        tokens.append((kind, found.group()))
        pos = found.end()
    return tokens


def _decode_string(token):
    inner = token[1:-1]
    parts = []
    pos = 0
    simple = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r",
              "b": "\b", "f": "\f"}
    while pos < len(inner):
        char = inner[pos]
        if char != "\\":
            parts.append(char)
            pos += 1
            continue
        if pos + 1 >= len(inner):
            raise EsdError("Expression string ends in a backslash.")
        esc = inner[pos + 1]
        if esc in simple:
            parts.append(simple[esc])
            pos += 2
        elif esc == "u":
            digits = inner[pos + 2:pos + 6]
            if len(digits) != 4 or not all(c in "0123456789abcdefABCDEF"
                                           for c in digits):
                raise EsdError("Bad unicode escape in expression string.")
            parts.append(chr(int(digits, 16)))
            pos += 6
        else:
            raise EsdError("Bad escape in expression string.")
    return "".join(parts)


class _Assembler:
    """Recursive descent parser turning text into expression bytecode."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return (None, "")

    def take(self, kind=None, value=None):
        actual_kind, actual = self.peek()
        if actual_kind != kind or (value is not None and actual != value):
            raise EsdError("Unexpected %r in expression." % actual)
        self.pos += 1
        return actual

    def parse(self):
        node = self.parse_or()
        kind, value = self.peek()
        if kind is not None:
            raise EsdError("Unexpected %r in expression." % value)
        return node

    def parse_or(self):
        node = self.parse_and()
        while self.peek() == ("name", "or"):
            self.pos += 1
            node = ("bin", "or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_cmp()
        while self.peek() == ("name", "and"):
            self.pos += 1
            node = ("bin", "and", node, self.parse_cmp())
        return node

    def parse_cmp(self):
        node = self.parse_add()
        kind, value = self.peek()
        if kind == "op" and value in _CMP_OPS:
            self.pos += 1
            node = ("bin", value, node, self.parse_add())
            kind, value = self.peek()
            if kind == "op" and value in _CMP_OPS:
                raise EsdError("Chained comparisons need parentheses.")
        return node

    def parse_add(self):
        node = self.parse_mul()
        while self.peek() in (("op", "+"), ("op", "-")):
            _kind, symbol = self.peek()
            self.pos += 1
            node = ("bin", symbol, node, self.parse_mul())
        return node

    def parse_mul(self):
        node = self.parse_unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            _kind, symbol = self.peek()
            self.pos += 1
            node = ("bin", symbol, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.peek() == ("op", "-"):
            self.pos += 1
            node = self.parse_unary()
            if node[0] == "lit" and node[1] in ("int", "i32", "f32", "f64"):
                return ("lit", node[1], -node[2])
            raise EsdError("Minus needs a literal; use neg(...) otherwise.")
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_atom()
        while self.peek() in (("dots", "..."), ("op", "!")):
            _kind, symbol = self.peek()
            self.pos += 1
            node = ("mark", node, symbol)
        return node

    def parse_atom(self):
        kind, value = self.peek()
        if kind == "num":
            self.pos += 1
            return ("lit", "int", int(value))
        if kind == "text":
            self.pos += 1
            return ("lit", "str", _decode_string(value))
        if kind == "name" and value == "i32":
            self.pos += 1
            self.take("op", "(")
            number = self.parse_number()
            self.take("op", ")")
            if isinstance(number, float):
                raise EsdError("i32 needs an integer in expression.")
            return ("lit", "i32", number)
        if kind == "name" and value in ("f32", "f64"):
            fid = 32 if value == "f32" else 64
            self.pos += 1
            self.take("op", "(")
            if self.peek() == ("op", ")"):
                self.pos += 1
                return ("call", fid, [])
            after_paren = self.pos
            negative = self.peek() == ("op", "-")
            if negative:
                self.pos += 1
            kind2, value2 = self.peek()
            if (kind2 == "float" and self.tokens[self.pos + 1:self.pos + 2]
                    == [("op", ")")]):
                self.pos += 2
                number = float(value2)
                return ("lit", value, -number if negative else number)
            self.pos = after_paren
            args = [self.parse_or()]
            while self.peek() == ("op", ","):
                self.pos += 1
                args.append(self.parse_or())
            self.take("op", ")")
            if len(args) > 7:
                raise EsdError("Expression calls take at most 7 arguments.")
            return ("call", fid, args)
        if kind == "name" and value == "neg":
            self.pos += 1
            self.take("op", "(")
            node = self.parse_or()
            self.take("op", ")")
            return ("neg", node)
        if kind == "name" and value == "margs":
            self.pos += 1
            self.take("op", "(")
            node = self.parse_or()
            self.take("op", ")")
            return ("margs", node)
        if kind == "name" and value in ("mstat", "ongoing"):
            self.pos += 1
            self.take("op", "(")
            self.take("op", ")")
            return (value,)
        if kind == "name" and re.match(r"f\d+$", value):
            self.pos += 1
            self.take("op", "(")
            args = []
            if self.peek() != ("op", ")"):
                args.append(self.parse_or())
                while self.peek() == ("op", ","):
                    self.pos += 1
                    args.append(self.parse_or())
            self.take("op", ")")
            if len(args) > 7:
                raise EsdError("Expression calls take at most 7 arguments.")
            return ("call", int(value[1:]), args)
        if kind == "name" and re.match(r"r[0-7]$", value):
            self.pos += 1
            return ("load", int(value[1:]))
        if kind == "op" and value == "(":
            self.pos += 1
            kind2, value2 = self.peek()
            if (kind2 == "name" and re.match(r"r[0-7]$", value2)
                    and self.tokens[self.pos + 1:self.pos + 2] == [("op", ":=")]):
                self.pos += 2
                node = self.parse_or()
                self.take("op", ")")
                return ("save", int(value2[1:]), node)
            node = self.parse_or()
            self.take("op", ")")
            return node
        raise EsdError("Unexpected %r in expression." % value)

    def parse_number(self):
        kind, value = self.peek()
        if kind == "num":
            self.pos += 1
            return int(value)
        if kind == "op" and value == "-":
            self.pos += 1
            number = self.parse_number()
            return -number
        if kind == "float":
            self.pos += 1
            try:
                return float(value)
            except ValueError:
                raise EsdError("Bad number %r in expression." % value)
        raise EsdError("Expected a number in expression.")


def _emit_int(out, value):
    if -64 <= value <= 63:
        out.append(value + 64)
    else:
        if not -(2 ** 31) <= value <= 2 ** 31 - 1:
            raise EsdError("Integer %d does not fit expression." % value)
        out.append(0x82)
        out += struct.pack("<i", value)


def _emit_node(out, node):
    kind = node[0]
    if kind == "lit":
        _kind, value = node[1], node[2]
        if _kind == "int":
            _emit_int(out, value)
        elif _kind == "i32":
            if not -(2 ** 31) <= value <= 2 ** 31 - 1:
                raise EsdError("Integer %d does not fit expression." % value)
            out.append(0x82)
            out += struct.pack("<i", value)
        elif _kind == "f32":
            try:
                packed = struct.pack("<f", value)
            except OverflowError:
                raise EsdError("Float %r does not fit expression." % value)
            out.append(0x80)
            out += packed
        elif _kind == "f64":
            try:
                packed = struct.pack("<d", value)
            except OverflowError:
                raise EsdError("Float %r does not fit expression." % value)
            out.append(0x81)
            out += packed
        elif _kind == "str":
            try:
                encoded = value.encode("utf-16-le")
            except UnicodeEncodeError:
                raise EsdError("Expression string is not encodable.")
            out.append(0xA5)
            out += encoded + b"\0\0"
        else:
            raise EsdError("Bad expression literal.")
    elif kind == "bin":
        _emit_node(out, node[2])
        _emit_node(out, node[3])
        out.append(_BINOP_BYTES[node[1]])
    elif kind == "call":
        _fid, args = node[1], node[2]
        if _fid < 0:
            raise EsdError("Expression call id is negative.")
        _emit_int(out, _fid)
        for arg in args:
            _emit_node(out, arg)
        out.append(0x84 + len(args))
    elif kind == "save":
        _emit_node(out, node[2])
        out.append(0xA7 + node[1])
    elif kind == "load":
        out.append(0xAF + node[1])
    elif kind == "mark":
        _emit_node(out, node[1])
        out.append(0xA6 if node[2] == "..." else 0xB7)
    elif kind == "margs":
        _emit_node(out, node[1])
        out.append(0xB8)
    elif kind == "mstat":
        out.append(0xB9)
    elif kind == "ongoing":
        out.append(0xBA)
    elif kind == "neg":
        _emit_node(out, node[1])
        out.append(0x8D)
    else:
        raise EsdError("Bad expression.")


def assemble(text):
    """Compile text in the docstring syntax back to expression bytecode."""
    out = bytearray()
    _emit_node(out, _Assembler(_tokenize(text)).parse())
    out.append(0xA1)
    return bytes(out)
