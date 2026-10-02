"""Build FF8's enabled tweak mods before the composer layers the library.

A tweak mod (see core/script_mods.py) carries its own script. Building one
writes its Hext patch, and any data file it owns, into its own folder; the
composer then deploys those exactly like a hand-made mod's files. The build
context is the whole interface a script gets from Lexeditor: the verified
executable, the game's own baseline files, the other enabled tweaks' values,
and requests for FFNx.toml keys or the Lexeditor FFNx derivative.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from core import script_mods

from . import runtime_layout

SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
ALLOWED_ROOTS = ("hext", "direct")
IMAGE_BASE = 0x400000


class BuildError(ValueError):
    """An enabled tweak mod could not be built; nothing was composed."""


class BuildContext:
    HEXT = "hext/ff8/en_nv"

    def __init__(self, game_root: Path, baseline_root: Path, enabled: dict[str, Path]):
        self.game_root = Path(game_root)
        self.baseline_root = Path(baseline_root)
        # flat_stat_abilities rewrites "the project's kernel, else the game's";
        # a tweak mod always starts from the game's own copy.
        self.empty_project = self.game_root / ".lexeditor-no-project"
        self._enabled = enabled
        self._executable: Path | None = None
        self.ffnx_keys: dict[str, object] = {}
        self._ffnx_owner: dict[str, str] = {}
        self.driver = False
        self.current = ""

    def executable(self) -> Path:
        if self._executable is None:
            path = self.game_root / "FF8_EN.exe"
            if not path.is_file():
                raise BuildError(f"FF8_EN.exe is missing from {self.game_root}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != SUPPORTED_EXE_SHA256:
                raise BuildError(f"The installed FF8_EN.exe build is not supported (SHA-256 {digest}). "
                                 "No tweak was built.")
            self._executable = path
        return self._executable

    def verify(self, hooks) -> None:
        """Every hook site must still hold the bytes the patch replaces."""
        with self.executable().open("rb") as stream:
            for address, original in hooks:
                stream.seek(address - IMAGE_BASE)
                if stream.read(len(original)) != original:
                    raise BuildError(f"{self.current}: the bytes at {address:X} do not match the verified build")

    def verify_stream(self, check) -> None:
        with self.executable().open("rb") as stream:
            check(stream)

    def enabled(self, mod_id: str) -> bool:
        return mod_id in self._enabled

    def settings(self, mod_id: str) -> dict | None:
        root = self._enabled.get(mod_id)
        return script_mods.values(root) if root else None

    def ffnx(self, key: str, value) -> None:
        if key in self.ffnx_keys and self.ffnx_keys[key] != value:
            raise BuildError(f"{self.current} and {self._ffnx_owner[key]} need different values for {key}")
        self.ffnx_keys[key] = value
        self._ffnx_owner[key] = self.current

    def need_driver(self) -> None:
        self.driver = True


def tweak_rows(project_root: Path, mods_root: Path) -> list[dict]:
    """Library rows that are tweak mods, in load order, with their schema."""
    rows = []
    for row in runtime_layout.catalog(project_root, mods_root):
        root = Path(row["path"])
        if row.get("selected") or not script_mods.is_script_mod(root):
            continue
        rows.append({**row, **script_mods.catalog_row(root), "id": row["id"], "name": row["name"]})
    return rows


def build_enabled(project_root: Path, mods_root: Path, game_root: Path, baseline_root: Path) -> dict:
    """Build every enabled tweak mod, or none: the first failure stops it."""
    rows = [row for row in tweak_rows(project_root, mods_root) if row["enabled"]]
    enabled = {row["id"]: Path(row["path"]) for row in rows}
    context = BuildContext(game_root, baseline_root, enabled)
    snapshots = {}
    for row in rows:
        if row["error"]:
            raise BuildError(f"{row['name']}: {row['error']}")
        missing = [need for need in row["schema"]["requires"] if need not in enabled]
        if missing:
            raise BuildError(f"{row['name']} requires {', '.join(missing)}, which is not enabled")
        if row["schema"]["blocker"]:
            raise BuildError(f"{row['name']}: {row['schema']['blocker']}")
        conflicts = [mod_id for mod_id in row["schema"]["conflicts"] if mod_id in enabled]
        if conflicts:
            raise BuildError(f"{row['name']} conflicts with {', '.join(conflicts)}")
        if row["trust"] != "trusted":
            raise BuildError(f"{row['name']}: its script is {row['trust']}; trust it before building")
        try:
            snapshots[row["id"]] = script_mods.snapshot_generated(Path(row["path"]), allowed_roots=ALLOWED_ROOTS)
        except Exception as error:
            raise BuildError(f"{row['name']}: {error}") from error
    built = []
    try:
        for row in rows:
            context.current = row["name"]
            result = script_mods.build(Path(row["path"]), context, allowed_roots=ALLOWED_ROOTS)
            built.append({"id": row["id"], "files": result["files"]})
    except Exception as error:
        failures = []
        for result in reversed(built):
            try:
                script_mods.restore_generated(enabled[result["id"]], snapshots[result["id"]],
                    new_files=result["files"], allowed_roots=ALLOWED_ROOTS)
            except Exception as rollback_error:
                failures.append(f"{result['id']}: {rollback_error}")
        suffix = "; rollback failed: " + "; ".join(failures) if failures else ""
        raise BuildError(f"{context.current}: {error}{suffix}") from error
    return {"built": built, "ffnx": context.ffnx_keys, "driver": context.driver}
