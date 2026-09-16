"""Which plugins use each shared UI component.

Generated rather than maintained: Blank's component catalogue shows it, so it
has to be a fact about the code instead of a list someone remembers to update.
Run with --check in tests to prove the committed copy still matches.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ui" / "component-usage.json"


def exports() -> list[str]:
    source = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    block = source[source.index("window.LexeditorUI = {"):]
    block = block[:block.index("};")]
    names = []
    for piece in block.split(","):
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::|$)", piece)
        if match and match.group(1) not in names:
            names.append(match.group(1))
    return sorted(names)


def usage() -> dict[str, list[str]]:
    names = exports()
    found: dict[str, set[str]] = {name: set() for name in names}
    sources = [(plugin.name, plugin) for plugin in sorted((ROOT / "games").iterdir()) if plugin.is_dir()]
    # The component catalogue is rendered by Blank, so a component with a sample
    # there is one Blank shows, whoever wrote the file.
    sources.append(("blank", ROOT / "ui" / "component-catalog.js"))
    for name, plugin in sources:
        for path in ([plugin] if plugin.is_file() else sorted(plugin.rglob("*"))):
            if path.suffix.lower() not in (".html", ".js") or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            # Both spellings a plugin can use: LexeditorUI.name(, and the name
            # pulled out of the shared object by destructuring.
            destructured = set()
            for block in re.findall(r"=\s*LexeditorUI\s*;|\{([^{}]*)\}\s*=\s*LexeditorUI", text):
                destructured.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block or ""))
            for component in names:
                if f"LexeditorUI.{component}" in text or f"UI.{component}(" in text or (
                        component in destructured
                        and re.search(rf"\b{re.escape(component)}\s*\(", text)):
                    found[component].add(name)
    return {name: sorted(plugins) for name, plugins in found.items()}


def shell_usage(names: list[str]) -> list[str]:
    """Components the shared UI calls itself, on every game's behalf.

    A game that never names applyTheme still gets themed, because mountShell
    applies it. Without this, the catalogue reads as though nothing uses it.
    """
    # The framework itself, plus the shell pages that are not a game: the home
    # screen and the editor host.
    source = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                       for path in sorted((ROOT / "ui").glob("*"))
                       if path.suffix in (".js", ".html") and path.name != "component-catalog.js")
    used = []
    for name in names:
        calls = len(re.findall(rf"(?<![\w.]){re.escape(name)}\s*\(", source))
        # The definition reads `const name = ...`, never `name(`, so any call
        # at all is the shared UI using it.
        if calls:
            used.append(name)
    return used


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    components = usage()
    payload = json.dumps({"components": components,
                          "shell": shell_usage(sorted(components))}, indent=2) + "\n"
    if arguments.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if current != payload:
            print("ui/component-usage.json is out of date; run tools/generate_component_usage.py")
            return 1
        print("Component usage is current.")
        return 0
    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} for {len(json.loads(payload)['components'])} components.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
