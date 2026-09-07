from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def edit(path: str, transform):
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        target.write_text(updated, encoding="utf-8", newline="\n")


def clean_warband(text: str) -> str:
    # The shared model-preview drawer owns the open/close action now. These
    # selectors were left behind when Warband migrated and could make a future
    # local preview button accidentally inherit obsolete behavior.
    text = text.replace('.warband-item-preview-action{display:grid;width:38px;height:38px;place-items:center;color:#651919;border:1px solid #8b6b39;background:#f4e7c5;cursor:pointer}', '')
    text = text.replace('.warband-item-preview-action:disabled{opacity:.45;cursor:default}', '')
    return text


def unify_table_editing_js(text: str) -> str:
    old = 'class: ["lex-column-list", options.editable ? "lex-editable-table" : "", options.class || ""].filter(Boolean).join(" "),'
    new = 'class: ["lex-column-list", options.class || ""].filter(Boolean).join(" "),'
    if old in text:
        text = text.replace(old, new, 1)
    return text


def unify_table_editing_css(text: str) -> str:
    # Editing is a per-cell/column capability. Any actual input/select/textarea
    # inside a Table receives the same geometry and focus treatment; there is no
    # separate Editable Table presentation mode.
    return text.replace('.lex-editable-table', '.lex-column-list')


edit("games/warband/editor.html", clean_warband)
edit("ui/framework.js", unify_table_editing_js)
edit("ui/framework.css", unify_table_editing_css)
