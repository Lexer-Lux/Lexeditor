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
    for plugin in sorted((ROOT / "games").iterdir()):
        if not plugin.is_dir():
            continue
        for path in sorted(plugin.rglob("*")):
            if path.suffix.lower() not in (".html", ".js") or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            # Both spellings a plugin can use: LexeditorUI.name(, and the name
            # pulled out of the shared object by destructuring.
            destructured = set()
            for block in re.findall(r"=\s*LexeditorUI\s*;|\{([^{}]*)\}\s*=\s*LexeditorUI", text):
                destructured.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block or ""))
            for name in names:
                if f"LexeditorUI.{name}" in text or (name in destructured
                        and re.search(rf"\b{re.escape(name)}\s*\(", text)):
                    found[name].add(plugin.name)
    return {name: sorted(plugins) for name, plugins in found.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    payload = json.dumps({"components": usage()}, indent=2) + "\n"
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
