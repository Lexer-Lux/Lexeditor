from pathlib import Path
import re


def sub_once(path: str, pattern: str, replacement: str, flags=0) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    assert count == 1, f"unexpected context in {path}: {pattern[:120]!r}"
    p.write_text(updated, encoding="utf-8")


rdr = "games/rdr/editor.html"

# Stop RDR1 from rebuilding generic Detail rows with a fixed 180px private lane.
# Keep only RDR-themed paint on the shared row/control classes; shared geometry,
# metadata rail, help placement, pinning and future fixes stay framework-owned.
sub_once(
    rdr,
    r'''\.detail-field\{display:grid;grid-template-columns:180px minmax\(0,1fr\);gap:12px;align-items:start;padding:9px 4px;border-bottom:1px solid #2a2419\}\.detail-label\{padding-top:5px;color:var\(--lex-highlight\);font-size:13px;letter-spacing:\.4px;text-transform:uppercase\}\.detail-label small\{display:block;margin-top:3px;color:var\(--lex-muted\);font-size:10px;letter-spacing:0;text-transform:none\}\.detail-control\{min-width:0;color:var\(--lex-text\)\}\.detail-control code\{display:block;overflow:hidden;color:#d8c7b0;text-overflow:ellipsis;white-space:nowrap\}\.detail-control input:not\(\[type=checkbox\]\),\.detail-control select\{width:100%;min-width:0;padding:7px 8px;color:var\(--lex-text\);border:1px solid #5b4b3d;background:#29241f\}\.detail-control input\[type=checkbox\]\{width:18px;height:18px;accent-color:var\(--lex-accent\)\}''',
    '''.record-detail .lex-detail-field{border-bottom:1px solid #2a2419}.record-detail .lex-detail-field-label{color:var(--lex-highlight);font-size:13px;letter-spacing:.4px;text-transform:uppercase}.record-detail .lex-detail-field-label small{display:block;margin-top:3px;color:var(--lex-muted);font-size:10px;letter-spacing:0;text-transform:none}.record-detail .lex-detail-field-control{min-width:0;color:var(--lex-text)}.record-detail .lex-detail-field-control code{display:block;overflow:hidden;color:#d8c7b0;text-overflow:ellipsis;white-space:nowrap}.record-detail .lex-detail-field-control input:not([type=checkbox]),.record-detail .lex-detail-field-control select{width:100%;min-width:0;padding:7px 8px;color:var(--lex-text);border:1px solid #5b4b3d;background:#29241f}.record-detail .lex-detail-field-control input[type=checkbox]{width:18px;height:18px;accent-color:var(--lex-accent)}''',
)
sub_once(
    rdr,
    r'''@media\(max-width:900px\)\{header\{grid-template-columns:1fr\}nav\{justify-content:flex-start\}\.header-actions\{position:absolute;right:12px;top:8px\}#toolbar input\{min-width:180px\}\.detail-field\{grid-template-columns:140px minmax\(0,1fr\)\}\}''',
    '''@media(max-width:900px){header{grid-template-columns:1fr}nav{justify-content:flex-start}.header-actions{position:absolute;right:12px;top:8px}#toolbar input{min-width:180px}}''',
)

# Delegate the plugin helper to the shared Detail primitive. A string belongs in
# `description`; `help` is the already-rendered Element slot in the shared API.
sub_once(
    rdr,
    r'''function detailField\(label,value,help=""\)\{const control=value instanceof Node\?value:el\("span",\{\},String\(value\?\?"—"\)\);return el\("div",\{class:"detail-field"\},el\("div",\{class:"detail-label"\},label,help\?LexeditorUI\.infoHelp\(help\):null\),el\("div",\{class:"detail-control"\},control\)\);\}''',
    '''function detailField(label,value,help=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return LexeditorUI.detailField({label,control,description:help||""});}''',
)

# XML storage mechanics are not semantic help. If we do not know a useful game
# consequence for an arbitrary imported field, show no circular info bubble.
sub_once(
    rdr,
    r'''\.\.\.item\.fields\.map\(field=>detailField\(field\.field,scalarControl\(item,field\),field\.storage==="value"\?"XML value attribute":"XML text"\)\)''',
    '''...item.fields.map(field=>detailField(field.field,scalarControl(item,field)))''',
)

# Mission reward bubbles explain the independent game consequence, while the
# input and Vanilla ref rail continue to expose bounds/current baseline normally.
sub_once(
    rdr,
    r'''const MISSION_REWARDS=\[\n    \{key:"cash",label:"Cash reward"\},\{key:"fame",label:"Fame reward"\},\{key:"honor",label:"Honor reward"\}\n  \];''',
    '''const MISSION_REWARDS=[\n    {key:"cash",label:"Cash reward",help:"Changes the cash awarded when this mission completes; it does not alter prices, pickups, or other missions."},\n    {key:"fame",label:"Fame reward",help:"Changes this mission's completion Fame award independently of its cash and Honor rewards."},\n    {key:"honor",label:"Honor reward",help:"Changes this mission's completion Honor adjustment independently of its cash and Fame rewards."}\n  ];''',
)
sub_once(
    rdr,
    r'''`Base value: \$\{mission\.baseRewards\[reward\.key\]\}\. Integer range \$\{rewardLimits\.minimum\} to \$\{rewardLimits\.maximum\}\.`''',
    '''reward.help''',
)

# Strengthen the semantic-help audit so it covers every plugin editor, including
# plugin-local wrapper functions rather than a hand-maintained game list.
test = "tests/test_info_bubble_semantics.py"
p = Path(test)
s = p.read_text(encoding="utf-8")
s = s.replace(
    'ROOT = Path(__file__).resolve().parents[1]\n',
    'ROOT = Path(__file__).resolve().parents[1]\nPLUGIN_EDITORS = sorted((ROOT / "games").glob("*/editor.html"))\n',
    1,
)
s = s.replace(
    '''    sources = "\\n".join(text(path) for path in (\n        "games/blank/editor.html", "games/ff7/editor.html", "games/ff8/editor.html",\n        "games/ff9/editor.html", "games/rdr/editor.html", "games/rdr2/editor.html",\n    ))\n''',
    '''    sources = "\\n".join(path.read_text("utf-8") for path in PLUGIN_EDITORS)\n''',
    1,
)
assert 'PLUGIN_EDITORS = sorted' in s and 'path.read_text("utf-8") for path in PLUGIN_EDITORS' in s
if 'def test_rdr_uses_shared_detail_fields_and_semantic_reward_help():' not in s:
    s += '''\n\ndef test_rdr_uses_shared_detail_fields_and_semantic_reward_help():\n    rdr = text("games/rdr/editor.html")\n    helper = rdr[rdr.index("function detailField"):rdr.index("function applyControlValue")]\n    assert "LexeditorUI.detailField({label,control,description:help||\\\"\\\"})" in helper\n    assert 'class:"detail-field"' not in helper\n    assert "XML value attribute" not in rdr\n    assert '"XML text"' not in rdr\n    assert "Base value:" not in rdr\n    assert "Integer range" not in rdr\n    for phrase in (\n        "Changes the cash awarded when this mission completes",\n        "completion Fame award independently",\n        "completion Honor adjustment independently",\n    ):\n        assert phrase in rdr\n    # RDR theming may paint shared rows, but it may not restore a plugin-owned\n    # fixed label lane or the legacy private generic Detail-row classes.\n    assert ".detail-field{display:grid" not in rdr\n    assert ".detail-field{grid-template-columns" not in rdr\n    assert ".record-detail .lex-detail-field-label" in rdr\n'''
p.write_text(s, encoding="utf-8")

# Fail closed before the one-shot transport removes itself.
final = Path(rdr).read_text(encoding="utf-8")
assert 'function detailField(label,value,help=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return LexeditorUI.detailField({label,control,description:help||""});}' in final
assert "XML value attribute" not in final
assert '"XML text"' not in final
assert "Base value:" not in final
assert "Integer range" not in final
assert ".detail-field{grid-template-columns" not in final

Path(".github/workflows/global-349-one-shot.yml").unlink()
Path(__file__).unlink()
