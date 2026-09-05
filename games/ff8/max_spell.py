"""Configurable FF8 spell-stock cap and junction normalization."""

from __future__ import annotations


DEFAULT_MAX_SPELL_ENABLED = False
DEFAULT_MAX_SPELL = 100
MIN_MAX_SPELL = 1
MAX_MAX_SPELL = 255

SCALE_CAVE = 0x027A1800
HP_SCALE_CAVE = 0x027A1820
LIMIT_VALUE = 0x027A1840

# Proven stock comparisons and clamps in the character, battle, Draw, and menu
# inventory paths. Only the immediate cap byte changes.
STOCK_LIMIT_SITES = (
    (0x0047ED56, 0x64), (0x0047ED72, 0x64), (0x0047ED7C, 0x64),
    (0x0047EDF5, 0x64), (0x0047EE66, 0x64),
    (0x00486A8C, 0x64), (0x00486B95, 0x64),
    (0x0048CB99, 0x64),
    (0x004A48DD, 0x64), (0x004A4910, 0x64),
    (0x004C2CCE, 0x64), (0x004C2CD2, 0x64),
    (0x004C2CFB, 0x64), (0x004C2CFF, 0x64),
)
UNSIGNED_STOCK_BRANCHES = (
    (0x00486A8D, 0x7D, 0x73),
    (0x00486B96, 0x7D, 0x73),
)

# The native Magic callback 004C8820 returns five-byte stock records.
# 004C8990 renders their quantity at +1; 004FDD90 selects and debits it.
# Byte stock is unsigned. Signed actor IDs, reserved-cast counts, and the
# signed result of quantity minus reserved casts keep their native meaning.
UNSIGNED_BATTLE_STOCK_SITES = (
    (0x004C8A14, bytes.fromhex("84 C0 7F 0A"), bytes.fromhex("84 C0 75 0A")),
    (0x004C8A52, bytes.fromhex("0F BE 56 01"), bytes.fromhex("0F B6 56 01")),
    (0x004FE2A5, bytes.fromhex("0F BE 70 01"), bytes.fromhex("0F B6 70 01")),
    (0x004FE3F0, bytes.fromhex("84 C9 7F 33"), bytes.fromhex("84 C9 75 33")),
    (0x004FE706, bytes.fromhex("0F BE 01"), bytes.fromhex("0F B6 01")),
)

HP_SITE = 0x00496392
HP_ORIGINAL = bytes.fromhex("0F AF 44 24 18 2B C2")

JUNCTION_SITES = (
    (0x004966AD, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B C2 C1 FE 02 C1 E8 1F 03 D0"), "standard_with_shift"),
    (0x0049674A, bytes.fromhex("B8 1F 85 EB 51 F7 EE C1 FA 05 8B C2 8B 74 24 14 C1 E8 1F 03 D0"), "esi"),
    (0x00496865, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B C2 03 D3 C1 E8 1F 03 C2"), "plus_ebx"),
    (0x004968EC, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 8B 4C 24 18 C1 FA 05 8B C2 C1 E8 1F 03 D0"), "load_ecx"),
    (0x004969AC, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 8B C2 5F C1 F8 05 8B D0 5E C1 EA 1F 5D 03 C2"), "return_eax"),
    (0x00496A54, bytes.fromhex("0F AF C5 8B C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B C2 C1 E8 1F 03 D0"), "multiply_ebp"),
    (0x00496B9C, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B C2 5F C1 E8 1F 5E 5D"), "return_with_pops"),
    (0x00496C48, bytes.fromhex("8B C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B C2 8B 74 24 14 C1 E8 1F 03 D0"), "load_esi"),
)


def bounded_limit(value) -> int:
    if isinstance(value, bool):
        raise ValueError("Max Spell must be a whole number from 1 to 255")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Max Spell must be a whole number from 1 to 255") from error
    if str(value).strip() not in {str(result), f"{result}.0"}:
        raise ValueError("Max Spell must be a whole number from 1 to 255")
    if not MIN_MAX_SPELL <= result <= MAX_MAX_SPELL:
        raise ValueError("Max Spell must be from 1 to 255")
    return result


def _call(site: int, target: int) -> bytes:
    return b"\xE8" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def _fit(prefix: bytes, length: int) -> bytes:
    if len(prefix) > length:
        raise AssertionError("Max Spell replacement exceeds its verified instruction range")
    return prefix + b"\x90" * (length - len(prefix))


def _junction_replacement(address: int, original: bytes, kind: str) -> bytes:
    call = _call(address + (2 if kind == "esi" else 3 if kind == "multiply_ebp" else 0), SCALE_CAVE)
    if kind == "standard_with_shift":
        return _fit(call + bytes.fromhex("89 C2 C1 FE 02"), len(original))
    if kind == "esi":
        return _fit(bytes.fromhex("89 F0") + call + bytes.fromhex("89 C2 8B 74 24 14"), len(original))
    if kind == "plus_ebx":
        return _fit(call + bytes.fromhex("01 D8"), len(original))
    if kind == "load_ecx":
        return _fit(call + bytes.fromhex("8B 4C 24 18 89 C2"), len(original))
    if kind == "return_eax":
        return _fit(call + bytes.fromhex("5F 5E 5D"), len(original))
    if kind == "multiply_ebp":
        return _fit(bytes.fromhex("0F AF C5") + call + bytes.fromhex("89 C2"), len(original))
    if kind == "return_with_pops":
        return _fit(call + bytes.fromhex("5F 5E 5D"), len(original))
    if kind == "load_esi":
        return _fit(call + bytes.fromhex("89 C2 8B 74 24 14"), len(original))
    raise AssertionError(f"Unknown junction replacement {kind}")


def _scale_cave() -> bytes:
    # EAX -> floor(EAX / configured cap), with caller ECX/EDX preserved.
    return (bytes.fromhex("52 51 31 D2 0F B6 0D")
            + LIMIT_VALUE.to_bytes(4, "little")
            + bytes.fromhex("F7 F1 59 5A C3"))


def _hp_scale_cave() -> bytes:
    # HP junction data is defined at 100x the other junction values.
    return (bytes.fromhex("52 51 6B C0 64 31 D2 0F B6 0D")
            + LIMIT_VALUE.to_bytes(4, "little")
            + bytes.fromhex("F7 F1 59 5A C3"))


def build_hext(enabled: bool, limit: int = DEFAULT_MAX_SPELL) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Max Spell must be true or false")
    cap = bounded_limit(limit)
    if not enabled:
        return ""
    hp_patch = _call(HP_SITE, HP_SCALE_CAVE) + bytes.fromhex("2B C2")
    rows = [
        f"# Max Spell: cap each spell at {cap}; a full stack keeps vanilla junction strength.",
        f"{SCALE_CAVE:X}:{len(_scale_cave()):X}",
        f"{HP_SCALE_CAVE:X}:{len(_hp_scale_cave()):X}",
        f"{LIMIT_VALUE:X}:1",
        f"{SCALE_CAVE:X} = {_scale_cave().hex(' ').upper()}",
        f"{HP_SCALE_CAVE:X} = {_hp_scale_cave().hex(' ').upper()}",
        f"{LIMIT_VALUE:X} = {cap:02X}",
        f"{HP_SITE:X} = {hp_patch.hex(' ').upper()}",
    ]
    for address, original, kind in JUNCTION_SITES:
        replacement = _junction_replacement(address, original, kind)
        rows.append(f"{address:X} = {replacement.hex(' ').upper()}")
    for address, original in STOCK_LIMIT_SITES:
        if original != 0x64:
            raise AssertionError("Unexpected stock-limit baseline")
        rows.append(f"{address:X} = {cap:02X}")
    for address, original, replacement in UNSIGNED_STOCK_BRANCHES:
        if original != 0x7D:
            raise AssertionError("Unexpected signed stock-limit branch")
        rows.append(f"{address:X} = {replacement:02X}")
    for address, _original, replacement in UNSIGNED_BATTLE_STOCK_SITES:
        rows.append(f"{address:X} = {replacement.hex(' ').upper()}")
    rows.append("")
    return "\n".join(rows)


def verify_executable(stream) -> None:
    stream.seek(HP_SITE - 0x400000)
    if stream.read(len(HP_ORIGINAL)) != HP_ORIGINAL:
        raise RuntimeError("The installed FF8 Max Spell HP-junction bytes do not match the verified build")
    for address, original, _kind in JUNCTION_SITES:
        stream.seek(address - 0x400000)
        if stream.read(len(original)) != original:
            raise RuntimeError("The installed FF8 Max Spell junction bytes do not match the verified build")
    for address, expected in STOCK_LIMIT_SITES:
        stream.seek(address - 0x400000)
        if stream.read(1) != bytes((expected,)):
            raise RuntimeError("The installed FF8 Max Spell stock-limit bytes do not match the verified build")
    for address, expected, _replacement in UNSIGNED_STOCK_BRANCHES:
        stream.seek(address - 0x400000)
        if stream.read(1) != bytes((expected,)):
            raise RuntimeError("The installed FF8 Max Spell comparison branch does not match the verified build")
    for address, expected, _replacement in UNSIGNED_BATTLE_STOCK_SITES:
        stream.seek(address - 0x400000)
        if stream.read(len(expected)) != expected:
            raise RuntimeError("The installed FF8 Max Spell battle stock instructions do not match the verified build")
