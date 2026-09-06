"""FF7 dataset availability and bounded character edits; no game assets bundled.

Character layout: Shojy/Elena d85e026, Sections/CharacterData.cs and
KernelSection.cs. Initial records are nine 132-byte slots in section 4;
growth and limit fields are in nine 56-byte slots in section 3.
"""
from __future__ import annotations

from copy import deepcopy
import tempfile
from threading import RLock
from pathlib import Path
import struct
import zlib

from . import kernel as base
from . import kernel_extra
from .storage import target_path, replace_project, records_match

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
INITIAL_FIELDS += tuple(base.Field(key, label, offset, kind, maximum=maximum)
    for key, label, offset, kind, maximum in (
        ("storedId", "Stored character ID (slot identity is unchanged)", 0, "B", 255),
        ("limitLevel", "Starting limit level", 0x0E, "B", 255),
        ("limitBar", "Starting limit gauge", 0x0F, "B", 255),
        ("weaponId", "Starting weapon ID", 0x1C, "B", 255),
        ("armorId", "Starting armor ID", 0x1D, "B", 255),
        ("accessoryId", "Starting accessory ID (255: none)", 0x1E, "B", 255),
        ("characterFlags", "Starting character flags", 0x1F, "B", 255),
        ("rowByte", "Starting row (254: back)", 0x20, "B", 255),
        ("levelProgress", "Level progress gauge", 0x21, "B", 255),
        ("learnedLimits", "Learned limit flags", 0x22, "H", 65535),
        ("killCount", "Starting kill count", 0x24, "H", 65535),
        ("limit1Uses", "Starting level 1 limit uses", 0x26, "H", 65535),
        ("limit2Uses", "Starting level 2 limit uses", 0x28, "H", 65535),
        ("limit3Uses", "Starting level 3 limit uses", 0x2A, "H", 65535),
    ))
for equipment, offset in (("weapon", 0x40), ("armor", 0x60)):
    for slot in range(8):
        INITIAL_FIELDS += (
            base.Field(f"{equipment}Materia{slot}", f"{equipment.title()} materia {slot + 1} ID (255: empty)", offset + slot * 4),
            base.Field(f"{equipment}MateriaAp{slot}", f"{equipment.title()} materia {slot + 1} AP", offset + slot * 4 + 1, "3", maximum=0xFFFFFF),
        )
LIMIT_FIELDS += tuple(base.Field(f"{name}Curve", f"{name.title()} growth curve index", offset)
    for offset, name in enumerate(("strength", "vitality", "magic", "spirit", "dexterity", "luck", "hp", "mp", "experience")))
LIMIT_FIELDS += (base.Field("recruitOffsetRaw", "Recruitment level offset (signed raw byte, half-level units)", 0x0A, "b", minimum=-128, maximum=127),)
LIMIT_FIELDS += tuple(base.Field(f"limitAttack{level}", f"Limit {level} attack ID", offset)
    for level, offset in (("11", 0x0C), ("12", 0x0D), ("21", 0x0F), ("22", 0x10), ("31", 0x12), ("32", 0x13), ("4", 0x15)))
LIMIT_FIELDS += tuple(base.Field(f"limitHpDivisor{i + 1}", f"Limit level {i + 1} HP divisor", 0x28 + i * 4, "I", maximum=0xFFFFFFFF) for i in range(4))
CHARACTER_NOTE = (
    "Initial stats, equipment, materia/AP, limit learning and growth-curve selection. "
    "These do not rewrite existing saves; recruitment scripts can override them. "
    "Curve coefficients, initial names and AI have their own editors. Slots 6/7 "
    "also hold Young Cloud/Sephiroth; Cait Sith/Vincent initialization in the executable "
    "is edited under Recruits. Numeric bounds describe storage, not sensible gameplay."
)
CATEGORIES = dict(base.CATEGORIES)
CATEGORIES["characters"] = base.Category(
    "characters", "Characters", 4, 0, 0, 132, INITIAL_FIELDS + LIMIT_FIELDS)
for key, spec in kernel_extra.EXTRAS.items():
    CATEGORIES[key] = base.Category(key, spec['label'], spec['section'], 0, 0,
                                    spec.get('size', 1), tuple(spec['fields']))
UNRESOLVED = {}  # Non-kernel source families are handled by extended.py.
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
        if category_key in kernel_extra.EXTRAS:
            return kernel_extra.records(self, category_key)
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
        if category_key in kernel_extra.EXTRAS:
            return kernel_extra.apply(self, category_key, records)
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
            "group": "Starting stats" if f in INITIAL_FIELDS else "Growth and limits"}
            for f in INITIAL_FIELDS + LIMIT_FIELDS]})
    result.extend(dict(id=key, label=spec['label'], fields=spec['fields'])
                  for key, spec in kernel_extra.EXTRAS.items())
    return result


def load_datasets(game_root: Path, project_root: Path) -> dict:
    """Keep unavailable categories visible without hiding the rest of the editor."""
    result = {"contract": "Lexeditor.ff7-kernel", "categories": category_metadata(),
        "records": {}, "vanilla": {}, "errors": {}, "unresolved": deepcopy(UNRESOLVED),
        "sourceRelativePath": None, "projectPath": None, "usingProject": False,
        "sourceSha256": None, "activeSha256": None}
    try:
        source, relative = base.resolve_kernel(game_root)
        project = target_path(game_root, project_root, source, relative)
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
    if project_root.resolve().is_relative_to(game_root.resolve()):
        raise ValueError("The project must not overwrite the installed KERNEL or other game data")
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), dict):
        raise ValueError("Save payload must contain a records object")
    available = load_datasets(game_root, project_root)
    records = payload["records"]
    if not records or set(records) != set(available["records"]):
        raise ValueError("Save must contain exactly the readable FF7 datasets; reload the editor")
    for key in ('activeSha256', 'sourceSha256', 'usingProject'):
        if key not in payload or type(payload[key]) is not type(available[key]) or payload[key] != available[key]:
            raise ValueError('FF7 data changed outside this editor. Reload before saving.')
    source, relative = base.resolve_kernel(game_root)
    target = target_path(game_root, project_root, source, relative)
    existed = target.exists()
    original = source.read_bytes()
    from .format_codec import digest
    if digest(original) != available['sourceSha256']:
        raise ValueError('Installed FF7 data changed while preparing the save. Reload before saving.')
    active = target.read_bytes() if existed else original
    kernel = Kernel(target if existed else source)
    if kernel.sha256 != available['activeSha256']:
        raise ValueError('FF7 data changed while preparing the save. Reload before saving.')
    for key, rows in records.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f'{key} records must be a list of objects')
        kernel.apply(key, rows)
    for key, rows in records.items():
        if not records_match(key, rows, kernel.records(key)):
            raise ValueError(f'{key} failed pre-save verification')
    output = kernel.to_bytes()
    # Readback must pass before replacing even a project file.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.verify', delete=False) as stream:
        checked = Path(stream.name); stream.write(output)
    try:
        verified = Kernel(checked)
        for key, rows in records.items():
            if not records_match(key, rows, verified.records(key)):
                raise ValueError(f'{key} failed binary readback')
    finally:
        checked.unlink(missing_ok=True)
    def check():
        target_path(game_root, project_root, source, relative)
        if source.read_bytes() != original:
            raise ValueError('FF7 installed source changed while saving; reload')
    backup = replace_project(target, output, active, existed, check)
    verified = Kernel(target)
    return {'saved': True, 'path': str(target), 'sha256': verified.sha256,
            'bytes': len(output), 'backup': backup, 'usingProject': True,
            'records': {key: verified.records(key) for key in records}}
