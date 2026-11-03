"""Manage source mods in the native port loader's own folder."""
from __future__ import annotations

from pathlib import Path
import re
import shutil

from core.mod_library import digest, file_tree
from core.native_port_settings import NativePortSettings, ini_values, updated_ini

LEDGER = ".lexeditor-native-mods.json"
RECOVERY = ".lexeditor-native-recovery"
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


def _tree(folder: Path) -> dict[str, str]:
    return {path.as_posix(): digest(folder / path) for path in file_tree(folder)}


def _folder(name: str) -> str:
    if not name.startswith("lexeditor-") or not IDENTITY.fullmatch(name.removeprefix("lexeditor-")):
        raise ValueError("Unrecognized Lexeditor mod deployment folder")
    return name


class NativeSourceModAdapter:
    def __init__(self, model: NativePortSettings, *, priority_key: str | None = "mods.{id}.priority"):
        self.model = model
        self.priority_key = priority_key

    verified = False
    message = "The native port's built-in C# source-mod loader. Close the game before changing mods. Installed-game acceptance is still in progress."
    package_types = ("folder", "zip")

    def inspect(self, root: Path, files: list[Path]) -> dict:
        problems = []
        sources = [path.as_posix() for path in files if path.suffix.casefold() == ".cs"]
        info = self.model.read_json(root / "mod.json")
        if not isinstance(info.get("id"), str) or not IDENTITY.fullmatch(info["id"]):
            problems.append("A native source mod needs a valid id in its root mod.json")
        if not str(info.get("name", "")).strip():
            problems.append("A native source mod needs a name in its root mod.json")
        if not sources:
            problems.append("This package has no C# source for the native mod compiler")
        for path in files:
            if path.suffix.casefold() in (".exe", ".dll", ".asi", ".bin", ".cue", ".chd"):
                problems.append(f"{path.as_posix()} is not a source-mod resource")
        return {"valid": not problems, "problems": problems, "packages": sources,
                "notDeployed": [], "assets": {}}

    def prepare_editable(self, root: Path) -> None:
        report = self.inspect(root, file_tree(root))
        if not report["valid"]:
            raise ValueError("; ".join(report["problems"]))

    def recover(self, game_root: Path) -> None:
        """Restore an interrupted transaction; refuse anything edited since it began."""
        data = self.model.data_root()
        recovery = data / RECOVERY
        if not recovery.exists():
            return
        self.model.ensure_closed()
        state = self.model.read_json(recovery / "transaction.json")
        expected = {"transaction.json", "interface.before", "ledger.before", "mods"}
        if {path.name for path in recovery.iterdir()} != expected:
            raise ValueError("Recovery copy was edited; preserve its added or missing files before continuing")
        for name, before in (("interface.ini", "interface.before"), (LEDGER, "ledger.before")):
            if self.model.fingerprint(self.model.read_bytes(recovery / before)) != state["before"][name]:
                raise ValueError(f"Recovery copy {before} was edited; recovery was preserved")
        backups = recovery / "mods"
        names = {path.name for path in backups.iterdir()}
        if names - state["old"].keys():
            raise ValueError("Recovery copy contains unrecognized mod files; recovery was preserved")
        for name in names:
            folder = backups / _folder(name)
            if not folder.is_dir() or _tree(folder) != state["old"][name]["files"]:
                raise ValueError(f"Recovery copy {name} was edited; recovery was preserved")
        if state.get("phase") == "committed":
            if names != state["old"].keys():
                raise ValueError("Recovery copy is incomplete; recovery was preserved")
            shutil.rmtree(recovery)
            return
        old, new = state["old"], state["new"]
        native = data / "mods"
        # Preflight all restoration before changing any destination.
        for name in old.keys() | new.keys():
            target, backup = native / _folder(name), recovery / "mods" / name
            if backup.exists() and (name not in old or not backup.is_dir() or _tree(backup) != old[name]["files"]):
                raise ValueError(f"Recovery copy {name} was edited; recovery was preserved without overwriting it")
            if target.exists():
                expected = new[name]["files"] if backup.exists() or name not in old else old[name]["files"]
                if _tree(target) != expected:
                    raise ValueError(f"Interrupted deployment {name} was edited; recovery was preserved without overwriting it")
        for name, before in (("interface.ini", "interface.before"), (LEDGER, "ledger.before")):
            current = self.model.read_bytes(data / name)
            original = self.model.read_bytes(recovery / before)
            if self.model.fingerprint(current) not in (self.model.fingerprint(original), state["after"][name]):
                raise ValueError(f"{name} changed since deployment was interrupted; recovery was preserved")
        for name in old.keys() | new.keys():
            target, backup = native / name, recovery / "mods" / name
            if backup.exists():
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            elif name not in old and target.exists():
                shutil.rmtree(target)
        for name, before in (("interface.ini", "interface.before"), (LEDGER, "ledger.before")):
            raw = self.model.read_bytes(recovery / before)
            if raw:
                self.model.atomic_write(data / name, raw)
            else:
                (data / name).unlink(missing_ok=True)
        shutil.rmtree(recovery)

    def library_root(self, game_root: Path) -> Path:
        return self.model.data_root() / "mods"

    def library_state(self, game_root: Path) -> dict:
        native = self.library_root(game_root)
        values = ini_values(self.model.read_bytes(self.model.data_root() / "interface.ini").decode("utf-8-sig"))
        result = {}
        for folder in native.iterdir() if native.is_dir() else []:
            if not folder.is_dir() or folder.name.startswith(".") or not (folder / "mod.json").is_file():
                continue
            try:
                identity = self.model.read_json(folder / "mod.json")["id"]
                key = f"mods.{identity}.enabled".casefold()
                row = {"enabled": values.get(key, "False").casefold() == "true"}
                if self.priority_key:
                    try:
                        row["order"] = int(values.get(self.priority_key.format(id=identity).casefold(), "1000"))
                    except ValueError:
                        row.update(order=1000, alerts=["The native loader priority is invalid. Reorder this mod to repair it."])
                result[folder.name] = row
            except (OSError, ValueError, KeyError, TypeError):
                result[folder.name] = {"enabled": False}
        return result

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        """Change native loader flags; source folders always stay in place."""
        from core.mod_builds import ModBuildError
        with self.model.lock:
            self.model.ensure_closed()
            if not self.model.installation(Path(game_root))["supported"]:
                raise ValueError("Locate a supported native port installation for this game")
            self.recover(game_root)
            native = self.library_root(game_root).resolve()
            identities = set()
            changes = {}
            for priority, folder in enumerate(mods, 1):
                if folder.resolve().parent != native:
                    raise ValueError("Choose mods from the game's native mods folder")
                try:
                    report = self.inspect(folder, file_tree(folder))
                    if not report["valid"]:
                        raise ValueError("; ".join(report["problems"]))
                    identity = self.model.read_json(folder / "mod.json")["id"]
                except (OSError, ValueError, KeyError) as error:
                    raise ModBuildError([folder], str(error)) from error
                if identity.casefold() in identities:
                    raise ValueError(f"Two selected mods use the native id {identity}")
                identities.add(identity.casefold())
                changes[f"mods.{identity}.enabled".casefold()] = "True"
                if self.priority_key:
                    changes[self.priority_key.format(id=identity).casefold()] = str(priority)
            # An enabled native ID would load every folder declaring that ID.
            # Reject duplicates before changing the one configuration file.
            discovered = set()
            for folder in native.iterdir() if native.is_dir() else []:
                if not folder.is_dir() or folder.name.startswith(".") or not (folder / "mod.json").is_file():
                    continue
                try:
                    identity = self.model.read_json(folder / "mod.json").get("id", "").casefold()
                except (OSError, ValueError, AttributeError):
                    continue
                if identity in identities and identity in discovered:
                    raise ValueError(f"Two native mod folders use the id {identity}")
                discovered.add(identity)
            data = self.model.data_root()
            raw = self.model.read_bytes(data / "interface.ini")
            values = ini_values(raw.decode("utf-8-sig"))
            for key in values:
                if key.startswith("mods.") and key.endswith(".enabled"):
                    changes.setdefault(key, "False")
            # Missing flags mean off in the native loader. Do not manufacture
            # metadata flags, copies, or a second deployment ledger.
            self.model.atomic_write(data / "interface.ini", updated_ini(raw, changes))
            return {"activated": [folder.name for folder in mods],
                    "mods": self.active_mod_ids(game_root), "dataRoot": str(data)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        values = ini_values(self.model.read_bytes(self.model.data_root() / "interface.ini").decode("utf-8-sig"))
        return [key[len("mods."):-len(".enabled")] for key, value in values.items()
                if key.startswith("mods.") and key.endswith(".enabled") and value.casefold() == "true"]

    def reorder_mod(self, folder: Path, delta: int, game_root: Path) -> None:
        from core import mods_service
        if self.priority_key is None:
            raise ValueError("This native loader determines mod order from dependencies and IDs")
        with self.model.lock:
            self.model.ensure_closed()
            root = self.library_root(game_root)
            rows = mods_service.library_rows(root, self.library_state(game_root))
            folders = [Path(row["path"]).resolve() for row in rows]
            index = folders.index(folder.resolve())
            folders.insert(min(max(index + delta, 0), len(folders) - 1), folders.pop(index))
            changes = {self.priority_key.format(id=self.model.read_json(each / "mod.json")["id"]).casefold(): str(position)
                       for position, each in enumerate(folders, 1)}
            ini = self.model.data_root() / "interface.ini"
            self.model.atomic_write(ini, updated_ini(self.model.read_bytes(ini), changes))

    def standalone_mods(self, game_root: Path) -> list[dict]:
        native = self.model.data_root() / "mods"
        owned = self.model.read_json(self.model.data_root() / LEDGER).get("folders", {})
        if not native.is_dir():
            return []
        return [{"path": str(folder), "name": self.model.read_json(folder / "mod.json").get("name", folder.name)}
                for folder in native.iterdir() if folder.is_dir() and folder.name not in owned and (folder / "mod.json").is_file()]

    def describe_changes(self, folder: Path, game_root: Path | None) -> dict:
        files = file_tree(folder)
        return {"changes": [], "loaded": [path.as_posix() for path in files if path.suffix == ".cs" or path.name == "mod.json"],
                "note": "Source mods attach their own runtime hooks. No record edits or hook compatibility are inferred from file names."}
