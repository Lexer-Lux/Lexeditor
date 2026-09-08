from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"unexpected context in {path}: {old[:100]!r}"
    p.write_text(text.replace(old, new), encoding="utf-8")

# FF8 was still explicitly re-inheriting its game font for the shared info bubble,
# defeating the shared glyph centering fix even though Blank passed.
replace_once(
    "games/ff8/editor.html",
    "      font-family:var(--lex-font)!important;\n",
    "      font-family:var(--lex-symbol-font)!important;\n",
)

# Any game editor can regress shared chrome, so every editor shell must now run
# the shared contract job, not only Blank and Warband.
workflow = ".github/workflows/shared-ui-contract.yml"
p = Path(workflow)
s = p.read_text(encoding="utf-8")
old = "      - 'games/blank/**'\n      - 'games/warband/editor.html'\n"
assert s.count(old) == 2, "shared-ui workflow path contract drifted"
s = s.replace(old, "      - 'games/**/editor.html'\n")
p.write_text(s, encoding="utf-8")

verifier = "tools/verify_shared_ui_contract.py"
p = Path(verifier)
s = p.read_text(encoding="utf-8")
needle = '''blank = text("games/blank/editor.html")\nwarband = text("games/warband/editor.html")\n\n'''
addition = '''blank = text("games/blank/editor.html")\nwarband = text("games/warband/editor.html")\n\n# Shared chrome is global by construction. Every real editor shell must load the\n# shared framework, and a game theme may not swap the info-bubble glyph back to\n# its own game font. This is what keeps Blank fixes from becoming Blank-only.\nplugin_editors = sorted((ROOT / "games").glob("*/editor.html"))\nrequire(plugin_editors, "no game editor shells were found")\nfor editor_path in plugin_editors:\n    source = editor_path.read_text(encoding="utf-8")\n    relative = editor_path.relative_to(ROOT).as_posix()\n    require('/shared/framework.css' in source and '/shared/framework.js' in source,\n            f"{relative} is bypassing the shared UI framework")\n    require("Lexer Mode" not in source and "lexerMode" not in source,\n            f"legacy Lexer Mode leaked into {relative}")\n    for block in re.findall(r"\\.lex-info-help\\s*\\{([^}]*)\\}", source, re.I | re.S):\n        family = re.search(r"font-family\\s*:\\s*([^;]+)", block, re.I)\n        require(not family or "--lex-symbol-font" in family.group(1),\n                f"{relative} overrides info-bubble glyph typography with a game font")\n\n'''
assert s.count(needle) == 1, "shared UI verifier prelude drifted"
p.write_text(s.replace(needle, addition), encoding="utf-8")

Path(".github/workflows/global-56-cross-plugin-one-shot.yml").unlink()
Path(__file__).unlink()
