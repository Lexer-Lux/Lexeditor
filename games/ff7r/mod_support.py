"""FF7 Remake Part 1 PAK import checks. Runtime and ReShade are separate."""
from pathlib import Path
import json
import shutil
import tempfile
from mod_library import digest, file_tree, metadata
from .tooling import list_pak, get_file, pack_directory


class PakModAdapter:
    def active_mod_ids(self, game_root: Path) -> list[str]:
        self.recover(game_root)
        destination = game_root / "End/Content/Paks/~mods/LexeditorLibrary"
        if not destination.exists():
            return []
        self._verify_deployment(destination)
        plan = json.loads((destination / "deployment.json").read_text(encoding="utf-8"))
        return plan.get("modIds", [Path(path).name for path in plan.get("mods", [])])

    verified = True
    message = (
        "Imports FF7R PAK folders/ZIPs, rejects exact asset collisions, and deploys "
        "only into Lexeditor's ownership-verified ~mods/LexeditorLibrary folder."
    )
    package_types = ("folder", "zip")

    @staticmethod
    def _verify_deployment(folder: Path) -> None:
        marker = folder / "deployment.json"
        if not marker.is_file():
            raise ValueError("The deployment folder contains unmanaged files")
        old = json.loads(marker.read_text(encoding="utf-8"))
        expected = {p["name"]: p["sha256"] for p in old["packages"]}
        actual = {p.as_posix(): digest(folder / p) for p in file_tree(folder)
                  if p.as_posix() != "deployment.json"}
        if actual != expected:
            raise ValueError("Deployed files changed outside Lexeditor. Preserve those changes before replacing them.")

    def recover(self, game_root: Path) -> None:
        parent = game_root / "End/Content/Paks/~mods"
        destination = parent / "LexeditorLibrary"
        backup = parent / ".LexeditorLibrary-recovery"
        if not backup.exists():
            return
        self._verify_deployment(backup)
        if not destination.exists():
            backup.rename(destination)
            return
        self._verify_deployment(destination)
        if backup.resolve().parent != parent.resolve() or backup.name != ".LexeditorLibrary-recovery":
            raise RuntimeError("Unexpected recovery folder")
        shutil.rmtree(backup)

    def prepare_editable(self, root: Path) -> None:
        """Materialize a copied PAK as editable project content."""
        from mod_library import relative_path, MAX_BYTES
        report = self.inspect(root, file_tree(root))
        if not report["valid"]:
            raise ValueError("; ".join(report["problems"]))
        total = 0
        with tempfile.TemporaryDirectory(prefix=".editable-", dir=root) as temp:
            staged = Path(temp) / "content"
            staged.mkdir()
            for package, entries in report["assets"].items():
                for entry in entries:
                    target = staged / relative_path(entry)
                    if target.exists():
                        raise ValueError(f"Two packages change {entry}; choose one before editing")
                    data = get_file(root / package, entry)
                    total += len(data)
                    if total > MAX_BYTES:
                        raise ValueError("Editable content exceeds the supported size")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            staged.rename(root / "content")
        info = metadata(root)
        info["editableContent"] = True
        (root / "mod.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    def inspect(self, root: Path, files: list[Path]) -> dict:
        if metadata(root).get("editableContent") is True:
            content = [p for p in files if p.parts[0] == "content"]
            problems = []
            if not content:
                problems.append("The editable mod has no content files")
            if any(not p.as_posix().startswith("content/End/Content/") for p in content):
                problems.append("Editable files must be under content/End/Content")
            for path in files:
                if path in content or path.name == "mod.json" or path.suffix.casefold() in {".pak", ".txt", ".md", ".png", ".jpg", ".jpeg"}:
                    continue
                problems.append(f"Unsupported editable project file: {path}")
            return {"valid": not problems, "problems": problems,
                    "packages": ["Editable content"], "assets": {}, "notDeployed": []}
        paks = [p for p in files if p.suffix.casefold() == ".pak"]
        problems = []
        assets = {}
        ignored = []
        names = set()
        for path in files:
            suffix = path.suffix.casefold()
            if suffix == ".pak":
                if path.name.casefold() in names:
                    problems.append(f"Two packages have the same name: {path.name}")
                names.add(path.name.casefold())
                try:
                    entries = list_pak(root / path)
                    if not entries or any(not entry.startswith("End/Content/")
                                          or ".." in entry.split("/") for entry in entries):
                        problems.append(f"{path.name} does not contain supported game content")
                    assets[path.as_posix()] = entries
                except Exception as error:
                    problems.append(f"Cannot read {path.name}: {error}")
            elif path.name.casefold() == "mod.json" or suffix in {".txt", ".md", ".png", ".jpg", ".jpeg"}:
                ignored.append(path.as_posix())
            else:
                problems.append(f"Unsupported file: {path.as_posix()}. This adapter loads PAK content only.")
        if not paks:
            problems.append("No PAK files found. Choose the folder that contains the packaged mod.")
        return {"valid": not problems, "problems": problems,
                "packages": [p.as_posix() for p in paks], "assets": assets,
                "notDeployed": ignored}

    def activation_plan(self, mods: list[Path], game_root: Path) -> dict:
        """Refuse ambiguous overrides until load-order handling is proved."""
        if not (game_root / "End/Binaries/Win64/ff7remake_.exe").is_file():
            raise ValueError("Choose the FF7 Remake Part 1 game folder")
        packages = []
        owners = {}
        filenames = set()
        for root in mods:
            report = self.inspect(root, file_tree(root))
            if not report["valid"]:
                raise ValueError("; ".join(report["problems"]))
            for package, entries in report["assets"].items():
                source = root / package
                if source.name.casefold() in filenames:
                    raise ValueError(f"Two active packages use the name {source.name}")
                filenames.add(source.name.casefold())
                for entry in entries:
                    key = entry.casefold()
                    if key in owners:
                        raise ValueError(f"Conflicting asset {entry}: {owners[key]} and {source.name}")
                    owners[key] = source.name
                packages.append({"source": str(source), "name": source.name,
                                 "sha256": digest(source)})
        destination = game_root / "End/Content/Paks/~mods/LexeditorLibrary"
        # Existing third-party PAKs must also take part in conflict checks.
        pak_root = game_root / "End/Content/Paks/~mods"
        if pak_root.exists():
            for path in file_tree(pak_root):
                if path.suffix.casefold() != ".pak" or path.parts[0] == "LexeditorLibrary":
                    continue
                for entry in list_pak(pak_root / path):
                    if entry.casefold() in owners:
                        raise ValueError(f"An installed mod also changes {entry}: {path}")
        return {"destination": str(destination), "packages": packages,
                "mods": [str(root) for root in mods], "modIds": [root.name for root in mods]}

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        """Build editable sources before applying the owned package set."""
        self.recover(game_root)
        with tempfile.TemporaryDirectory(prefix="lexeditor-editable-build-") as temp:
            prepared = []
            for index, root in enumerate(mods):
                if metadata(root).get("editableContent") is not True:
                    prepared.append(root)
                    continue
                report = self.inspect(root, file_tree(root))
                if not report["valid"]:
                    raise ValueError("; ".join(report["problems"]))
                folder = Path(temp) / str(index)
                folder.mkdir()
                pack_directory(root / "content", folder / (root.name + "_P.pak"), version="V4")
                prepared.append(folder)
            return self._activate_prepared(prepared, game_root, mods)

    def _activate_prepared(self, mods: list[Path], game_root: Path, logical_mods: list[Path]) -> dict:
        """Replace only our verified deployment; keep the old set on failure."""
        plan = self.activation_plan(mods, game_root)
        plan["mods"] = [str(root) for root in logical_mods]
        plan["modIds"] = [root.name for root in logical_mods]
        destination = Path(plan["destination"])
        parent = destination.parent
        backup = parent / ".LexeditorLibrary-recovery"
        # Never erase a recovery copy after an interrupted change.
        if backup.exists():
            raise RuntimeError(f"A previous change needs recovery: {backup}")
        if destination.exists():
            self._verify_deployment(destination)
        parent.mkdir(parents=True, exist_ok=True)
        required = sum(Path(p["source"]).stat().st_size for p in plan["packages"])
        if required > shutil.disk_usage(parent).free:
            raise OSError("There is not enough space to activate these mods")
        with tempfile.TemporaryDirectory(prefix=".lexeditor-activate-", dir=parent) as temp:
            staged = Path(temp) / "content"
            staged.mkdir()
            for package in plan["packages"]:
                target = staged / package["name"]
                shutil.copyfile(package["source"], target)
                if digest(target) != package["sha256"]:
                    raise OSError(f"Package changed during activation: {package['name']}")
            (staged / "deployment.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            if destination.exists():
                destination.rename(backup)
            try:
                staged.rename(destination)
            except Exception:
                if backup.exists():
                    backup.rename(destination)
                raise
        if backup.exists():
            if backup.resolve().parent != parent.resolve() or backup.name != ".LexeditorLibrary-recovery":
                raise RuntimeError("Unexpected recovery folder")
            shutil.rmtree(backup)
        return plan
