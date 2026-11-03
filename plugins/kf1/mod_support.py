"""Use Verdite1's native C# loader directly on the shared mod library."""
from __future__ import annotations

from pathlib import Path
import re

from core.mod_library import file_tree, metadata
from .settings import LOCK, parse_ini, read_file, write_settings


class Kf1ModAdapter:
    verified = False
    message = "Verdite1 compiles source mods from the shared library. Native hook compatibility still needs testing per mod."
    package_types = ("folder", "zip")

    def conflicts(self, mods: list[Path], game_root: Path) -> dict:
        owners = {}
        for mod in mods:
            owners.setdefault(str(metadata(mod).get("id", "")).casefold(), []).append(mod)
        return {str(mod): [f"Duplicate native mod id: {identity}"]
                for identity, folders in owners.items() if len(folders) > 1 for mod in folders}

    def inspect(self, root: Path, files: list[Path]) -> dict:
        info = metadata(root)
        problems = []
        identity = info.get("id", "")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", identity):
            problems.append("A native source mod needs an id in mod.json")
        sources = [path for path in files if path.suffix.lower() == ".cs"]
        if not sources:
            problems.append("A native source mod needs C# source files")
        if any(path.suffix.lower() in {".exe", ".bin", ".cue", ".iso", ".chd", ".dll"} for path in files):
            problems.append("Import source mods only; executable and disc payloads are unsupported")
        return {"valid": not problems, "problems": problems, "packages": [info.get("name", root.name)],
                "notDeployed": [], "conflictModel": "native hooks; compatibility depends on the mod"}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        values = parse_ini(read_file(game_root, "interface.ini"))
        library = values.get("mods.root")
        if not library or not Path(library).is_dir():
            return []
        active = []
        for folder in Path(library).iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                identity = metadata(folder).get("id", "")
                if values.get(f"mods.{identity}.enabled".casefold(), "False").lower() == "true":
                    active.append(folder.name)
        return active

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        with LOCK:
            values = parse_ini(read_file(game_root, "interface.ini"))
            parents = {mod.resolve().parent for mod in mods}
            if len(parents) > 1:
                raise ValueError("Native mods must share one library folder")
            library = next(iter(parents), Path(values.get("mods.root", game_root / "mods")))
            identities = set()
            for mod in mods:
                report = self.inspect(mod, file_tree(mod))
                if not report["valid"]:
                    raise ValueError("; ".join(report["problems"]))
                identity = metadata(mod)["id"]
                if identity.casefold() in identities:
                    raise ValueError(f"Two enabled mods have the native id {identity}")
                identities.add(identity.casefold())
            changes = {key: "False" for key in values if key.startswith("mods.") and key.endswith(".enabled")}
            # Disable other library folders too: native mods default off, but a
            # stale key from an earlier installation must not enable one.
            discovered = set()
            if library.is_dir():
                for folder in library.iterdir():
                    if folder.is_dir() and not folder.name.startswith(".") and (folder / "mod.json").is_file():
                        identity = metadata(folder).get("id", "")
                        if identity:
                            key = identity.casefold()
                            if key in discovered and key in identities:
                                raise ValueError(f"Two library folders have the native id {identity}")
                            discovered.add(key)
                            changes[f"mods.{key}.enabled"] = "True" if key in identities else "False"
            changes["mods.root"] = str(library)
            write_settings(game_root, changes)
            return {"mods": [str(mod) for mod in mods], "modIds": [mod.name for mod in mods], "destination": str(library)}
