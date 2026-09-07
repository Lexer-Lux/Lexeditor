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


edit("games/warband/editor.html", clean_warband)
