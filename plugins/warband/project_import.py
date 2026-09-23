"""Non-destructive setup for real flat Warband Module System source trees."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


IMPORT_ROOT = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
) / "Lexeditor" / "warband-projects"
IGNORED_NAMES = {".git", ".pytest_cache", "__pycache__", "out"}
REQUIRED_FLAT = ("module_items.py", "module_troops.py", "module_info.py", "build_module.bat")
MAX_FILES = 10_000
MAX_BYTES = 128 * 1024 * 1024
MANIFEST = ".lexeditor-warband-import.json"


def _candidate_names(root: Path) -> list[Path]:
    """Potential flat Module System roots when a repository root was selected."""
    candidates = [root]
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or child.is_symlink():
                continue
            folded = re.sub(r"[^a-z0-9]", "", child.name.casefold())
            if folded.startswith("modulesystem"):
                candidates.append(child)
    return candidates


def find_flat_module_system(root: Path) -> Path | None:
    """Return one unambiguous flat Module System root, or None when unsupported."""
    root = Path(root).expanduser().resolve()
    matches = []
    for candidate in _candidate_names(root):
        if all((candidate / name).is_file() for name in REQUIRED_FLAT):
            matches.append(candidate.resolve())
    unique = list(dict.fromkeys(matches))
    if len(unique) > 1:
        raise ValueError(
            "This folder contains several Warband Module System trees. "
            "Choose the specific Module System folder to import."
        )
    return unique[0] if unique else None


def _iter_source_files(root: Path):
    count = 0
    bytes_seen = 0
    for folder, folders, files in os.walk(root):
        base = Path(folder)
        kept = []
        for name in folders:
            path = base / name
            if name in IGNORED_NAMES:
                continue
            if path.is_symlink():
                raise ValueError(f"Warband import refuses symbolic-link folder: {path}")
            kept.append(name)
        folders[:] = kept
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = base / name
            if path.is_symlink():
                raise ValueError(f"Warband import refuses symbolic-link file: {path}")
            if not path.is_file():
                continue
            count += 1
            bytes_seen += path.stat().st_size
            if count > MAX_FILES or bytes_seen > MAX_BYTES:
                raise ValueError(
                    "This folder is too large to be a Warband Module System source import. "
                    "Choose the source tree rather than the game or compiled module folder."
                )
            yield path


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(_iter_source_files(root), key=lambda value: value.relative_to(root).as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def _read_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1254", "latin1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1"), "latin1"


def _rewrite_module_info(path: Path) -> str:
    """Point only the managed copy at its local Module output."""
    text, encoding = _read_source(path)
    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)export_dir[ \t]*=[ \t]*"
        r"(?P<quote>[\"'])(?P<value>[^\"']*)(?P=quote)"
        r"(?P<tail>[ \t]*(?:#.*)?)(?P<cr>\r?)$"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            "Warband flat-source import needs exactly one literal export_dir assignment "
            "in module_info.py; nothing was copied."
        )
    match = matches[0]
    replacement = (
        f"{match.group('indent')}export_dir = {match.group('quote')}../Module/{match.group('quote')}"
        f"{match.group('tail')}{match.group('cr')}"
    )
    candidate = text[:match.start()] + replacement + text[match.end():]
    path.write_bytes(candidate.encode(encoding))
    return match.group("value")


def _casefold_file(root: Path, name: str) -> Path | None:
    direct = root / name
    if direct.is_file():
        return direct
    target = name.casefold()
    return next((path for path in root.iterdir() if path.is_file() and path.name.casefold() == target), None)


def safe_build_steps(root: Path) -> list[str]:
    """Extract one-shot Python build steps; reject arbitrary batch execution."""
    source = root / "build_module.bat"
    text, _encoding = _read_source(source)
    steps: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        command = line.lstrip("@").strip()
        lower = command.casefold()
        if (
            lower == "echo off"
            or lower == "cls"
            or lower.startswith("echo")
            or lower.startswith("rem ")
            or command.startswith("::")
            or command.startswith(":")
            or lower.startswith("pause")
            or lower.startswith("goto ")
        ):
            continue
        if re.fullmatch(r"(?i)del(?: /[a-z]+)* \*\.pyc", command):
            continue
        match = re.fullmatch(r"(?i)python(?:\.exe)?\s+(.+)", command)
        if not match:
            raise ValueError(
                f"Unsupported command on build_module.bat line {number}: {line}. "
                "Lexeditor will not execute arbitrary batch commands."
            )
        arguments = match.group(1).strip()
        if any(character in arguments for character in "&|<>%^!"):
            raise ValueError(
                f"Unsafe shell syntax on build_module.bat line {number}; nothing was imported."
            )
        tokens = arguments.split()
        if not tokens or any(
            not re.fullmatch(r"-[A-Za-z0-9]+|[A-Za-z0-9_.\\/-]+", token)
            for token in tokens
        ):
            raise ValueError(
                f"Unsupported Python arguments on build_module.bat line {number}; nothing was imported."
            )
        script = next((token for token in reversed(tokens) if token.casefold().endswith(".py")), "")
        if not script or _casefold_file(root, script) is None:
            raise ValueError(
                f"build_module.bat references missing Python script {script or arguments!r}; "
                "nothing was imported."
            )
        steps.append(arguments)
    if not steps:
        raise ValueError("build_module.bat contains no supported Python build steps")
    return steps


def _build_wrapper(steps: list[str]) -> str:
    lines = [
        "@echo off",
        "setlocal",
        'cd /d "%~dp0ModuleSystem"',
        'set "LEX_WARBAND_PY="',
        'set "LEX_WARBAND_PY_ARGS="',
        'if exist "C:\\Python27\\python.exe" set "LEX_WARBAND_PY=C:\\Python27\\python.exe"',
        'if not defined LEX_WARBAND_PY (',
        '  py -2 -c "import sys" >nul 2>nul',
        '  if not errorlevel 1 set "LEX_WARBAND_PY=py"',
        '  if not errorlevel 1 set "LEX_WARBAND_PY_ARGS=-2"',
        ')',
        'if not defined LEX_WARBAND_PY set "LEX_WARBAND_PY=python"',
    ]
    for arguments in steps:
        lines.extend([
            f'call "%LEX_WARBAND_PY%" %LEX_WARBAND_PY_ARGS% {arguments}',
            "if errorlevel 1 exit /b %errorlevel%",
        ])
    lines.extend([
        "del /q *.pyc 2>nul",
        "echo Build verified: imported Warband Module System",
        "exit /b 0",
        "",
    ])
    return "\r\n".join(lines)


def _copy_source(source: Path, destination: Path) -> None:
    for path in _iter_source_files(source):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned or "warband-module-system"


def _manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def import_flat_module_system(selected_root: Path, source_root: Path) -> Path:
    """Create/reuse a managed wrapper; never mutate the selected source tree."""
    selected_root = Path(selected_root).expanduser().resolve()
    source_root = Path(source_root).expanduser().resolve()
    fingerprint = source_fingerprint(source_root)
    import_root = IMPORT_ROOT.resolve()
    if (
        import_root == source_root
        or import_root in source_root.parents
        or source_root in import_root.parents
    ):
        raise ValueError(
            "Warband import source and managed destination must be separate folders."
        )
    import_root.mkdir(parents=True, exist_ok=True)
    target = import_root / f"{_safe_name(selected_root.name)}-{fingerprint[:12]}"
    expected = {
        "format": 1,
        "source": str(selected_root),
        "moduleSystem": str(source_root),
        "sourceFingerprint": fingerprint,
    }
    if target.exists():
        current = _manifest(target / MANIFEST)
        if all(current.get(key) == value for key, value in expected.items()):
            return target.resolve()
        raise ValueError(
            f"Warband import destination already exists but does not match this source: {target}"
        )

    steps = safe_build_steps(source_root)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=import_root))
    try:
        module_system = temporary / "ModuleSystem"
        module_system.mkdir()
        _copy_source(source_root, module_system)
        if (
            source_fingerprint(module_system) != fingerprint
            or source_fingerprint(source_root) != fingerprint
        ):
            raise ValueError(
                "The Warband Module System source changed while it was being imported. "
                "Retry after the source tree is stable."
            )
        original_export = _rewrite_module_info(module_system / "module_info.py")
        (temporary / "Module").mkdir()
        (temporary / "settings.ini").write_text(
            "; Imported flat Module System has no Lexeditor-specific tweak settings.\n",
            encoding="utf-8",
        )
        (temporary / "build.bat").write_text(_build_wrapper(steps), encoding="utf-8", newline="")
        manifest = {
            **expected,
            "originalExportDir": original_export,
            "buildSteps": steps,
            "sourceFiles": sum(1 for _ in _iter_source_files(source_root)),
        }
        (temporary / MANIFEST).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (temporary / "IMPORT.md").write_text(
            "# Imported Warband Module System\n\n"
            f"Source: `{selected_root}`\n\n"
            f"Detected Module System: `{source_root}`\n\n"
            "Lexeditor copied the source into `ModuleSystem/`; the original folder is never "
            "written. The managed copy rewrites only `module_info.py`'s literal "
            "`export_dir` to `../Module/` so builds stay inside this project. "
            "Its generated `build.bat` runs one pass of the upstream Python build steps "
            "and deliberately omits pause/loop UI commands. Re-selecting the unchanged "
            "source reuses this project and preserves Lexeditor edits.\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target.resolve()


def prepare_existing_project(root: Path) -> Path:
    """ProjectManager hook: import flat source trees, leave valid shapes unchanged."""
    root = Path(root).expanduser().resolve()
    source = find_flat_module_system(root)
    if source is None:
        return root
    return import_flat_module_system(root, source)
