"""Guarded native GF spellbook hooks for the supported English FF8 build.

Native x86 tests cover the hook chain. Live battle acceptance remains separate.
No functions here mutate a game or project.
"""
from hashlib import sha256
from . import gf_spellbooks as model
from . import gf_spellbooks_native_asm as layout
from .gf_spellbooks_native_code import CODE

SUPPORTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
RUNTIME_READY = False
HOOKS = (
    (0x4C8820, bytes.fromhex("8b4424048d0cc500000000"), layout.CALLBACK),
    (0x4FE71B, bytes.fromhex("4283c1053bd67cdc"), layout.DEBIT),
    (0x4C8A0C, bytes.fromhex("8a4601bb07000000"), layout.ROW),
    (0x4C8A47, bytes.fromhex("83c41c85db7422"), layout.NUMBER),
    (0x4C8A68, bytes.fromhex("e803abfdff"), layout.COLOR_NUMBER),
    (0x4FDEB4, bytes.fromhex("8bc3881df068d701"), layout.EXTENT),
)


def verify_executable(raw):
    if sha256(raw).hexdigest() != SUPPORTED_EXE:
        raise model.SpellbookError("GF spellbooks require the verified English FF8 executable")
    for site, original, _target in HOOKS:
        if raw[site-0x400000:site-0x400000+len(original)] != original:
            raise model.SpellbookError("GF spellbook hook does not match the verified executable")


def candidate_fragments(document, *, monogamy, shared_magic):
    """Return code/data fragments; the caller owns composition and installation."""
    if monogamy is not True or shared_magic is not False:
        raise model.SpellbookError("This spellbook candidate requires Monogamy and Shared Magic off")
    checked = model.validate(document)
    definitions = bytearray(1024)
    pages = bytearray(16)
    for book in checked["books"]:
        gf = book["gfId"]
        if not 1 <= len(book["pages"]) <= 8 or any(len(page) > 4 for page in book["pages"]):
            raise model.SpellbookError("The native candidate supports one to eight pages, at most four spells per page")
        pages[gf] = len(book["pages"])
        for page_index, page in enumerate(book["pages"]):
            for index, slot in enumerate(page):
                offset = gf*64 + (page_index*4+index)*2
                definitions[offset] = slot["magicId"]
                definitions[offset+1] = 255 if slot["abilityId"] is None else slot["abilityId"]
    fragments = {address: bytes.fromhex(code) for address, code in CODE.items()}
    fragments.update({layout.DEFS: bytes(definitions), layout.PAGES: bytes(pages), layout.VIEWS: bytes(480), layout.MAPS: bytes(384), layout.ACTIVE: bytes(3), layout.PAGE_COUNTS: bytes(3)})
    for site, original, target in HOOKS:
        fragments[site] = (b"\xe8" if site == 0x4C8A68 else b"\xe9") + (target-site-5).to_bytes(4,"little",signed=True) + b"\x90"*(len(original)-5)
    return fragments


def build_hext(document, *, monogamy, shared_magic, executable):
    """Generate a verified patch; the caller owns composition and installation."""
    raise model.SpellbookError("GF spellbooks need loader-owned memory; the proposed cave overlaps executable resources")
    verify_executable(executable)
    fragments = candidate_fragments(document, monogamy=monogamy, shared_magic=shared_magic)
    if not model.validate(document)["books"]:
        return ""
    rows = ["# GF spellbooks: ordered pages with stock and learned-ability gates.",
            f"{layout.BASE:X}:2000"]
    rows.extend(f"{address:X} = {data.hex(' ').upper()}" for address, data in sorted(fragments.items()))
    return "\n".join(rows) + "\n"
