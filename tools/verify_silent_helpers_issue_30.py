"""Reject visible console allocation by Lexeditor-owned background helpers."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = (
    ROOT / "service_session.py",
    ROOT / "github_integration.py",
    ROOT / "games",
)


def python_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCTION_ROOTS:
        if root.is_file():
            files.append(root)
        else:
            files.extend(root.rglob("*.py"))
    return [path for path in files if "_scratch" not in path.parts]


def main() -> int:
    missing: list[str] = []
    calls = 0
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (not isinstance(owner, ast.Name) or owner.id != "subprocess"
                    or node.func.attr not in {"run", "Popen"}):
                continue
            calls += 1
            if not any(keyword.arg == "creationflags" for keyword in node.keywords):
                missing.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert calls, "no production subprocess calls were inventoried"
    assert not missing, "background helpers can open consoles: " + ", ".join(missing)
    print(f"All {calls} Lexeditor background helper launches suppress console windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
