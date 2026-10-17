"""Three-way DS1 PARAM composition against one explicit, matching baseline.

Container and PARAM parsing stays in formats.py. This module does not install
anything, infer a pristine baseline, resolve gameplay dependencies, or patch
unknown layouts. See MOD_LOADER.md for supported and unsupported cases.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

MAX_MODS = 64
MAX_CHANGES = 250_000
MAX_CONFLICTS = 10_000


class CompositionError(ValueError):
    """The input cannot be composed without an explicit decision."""


class ConflictError(CompositionError):
    def __init__(self, report: dict):
        self.report = report
        super().__init__(f"{len(report['conflicts'])} conflicting overrides; choose a load order explicitly")


@dataclass(frozen=True)
class Cell:
    member: str
    table: str | None
    row_id: int | None
    field: str | None
    offset: int
    size: int
    mask: int | None = None

    @property
    def key(self):
        return self.member, self.row_id, self.field

    def read(self, data: bytes | bytearray) -> bytes:
        value = bytes(data[self.offset:self.offset + self.size])
        if len(value) != self.size:
            raise CompositionError("Cell is outside its archive")
        if self.mask is not None:
            value = (int.from_bytes(value, "little") & self.mask).to_bytes(self.size, "little")
        return value

    def write(self, data: bytearray, value: bytes) -> None:
        if len(value) != self.size:
            raise CompositionError("Invalid cell replacement size")
        if self.mask is not None:
            old = int.from_bytes(data[self.offset:self.offset + self.size], "little")
            new = (old & ~self.mask) | (int.from_bytes(value, "little") & self.mask)
            value = new.to_bytes(self.size, "little")
        data[self.offset:self.offset + self.size] = value

    def identity(self) -> dict:
        return {"member": self.member, "table": self.table, "rowId": self.row_id,
                "field": self.field, "granularity": "field" if self.field else "member"}


def _changes(base, candidate):
    """Locate semantic cells, then prove that every other byte was preserved."""
    from .formats import SIZES

    if base.members != candidate.members:
        raise CompositionError("Binder member layout changed; additions, deletions and relocation are not supported")
    if len(base.original_plain) != len(candidate.original_plain):
        raise CompositionError("Archive size changed")
    if base.original[:28] + base.original[36:76] != candidate.original[:28] + candidate.original[36:76]:
        raise CompositionError("DCX header changed outside its size fields")

    normalized = bytearray(candidate.original_plain)
    changes = []
    for table, param in base.params.items():
        other = candidate.params[table]
        identity = lambda rows: [(row.row_id, row.data_offset) for row in rows]
        if identity(param.rows) != identity(other.rows):
            raise CompositionError(f"{table}: row identity/layout changed")
        member = base.members[table + ".param"]
        row_size = base.schemas[table]["size"]
        for row in param.rows:
            start = member.offset + row.data_offset
            if base.original_plain[start:start + row_size] == candidate.original_plain[start:start + row_size]:
                continue
            for entry in base.schemas[table]["fields"]:
                spec = entry["spec"]
                # Preserve padding. Fields with known storage but no editor
                # control can be copied as authored; no values are invented.
                if spec.padding:
                    continue
                size = SIZES[spec.dtype] * spec.array_length
                mask = None if spec.bit_size is None else ((1 << spec.bit_size) - 1) << spec.bit_offset
                cell = Cell(member.name, table, row.row_id, spec.key, start + spec.offset, size, mask)
                before, after = cell.read(base.original_plain), cell.read(candidate.original_plain)
                if before != after:
                    changes.append((cell, before, after))
                    cell.write(normalized, before)
                    if len(changes) > MAX_CHANGES:
                        raise CompositionError("Too many modified fields")

    known_members = {table + ".param" for table in base.params}
    for name, member in base.members.items():
        if name in known_members:
            continue
        # An unmodeled member is an indivisible override, never a byte merge.
        cell = Cell(name, None, None, None, member.offset, member.size)
        before, after = cell.read(base.original_plain), cell.read(candidate.original_plain)
        if before != after:
            changes.append((cell, before, after))
            cell.write(normalized, before)

    if normalized != base.original_plain:
        raise CompositionError("Changes to PARAM headers, row names, padding or unmodeled container bytes are unsupported")
    return changes


def compose(base_bytes: bytes, mods: list[tuple[str, bytes]], *, policy: str = "error") -> tuple[bytes, dict]:
    """Compose enabled archives in low-to-high priority order.

    Each mod is compared to base, not to the previous mod. An unchanged value
    therefore never undoes another mod. Exact same-field values coalesce.
    policy='last-wins' is the explicit opt-in for conflicting values.
    """
    from .formats import ItemDocument, MAX_ARCHIVE

    if policy not in ("error", "last-wins"):
        raise CompositionError("Unknown conflict policy")
    if len(mods) > MAX_MODS:
        raise CompositionError("Too many enabled mods")
    ids = [name for name, _ in mods]
    if any(not isinstance(name, str) or not name.strip() or len(name) > 128 for name in ids):
        raise CompositionError("Every mod needs a nonempty ID of at most 128 characters")
    if len(set(ids)) != len(ids):
        raise CompositionError("Duplicate mod IDs")
    if len(base_bytes) > MAX_ARCHIVE or any(len(data) > MAX_ARCHIVE for _, data in mods):
        raise CompositionError("Parameter archive exceeds the size limit")

    base = ItemDocument(base_bytes)
    report = {"schema": 1, "baseSha256": sha256(base_bytes).hexdigest(),
              "policy": policy, "order": ids, "sources": [], "conflicts": [], "changedCells": 0}
    chosen = {}
    for name, data in mods:
        candidate = ItemDocument(data)
        changes = _changes(base, candidate)
        report["sources"].append({"id": name, "sha256": sha256(data).hexdigest(), "changedCells": len(changes)})
        for cell, before, after in changes:
            previous = chosen.get(cell.key)
            if previous is not None and previous[2] != after:
                if len(report["conflicts"]) >= MAX_CONFLICTS:
                    raise CompositionError("Too many conflicts to report safely")
                # Hash opaque/large values rather than retaining entire payloads.
                display = lambda value: value.hex() if len(value) <= 16 else "sha256:" + sha256(value).hexdigest()
                report["conflicts"].append({**cell.identity(), "loser": previous[0], "winner": name,
                                            "baseline": display(before), "previous": display(previous[2]),
                                            "replacement": display(after)})
            chosen[cell.key] = (name, cell, after)
            if len(chosen) > MAX_CHANGES:
                raise CompositionError("Too many composed fields")

    report["changedCells"] = len(chosen)
    if report["conflicts"] and policy == "error":
        raise ConflictError(report)
    for _, cell, value in chosen.values():
        cell.write(base.plain, value)
    output = base.export()
    # Reopen with the actual parser, not a second guessed serializer.
    ItemDocument(output)
    report["outputSha256"] = sha256(output).hexdigest()
    return output, report
