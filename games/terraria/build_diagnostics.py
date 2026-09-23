"""Parse compiler/MSBuild diagnostics emitted by tModLoader's native build."""

from __future__ import annotations

from pathlib import Path
import os
import re


_DIAGNOSTIC = re.compile(
    r"^(?P<path>.+?\.cs)"
    r"\((?P<line>\d+),(?P<column>\d+)"
    r"(?:,(?P<end_line>\d+),(?P<end_column>\d+))?\)"
    r":\s*(?P<severity>error|warning)\s+"
    r"(?P<code>[A-Za-z]+\d+)\s*:\s*"
    r"(?P<message>.*?)"
    r"(?:\s+\[[^\]]+\])?$",
    re.IGNORECASE,
)


def _display_path(raw: str, project: Path | None) -> tuple[str, bool]:
    value = raw.strip().strip('"')
    if project is None:
        return value, False
    root = Path(project).resolve()
    try:
        candidate = Path(value).resolve()
    except (OSError, ValueError):
        return value, False
    try:
        relative = candidate.relative_to(root).as_posix()
    except ValueError:
        return value, False
    return relative, relative.casefold().endswith(".cs")


def parse_build_diagnostics(output: object, project: Path | None = None) -> list[dict]:
    """Return de-duplicated C# warnings/errors from standard MSBuild output."""
    if output is None:
        return []
    text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
    diagnostics: list[dict] = []
    seen: set[tuple] = set()
    for raw_line in text.splitlines():
        match = _DIAGNOSTIC.match(raw_line.strip())
        if match is None:
            continue
        path, project_file = _display_path(match.group("path"), project)
        diagnostic = {
            "path": path,
            "projectFile": project_file,
            "line": int(match.group("line")),
            "column": int(match.group("column")),
            "endLine": int(match.group("end_line") or match.group("line")),
            "endColumn": int(match.group("end_column") or match.group("column")),
            "severity": match.group("severity").casefold(),
            "code": match.group("code").upper(),
            "message": match.group("message").strip(),
        }
        key = (
            diagnostic["path"], diagnostic["line"], diagnostic["column"],
            diagnostic["severity"], diagnostic["code"], diagnostic["message"],
        )
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(diagnostic)
    diagnostics.sort(key=lambda row: (
        row["severity"] != "error",
        os.path.normcase(row["path"]),
        row["line"],
        row["column"],
        row["code"],
    ))
    return diagnostics
