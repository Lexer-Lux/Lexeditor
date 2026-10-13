"""Every published Lexer's Mod README meets the first-run contract.

The first-run screen lists a Lexmod's features from its README's Features
section, which must end with the customisable-modules line (core/lexmods.py).
A Lexmod with no published modules (empty, missing, or private to its owner) is
reported and skipped: players cannot download it either.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import lexmods  # noqa: E402


def declared() -> dict[str, str]:
    result = {}
    for folder in sorted((ROOT / "plugins").iterdir()):
        if (folder / "plugin.json").is_file():
            plugin = importlib.import_module(f"plugins.{folder.name}.plugin").PLUGIN
            if plugin.lexmod:
                result[plugin.plugin_id] = plugin.lexmod
    return result


def main() -> int:
    failures = []
    for plugin_id, repository in declared().items():
        try:
            catalog = lexmods.catalog(repository)
        except lexmods.LexmodError as error:
            print(f"{plugin_id}: {repository}: not checked ({error})")
            continue
        problems = catalog['readmeProblems']
        print(f"{plugin_id}: {repository}: {'; '.join(problems) or 'ok'}")
        failures += [f"{repository}: {problem}" for problem in problems]
    if failures:
        print("Lexmod README contract failures:\n" + "\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
