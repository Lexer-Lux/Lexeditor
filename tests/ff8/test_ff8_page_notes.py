"""FF8 pages print a note only for a state the reader must act on.

AGENTS.md: necessary information belongs in the question-mark help, not in a
paragraph on the page; a visible note is only for a state such as an error,
a missing file, an empty table or something to switch on. Lexer, 2026-09-27,
on "This table names 72 positions. Rinoa's Toolset edits the same table..."
printed on World > World to Field: "what is it with the random graffiti
everywhere?" - a verifier for this had been promised and never existed.

Every detailNote call in the FF8 pages is listed here by the start of what it
prints. A new one fails until it is reviewed: if it is information, it goes in
a help bubble; if it is a state to act on, it is added to this list.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# States the reader acts on: missing or unreadable data, errors, read-only
# reasons, empty results, and settings to switch on. The start of each call.
ALLOWED = {
    "row.note)",
    '"No mod replaces this sound."',
    "state.data.sfx.configError)",
    '"FFNx external SFX are off, so the game ignores replacements. Turn on',
    '"Only PNG mod textures can be previewed."',
    '"No mod replaces this texture."',
    '"World geometry is unavailable."',
    "blocker)",
    '"")',
    '"RANDOM = 240 to 272")',
    "`INCOMPLETE: ${formula.blocker}`)",
    "settings.formulaeReworkBlocker",
    "'Location data is unavailable.')",
    "`Could not load opponent: ${map._error}`)",
    "`No other CARDGAME call in the game data names deck ${deck}.`)",
    "'No players match this search.')",
    '"Enable GF Spellbooks on the Tweaks page.")',
    '"GF Spellbooks needs Monogamy on and Shared Party Magic Inventory off.',
    "error.message)",
    "'No initial state for this GF.')",
    "'This enemy has no battle-script section.')",
    '"This enemy has no battle-script section.")',
    '"This enemy has no local battle dialogue.")',
    "`${method.groupType.toLocaleUpperCase()} GROUP ${method.groupId}",
    '"This method has an unknown opcode or a branch outside the method, so',
    "background?.error?`This background is read-only: ${background.error}`:",
    "mesh?.error?`This walkmesh is read-only: ${mesh.error}`:",
    "row.camera?.error?`These cameras are read-only: ${row.camera.error}`:",
    "row.movie?.error?`These movie frames are read-only: ${row.movie.error}`",
    'row.unsupported.join(" / ")',
}

# Information that was printed on the page and now lives in help bubbles.
MOVED_TO_HELP = (
    "This table names 72 positions",
    "Rinoa's Toolset edits the same table",
    "is stored in FF8_EN.exe, so it is not edited here",
    "A hit rate of 255 receives no bypass",
    "requested runtime formulae are implemented",
    "This INF variant does not store PVP",
    "Click the map to place this record",
)


def _notes():
    for path in sorted((ROOT / "plugins/ff8").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"detailNote\(", text):
            yield path.name, text[match.end():match.end() + 90].split("\n")[0]


def test_every_ff8_page_note_is_a_state_to_act_on():
    unreviewed = [(name, start) for name, start in _notes()
                  if not any(start.startswith(allowed) for allowed in ALLOWED)]
    assert not unreviewed, (
        "A page note must be a state the reader acts on. Put information in a help "
        f"bubble, or add a reviewed state to ALLOWED: {unreviewed}")


def test_moved_information_stays_off_the_page():
    pages = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "plugins/ff8").glob("*.js"))
    back = [text for text in MOVED_TO_HELP if text in pages]
    assert not back, back
