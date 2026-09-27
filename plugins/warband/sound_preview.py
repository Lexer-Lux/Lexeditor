"""Preview literal sound samples without executing Module System expressions."""
import ast
from pathlib import Path
import re


def sample_names(expression: str) -> list[str]:
    try:
        value = ast.parse(expression, mode="eval").body
    except (SyntaxError, ValueError):
        return []
    if not isinstance(value, (ast.List, ast.Tuple)):
        return []
    names = []
    for entry in value.elts:
        # A tuple's second member contains flags, which need not be literal.
        if isinstance(entry, (ast.List, ast.Tuple)) and entry.elts:
            entry = entry.elts[0]
        if isinstance(entry, ast.Constant) and isinstance(entry.value, str):
            names.append(entry.value)
    return names


def sample_path(project: Path, game: Path, name: str) -> Path:
    relative = Path(name.replace("\\", "/"))
    if relative.is_absolute() or relative.drive or ".." in relative.parts or ":" in name:
        raise ValueError("Sound preview must name a file inside Sounds")
    if relative.suffix.lower() not in {".wav", ".ogg"}:
        raise ValueError("Sound preview supports WAV and OGG samples")
    module = project if (project / "module.ini").is_file() else project / "Module"
    ini = module / "module.ini"
    scan = False
    if ini.is_file():
        for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"\s*scan_module_sounds\s*=\s*([01])\b", line, re.I)
            if match:
                scan = match[1] == "1"
    roots = ([module / "Sounds"] if scan else []) + [game / "Sounds"]
    for root in roots:
        root = root.resolve()
        candidate = (root / relative).resolve()
        if root not in candidate.parents:
            raise ValueError("Sound preview escapes its Sounds folder")
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Sound sample not found: {name}")
