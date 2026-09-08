from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"unexpected context in {path}: {old[:100]!r}"
    p.write_text(text.replace(old, new), encoding="utf-8")

ff8 = "games/ff8/editor.html"
replace_once(
    ff8,
    ".lex-info-help{font-family:var(--lex-font)!important;font-size:13px!important;line-height:1!important;text-shadow:none!important}",
    ".lex-info-help{font-family:var(--lex-symbol-font)!important;font-size:13px!important;line-height:1!important;text-shadow:none!important}",
)
replace_once(
    ff8,
    "    .lex-info-help>span{transform:translate(.08em,.05em)}\n",
    "",
)

verifier = "tools/verify_shared_ui_contract.py"
p = Path(verifier)
s = p.read_text(encoding="utf-8")
needle = '''        require(not family or "--lex-symbol-font" in family.group(1),\n                f"{relative} overrides info-bubble glyph typography with a game font")\n\n'''
addition = '''        require(not family or "--lex-symbol-font" in family.group(1),\n                f"{relative} overrides info-bubble glyph typography with a game font")\n    for block in re.findall(r"\\.lex-info-help\\s*>\\s*span\\s*\\{([^}]*)\\}", source, re.I | re.S):\n        require(not re.search(r"(?:transform|translate|top|bottom|left|right|font-family)\\s*:", block, re.I),\n                f"{relative} overrides shared info-bubble glyph geometry")\n\n'''
assert s.count(needle) == 1, "shared UI verifier info-bubble contract drifted"
p.write_text(s.replace(needle, addition), encoding="utf-8")

Path(".github/workflows/global-56-ff8-cleanup-one-shot.yml").unlink()
Path(__file__).unlink()
