"""Deploy source-mod folders through a configured native port loader."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile

from core.mod_library import digest, file_tree
from core.native_port_settings import NativePortSettings, ini_values, updated_ini

LEDGER = ".lexeditor-native-mods.json"
RECOVERY = ".lexeditor-native-recovery"
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


def _json(value) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _tree(folder: Path) -> dict[str, str]:
    return {path.as_posix(): digest(folder / path) for path in file_tree(folder)}


def _folder(name: str) -> str:
    if not name.startswith("lexeditor-") or not IDENTITY.fullmatch(name):
        raise ValueError("Unrecognized Lexeditor mod deployment folder")
    return name


class NativeSourceModAdapter:
    def __init__(self, model: NativePortSettings):
        self.model = model

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

    @staticmethod
    def _verify(native: Path, entries: dict) -> None:
        for name, entry in entries.items():
            folder = native / _folder(name)
            if not folder.is_dir() or _tree(folder) != entry["files"]:
                raise ValueError(f"Deployed mod {name} changed outside Lexeditor; preserve those changes before replacing it")

    def recover(self, game_root: Path) -> None:
        """Restore an interrupted transaction; refuse anything edited since it began."""
        data = self.model.data_root()
        recovery = data / RECOVERY
        if not recovery.exists():
            return
        self.model.ensure_closed()
        state = self.model.read_json(recovery / "transaction.json")
        if state.get("phase") == "committed":
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

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        with self.model.lock:
            self.model.ensure_closed()
            if not self.model.installation(Path(game_root))["supported"]:
                raise ValueError("Locate a supported native port installation for this game")
            self.recover(game_root)
            data = self.model.data_root()
            native = data / "mods"
            native.mkdir(parents=True, exist_ok=True)
            ledger = self.model.read_json(data / LEDGER)
            old = ledger.get("folders", {})
            self._verify(native, old)
            raw_interface = self.model.read_bytes(data / "interface.ini")
            values = ini_values(raw_interface.decode("utf-8-sig"))
            new = {}
            identities = set()
            changes = {}
            for priority, folder in enumerate(mods, 1):
                report = self.inspect(folder, file_tree(folder))
                if not report["valid"]:
                    raise ValueError("; ".join(report["problems"]))
                info = self.model.read_json(folder / "mod.json")
                identity = info["id"]
                if identity.casefold() in identities:
                    raise ValueError(f"Two selected mods use the native id {identity}")
                identities.add(identity.casefold())
                name = "lexeditor-" + identity
                if (native / name).exists() and name not in old:
                    raise ValueError(f"{name} already exists outside Lexeditor")
                keys = {f"mods.{identity}.enabled".casefold(): "True", f"mods.{identity}.priority".casefold(): str(priority)}
                before = old[name]["before"] if name in old else {key: values.get(key) for key in keys}
                new[name] = {"id": identity, "source": str(folder.resolve()), "files": _tree(folder), "before": before}
                changes.update(keys)
            for folder in native.iterdir():
                if folder.is_dir() and folder.name not in old and (folder / "mod.json").is_file():
                    identity = self.model.read_json(folder / "mod.json").get("id", "")
                    if str(identity).casefold() in identities:
                        raise ValueError(f"Native mod {identity} already exists outside Lexeditor")
            for name in old.keys() - new.keys():
                changes.update(old[name]["before"])
            after_interface = updated_ini(raw_interface, changes)
            after_ledger = _json({"folders": new})
            required = sum((folder / path).stat().st_size for folder in mods for path in file_tree(folder))
            if shutil.disk_usage(data).free < required + 4 * self.model.MAX_CONFIG:
                raise OSError("There is not enough free space to stage the enabled source mods")
            recovery = data / RECOVERY
            with tempfile.TemporaryDirectory(prefix=".lexeditor-native-stage-", dir=data) as temporary:
                staged = Path(temporary)
                for name, entry in new.items():
                    shutil.copytree(Path(entry["source"]), staged / name)
                    if _tree(staged / name) != entry["files"]:
                        raise ValueError(f"{name} changed while being prepared; nothing was deployed")
                recovery.mkdir()
                (recovery / "mods").mkdir()
                self.model.atomic_write(recovery / "interface.before", raw_interface)
                self.model.atomic_write(recovery / "ledger.before", self.model.read_bytes(data / LEDGER))
                transaction = {"phase": "applying", "old": old, "new": new,
                               "after": {"interface.ini": self.model.fingerprint(after_interface), LEDGER: self.model.fingerprint(after_ledger)}}
                self.model.atomic_write(recovery / "transaction.json", _json(transaction))
                try:
                    for name in old:
                        (native / name).rename(recovery / "mods" / name)
                    for name in new:
                        (staged / name).rename(native / name)
                    self.model.atomic_write(data / "interface.ini", after_interface)
                    self.model.atomic_write(data / LEDGER, after_ledger)
                    transaction["phase"] = "committed"
                    self.model.atomic_write(recovery / "transaction.json", _json(transaction))
                except BaseException:
                    self.recover(game_root)
                    raise
                shutil.rmtree(recovery)
            return {"activated": [folder.name for folder in mods], "mods": self.active_mod_ids(game_root), "dataRoot": str(data)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        values = ini_values(self.model.read_bytes(self.model.data_root() / "interface.ini").decode("utf-8-sig"))
        return [key[len("mods."):-len(".enabled")] for key, value in values.items()
                if key.startswith("mods.") and key.endswith(".enabled") and value.casefold() == "true"]

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
