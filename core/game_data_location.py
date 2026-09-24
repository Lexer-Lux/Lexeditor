"""Resolve Data Map filenames inside installed or prepared original game data."""
from pathlib import Path
import os
import re


def find_original_location(filename: str, roots: list[Path], installation: Path | None = None) -> Path:
    name = str(filename).strip().replace("\\", "/")
    if not name or "\x00" in name or any(part == ".." for part in name.split("/")):
        raise ValueError("Invalid game-data filename")
    # Data Map rows may document a group (for example *.xml). A location
    # button then reveals the containing original-data folder.
    parts = [part.strip() for part in re.split(r"\s+\+\s+|\s*,\s*", name)]
    # RDR Data Map identities include an archive boundary. Prepared files are
    # addressed by the member path after that boundary.
    prepared_parts = [part.split(":/", 1)[1].lstrip("/") if ":/" in part else part
                      for part in parts]
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        matches = []
        for part in prepared_parts:
            relative = Path(part)
            direct = (root / relative).resolve()
            if direct.is_relative_to(root) and direct.is_file():
                matches.append(direct)
                continue
            leaf = relative.name
            if not leaf or leaf in ("*", "**"):
                continue
            for candidate in root.rglob(leaf):
                candidate = candidate.resolve()
                if candidate.is_file() and candidate.is_relative_to(root):
                    # A supplied archive-relative path must match its suffix;
                    # do not silently open a same-named unrelated file.
                    if len(relative.parts) == 1 or candidate.as_posix().lower().endswith("/" + part.lower()):
                        matches.append(candidate)
        matches = sorted(set(matches))
        if len(matches) == 1:
            return matches[0]
        if matches:
            return Path(os.path.commonpath([str(path.parent) for path in matches]))
    # Installed mod folders are not original data. Only accept an exact file
    # in the game root (or a source archive explicitly named by the Data Map).
    if installation is not None:
        game = installation.resolve()
        direct_names = list(parts)
        for part in parts:
            if ":/" in part:
                archive = part.split(":/", 1)[0]
                direct_names.extend([archive, archive.removeprefix("game/")])
        if name.startswith("ff8/en/exe/") and name.endswith(".msd"):
            direct_names.append("FF8_EN.exe")
        for relative in direct_names:
            candidate = (game / relative).resolve()
            if candidate.is_relative_to(game) and candidate.is_file():
                return candidate
    raise FileNotFoundError(f"The original file is not prepared or installed as a loose file: {name}")
