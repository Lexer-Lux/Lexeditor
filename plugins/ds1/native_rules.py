"""Project-owned native-rule editing, composed with the library's tweak mods.

The editor owns data, not a built-in balance preset. New projects start with
vanilla values. The library Tweaks screen remains independent and schema-driven.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from core.plugin_files import atomic_write
from . import deployment, encumbrance, load_bands, load_bands_patch
from . import stamina_patch as legacy_native
from . import tweak_mods
from .formats import ItemDocument, MAX_ARCHIVE
from .store import MARKER, RELATIVE

SETTINGS_FILE = ".lexeditor-ds1-native-rules.json"
LEGACY_FILE = ".lexeditor-ds1-stamina.json"
SETTINGS_LIMIT = 32768
DEFAULTS = {"baseRecovery": 45.0, "nextBandId": 5, **load_bands.project_defaults()}


def digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def settings(value):
    if type(value) is not dict or set(value) != set(DEFAULTS):
        raise ValueError("Unsupported native-rule settings")
    projection = load_bands.native_projection(value)
    bands = load_bands.validate_bands(value["bands"])
    identity = value["nextBandId"]
    if type(identity) is not int or not max(b["id"] for b in bands) < identity <= 2**31 - 1024:
        raise ValueError("Invalid next load-band identity")
    return {**projection, "bands": bands, "nextBandId": identity}


def _read_optional(path, limit):
    path = tweak_mods.checked(path)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f"Unsupported file type or size: {path.name}")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"File exceeds its size limit: {path.name}")
    return raw


class NativeRules:
    def __init__(self, game_root, project=None, read_only=True):
        self.game_root = tweak_mods.checked(Path(game_root))
        self.project = tweak_mods.checked(Path(project)) if project else None
        self.read_only = bool(read_only or self.project is None)
        self.legacy = None
        self.saved, self.saved_hash = self._read()
        self.value = deepcopy(self.saved)
        self.live = {"available": False, "backupOk": False, "rate": None, "problem": ""}

    def _path(self):
        if self.project is None:
            raise PermissionError("Select or create a mod before editing native rules")
        game, project = tweak_mods.checked(self.game_root), tweak_mods.checked(self.project)
        deployment._assert_disjoint(game, project)
        if _read_optional(project / MARKER, 4096) is None:
            raise ValueError("Select a valid Remastered mod project")
        return tweak_mods.checked(project / SETTINGS_FILE)

    def _read(self):
        if self.project is None:
            return deepcopy(DEFAULTS), None
        self.legacy = None
        raw = _read_optional(self._path(), SETTINGS_LIMIT)
        if raw is not None:
            content = json.loads(raw)
            if (type(content) is not dict or set(content) != {"schema", "rules"}
                    or type(content["schema"]) is not int or content["schema"] != 1):
                raise ValueError("Unsupported native-rule settings file")
            return settings(content["rules"]), digest(raw)
        # Read the predecessor's draft settings without ever overwriting them.
        legacy_raw = _read_optional(self.project / LEGACY_FILE, SETTINGS_LIMIT)
        self.legacy = None
        if legacy_raw is None:
            return deepcopy(DEFAULTS), None
        content = json.loads(legacy_raw)
        from .legacy_stamina import parse
        value = parse(content)
        migrated = deepcopy(DEFAULTS)
        if value["enabled"]:
            migrated["baseRecovery"] = value["baseRecovery"]
        if value["encumbranceEnabled"]:
            for key in ("bands", "nextBandId", "specialLight", "forcedRecovery"):
                migrated[key] = deepcopy(value[key])
        self.legacy = {"value": value, "sha256": digest(legacy_raw)}
        return settings(migrated), None

    def editable(self):
        if self.read_only:
            raise PermissionError("Vanilla and reference mods are read-only")
        self._path()

    @property
    def dirty_count(self):
        return sum(self.value[key] != self.saved[key] for key in DEFAULTS)

    def validate_save(self):
        self.editable()
        if digest(_read_optional(self._path(), SETTINGS_LIMIT)) != self.saved_hash:
            raise ValueError("Native-rule settings changed outside this editor; discard and reload")
        if self.legacy is not None:
            if digest(_read_optional(self.project / LEGACY_FILE, SETTINGS_LIMIT)) != self.legacy["sha256"]:
                raise ValueError("Legacy settings changed outside this editor; discard and reload")

    def save(self):
        self.validate_save()
        if self.dirty_count:
            raw = (json.dumps({"schema": 1, "rules": self.value}, indent=2, allow_nan=False) + "\n").encode()
            atomic_write(self._path(), raw)
            self.saved, self.saved_hash = deepcopy(self.value), digest(raw)
        return self.snapshot()

    def discard(self):
        self.saved, self.saved_hash = self._read()
        self.value = deepcopy(self.saved)
        return self.snapshot()

    def band_revision(self):
        return digest(json.dumps({k: self.value[k] for k in
            ("bands", "nextBandId", "specialLight", "forcedRecovery")},
            sort_keys=True, separators=(",", ":")).encode())

    def snapshot(self, refresh=False):
        if refresh:
            state = tweak_mods.status(self.game_root)
            self.live = {"available": not bool(state["problem"]), "backupOk": state["backupOk"],
                         "problem": state["problem"], "rate": None}
            if not state["problem"]:
                image = tweak_mods._read(self.game_root / tweak_mods.exe_patches.EXECUTABLE)
                import struct
                if len(image) >= legacy_native.BASELINE_OFFSET + 4:
                    self.live["rate"] = struct.unpack_from("<f", image, legacy_native.BASELINE_OFFSET)[0]
        migration = ""
        if self.legacy is not None:
            migration = "Imported the active native values from the earlier draft. Its original settings file remains unchanged."
            if self.legacy["value"]["enabled"]:
                migration += " Its old shield preset is not applied automatically. Set the shield's value in Effects before Apply."
        return {**deepcopy(self.value), "saved": deepcopy(self.saved),
                "dirtyCount": self.dirty_count, "bandRevision": self.band_revision(),
                "maxBands": load_bands.MAX_BANDS, "readOnly": self.read_only,
                "native": dict(self.live), "migration": migration}

    def list_rows(self, tab):
        if tab == "encumbrance":
            lower, result = 0, []
            for band in self.value["bands"]:
                upper = band["upper"]
                label = ("0" if lower == 0 else f">{lower:g}") + "%"
                if upper is not None:
                    label += f" to {upper:g}%"
                result.append({"id": 1000 + band["id"], "table": "NativeRules",
                               "name": band["name"], "range": label})
                lower = upper
            return result
        if tab == "encumbrance-overrides":
            return [{"id": 200, "table": "NativeRules", "name": "Effect-driven overrides"}]
        if tab == "misc":
            return [{"id": 0, "table": "NativeRules", "name": "Stamina"}]
        raise ValueError("Unknown native-rules tab")

    def read_row(self, row_id):
        if type(row_id) is not int:
            raise ValueError("Invalid native rule identity")
        if row_id >= 1001:
            return encumbrance.row(row_id - 1000, self.value, read_only=self.read_only)
        if row_id == 200:
            return encumbrance.overrides(self.value, read_only=self.read_only)
        if row_id == 0:
            field = encumbrance.number("baseRecovery", "Base regeneration (stamina/second)",
                self.value["baseRecovery"], 0, 200,
                "Sets recovery before active effect bonuses and load penalties. The original rate is 45. Save and Apply to use this value.")
            field["disabled"] = self.read_only
            return {"id": 0, "table": "NativeRules", "name": "Stamina", "fields": [field]}
        raise ValueError("Unknown native rule identity")

    def edit_row(self, row_id, key, value):
        self.editable()
        field = next((f for f in self.read_row(row_id)["fields"]
                      if f["key"] == key and f["editable"]), None)
        if field is None or field.get("disabled"):
            raise ValueError("This native rule is not editable")
        updates = {}
        if row_id >= 1001:
            updates["bands"] = load_bands.edit(self.value["bands"], row_id - 1000, key, value)
        elif row_id == 200:
            if key == "specialEnabled":
                if type(value) not in (int, bool) or value not in (0, 1):
                    raise ValueError("Expected a checkbox value")
                updates["specialLight"] = {**self.value["specialLight"], "enabled": bool(value)}
            elif key == "specialRecovery":
                updates["specialLight"] = {**self.value["specialLight"], "recovery": value}
            else:
                updates["forcedRecovery"] = value
        else:
            updates["baseRecovery"] = value
        self.value = settings({**self.value, **updates})
        return self.read_row(row_id)

    def band_action(self, action, row_id, *, revision, at=None, neighbour=None, keep=None):
        self.editable()
        if type(revision) is not str or revision != self.band_revision():
            raise ValueError("Load bands changed. Reload the band list before trying again.")
        if type(row_id) is not int or row_id < 1001:
            raise ValueError("Select a load band")
        if action == "add":
            bands, identity = load_bands.split(self.value["bands"], row_id - 1000, at,
                                               new_id=self.value["nextBandId"])
            updates = {"bands": bands, "nextBandId": self.value["nextBandId"] + 1}
        elif action == "delete":
            if type(neighbour) is not int or neighbour < 1001:
                raise ValueError("Choose a neighbouring load band")
            bands, identity = load_bands.merge(self.value["bands"], row_id - 1000, neighbour - 1000, keep)
            updates = {"bands": bands}
        else:
            raise ValueError("Unknown load-band operation")
        self.value = settings({**self.value, **updates})
        return self.read_row(1000 + identity)

    def _contribution(self, original):
        self.validate_save()
        spec = load_bands_patch.patch_spec(original, load_bands.native_projection(self.saved))
        if not spec["hooks"] and not spec["islands"]:
            return None
        encoded = json.dumps(self.saved, sort_keys=True, separators=(",", ":")).encode()
        return {"path": str(self.project.resolve()), "settingsHash": digest(encoded), "spec": spec}

    def _needs_native(self):
        return (load_bands.native_projection(self.saved) != load_bands.native_projection(DEFAULTS)
                or any(row["enabled"] for row in tweak_mods.tweak_rows())
                or any(tweak_mods.checked(self.game_root / name).exists()
                       for name in (tweak_mods.MANIFEST_FILE, tweak_mods.BACKUP_FILE)))

    def _preflight_params(self, store):
        store.validate_save()
        source = _read_optional(self.project / RELATIVE, MAX_ARCHIVE)
        if source is None:
            raise ValueError("Save the project before applying")
        ItemDocument(source)
        for path in (self.game_root / RELATIVE, deployment._backup_path(self.game_root),
                     deployment._marker_path(self.game_root)):
            tweak_mods.checked(path)
        state = deployment.status(self.game_root, self.project)
        if state["changedExternally"] or (state["everApplied"] and not state["backupOk"]):
            raise ValueError("The installed parameter archive or its original changed outside Lexeditor")
        if not state["everApplied"] and deployment._backup_path(self.game_root).exists():
            raise ValueError("An unmanaged parameter backup already exists")
        return source

    def apply(self, store):
        self.validate_save()
        if self.dirty_count or store.get().dirty_count:
            raise ValueError("Save or discard all changes before applying")
        source = self._preflight_params(store)
        plan = tweak_mods.prepare(self.game_root, project=self._contribution) if self._needs_native() else None

        def checked_source(current):
            self.validate_save()
            store.validate_save()
            if current != source:
                raise ValueError("The saved project changed while Apply was being prepared")
            return current

        # Preflight again after building scripts, before touching installed data.
        checked_source(_read_optional(self.project / RELATIVE, MAX_ARCHIVE))
        if plan is not None:
            tweak_mods.commit(self.game_root, plan)
        try:
            deployment.apply(self.game_root, self.project, transform=checked_source)
        except Exception as error:
            if plan is not None:
                try:
                    tweak_mods.rollback(self.game_root, plan)
                except Exception as rollback_error:
                    raise RuntimeError("Apply stopped with incomplete changes. Retry Apply or Restore original. "
                                       f"{error}; native rollback: {rollback_error}") from error
            raise
        return self.deployment_status()

    def restore(self):
        # Original restoration never changes project values or tweak switches.
        shared = any(tweak_mods.checked(self.game_root / name).exists()
                     for name in (tweak_mods.MANIFEST_FILE, tweak_mods.BACKUP_FILE))
        if shared:
            tweak_mods.restore(self.game_root)
        elif legacy_native.checked(self.game_root / legacy_native.BACKUP).exists():
            legacy_native.install(self.game_root, legacy_native.DEFAULT_RULES)
        deployment.disable(self.game_root)
        return self.deployment_status()

    def deployment_status(self):
        result = deployment.status(self.game_root, self.project)
        result["native"] = tweak_mods.status(self.game_root)
        result["legacyRestoreAvailable"] = False
        if not result["native"]["backupOk"]:
            old_backup = tweak_mods.checked(self.game_root / legacy_native.BACKUP)
            if old_backup.exists():
                try:
                    legacy_native.inspect(self.game_root)
                    result["legacyRestoreAvailable"] = True
                except (ValueError, RuntimeError, OSError):
                    pass
        result["nativeRules"] = self.snapshot()
        current = result["native"].get("project")
        encoded = json.dumps(self.saved, sort_keys=True, separators=(",", ":")).encode()
        active = bool(current and self.project and current["path"] == str(self.project.resolve()))
        result["nativeProjectActive"] = active
        result["nativeStale"] = bool(active and current["settingsHash"] != digest(encoded))
        result["stale"] = bool(result["stale"] or result["nativeStale"])
        return result
