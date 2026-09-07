"""Structural regression audit for every Lexeditor game UI.

Blank is the canonical gallery and ui/framework.* owns shared interaction and
geometry. Game editors may theme shared primitives, but they must not quietly
recreate old property/table/GitHub systems that stop inheriting framework fixes.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "games"


def read(path: Path | str) -> str:
    p = path if isinstance(path, Path) else ROOT / path
    return p.read_text(encoding="utf-8")


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


editors = sorted(GAMES.glob("*/editor.html"))
require(editors, "no game editors found")

for editor in editors:
    game = editor.parent.name
    text = read(editor)
    require('/shared/framework.css' in text, f"{game}: editor does not load shared framework CSS")
    require('/shared/framework.js' in text, f"{game}: editor does not load shared framework JS")
    require('mountShell(' in text, f"{game}: editor bypasses the shared shell")
    for dead in ("lexerMode", "Editable Table", "editableTablePanel", "lex-editable-table", "design-review"):
        require(dead not in text, f"{game}: legacy UI concept remains: {dead}")

# The host owns one issue tracker. Every game workspace must be the central
# Lexeditor repository with the plugin id as its canonical label filter.
host = read("desktop_host.py")
require("full_name=LEXEDITOR_REPOSITORY.full_name" in host, "host no longer centralizes GitHub issues")
require("issue_label=plugin_id" in host, "host no longer scopes GitHub issues by plugin")
for plugin in sorted(GAMES.glob("*/plugin.py")):
    text = read(plugin)
    marker = "github=GitHubRepository("
    if marker not in text:
        continue
    match = re.search(r'plugin_id\s*=\s*["\']([^"\']+)["\']', text)
    require(bool(match), f"{plugin.parent.name}: cannot determine plugin id")
    game = match.group(1)
    start = text.index(marker)
    block = text[start:start + 600]
    require('full_name="Lexer-Lux/Lexeditor"' in block,
            f"{game}: plugin metadata still points its GitHub button at another repository")
    require(f'issue_label="{game}"' in block,
            f"{game}: plugin metadata does not filter the central tracker by game")

# FF8 already uses shared detailField()/detailSection(). Old theme geometry was
# defeating those primitives, so these are specifically forbidden regressions.
ff8 = read("games/ff8/editor.html")
require("--lex-detail-label-width:max(125px,15%)" not in ff8,
        "ff8: property-name lane regressed to 15%")
require(".field-row{display:contents}" not in ff8,
        "ff8: shared detail fields are being flattened with display:contents")
require(".ff8-character-curve:not(.ff8-enemy-curve){grid-template-columns" not in ff8,
        "ff8: curve variables are forced back into a right-hand column")
require('detailField({className:"gf-field-row"' in ff8,
        "ff8: GF properties are not routed through shared detailField")

# RDR1 and RDR2 historically implemented private detail/property rows. Their
# adapters must now produce the shared field primitive so label width, info
# bubbles, semantic Boolean behavior, hover and reset feedback are inherited.
rdr = read("games/rdr/editor.html")
require("detailField:sharedDetailField" in rdr and "return sharedDetailField({label,control" in rdr,
        "rdr: record properties bypass shared detailField")
rdr2 = read("games/rdr2/editor.html")
require("return LexeditorUI.detailField({label,control" in rdr2,
        "rdr2: item properties bypass shared detailField")
require('const field=(label,control,help="")=>LexeditorUI.detailField({' in rdr2,
        "rdr2: effect properties bypass shared detailField")
require('LexeditorUI.detailField({label:"Used by"' in rdr2,
        "rdr2: behavior properties bypass shared detailField")

# Shared terminology/semantic representation is documentation, not a Blank-only
# convention.
manual = read("docs/UI-MANUAL.md").casefold()
for phrase in ("info bubble", "ref rail", "checkless toggle", "human-friendly"):
    require(phrase in manual, f"UI manual missing shared term/rule: {phrase}")

print("all-plugin UI contract audit passed for:", ", ".join(p.parent.name for p in editors))
