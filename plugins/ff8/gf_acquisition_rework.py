"""Guardian Force acquisition without Draw for GitHub issue #318.

Owner-approved rule (a tweak named "GF Acquisition Rework"):

- The six drawable GFs are awarded automatically on winning the fight that
  makes them available in vanilla, when they are not already owned: Siren on
  Elvoret, Carbuncle on Iguion, Leviathan on NORG, Pandemona on Fujin,
  Alexander on Edea, and Eden on Ultima Weapon.
- A GF missed at its primary fight is recovered at the game's existing Disc 4
  recovery boss instead of through Draw: Siren on Tri-Point, Carbuncle on
  Krysta, Leviathan on Trauma, Pandemona on Red Giant, Alexander on
  Catoblepas, and Eden on Tiamat.
- While the tweak is on, formerly drawable GFs are not offered as Draw
  results; ordinary spell Draw is unaffected.
- Awards use the normal GF-owned state, so they never duplicate or reset
  learned abilities, and disabling the tweak later never revokes a GF.
- Every other GF keeps its native acquisition path; this is not a giveaway.

Boss labels below are the canonical names from the approved acquisition map.

The native patch does not hard-code that map. Every boss that makes a GF
drawable carries it in its own Draw list as 0x40 + GF index, and the Disc 4
recovery bosses carry the same entries, so the game's own data is the map.
Against FF8_EN.exe SHA-256 064d466b...9570:

- Battle setup (0048BA10) loads up to eight enemies, each with four Draw
  entries at 01D28F18 + enemy x 0x47 + entry x 4 (present when byte
  01D2885C + enemy is non-zero). At 0048BB87, after the last enemy is loaded,
  the patch records each GF entry and blanks it to 0, the value an empty
  Draw slot holds, so no GF can be drawn.
- Victory is decided at 0048655F (`mov byte [01CFF6E7], 4`). There the patch
  awards each recorded GF the save does not already own (exists bit, byte
  01CFDCB9 + GF x 0x44) the way enemy AI awards a GF at battle end (00489E1C):
  call 0047E480(GF), then append the GF to the post-battle list at 01CFF6E4
  (three entries, count at 01D28E17), which drives the native "GF acquired"
  screen. A GF already owned is skipped, so abilities are never reset.
- Escape, defeat and game over never reach the victory write, so they award
  nothing; the record is rebuilt at the next battle's setup.
"""

from __future__ import annotations

TWEAK_NAME = "GF Acquisition Rework"

DEFAULT_GF_ACQUISITION_REWORK = False

GF_ACQUISITION_AVAILABLE = True
GF_ACQUISITION_BLOCKER = ""

CAPTURE_HOOK = 0x0048BB87
CAPTURE_ORIGINAL = bytes.fromhex("BE FC 7D D2 01")  # mov esi, 01D27DFC
CAPTURE_RESUME = 0x0048BB8C
VICTORY_HOOK = 0x0048655F
VICTORY_ORIGINAL = bytes.fromhex("C6 05 E7 F6 CF 01 04")  # mov byte [01CFF6E7], 4
VICTORY_RESUME = 0x00486566
ENEMY_PRESENT = 0x01D2885C  # + enemy (0..7)
ENEMY_DRAW = 0x01D28F18  # + enemy x 0x47 + entry x 4
ENEMY_DRAW_STRIDE = 0x47
ENEMY_COUNT = 8
GF_DRAW_BASE = 0x40
GF_COUNT = 16
GF_EXISTS = 0x01CFDCB9  # + GF x 0x44, bit 0
GF_STRIDE = 0x44
BATTLE_END = 0x01CFF6E7
AWARD_GF = 0x0047E480
AWARD_LIST = 0x01CFF6E4
AWARD_COUNT = 0x01D28E17
AWARD_LIST_SIZE = 3

CAVE = 0x027AB600
CAPTURED = 0x027AB7F0  # one bit per GF seen in this battle's Draw lists

ASSEMBLY = f"""
capture:
    pushad
    mov dword ptr [{CAPTURED:#x}], 0
    xor ebx, ebx
next_enemy:
    cmp byte ptr [ebx + {ENEMY_PRESENT:#x}], 0
    je skip_enemy
    imul esi, ebx, {ENEMY_DRAW_STRIDE}
    add esi, {ENEMY_DRAW:#x}
    mov ecx, 4
next_entry:
    movzx eax, byte ptr [esi]
    sub eax, {GF_DRAW_BASE}
    cmp eax, {GF_COUNT - 1}
    ja keep
    bts dword ptr [{CAPTURED:#x}], eax
    mov byte ptr [esi], 0
keep:
    add esi, 4
    dec ecx
    jnz next_entry
skip_enemy:
    inc ebx
    cmp ebx, {ENEMY_COUNT}
    jb next_enemy
    popad
    mov esi, 0x1d27dfc
    push {CAPTURE_RESUME:#x}
    ret
victory:
    mov byte ptr [{BATTLE_END:#x}], 4
    pushad
    xor ebx, ebx
next_gf:
    bt dword ptr [{CAPTURED:#x}], ebx
    jnc skip_gf
    imul eax, ebx, {GF_STRIDE}
    test byte ptr [eax + {GF_EXISTS:#x}], 1
    jne skip_gf
    push ebx
    call {AWARD_GF:#x}
    add esp, 4
    movzx eax, byte ptr [{AWARD_COUNT:#x}]
    cmp eax, {AWARD_LIST_SIZE}
    jae skip_gf
    mov byte ptr [eax + {AWARD_LIST:#x}], bl
    inc eax
    mov byte ptr [{AWARD_COUNT:#x}], al
skip_gf:
    inc ebx
    cmp ebx, {GF_COUNT}
    jb next_gf
    mov dword ptr [{CAPTURED:#x}], 0
    popad
    push {VICTORY_RESUME:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_gf_acquisition_native.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "60 C7 05 F0 B7 7A 02 00 00 00 00 31 DB 80 BB 5C"
    "88 D2 01 00 74 29 6B F3 47 81 C6 18 8F D2 01 B9"
    "04 00 00 00 0F B6 06 83 E8 40 83 F8 0F 77 0A 0F"
    "AB 05 F0 B7 7A 02 C6 06 00 83 C6 04 49 75 E5 43"
    "83 FB 08 72 C8 61 BE FC 7D D2 01 68 8C BB 48 00"
    "C3 C6 05 E7 F6 CF 01 04 60 31 DB 0F A3 1D F0 B7"
    "7A 02 73 2D 6B C3 44 F6 80 B9 DC CF 01 01 75 21"
    "53 E8 0A 2E CD FD 83 C4 04 0F B6 05 17 8E D2 01"
    "83 F8 03 73 0C 88 98 E4 F6 CF 01 40 A2 17 8E D2"
    "01 43 83 FB 10 72 C4 C7 05 F0 B7 7A 02 00 00 00"
    "00 61 68 66 65 48 00 C3"
)
ENTRY = {
    "capture": 0x027ab600,
    "victory": 0x027ab651,
}

# Drawable in vanilla; awarded on victory while the tweak is on.
PRIMARY_VICTORY = {
    "Siren": "Elvoret",
    "Carbuncle": "Iguion",
    "Leviathan": "NORG",
    "Pandemona": "Fujin",
    "Alexander": "Edea",
    "Eden": "Ultima Weapon",
}

# The game's existing Disc 4 recovery bosses, minus the Draw dependency.
RECOVERY_VICTORY = {
    "Siren": "Tri-Point",
    "Carbuncle": "Krysta",
    "Leviathan": "Trauma",
    "Pandemona": "Red Giant",
    "Alexander": "Catoblepas",
    "Eden": "Tiamat",
}

# Native acquisition paths; the tweak never touches these.
UNCHANGED_GFS = (
    "Quezacotl", "Shiva", "Ifrit", "Brothers", "Diablos", "Cerberus",
    "Doomtrain", "Cactuar", "Tonberry", "Bahamut",
)

DRAWN_GFS = tuple(PRIMARY_VICTORY)
KNOWN_GFS = frozenset(DRAWN_GFS) | frozenset(UNCHANGED_GFS)


def _clean_owned(owned) -> set[str]:
    """Validate an owned-GF collection; reject unknown names."""
    if isinstance(owned, str) or not isinstance(owned, (list, tuple, set, frozenset)):
        raise ValueError("Owned GFs must be a collection of GF names")
    cleaned = set()
    for name in owned:
        if not isinstance(name, str) or name not in KNOWN_GFS:
            raise ValueError(f"Unknown GF: {name!r}")
        cleaned.add(name)
    return cleaned


def _clean_defeated(defeated: str) -> str:
    if isinstance(defeated, bool) or not isinstance(defeated, str) or not defeated:
        raise ValueError("Defeated boss must be a non-empty name")
    return defeated


def awards_for_victory(defeated: str, owned) -> list[str]:
    """Return GFs the victory awards: missing and owed at this boss.

    Unknown bosses award nothing; an unknown encounter must never grant a
    GF. Owned GFs are never re-awarded, so abilities are never reset.
    """
    boss = _clean_defeated(defeated)
    have = _clean_owned(owned)
    awards = []
    for gf in DRAWN_GFS:
        if gf in have:
            continue
        if PRIMARY_VICTORY[gf] == boss or RECOVERY_VICTORY[gf] == boss:
            awards.append(gf)
    return awards


def apply_victory(owned, defeated: str) -> list[str]:
    """Return owned plus the victory awards, preserving owned order.

    Awards only append; nothing is ever removed, so disabling the tweak
    later keeps every legitimately acquired GF.
    """
    boss = _clean_defeated(defeated)
    have = _clean_owned(owned)
    ordered = [name for name in owned if name in have]
    for gf in awards_for_victory(boss, have):
        ordered.append(gf)
    return ordered


def filter_draw_entries(entries: list[dict]) -> list[dict]:
    """Drop GF entries from a Draw list; ordinary spell entries keep order.

    Unknown entry kinds raise instead of passing through: a GF under an
    unrecognized label must not slip back into the Draw results.
    """
    if not isinstance(entries, list):
        raise ValueError("Draw entries must be a list")
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Draw entries must be objects")
        kind = entry.get("kind")
        entry_id = entry.get("id")
        if kind not in ("spell", "gf"):
            raise ValueError(f"Unknown Draw entry kind: {kind!r}")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("Draw entries need a non-empty string id")
        if kind == "spell":
            kept.append(entry)
    return kept


def requirement_errors(*, enabled: bool) -> list[str]:
    """Activation blockers; empty means no objection."""
    if not isinstance(enabled, bool):
        raise ValueError(f"{TWEAK_NAME} must be true or false")
    if not enabled:
        return []
    if not GF_ACQUISITION_AVAILABLE:
        return [GF_ACQUISITION_BLOCKER]
    return []


def _assemble() -> tuple[bytes, dict[str, int]]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])
    entry = {}
    for name in ("capture", "victory"):
        probe = ASSEMBLY.split(f"\n{name}:")[0] + f"\n{name}:\n nop"
        entry[name] = CAVE + len(ks.asm(probe, CAVE)[0]) - 1
    return code, entry


def _jump(site: int, target: int) -> bytes:
    return b"\xE9" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def build_hext(enabled: bool) -> str:
    """Return the Hext fragment, or nothing when the tweak is off."""
    errors = requirement_errors(enabled=enabled)
    if errors:
        raise ValueError(errors[0])
    if not enabled:
        return ""
    return "\n".join((
        "# GF Acquisition Rework: GFs leave the Draw lists and are awarded on victory.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{CAPTURED:X}:4",
        f"{CAPTURED:X} = 00 00 00 00",
        f"{CAPTURE_HOOK:X} = {_jump(CAPTURE_HOOK, ENTRY['capture']).hex(' ').upper()}",
        f"{VICTORY_HOOK:X} = {(_jump(VICTORY_HOOK, ENTRY['victory']) + bytes.fromhex('90 90')).hex(' ').upper()}",
        "",
    ))


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(CAPTURE_HOOK, CAPTURE_ORIGINAL), (VICTORY_HOOK, VICTORY_ORIGINAL)]
