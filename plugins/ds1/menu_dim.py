"""Dimmed talk-list options: gray, unselectable rows any DS1 mod can ask for.

Bonfire menus and NPC dialogue lists share one retail list (F04). Its row
drawing already resolves a grayout_drop%d node and passes a dim switch to it
(RVA 0x66B1C8: `movzx edx, sil` picks the switch, then `mov rcx, rax`), but
talk scripts have no command that sets that switch: AddTalkListData's flag
omits a row rather than disabling it. Confirmation (RVA 0x66B477: `mov eax,
[rdx+4]; xor edx, edx` reads the chosen row's result) accepts any existing
row, so gray alone would still be selectable.

A mod therefore marks a row by its text: it builds `menu-dim/<id>.json`,
{"version": 1, "textIds": [message IDs]}, and its talk script shows one of
those IDs exactly when the option is unavailable (an affordable or allowed
option uses a different ID). Lexeditor owns the two detours and combines
every enabled mod's IDs into one table, so mods never hook these
instructions themselves, which the patch composer would refuse as a
collision. A row whose text ID is in the table draws dimmed and rejects
confirmation before the list publishes a result, closes, or plays its
confirm sound. Other rows, and the list's own dimming of empty rows, are
unchanged.
"""
from __future__ import annotations

FOLDER = "menu-dim"
VERSION = 1
OWNER = "Lexeditor dimmed talk options"
MAX_IDS = 4096

DRAW_RVA = 0x66B1C8
DRAW_ORIGINAL = "400fb6d6488bc8"
DRAW_CONTINUE = 0x66B1CF
SELECT_RVA = 0x66B477
SELECT_ORIGINAL = "8b420433d2"
SELECT_CONTINUE = 0x66B47C
SELECT_REJECT = 0x66B4A4

# Both detours scan the table that follows the code, ending at -1 (no
# message has that ID). Draw (offset 0): RDI is the row ({text ID, result})
# or null for an unused row; EDX becomes the dim switch. Select (offset 51):
# RDX is the chosen row; RAX and RCX are restored on both paths. Assembled
# from this source; keep them in step:
#   draw:   pushfq; test rdi, rdi; jz plain; mov edx, [rdi]; lea rcx, [table]
#   dloop:  cmp dword [rcx], -1; je plain; cmp [rcx], edx; je dim
#           add rcx, 4; jmp dloop
#   dim:    popfq; mov edx, 1; jmp tail
#   plain:  popfq; movzx edx, sil
#   tail:   mov rcx, rax; jmp DRAW_CONTINUE
#   select: pushfq; push rax; push rcx; mov eax, [rdx]; lea rcx, [table]
#   sloop:  cmp dword [rcx], -1; je accept; cmp [rcx], eax; je reject
#           add rcx, 4; jmp sloop
#   accept: pop rcx; pop rax; popfq; mov eax, [rdx+4]; xor edx, edx
#           jmp SELECT_CONTINUE
#   reject: pop rcx; pop rax; popfq; jmp SELECT_REJECT
CODE = bytes.fromhex(
    "9c4885ff74208b17488d0d540000008339ff7412391174064883c104ebf19dba01000000"
    "eb059d400fb6d64889c1e900000000"
    "9c50518b02488d0d240000008339ff740a390174134883c104ebf159589d8b420431d2"
    "e90000000059589de900000000")
SELECT_OFFSET = 51
RELOCATIONS = ((47, DRAW_CONTINUE), (87, SELECT_CONTINUE), (95, SELECT_REJECT))
END = 0xFFFFFFFF


def validate(value, owner: str) -> dict:
    """One mod's built menu-dim description, normalised."""
    if not isinstance(value, dict) or value.get("version") != VERSION or set(value) != {"version", "textIds"}:
        raise ValueError(f'{owner}: {FOLDER} files are {{"version": {VERSION}, "textIds": [...]}}')
    ids = value["textIds"]
    if (type(ids) is not list or len(ids) > MAX_IDS
            or any(type(rid) is not int or not 0 <= rid < END for rid in ids)):
        raise ValueError(f"{owner}: textIds must list up to {MAX_IDS} message IDs")
    return {"owner": owner, "textIds": sorted(set(ids))}


def patch_spec(specs: list[dict]) -> dict | None:
    """The loader's detours over every mod's IDs; None when no mod dims anything."""
    ids = sorted({rid for spec in specs for rid in spec["textIds"]})
    if not ids:
        return None
    if len(ids) > MAX_IDS:
        raise ValueError(f"Enabled mods dim more than {MAX_IDS} talk options together")
    table = b"".join(rid.to_bytes(4, "little") for rid in ids) + END.to_bytes(4, "little")
    return {"version": 2,
            "islands": [{"name": "menu-dim", "code": (CODE + table).hex(), "functions": [],
                         "relocations": [{"at": at, "rel32": target} for at, target in RELOCATIONS]}],
            "hooks": [{"rva": DRAW_RVA, "original": DRAW_ORIGINAL, "pad": "9090",
                       "branch": {"opcode": "E9", "island": "menu-dim", "offset": 0}},
                      {"rva": SELECT_RVA, "original": SELECT_ORIGINAL, "pad": "",
                       "branch": {"opcode": "E9", "island": "menu-dim", "offset": SELECT_OFFSET}}]}
