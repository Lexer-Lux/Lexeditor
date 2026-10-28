"""Three-way composition of independent edits to the same talk state machine."""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from difflib import SequenceMatcher

from . import esd


def _key(value):
    if is_dataclass(value):
        return tuple((f.name, _key(getattr(value, f.name))) for f in fields(value))
    if isinstance(value, dict):
        return tuple((key, _key(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(_key(item) for item in value)
    return value


def compose(original: bytes, mods: list[tuple[str, bytes]]) -> tuple[bytes, list[tuple[str, list[str]]]]:
    """Merge fields and disjoint command/condition edits, reporting true collisions.

    All changes are compared with the original, never with another mod's output.
    Unresolvable collisions retain the later value, as the host's conflict UI
    reports; independent inserts at one boundary retain both in library order.
    """
    changed = [(owner, data) for owner, data in mods if data != original]
    if not changed:
        return original, []
    if len(changed) == 1 or len({data for _, data in changed}) == 1:
        return changed[-1][1], []
    base = esd.parse(original)
    variants = [(owner, esd.parse(data)) for owner, data in changed]
    conflicts = []

    def merge(before, versions, path):
        versions = [(owner, after) for owner, after in versions if after != before]
        if not versions:
            return deepcopy(before)
        if all(after == versions[0][1] for _, after in versions):
            return deepcopy(versions[0][1])
        if is_dataclass(before) and all(type(after) is type(before) for _, after in versions):
            result = deepcopy(before)
            for f in fields(before):
                setattr(result, f.name, merge(getattr(before, f.name),
                        [(owner, getattr(after, f.name)) for owner, after in versions], f"{path}/{f.name}"))
            return result
        if isinstance(before, dict) and all(isinstance(after, dict) for _, after in versions):
            result = {}
            absent = object()
            for key in sorted(set(before).union(*(after for _, after in versions))):
                value = before.get(key, absent)
                edits = [(owner, after.get(key, absent)) for owner, after in versions]
                if value is absent or any(item is absent for _, item in edits):
                    edits = [(owner, item) for owner, item in edits if item != value]
                    if not edits:
                        result[key] = deepcopy(value)
                        continue
                    if any(item != edits[0][1] for _, item in edits):
                        conflicts.append((f"{path}/{key}", [owner for owner, _ in edits]))
                    if edits[-1][1] is not absent:
                        result[key] = deepcopy(edits[-1][1])
                else:
                    result[key] = merge(value, edits, f"{path}/{key}")
            return result
        if isinstance(before, list) and all(isinstance(after, list) for _, after in versions):
            patches = []
            for owner, after in versions:
                matcher = SequenceMatcher(a=[_key(item) for item in before],
                                          b=[_key(item) for item in after], autojunk=False)
                for tag, low, high, start, end in matcher.get_opcodes():
                    if tag == "equal":
                        continue
                    payload = after[start:end]
                    prior = [p for p in patches if (low == high == p[0] == p[1])
                             or max(low, p[0]) < min(high, p[1])
                             or (p[0] == p[1] and low < p[0] < high)
                             or (low == high and p[0] < low < p[1])]
                    if len(prior) == 1 and prior[0][:2] == [low, high]:
                        old = prior[0]
                        if old[2] == payload:
                            old[3].append(owner)
                            continue
                        if low == high:
                            old[2].extend(deepcopy(item) for item in payload if item not in old[2])
                            old[3].append(owner)
                            continue
                        if high == low + 1 and len(old[2]) == len(payload) == 1:
                            old[2] = [merge(before[low], [(name, old[2][0]) for name in old[3]]
                                           + [(owner, payload[0])], f"{path}/{low}")]
                            old[3].append(owner)
                            continue
                    if prior:
                        conflicts.append((f"{path}/{low}:{high}", list(dict.fromkeys(
                            [name for p in prior for name in p[3]] + [owner]))))
                        for old in prior:
                            patches.remove(old)
                    patches.append([low, high, deepcopy(payload), [owner]])
            result, at = [], 0
            for low, high, payload, _ in sorted(patches, key=lambda p: (p[0], p[1])):
                result.extend(deepcopy(before[at:low]))
                result.extend(payload)
                at = high
            result.extend(deepcopy(before[at:]))
            # Independent insertions still collide if they give two different
            # bonfire choices the same result ID. Byte-level disjointness is
            # insufficient: the game would dispatch either choice identically.
            if all(isinstance(item, esd.Command) for item in result):
                option_ids = {item.args[0] for item in result
                              if (item.bank, item.id) == (1, 19) and item.args}
                for option in option_ids:
                    def choices(commands):
                        return [item for item in commands if (item.bank, item.id) == (1, 19)
                                and item.args and item.args[0] == option]
                    picked = choices(result)
                    if len({_key(item) for item in picked}) <= 1 or len(choices(before)) > 1:
                        continue
                    edits = [(owner, choices(after)) for owner, after in versions
                             if choices(after) != choices(before)]
                    conflicts.append((f"{path}/talk-option/{esd.disassemble(option)}",
                                      [owner for owner, _ in edits]))
                    chosen = edits[-1][1]
                    first = result.index(picked[0])
                    result = [item for item in result if item not in picked]
                    result[first:first] = deepcopy(chosen)
            return result
        conflicts.append((path, [owner for owner, _ in versions]))
        return deepcopy(versions[-1][1])

    result = merge(base, variants, "ESD")
    return result.to_bytes(), conflicts
