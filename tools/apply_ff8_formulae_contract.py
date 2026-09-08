"""One-shot guarded repair for Formulae Rework contract name shadowing."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one integration seam, found {count}")
    return text.replace(old, new, 1)


def patch_settings() -> None:
    path = ROOT / "games/ff8/gameplay_settings.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from . import formulae_rework\n",
        "from . import formulae_rework as formulae_rework_contract\n",
        "formulae contract import alias",
    )
    text = replace_once(
        text,
        "    if not formulae_rework.available():\n        formulae_rework = False\n",
        "    if not formulae_rework_contract.available():\n        formulae_rework = False\n",
        "load availability gate",
    )
    text = replace_once(
        text,
        '        "formulaeReworkAvailable": formulae_rework.available(),\n'
        '        "formulaeReworkFormulas": formulae_rework.rows(),\n',
        '        "formulaeReworkAvailable": formulae_rework_contract.available(),\n'
        '        "formulaeReworkFormulas": formulae_rework_contract.rows(),\n',
        "load contract payload",
    )
    text = replace_once(
        text,
        '    if formulae_rework and not formulae_rework.available():\n'
        '        missing = ", ".join(formulae_rework.incomplete_ids())\n',
        '    if formulae_rework and not formulae_rework_contract.available():\n'
        '        missing = ", ".join(formulae_rework_contract.incomplete_ids())\n',
        "save availability gate",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    patch_settings()
    print("Fixed FF8 Formulae Rework contract name shadowing")
