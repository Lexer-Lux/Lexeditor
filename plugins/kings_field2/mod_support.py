"""Deploy ordinary source-mod folders to Verdite2's own C# mod loader."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile

from core.mod_library import digest, file_tree, relative_path
from . import model

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


class VerditeModAdapter:
    verified = False
    message = "Verdite2's built-in C# source-mod loader. Close the game before changing mods. Installed-game acceptance is still in progress."
    package_types = ("folder", "zip")

    def inspect(self, root: Path, files: list[Path]) -> dict:
        problems = []
        sources = [path.as_posix() for path in files if path.suffix.casefold() == ".cs"]
        info = model.read_json(root / "mod.json")
        if not isinstance(info.get("id"), str) or not IDENTITY.fullmatch(info["id"]):
            problems.append("A Verdite2 source mod needs a valid id in its root mod.json")
        if not str(info.get("name", "")).strip():
            problems.append("A Verdite2 source mod needs a name in its root mod.json")
        if not sources:
            problems.append("This package has no C# source for Verdite2's built-in mod compiler")
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
        data = model.data_root()
        recovery = data / RECOVERY
        if not recovery.exists():
            return
        model.ensure_closed()
        state = model.read_json(recovery / "transaction.json")
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
        for name, before in (("settings.json", "settings.before"), (LEDGER, "ledger.before")):
            current = model.read_bytes(data / name)
            original = model.read_bytes(recovery / before)
            if model.fingerprint(current) not in (model.fingerprint(original), state["after"][name]):
                raise ValueError(f"{name} changed since deployment was interrupted; recovery was preserved")
        for name in old.keys() | new.keys():
            target, backup = native / name, recovery / "mods" / name
            if backup.exists():
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            elif name not in old and target.exists():
                shutil.rmtree(target)
        for name, before in (("settings.json", "settings.before"), (LEDGER, "ledger.before")):
            raw = model.read_bytes(recovery / before)
            if raw:
                model.atomic_write(data / name, raw)
            else:
                (data / name).unlink(missing_ok=True)
        shutil.rmtree(recovery)

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        with model.LOCK:
            model.ensure_closed()
            if not model.installation(Path(game_root))["supported"]:
                raise ValueError("Locate a Verdite2 installation for King's Field II (SLUS-00158)")
            self.recover(game_root)
            data = model.data_root()
            native = data / "mods"
            native.mkdir(parents=True, exist_ok=True)
            ledger = model.read_json(data / LEDGER)
            old = ledger.get("folders", {})
            self._verify(native, old)
            new = {}
            identities = set()
            for folder in mods:
                report = self.inspect(folder, file_tree(folder))
                if not report["valid"]:
                    raise ValueError("; ".join(report["problems"]))
                info = model.read_json(folder / "mod.json")
                identity = info["id"]
                if identity.casefold() in identities:
                    raise ValueError(f"Two selected mods use the native id {identity}")
                identities.add(identity.casefold())
                name = "lexeditor-" + identity
                if (native / name).exists() and name not in old:
                    raise ValueError(f"{name} already exists outside Lexeditor")
                new[name] = {"id": identity, "source": str(folder.resolve()), "files": _tree(folder)}
            for folder in native.iterdir():
                if folder.is_dir() and folder.name not in old and (folder / "mod.json").is_file():
                    identity = model.read_json(folder / "mod.json").get("id", "")
                    if str(identity).casefold() in identities:
                        raise ValueError(f"Native mod {identity} already exists outside Lexeditor")
            raw_settings = model.read_bytes(data / "settings.json")
            settings = model.read_json(data / "settings.json")
            active = settings.get("ActiveMods", [])
            if not isinstance(active, list) or any(not isinstance(value, str) for value in active):
                raise ValueError("Verdite2 ActiveMods must be a list of native mod ids")
            owned_ids = {entry["id"] for entry in old.values()}
            settings["ActiveMods"] = [value for value in active if value not in owned_ids] + [entry["id"] for entry in new.values()]
            after_settings, after_ledger = _json(settings), _json({"folders": new})
            required = sum((folder / path).stat().st_size for folder in mods for path in file_tree(folder))
            if shutil.disk_usage(data).free < required + 4 * model.MAX_CONFIG:
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
                model.atomic_write(recovery / "settings.before", raw_settings)
                model.atomic_write(recovery / "ledger.before", model.read_bytes(data / LEDGER))
                transaction = {"phase": "applying", "old": old, "new": new,
                               "after": {"settings.json": model.fingerprint(after_settings), LEDGER: model.fingerprint(after_ledger)}}
                model.atomic_write(recovery / "transaction.json", _json(transaction))
                try:
                    for name in old:
                        (native / name).rename(recovery / "mods" / name)
                    for name in new:
                        (staged / name).rename(native / name)
                    model.atomic_write(data / "settings.json", after_settings)
                    model.atomic_write(data / LEDGER, after_ledger)
                    transaction["phase"] = "committed"
                    model.atomic_write(recovery / "transaction.json", _json(transaction))
                except BaseException:
                    self.recover(game_root)
                    raise
                shutil.rmtree(recovery)
            return {"activated": [folder.name for folder in mods], "mods": settings["ActiveMods"], "dataRoot": str(data)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        return list(model.read_json(model.data_root() / "settings.json").get("ActiveMods", []))

    def standalone_mods(self, game_root: Path) -> list[dict]:
        native = model.data_root() / "mods"
        owned = model.read_json(model.data_root() / LEDGER).get("folders", {})
        if not native.is_dir():
            return []
        return [{"path": str(folder), "name": model.read_json(folder / "mod.json").get("name", folder.name)}
                for folder in native.iterdir() if folder.is_dir() and folder.name not in owned and (folder / "mod.json").is_file()]

    def describe_changes(self, folder: Path, game_root: Path | None) -> dict:
        files = file_tree(folder)
        return {"changes": [], "loaded": [path.as_posix() for path in files if path.suffix == ".cs" or path.name == "mod.json"],
                "note": "Source mods attach their own runtime hooks. No record edits or hook compatibility are inferred from file names."}
