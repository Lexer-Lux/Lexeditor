"""FF7 dataset availability and bounded character edits; no game assets bundled.

Character layout: Shojy/Elena d85e026, Sections/CharacterData.cs and
KernelSection.cs. Initial records are nine 132-byte slots in section 4;
limit-learning thresholds are in nine 56-byte slots in section 3.
"""
from __future__ import annotations

from copy import deepcopy
import os
import shutil
import tempfile
from threading import RLock
from pathlib import Path
import struct
import zlib

from . import kernel as base

INITIAL_FIELDS = (
    base.Field("level", "Starting level", 0x01),
    *(base.Field(key, label, offset) for offset, key, label in (
        (0x02, "strength", "Strength"), (0x03, "vitality", "Vitality"),
        (0x04, "magic", "Magic"), (0x05, "spirit", "Spirit"),
        (0x06, "dexterity", "Dexterity"), (0x07, "luck", "Luck"),
        (0x08, "strengthBonus", "Strength bonus"), (0x09, "vitalityBonus", "Vitality bonus"),
        (0x0A, "magicBonus", "Magic bonus"), (0x0B, "spiritBonus", "Spirit bonus"),
        (0x0C, "dexterityBonus", "Dexterity bonus"), (0x0D, "luckBonus", "Luck bonus"),
    )),
    *(base.Field(key, label, offset, "H", maximum=65535) for offset, key, label in (
        (0x2C, "currentHp", "Starting current HP"), (0x2E, "baseHp", "Base HP"),
        (0x30, "currentMp", "Starting current MP"), (0x32, "baseMp", "Base MP"),
        (0x38, "maxHp", "Starting maximum HP"), (0x3A, "maxMp", "Starting maximum MP"),
    )),
    base.Field("currentExp", "Starting experience", 0x3C, "I", maximum=0xFFFFFFFF),
    base.Field("expToNextLevel", "Experience to next level", 0x80, "I", maximum=0xFFFFFFFF),
)
LIMIT_FIELDS = tuple(base.Field(key, label, offset, "H", maximum=65535)
    for offset, key, label in (
        (0x18, "killsForLimit2", "Kills to learn level 2"),
        (0x1A, "killsForLimit3", "Kills to learn level 3"),
        (0x1C, "usesForLimit12", "Uses to learn limit 1-2"),
        (0x20, "usesForLimit22", "Uses to learn limit 2-2"),
        (0x24, "usesForLimit32", "Uses to learn limit 3-2"),
    ))
CHARACTER_NOTE = (
    "Starting stats and limit-learning thresholds only. Starting stats do not rewrite "
    "existing saves; recruitment scripts can override them. Equipment, learned limits, "
    "growth curves and character AI are preserved, not edited. Slots 6 and 7 are also "
    "used for Young Cloud and Sephiroth. Numeric bounds are storage bounds, not a "
    "promise that every value is sensible in game."
)
CATEGORIES = dict(base.CATEGORIES)
CATEGORIES["characters"] = base.Category(
    "characters", "Characters", 4, 0, 0, 132, INITIAL_FIELDS + LIMIT_FIELDS)
UNRESOLVED = {
    "enemies": {
        "label": "Enemies", "source": "Battle scene data (scene.bin)",
        "reason": "The plugin has no scene archive reader/writer connected for enemies, attacks or rewards.",
        "unlock": "Implement scene parsing, record schemas and safe archive repacking; verify the installed product's deployment path and text sources.",
    },
    "encounters": {
        "label": "Encounters", "source": "Battle formations and field/world encounter placement",
        "reason": "Formation composition and where encounters occur are separate datasets; neither is connected here.",
        "unlock": "Connect formation and placement readers/writers, preserve their cross-references, and verify deployment for each product.",
    },
    "shops": {
        "label": "Shops", "source": "Shop inventories, prices and shop-opening scripts",
        "reason": "No product-specific shop source and writable deployment path has been verified by this plugin.",
        "unlock": "Identify the installed product's shop tables and script references, then implement bounded editing and write/readback tests.",
    },
}
READ_ERRORS = (OSError, ValueError, EOFError, struct.error, zlib.error)
_SAVE_LOCK = RLock()


class Kernel(base.Kernel):
    """Extend the established container without rewriting unexposed bytes."""

    def _character_sections(self):
        initial, growth = self.sections[3], self.sections[2]
        if len(initial) < 9 * 132 or len(growth) < 9 * 56:
            raise ValueError("Character initialization/growth section is truncated")
        return initial, growth

    def records(self, category_key):
        if category_key != "characters":
            return super().records(category_key)
        initial, growth = self._character_sections()
        rows = []
        for index in range(9):
            record = initial[index * 132:(index + 1) * 132]
            limits = growth[index * 56:(index + 1) * 56]
            values = {f.key: base._read_field(record, f) for f in INITIAL_FIELDS}
            values.update({f.key: base._read_field(limits, f) for f in LIMIT_FIELDS})
            rows.append({"id": index,
                "name": base._decode_text(record[0x10:0x1C]) or f"Character slot {index}",
                "description": CHARACTER_NOTE, "values": values})
        return rows

    def apply(self, category_key, records):
        # Validate the source before allowing even the legacy writer to touch it.
        self.records(category_key)
        if category_key != "characters":
            return super().apply(category_key, records)
        if not isinstance(records, list) or len(records) != 9:
            raise ValueError("Characters must contain exactly nine records")
        initial, growth = map(bytearray, self._character_sections())
        fields = {f.key for f in INITIAL_FIELDS + LIMIT_FIELDS}
        seen = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Character record must be an object")
            index, values = record.get("id"), record.get("values")
            if type(index) is not int or not 0 <= index < 9 or index in seen:
                raise ValueError("Character slot must be a unique integer from 0 to 8")
            if not isinstance(values, dict) or set(values) != fields:
                raise ValueError("Character record has an invalid field set")
            seen.add(index)
            for section, stride, selected in (
                (initial, 132, INITIAL_FIELDS), (growth, 56, LIMIT_FIELDS)):
                start = index * stride
                data = section[start:start + stride]
                for field in selected:
                    base._write_field(data, field, values[field.key])
                section[start:start + stride] = data
        # A rejected record must leave both sections untouched.
        self.sections[3], self.sections[2] = initial, growth


def category_metadata():
    result = base.category_metadata()
    result.append({"id": "characters", "label": "Characters", "note": CHARACTER_NOTE,
        "fields": [{"key": f.key, "label": f.label, "dataType": "int",
            "minimum": f.minimum, "maximum": f.maximum, "step": f.scale,
            "group": "Starting stats" if f in INITIAL_FIELDS else "Limit learning"}
            for f in INITIAL_FIELDS + LIMIT_FIELDS]})
    return result


def load_datasets(game_root: Path, project_root: Path) -> dict:
    """Keep unavailable categories visible without hiding the rest of the editor."""
    result = {"contract": "Lexeditor.ff7-kernel", "categories": category_metadata(),
        "records": {}, "vanilla": {}, "errors": {}, "unresolved": deepcopy(UNRESOLVED),
        "sourceRelativePath": None, "projectPath": None, "usingProject": False,
        "sourceSha256": None, "activeSha256": None}
    try:
        source, relative = base.resolve_kernel(game_root)
        project = project_root / relative
        result.update(sourceRelativePath=relative.as_posix(), projectPath=str(project),
                      usingProject=project.is_file())
        vanilla = Kernel(source)
        current = Kernel(project if project.is_file() else source)
        result.update(sourceSha256=vanilla.sha256, activeSha256=current.sha256)
    except READ_ERRORS as error:
        result["errors"] = {key: str(error) for key in CATEGORIES}
        return result
    for key in CATEGORIES:
        try:
            original, active = vanilla.records(key), current.records(key)
            if len(original) != len(active):
                raise ValueError("Project and installed source have different record counts")
            if not active:
                raise ValueError("The dataset contains no records")
            result["records"][key], result["vanilla"][key] = active, original
        except READ_ERRORS as error:
            result["errors"][key] = str(error)
    return result


def save_datasets(game_root: Path, project_root: Path, payload: object) -> dict:
    with _SAVE_LOCK:
        return _save_datasets(game_root, project_root, payload)


def _save_datasets(game_root: Path, project_root: Path, payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), dict):
        raise ValueError("Save payload must contain a records object")
    available = load_datasets(game_root, project_root)
    records = payload["records"]
    if not records or set(records) != set(available["records"]):
        raise ValueError("Save must contain exactly the readable FF7 datasets; reload the editor")
    # New clients provide a snapshot; retain compatibility with installed smoke clients.
    for key in ("activeSha256", "sourceSha256"):
        if key in payload and payload[key] != available[key]:
            raise ValueError("FF7 data changed outside this editor. Reload before saving.")
    source, relative = base.resolve_kernel(game_root)
    target = project_root / relative
    if target.resolve() == source.resolve() or (target.exists() and target.samefile(source)):
        raise ValueError("The mod project must not overwrite the installed KERNEL.BIN")
    kernel = Kernel(target if target.is_file() else source)
    if kernel.sha256 != available["activeSha256"]:
        raise ValueError("FF7 data changed while preparing the save. Reload before saving.")
    for key, rows in records.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{key} records must be a list of objects")
        kernel.apply(key, rows)
    # Check all decoded values before replacing the project file.
    for key, rows in records.items():
        expected = {row["id"]: row["values"] for row in rows}
        if {row["id"]: row["values"] for row in kernel.records(key)} != expected:
            raise ValueError(f"{key} failed pre-save verification")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    backup = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(kernel.to_bytes())
        verified = Kernel(temporary)
        for key in records:
            if verified.records(key) != kernel.records(key):
                raise ValueError(f"{key} failed binary readback before replacement")
        current_path = target if target.is_file() else source
        if Kernel(current_path).sha256 != available["activeSha256"] or Kernel(source).sha256 != available["sourceSha256"]:
            raise ValueError("FF7 data changed while preparing the save. Reload before saving.")
        if target.is_file():
            backup = target.with_name(target.name + ".lexeditor.bak")
            shutil.copy2(target, backup)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    verified = Kernel(target)
    for key, rows in records.items():
        if {row["id"]: row["values"] for row in verified.records(key)} != {
                row["id"]: row["values"] for row in rows}:
            raise ValueError(f"{key} failed saved-file verification")
    return {"saved": True, "path": str(target), "sha256": verified.sha256,
        "bytes": target.stat().st_size, "backup": str(backup) if backup else None}
