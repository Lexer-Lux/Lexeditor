"""Safe editor model for Palworld's official v0.7+ mod-package ``Info.json``.

The official loader treats ``Info.json`` as package metadata and copies package
Targets according to InstallRule.  This module deliberately stops at that
package boundary: Unreal PAK/uasset payloads are recognized by the plugin but
are not parsed here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any


INFO_FILENAME = "Info.json"
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9]+$")
INSTALL_RULE_TYPES = ("Lua", "Paks", "LogicMods", "UE4SS", "PalSchema")
OFFICIAL_TAGS = (
    "PalSchema",
    "UE4SS",
    "Model Replacement",
    "Utilities",
    "Gameplay",
    "User Interface",
)
EDITABLE_FIELDS = frozenset(
    {
        "ModName",
        "PackageName",
        "Thumbnail",
        "Version",
        "DebugMode",
        "MinRevision",
        "Author",
        "Dependencies",
        "Tags",
        "InstallRule",
    }
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str


class PackageValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues if issue.severity == "error"))


class StaleInfoError(RuntimeError):
    """Raised when Info.json changed on disk after Lexeditor loaded it."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _target_is_safe(value: str) -> bool:
    """Package targets must stay relative to the package root.

    Pocketpair's examples use values such as ``./Scripts`` and ``./Paks/``.
    Normalizing to PurePosixPath lets the same validation run on every host OS
    without accidentally accepting a Windows drive/UNC path.
    """
    text = value.strip().replace("\\", "/")
    if not text or text.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", text):
        return False
    parts = PurePosixPath(text).parts
    return ".." not in parts


def validate_info(data: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def error(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue("error", code, path, message))

    def warning(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue("warning", code, path, message))

    if not isinstance(data, dict):
        return [ValidationIssue("error", "root.type", "$", "Info.json must contain one JSON object.")]

    package_name = data.get("PackageName")
    if not isinstance(package_name, str) or not package_name.strip():
        error("package.required", "PackageName", "PackageName is required.")
    elif not PACKAGE_NAME_RE.fullmatch(package_name.strip()):
        error(
            "package.characters",
            "PackageName",
            "PackageName must contain only ASCII letters and digits, matching the official uploader.",
        )

    for field in ("ModName", "Thumbnail", "Version", "Author"):
        if field in data and not isinstance(data[field], str):
            error("field.string", field, f"{field} must be a string when present.")

    if "DebugMode" in data and not isinstance(data["DebugMode"], bool):
        error("debug.bool", "DebugMode", "DebugMode must be true or false.")

    if "MinRevision" in data:
        revision = data["MinRevision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            error("revision.integer", "MinRevision", "MinRevision must be a non-negative integer.")

    dependencies = data.get("Dependencies", [])
    if not isinstance(dependencies, list):
        error("dependencies.array", "Dependencies", "Dependencies must be an array of package names.")
    else:
        for index, dependency in enumerate(dependencies):
            path = f"Dependencies[{index}]"
            if not isinstance(dependency, str) or not dependency.strip():
                error("dependency.string", path, "Dependency package names must be non-empty strings.")
            elif not PACKAGE_NAME_RE.fullmatch(dependency.strip()):
                error("dependency.characters", path, "Dependency package names must contain only ASCII letters and digits.")

    tags = data.get("Tags", [])
    if not isinstance(tags, list):
        error("tags.array", "Tags", "Tags must be an array of strings.")
    else:
        official = set(OFFICIAL_TAGS)
        for index, tag in enumerate(tags):
            path = f"Tags[{index}]"
            if not isinstance(tag, str) or not tag.strip():
                error("tag.string", path, "Tags must be non-empty strings.")
            elif tag not in official:
                warning("tag.unknown", path, f"Unknown Workshop tag {tag!r}; it will be preserved for forward compatibility.")

    rules = data.get("InstallRule")
    if not isinstance(rules, list) or not rules:
        error("rules.required", "InstallRule", "At least one InstallRule entry is required.")
        return issues

    valid_types = set(INSTALL_RULE_TYPES)
    for index, rule in enumerate(rules):
        base = f"InstallRule[{index}]"
        if not isinstance(rule, dict):
            error("rule.object", base, "Each InstallRule entry must be an object.")
            continue
        rule_type = rule.get("Type")
        if not isinstance(rule_type, str) or not rule_type:
            error("rule.type.required", base + ".Type", "InstallRule Type is required.")
        elif rule_type not in valid_types:
            error("rule.type.unknown", base + ".Type", f"Unsupported InstallRule Type {rule_type!r}.")
        if "IsServer" in rule and not isinstance(rule["IsServer"], bool):
            error("rule.server.bool", base + ".IsServer", "IsServer must be true or false when present.")
        targets = rule.get("Targets")
        if not isinstance(targets, list) or not targets:
            error("rule.targets.required", base + ".Targets", "InstallRule Targets must contain at least one path.")
            continue
        for target_index, target in enumerate(targets):
            path = f"{base}.Targets[{target_index}]"
            if not isinstance(target, str) or not target.strip():
                error("rule.target.string", path, "InstallRule targets must be non-empty strings.")
            elif not _target_is_safe(target):
                error("rule.target.unsafe", path, "InstallRule targets must stay inside the package directory.")
    return issues


def default_info(package_name: str = "LexeditorPalworldMod") -> dict[str, Any]:
    candidate = "".join(character for character in package_name if character.isascii() and character.isalnum())
    if not candidate:
        candidate = "LexeditorPalworldMod"
    return {
        "ModName": candidate,
        "PackageName": candidate,
        "Version": "0.1.0",
        "DebugMode": True,
        "Author": "",
        "Dependencies": [],
        "Tags": [],
        "InstallRule": [{"Type": "Paks", "Targets": ["./Paks/"]}],
    }


class InfoDocument:
    """One Info.json with stale-write protection and unknown-key preservation."""

    def __init__(self, data: dict[str, Any], source_bytes: bytes | None = None):
        self.data = deepcopy(data)
        self._original = deepcopy(data)
        self._source_bytes = source_bytes
        self.source_sha256 = sha256_bytes(source_bytes) if source_bytes is not None else ""

    @classmethod
    def from_bytes(cls, raw: bytes) -> "InfoDocument":
        try:
            value = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid Palworld Info.json: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("Invalid Palworld Info.json: root must be a JSON object")
        return cls(value, raw)

    @classmethod
    def load(cls, path: Path) -> "InfoDocument":
        return cls.from_bytes(Path(path).read_bytes())

    def issues(self) -> list[ValidationIssue]:
        return validate_info(self.data)

    def update(self, changes: dict[str, Any]) -> None:
        unknown = sorted(set(changes) - EDITABLE_FIELDS)
        if unknown:
            raise ValueError("Unsupported Info.json edit fields: " + ", ".join(unknown))
        for key, value in changes.items():
            if value is None:
                self.data.pop(key, None)
            else:
                self.data[key] = deepcopy(value)

    def serialized(self) -> bytes:
        return (json.dumps(self.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def save(self, path: Path, *, expected_sha256: str | None = None, backup: bool = True) -> str:
        destination = Path(path)
        errors = [issue for issue in self.issues() if issue.severity == "error"]
        if errors:
            raise PackageValidationError(errors)

        current = destination.read_bytes() if destination.is_file() else None
        current_sha = sha256_bytes(current) if current is not None else ""
        expected = expected_sha256 if expected_sha256 is not None else self.source_sha256
        if expected and current_sha != expected:
            raise StaleInfoError("Info.json changed on disk after it was loaded; reload before saving.")

        # Byte-exact no-op: opening/saving an untouched document does not reformat it.
        if self.data == self._original and current is not None:
            return current_sha

        payload = self.serialized()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if backup and current is not None:
            backup_path = destination.with_name(destination.name + ".lexeditor.bak")
            shutil.copyfile(destination, backup_path)

        fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

        self._source_bytes = payload
        self.source_sha256 = sha256_bytes(payload)
        self._original = deepcopy(self.data)
        return self.source_sha256
