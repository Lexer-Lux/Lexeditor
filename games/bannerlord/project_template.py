"""Packaged clean-project initialization for Bannerlord modules."""
from __future__ import annotations

from pathlib import Path
import html
import re


_PLACEHOLDERS = {
    "{{MODULE_NAME}}",
    "{{MODULE_ID}}",
}
_TEMPLATE_FILES = (
    "SubModule.xml",
    "BannerlordModule.csproj",
    "src/SubModule.cs",
)


def module_id_from_name(name: str) -> str:
    """Turn a user-visible folder name into one safe C#/Bannerlord identifier."""
    words = re.findall(r"[A-Za-z0-9]+", str(name))
    candidate = "".join(word[:1].upper() + word[1:] for word in words) or "BannerlordMod"
    if candidate[0].isdigit():
        candidate = "Mod" + candidate
    return candidate


def initialize_project(target: Path) -> None:
    """Resolve template placeholders after ProjectManager copies the package."""
    target = Path(target).resolve()
    module_name = target.name.strip() or "Bannerlord Mod"
    module_id = module_id_from_name(module_name)
    for relative in _TEMPLATE_FILES:
        path = target / relative
        if not path.is_file():
            raise FileNotFoundError(f"Bannerlord project template is missing {relative}")
        text = path.read_text(encoding="utf-8")
        xml_context = path.suffix.casefold() in {".xml", ".csproj", ".props", ".targets"}
        replacements = {
            "{{MODULE_NAME}}": html.escape(module_name, quote=True) if xml_context else module_name,
            "{{MODULE_ID}}": module_id,
        }
        for token, value in replacements.items():
            text = text.replace(token, value)
        unresolved = sorted(token for token in _PLACEHOLDERS if token in text)
        if unresolved:
            raise ValueError(f"Unresolved Bannerlord template placeholders in {relative}: {', '.join(unresolved)}")
        path.write_text(text, encoding="utf-8")

    generic_project = target / "BannerlordModule.csproj"
    final_project = target / f"{module_id}.csproj"
    if final_project.exists() and final_project != generic_project:
        raise FileExistsError(final_project)
    generic_project.rename(final_project)
