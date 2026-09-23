"""Chrono Trigger CTP mod-library interoperability for an existing CTExt install.

This is an independent adapter around CTExt's documented/publicly demonstrated
contract. It does not bundle CTExt. Runtime verification remains false until an
installed Steam game proves activation and removal in-game.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from mod_library import digest, file_tree, metadata
from .archive import ResourcesBin
from .project import PROJECT_MARKER, initialize_project, validate_resource_path


OWNED_NAMESPACE = "LexeditorLibrary"
DEPLOYMENT_FILE = "deployment.json"
IGNORED_SUFFIXES = {".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}


def _owned_entry(value: str) -> bool:
    normalized = str(value).replace("\\", "/").casefold()
    return normalized.startswith((OWNED_NAMESPACE + "/").casefold())


def _read_ctp_entries(path: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    resources: list[str] = []
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                try:
                    resource = validate_resource_path(info.filename)
                except ValueError as error:
                    problems.append(f"{path.name}: {error}")
                    continue
                key = resource.casefold()
                if key in seen:
                    problems.append(f"{path.name}: duplicate resource path {resource}")
                    continue
                seen.add(key)
                resources.append(resource)
    except (OSError, zipfile.BadZipFile) as error:
        problems.append(f"Cannot read {path.name} as a CTP ZIP: {error}")
    if not resources and not problems:
        problems.append(f"{path.name} contains no Game/... or Localize/... resources")
    return sorted(resources, key=str.casefold), problems


def _expanded_resources(root: Path, files: list[Path]) -> tuple[list[str], list[str], list[str]]:
    resources: list[str] = []
    ignored: list[str] = []
    problems: list[str] = []
    for relative in files:
        name = relative.as_posix()
        # Resource suffixes overlap ordinary documentation suffixes: localized
        # Steam text is itself a .txt resource. Classify the archive-relative
        # resource roots first, then treat only files outside them as metadata.
        if relative.parts and relative.parts[0] in {"Game", "Localize"}:
            try:
                resources.append(validate_resource_path(name))
            except ValueError as error:
                problems.append(str(error))
            continue
        if relative.name in {"mod.json", PROJECT_MARKER} or relative.suffix.casefold() in IGNORED_SUFFIXES:
            ignored.append(name)
            continue
        problems.append(f"Unsupported file: {name}. CTP mods contain Game/... or Localize/... resources only.")
    if not resources and not problems:
        problems.append("No Chrono Trigger resource files found")
    return sorted(resources, key=str.casefold), ignored, problems


def _config(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError("CTExt ctext.json was not found in the Chrono Trigger folder") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read CTExt ctext.json: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("mods"), dict):
        raise ValueError("CTExt ctext.json has no mods object")
    mods = value["mods"]
    order = mods.get("load_order")
    if not isinstance(order, list) or any(not isinstance(item, str) or not item.strip() for item in order):
        raise ValueError("CTExt mods.load_order must be a list of mod names")
    if mods.get("enabled") is not True or mods.get("enable_ctp_loading") is not True:
        raise ValueError("Enable CTExt mods and CTP loading before applying Lexeditor library mods")
    return value


def _load_order(config: dict) -> list[str]:
    return list(config["mods"]["load_order"])


def _write_config(path: Path, value: dict) -> Path:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".ctext-", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


class ChronoCtpAdapter:
    verified = False
    message = (
        "CTP import and CTExt deployment are implemented for author testing; "
        "installed-game loading and removal are not verified yet."
    )
    package_types = ("folder", "zip", "ctp")

    def inspect(self, root: Path, files: list[Path]) -> dict:
        ctp_files = [path for path in files if path.suffix.casefold() == ".ctp"]
        resource_files = [path for path in files if path.parts and path.parts[0] in {"Game", "Localize"}]
        problems: list[str] = []
        ignored: list[str] = []
        resources: list[str] = []
        packages: list[str] = []

        if ctp_files:
            if len(ctp_files) != 1 or resource_files:
                problems.append("Choose one CTP package or one expanded Game/Localize tree, not both")
            else:
                package = ctp_files[0]
                packages.append(package.as_posix())
                resources, ctp_problems = _read_ctp_entries(root / package)
                problems.extend(ctp_problems)
                for relative in files:
                    if relative == package:
                        continue
                    if relative.name in {"mod.json", PROJECT_MARKER} or relative.suffix.casefold() in IGNORED_SUFFIXES:
                        ignored.append(relative.as_posix())
                    else:
                        problems.append(f"Unsupported file beside CTP: {relative.as_posix()}")
        else:
            resources, ignored, expanded_problems = _expanded_resources(root, files)
            problems.extend(expanded_problems)
            packages = ["Expanded resources"] if resources else []

        return {
            "valid": not problems,
            "problems": problems,
            "packages": packages,
            "resources": resources,
            "resourceCount": len(resources),
            "notDeployed": ignored,
            "conflictModel": "whole-resource; later selected CTP wins",
        }

    def prepare_editable(self, root: Path) -> None:
        files = file_tree(root)
        report = self.inspect(root, files)
        if not report["valid"]:
            raise ValueError("; ".join(report["problems"]))
        ctp_files = [path for path in files if path.suffix.casefold() == ".ctp"]
        if ctp_files:
            package = root / ctp_files[0]
            with tempfile.TemporaryDirectory(prefix=".chrono-ctp-", dir=root) as temp:
                staged = Path(temp) / "content"
                staged.mkdir()
                with zipfile.ZipFile(package) as archive:
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        resource = validate_resource_path(info.filename)
                        target = staged.joinpath(*Path(resource).parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as source, target.open("xb") as output:
                            shutil.copyfileobj(source, output, 1024 * 1024)
                for child in staged.iterdir():
                    target = root / child.name
                    if target.exists():
                        raise FileExistsError(f"Editable CTP extraction would replace {target.name}")
                    child.rename(target)
            package.unlink()
        initialize_project(root)
        info = metadata(root)
        info["editableContent"] = True
        (root / "mod.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _deployment_root(game_root: Path) -> Path:
        return Path(game_root) / "mods" / OWNED_NAMESPACE

    @staticmethod
    def _verify_deployment(folder: Path) -> dict:
        marker = folder / DEPLOYMENT_FILE
        if not marker.is_file():
            raise ValueError("The Lexeditor CTExt deployment folder is unmanaged")
        value = json.loads(marker.read_text(encoding="utf-8"))
        expected = {row["name"]: row["sha256"] for row in value.get("packages", [])}
        actual = {
            relative.as_posix(): digest(folder / relative)
            for relative in file_tree(folder)
            if relative.as_posix() != DEPLOYMENT_FILE
        }
        if actual != expected:
            raise ValueError(
                "Deployed Chrono Trigger CTPs changed outside Lexeditor. "
                "Preserve those changes before applying or removing library mods."
            )
        return value

    def recover(self, game_root: Path) -> None:
        game_root = Path(game_root)
        parent = game_root / "mods"
        destination = parent / OWNED_NAMESPACE
        backup = parent / f".{OWNED_NAMESPACE}-recovery"
        if not backup.exists():
            return
        old = self._verify_deployment(backup)
        current_order = _load_order(_config(game_root / "ctext.json"))
        current_owned = [item for item in current_order if _owned_entry(item)]
        if destination.exists():
            new = self._verify_deployment(destination)
            if current_owned == new.get("ownedEntries", []):
                shutil.rmtree(backup)
                return
        if current_owned == old.get("ownedEntries", []):
            if destination.exists():
                self._verify_deployment(destination)
                shutil.rmtree(destination)
            backup.rename(destination)
            return
        raise ValueError("CTExt load order changed during Lexeditor deployment recovery")

    def active_mod_ids(self, game_root: Path) -> list[str]:
        self.recover(game_root)
        destination = self._deployment_root(game_root)
        if not destination.exists():
            return []
        plan = self._verify_deployment(destination)
        order = _load_order(_config(Path(game_root) / "ctext.json"))
        if [item for item in order if _owned_entry(item)] != plan.get("ownedEntries", []):
            raise ValueError("CTExt Lexeditor load-order entries changed outside Lexeditor")
        return list(plan.get("modIds", []))

    def _mod_resources(self, root: Path) -> tuple[list[str], Path | None]:
        files = file_tree(root)
        report = self.inspect(root, files)
        if not report["valid"]:
            raise ValueError("; ".join(report["problems"]))
        ctp = next((root / path for path in files if path.suffix.casefold() == ".ctp"), None)
        return list(report["resources"]), ctp

    def activation_plan(self, mods: list[Path], game_root: Path) -> dict:
        game_root = Path(game_root).resolve()
        if not (game_root / "Chrono Trigger.exe").is_file() or not (game_root / "resources.bin").is_file():
            raise ValueError("Choose the supported Chrono Trigger Steam game folder")
        if not (game_root / "ctext.dll").is_file():
            raise ValueError("CTExt is not installed in the selected Chrono Trigger folder")
        config_path = game_root / "ctext.json"
        config = _config(config_path)
        current_order = _load_order(config)
        destination = self._deployment_root(game_root)
        if destination.exists():
            previous = self._verify_deployment(destination)
            current_owned = [item for item in current_order if _owned_entry(item)]
            if current_owned != previous.get("ownedEntries", []):
                raise ValueError("CTExt Lexeditor load-order entries changed outside Lexeditor")
        elif any(_owned_entry(item) for item in current_order):
            raise ValueError("CTExt contains LexeditorLibrary load-order entries without a managed deployment")

        archive = ResourcesBin(game_root / "resources.bin")
        owners: dict[str, str] = {}
        conflicts = []
        packages = []
        owned_entries = []
        seen_names = set()
        for root in mods:
            root = Path(root).resolve()
            name = root.name
            key = name.casefold()
            if key in seen_names:
                raise ValueError(f"Choose each Chrono Trigger library mod once: {name}")
            seen_names.add(key)
            resources, source_ctp = self._mod_resources(root)
            for resource in resources:
                if not archive.has(resource):
                    raise ValueError(f"{name} changes a resource not present in this resources.bin: {resource}")
                resource_key = resource.casefold()
                if resource_key in owners:
                    conflicts.append({"path": resource, "lower": owners[resource_key], "higher": name})
                owners[resource_key] = name
            package_name = name + ".ctp"
            owned_entries.append(f"{OWNED_NAMESPACE}/{name}")
            packages.append({
                "root": str(root), "name": package_name,
                "sourceCtp": str(source_ctp) if source_ctp else "",
                "resources": resources,
            })
        external = [item for item in current_order if not _owned_entry(item)]
        load_order_after = external + owned_entries
        return {
            "destination": str(destination),
            "config": str(config_path),
            "mods": [str(Path(root).resolve()) for root in mods],
            "modIds": [Path(root).name for root in mods],
            "packages": packages,
            "conflicts": conflicts,
            "externalEntries": external,
            "ownedEntries": owned_entries,
            "loadOrderAfter": load_order_after,
            "priority": "low-to-high; later selected Lexeditor CTP wins whole-resource conflicts",
        }

    @staticmethod
    def _write_package(root: Path, source_ctp: str, resources: list[str], target: Path) -> None:
        if source_ctp:
            shutil.copyfile(source_ctp, target)
            return
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for resource in sorted(resources, key=str.casefold):
                info = zipfile.ZipInfo(resource, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, root.joinpath(*Path(resource).parts).read_bytes(),
                                 compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        game_root = Path(game_root).resolve()
        self.recover(game_root)
        plan = self.activation_plan(mods, game_root)
        destination = Path(plan["destination"])
        parent = destination.parent
        backup = parent / f".{OWNED_NAMESPACE}-recovery"
        if backup.exists():
            raise RuntimeError(f"A previous Chrono Trigger mod change needs recovery: {backup}")
        parent.mkdir(parents=True, exist_ok=True)

        config_path = Path(plan["config"])
        config = _config(config_path)
        config["mods"]["load_order"] = list(plan["loadOrderAfter"])
        config_temp = _write_config(config_path, config)
        required = sum(
            Path(row["sourceCtp"]).stat().st_size if row["sourceCtp"] else
            sum((Path(row["root"]).joinpath(*Path(resource).parts).stat().st_size
                 for resource in row["resources"]))
            for row in plan["packages"]
        )
        if required > shutil.disk_usage(parent).free:
            config_temp.unlink(missing_ok=True)
            raise OSError("There is not enough space to stage the selected Chrono Trigger mods")

        try:
            with tempfile.TemporaryDirectory(prefix=".lexeditor-chrono-", dir=parent) as temp:
                staged = Path(temp) / OWNED_NAMESPACE
                staged.mkdir()
                deployed_packages = []
                for row in plan["packages"]:
                    target = staged / row["name"]
                    self._write_package(Path(row["root"]), row["sourceCtp"], row["resources"], target)
                    deployed_packages.append({
                        "name": row["name"], "sha256": digest(target),
                        "resources": row["resources"],
                    })
                marker = {
                    **plan,
                    "packages": deployed_packages,
                }
                (staged / DEPLOYMENT_FILE).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
                if destination.exists():
                    self._verify_deployment(destination)
                    destination.rename(backup)
                staged.rename(destination)
                try:
                    os.replace(config_temp, config_path)
                except Exception:
                    self._verify_deployment(destination)
                    shutil.rmtree(destination)
                    if backup.exists():
                        backup.rename(destination)
                    raise
            if backup.exists():
                self._verify_deployment(backup)
                shutil.rmtree(backup)
        finally:
            config_temp.unlink(missing_ok=True)
        return marker
