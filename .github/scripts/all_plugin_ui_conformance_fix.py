from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def edit(path: str, transform) -> None:
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        target.write_text(updated, encoding="utf-8", newline="\n")


def fix_ff8(text: str) -> str:
    # FF8 already routes ordinary fields through shared detailField(), but these
    # old theme rules were still overriding the shared geometry contract.
    text = text.replace('.field-row{display:contents}', '')
    text = text.replace('.lex-detail-panel{--lex-detail-label-width:max(125px,15%)}',
                        '.lex-detail-panel{--lex-detail-label-width:10%}')
    text = text.replace('.ff8-character-curve:not(.ff8-enemy-curve){grid-template-columns:minmax(0,1fr) minmax(150px,16%)}', '')
    text = text.replace('color:#fff;font-size:22px}', 'color:#fff}', 1)
    # Editable is a cell/column capability, never a separate Table type.
    text = text.replace('.lex-editable-table', '.lex-column-list')
    return text


def fix_rdr(text: str) -> str:
    old_import = 'const {el,list,pagedListDetail,pager,provenanceControl,clone,showAlert}=LexeditorUI;'
    new_import = 'const {el,list,pagedListDetail,pager,provenanceControl,clone,showAlert,detailField:sharedDetailField,infoHelp}=LexeditorUI;'
    text = text.replace(old_import, new_import, 1)
    old = 'function detailField(label,value,help=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return el("div",{class:"detail-field"},el("div",{class:"detail-label"},label,help?LexeditorUI.infoHelp(help):null),el("div",{class:"detail-control"},control));}'
    new = 'function detailField(label,value,help=""){const control=value instanceof Node?value:el("span",{},String(value??"—"));return sharedDetailField({label,control,help:help?infoHelp(help):null});}'
    text = text.replace(old, new, 1)
    return text


def fix_rdr2(text: str) -> str:
    old = '''  const field=(label,cell,help)=>{\n    const control=controlFor(cell);\n    return el("div",{class:"detail-field"},\n      el("div",{class:"detail-label"},label,help?fieldHelp(help):""),control);\n  };'''
    new = '''  const field=(label,cell,help)=>{\n    const control=controlFor(cell);\n    return LexeditorUI.detailField({label,control,help:help?LexeditorUI.infoHelp(help):null});\n  };'''
    text = text.replace(old, new, 1)

    old2 = '''  const field=(label,control,help="")=>el("div",{class:"detail-field"},\n    el("div",{class:"detail-label"},label,help?fieldHelp(help):""),el("div",{class:"detail-control"},control));'''
    new2 = '''  const field=(label,control,help="")=>LexeditorUI.detailField({\n    label,control,help:help?LexeditorUI.infoHelp(help):null\n  });'''
    text = text.replace(old2, new2, 1)

    old3 = '''  pane.append(el("div",{class:"detail-field"},el("div",{class:"detail-label"},"Used by"),\n    el("div",{class:"detail-control"},usage.childElementCount?usage:el("span",{class:"cat"},"No effects"))));'''
    new3 = '''  pane.append(LexeditorUI.detailField({label:"Used by",\n    control:usage.childElementCount?usage:el("span",{class:"cat"},"No effects")}));'''
    text = text.replace(old3, new3, 1)
    return text


def centralize_plugin_github(text: str) -> str:
    match = re.search(r'plugin_id\s*=\s*["\']([^"\']+)["\']', text)
    if not match or 'github=GitHubRepository(' not in text:
        return text
    plugin_id = match.group(1)
    pattern = re.compile(
        r'github=GitHubRepository\(\s*full_name=["\'][^"\']+["\']\s*,\s*'
        r'authorized_logins=\(["\']Lexer-Lux["\']\s*,?\)\s*,?\s*'
        r'(?:issue_label=["\'][^"\']+["\']\s*,?\s*)?\)', re.S)
    replacement = (f'github=GitHubRepository(\n'
                   f'        full_name="Lexer-Lux/Lexeditor",\n'
                   f'        authorized_logins=("Lexer-Lux",),\n'
                   f'        issue_label="{plugin_id}",\n'
                   f'    )')
    return pattern.sub(replacement, text, count=1)


edit("games/ff8/editor.html", fix_ff8)
edit("games/rdr/editor.html", fix_rdr)
edit("games/rdr2/editor.html", fix_rdr2)

for plugin in sorted((ROOT / "games").glob("*/plugin.py")):
    original = plugin.read_text(encoding="utf-8")
    updated = centralize_plugin_github(original)
    if updated != original:
        plugin.write_text(updated, encoding="utf-8", newline="\n")
