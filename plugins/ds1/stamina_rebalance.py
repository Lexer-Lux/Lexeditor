"""The shared-UI stamina rebalance: saved settings and an Apply-time overlay.

Effects remain authored project data. The toggle changes the deployed projection,
not those source values. Each installed file has its own verified original and
atomic replacement; a stopped two-file Apply must be retried or restored.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
import json
from pathlib import Path

from core.plugin_files import atomic_write
from . import deployment, stamina_patch as native
from .effects import TABLE, RECOVERY_KEY
from . import encumbrance, load_bands
from .formats import ItemDocument, MAX_ARCHIVE
from .store import RELATIVE, MARKER

TWEAK_ID = "stamina-rebalance"
SETTINGS_FILE = ".lexeditor-ds1-stamina.json"
LEGACY_DEFAULTS = {"enabled": False, "baseRecovery": 60.0, "shieldRecovery": 5,
                   "encumbranceEnabled": False,
                   **{k: v for k, v in native.DEFAULT_RULES.items() if k != "baseRecovery"}}
DEFAULTS = {"enabled": False, "baseRecovery": 60.0, "shieldRecovery": 5,
            "encumbranceEnabled": False, "nextBandId": 5, **load_bands.project_defaults()}
SETTINGS_LIMIT = 32768
SHIELD_BASES = (1453000, 1453100, 1453200, 1453400, 1453600, 1453800)
PASSIVES = ("residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2")
HELP = (
    "Uses base recovery from Misc. and the shield bonus below when you Apply. "
    "The proposed balance is 60 base and +5 shield; the original engine baseline is 45. "
    "Disabling and applying restores that baseline and the project's authored effects."
)
APPLY_HELP = (
    "Save first, then Apply with the game closed. This modifies the supported executable "
    "and installs the saved parameter archive with the shield override; each original is "
    "preserved once. Test offline: game startup and multiplayer safety are not verified."
)


def digest(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def settings(value: dict) -> dict:
    if type(value) is not dict:
        raise ValueError("Unsupported native settings")
    if set(value) == set(LEGACY_DEFAULTS):
        legacy = native.validate_rules({key: value[key] for key in native.DEFAULT_RULES})
        value = {**{k: value[k] for k in ("enabled", "encumbranceEnabled", "shieldRecovery")},
                 "baseRecovery": legacy["baseRecovery"], "nextBandId": 5,
                 **load_bands.legacy_bands(legacy)}
    if set(value) != set(DEFAULTS):
        raise ValueError("Unsupported native settings")
    if type(value["enabled"]) is not bool or type(value["encumbranceEnabled"]) is not bool:
        raise ValueError("Tweaks must be on or off")
    bonus = value["shieldRecovery"]
    if type(bonus) not in (int, float) or not 0 <= bonus <= 100 or int(bonus) != bonus:
        raise ValueError("Shield recovery must be a whole number from 0 to 100")
    bands = load_bands.validate_bands(value["bands"])
    next_id = value["nextBandId"]
    if (type(next_id) is not int or not max(b["id"] for b in bands) < next_id <= 2**31 - 1024):
        raise ValueError("Invalid next load-band identity")
    return {"baseRecovery": native.rate_value(value["baseRecovery"]),
            "enabled": value["enabled"], "encumbranceEnabled": value["encumbranceEnabled"],
            "shieldRecovery": int(bonus), "nextBandId": next_id, "bands": bands,
            "specialLight": load_bands.special(value["specialLight"]),
            "forcedRecovery": load_bands.percent(value["forcedRecovery"])}


def effective_rules(config: dict) -> dict:
    config = settings(config)
    result = dict(native.DEFAULT_RULES)
    if config["enabled"]:
        result["baseRecovery"] = config["baseRecovery"]
    if config["encumbranceEnabled"]:
        projected = load_bands.native_projection({**config, "baseRecovery": result["baseRecovery"]})
        default = load_bands.native_projection({
            **load_bands.project_defaults(), "baseRecovery": result["baseRecovery"]})
        # The ordinary defaults require no executable extension.
        if projected != default:
            return projected
    return native.validate_rules(result)


def shield_targets(document: ItemDocument) -> set[int]:
    """Resolve existing shield variants, refusing ambiguous custom passive sets."""
    if TABLE not in document.params:
        raise ValueError("The stamina rebalance needs SpEffectParam.param")
    rows = [row for row in document.params["EquipParamWeapon"].rows
            if any(base <= row.row_id < base + 100 for base in SHIELD_BASES)]
    if not any(row.row_id == 1453000 for row in rows):
        raise ValueError("Grass Crest Shield is missing from this project")
    known = {row.row_id for row in document.params[TABLE].rows}
    targets = set()
    for row in rows:
        refs = {document.value("EquipParamWeapon", row.row_id, key) for key in PASSIVES}
        refs.discard(-1)
        # Some existing archives use 0 for a vacant passive slot.
        refs.discard(0)
        if not refs or not refs <= known:
            raise ValueError(f"Shield variant {row.row_id} has missing passive effects")
        if 6890 in refs:
            target = 6890
        elif len(refs) == 1:
            target = next(iter(refs))
        else:
            recovery = {ref for ref in refs if document.value(TABLE, ref, RECOVERY_KEY) != 0}
            if len(recovery) != 1:
                raise ValueError(f"Shield variant {row.row_id} has ambiguous recovery effects; edit Effects directly")
            target = next(iter(recovery))
        targets.add(target)
    return targets


def project_overlay(source: bytes, config: dict) -> bytes:
    """Patch only the resolved recovery cells; disabling is byte-exact no-op."""
    config = settings(config)
    document = ItemDocument(source)
    if not config["enabled"]:
        return source
    for effect_id in sorted(shield_targets(document)):
        document.edit(TABLE, effect_id, RECOVERY_KEY, config["shieldRecovery"])
    return document.export()


class StaminaRebalance:
    def __init__(self, game_root, project=None, read_only=True):
        # Preserve lexical paths until the shared reparse guard has checked them.
        self.game_root = Path(game_root)
        self.project = Path(project) if project else None
        self.read_only = bool(read_only or self.project is None)
        self.saved, self.saved_hash = self._read()
        self.value = deepcopy(self.saved)
        self.live = {"available": False, "rate": None, "backupOk": False,
                     "problem": "", "checked": False}

    def _settings_path(self) -> Path:
        if self.project is None:
            raise PermissionError("Select or create a mod before editing tweaks")
        project, game = native.checked(self.project), native.checked(self.game_root)
        deployment._assert_disjoint(game, project)
        marker = native.read_file(project / MARKER, 4096)
        if marker is None:
            raise ValueError("Select a valid Remastered mod project")
        return native.checked(project / SETTINGS_FILE)

    def _read(self) -> tuple[dict, str | None]:
        if self.project is None:
            return deepcopy(DEFAULTS), None
        raw = native.read_file(self._settings_path(), SETTINGS_LIMIT, optional=True)
        if raw is None:
            return deepcopy(DEFAULTS), None
        content = json.loads(raw)
        if type(content) is not dict or set(content) != {"schema", TWEAK_ID} or type(content["schema"]) is not int or content["schema"] not in (1, 2):
            raise ValueError("Unsupported stamina settings file; it was left unchanged")
        values = content[TWEAK_ID]
        expected = LEGACY_DEFAULTS if content["schema"] == 1 else DEFAULTS
        if type(values) is not dict or set(values) != set(expected):
            raise ValueError("Stamina settings do not match their schema version")
        return settings(values), digest(raw)

    def editable(self) -> None:
        if self.read_only:
            raise PermissionError("Vanilla and reference mods are read-only")
        self._settings_path()

    @property
    def dirty_count(self) -> int:
        return sum(self.value[key] != self.saved[key] for key in DEFAULTS)

    def edit(self, key, value) -> dict:
        self.editable()
        if key not in DEFAULTS:
            raise ValueError("Unknown stamina setting")
        self.value = settings({**self.value, key: value})
        return self.snapshot()

    def validate_save(self) -> None:
        self.editable()
        if self._read()[1] != self.saved_hash:
            raise ValueError("Stamina settings changed outside this editor; discard and reload")

    def save(self) -> dict:
        self.validate_save()
        if self.dirty_count:
            raw = (json.dumps({"schema": 2, TWEAK_ID: self.value}, indent=2) + "\n").encode()
            atomic_write(self._settings_path(), raw)
            self.saved, self.saved_hash = deepcopy(self.value), digest(raw)
        return self.snapshot()

    def discard(self) -> dict:
        self.saved, self.saved_hash = self._read()
        self.value = deepcopy(self.saved)
        return self.snapshot()

    def snapshot(self, refresh=False) -> dict:
        if refresh:
            try:
                _, current, backup = native.inspect(self.game_root)
                rate = current["baseRecovery"]
                self.live = {"available": True, "rate": rate, "backupOk": backup,
                             "problem": "", "checked": True, "rules": current}
            except (ValueError, RuntimeError, OSError) as error:
                self.live = {"available": False, "rate": None, "backupOk": False,
                             "problem": str(error), "checked": True}
        return {**deepcopy(self.value), "saved": deepcopy(self.saved), "dirtyCount": self.dirty_count,
                "bandRevision": self.band_revision(), "maxBands": load_bands.MAX_BANDS,
                "readOnly": self.read_only, "native": dict(self.live), "help": HELP,
                "applyHelp": APPLY_HELP}

    def describe_row(self, row: dict, document: ItemDocument) -> dict:
        if not self.value["enabled"] or row["table"] != TABLE:
            return row
        try:
            targets = shield_targets(document)
        except ValueError:
            return row
        if row["id"] in targets:
            for field in row["fields"]:
                if field["key"] == RECOVERY_KEY:
                    field["description"] += (
                        f" Stamina rebalance overrides this authored value with "
                        f"{self.value['shieldRecovery']} on Apply; turn it off to use this value."
                    )
        return row

    def list_rows(self, tab):
        if tab == "encumbrance":
            result = []
            lower = 0
            for band in self.value["bands"]:
                upper = band["upper"]
                label = f"{lower:g}" if lower == 0 else f">{lower:g}"
                label += "%" if upper is None else f"–{upper:g}%"
                result.append({"id": 1000 + band["id"], "table": "NativeRules",
                               "name": band["name"], "range": label})
                lower = upper
            return result
        if tab == "encumbrance-overrides":
            return [{"id": 200, "table": "NativeRules", "name": "Effect-driven overrides"}]
        if tab in ("misc", "tweaks"):
            return [{"id": 0 if tab == "misc" else 100, "table": "NativeRules",
                     "name": "Stamina" if tab == "misc" else "Tweaks"}]
        raise ValueError("Unknown native-rules tab")

    def read_row(self, row_id):
        if type(row_id) is not int:
            raise ValueError("Invalid native rule identity")
        value = self.value
        if row_id >= 1001:
            return encumbrance.row(row_id - 1000, value, read_only=self.read_only)
        if row_id == 200:
            return encumbrance.overrides(value, read_only=self.read_only)
        if row_id == 0:
            rate = native.VANILLA_RATE if self.project is None else value["baseRecovery"]
            field = encumbrance.number("baseRecovery", "Base regeneration (stamina/second)",
                rate, native.MIN_RATE, native.MAX_RATE,
                "Sets recovery before effect bonuses and load penalties. "
                "Used when Stamina rebalance is enabled in Tweaks. The original rate is 45.")
            field["disabled"] = self.read_only or not value["enabled"]
            return {"id": 0, "table": "NativeRules", "name": "Stamina", "fields": [field]}
        if row_id == 100:
            def switch(key, label, help_text):
                return {"key": key, "label": label, "value": value[key], "description": help_text,
                        "editable": True, "disabled": self.read_only, "type": "bool", "dtype": "bool",
                        "minimum": 0, "maximum": 1, "enum": {}, "group": label}
            bonus = encumbrance.number("shieldRecovery", "Grass Crest Shield bonus (stamina/second)",
                value["shieldRecovery"], 0, 100,
                "Overrides the recovery effect used by existing Grass Crest Shield variants on Apply. "
                "Other items sharing that effect change too. Disabling restores the saved project's effect values.",
                group="Stamina rebalance")
            bonus.update(dtype="s32", step=1, disabled=self.read_only or not value["enabled"])
            return {"id": 100, "table": "NativeRules", "name": "Tweaks", "fields": [
                switch("enabled", "Stamina rebalance", HELP), bonus,
                switch("encumbranceEnabled", "Encumbrance rules", encumbrance.HELP)]}
        raise ValueError("Unknown native rule identity")

    def band_revision(self):
        encoded = json.dumps({k: self.value[k] for k in
                             ("bands", "nextBandId", "specialLight", "forcedRecovery")},
                             sort_keys=True, separators=(",", ":")).encode()
        return digest(encoded)

    def band_action(self, action, row_id, *, revision, at=None, neighbour=None, keep=None):
        self.editable()
        if not self.value["encumbranceEnabled"]:
            raise ValueError("Enable Encumbrance rules before changing bands")
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
            bands, identity = load_bands.merge(self.value["bands"], row_id - 1000,
                                               neighbour - 1000, keep)
            updates = {"bands": bands}
        else:
            raise ValueError("Unknown load-band operation")
        self.value = settings({**self.value, **updates})
        return self.read_row(1000 + identity)

    def edit_row(self, row_id, key, value):
        self.editable()
        field = next((f for f in self.read_row(row_id)["fields"]
                      if f["key"] == key and f["editable"]), None)
        if field is None:
            raise ValueError("This native rule is not editable")
        if field.get("disabled") and key not in ("enabled", "encumbranceEnabled"):
            raise ValueError("Enable the related tweak before editing its rules")
        if row_id >= 1001:
            bands = load_bands.edit(self.value["bands"], row_id - 1000, key, value)
            self.edit("bands", bands)
        elif row_id == 200:
            if key == "specialEnabled":
                if type(value) not in (int, bool) or value not in (0, 1):
                    raise ValueError("Expected a checkbox value")
                self.edit("specialLight", {**self.value["specialLight"], "enabled": bool(value)})
            elif key == "specialRecovery":
                self.edit("specialLight", {**self.value["specialLight"], "recovery": value})
            else:
                self.edit("forcedRecovery", value)
        else:
            if key in ("enabled", "encumbranceEnabled"):
                if type(value) not in (int, bool) or value not in (0, 1):
                    raise ValueError("Expected a checkbox value")
                value = bool(value)
            self.edit(key, value)
        return self.read_row(row_id)

    def _preflight_params(self, source: bytes) -> None:
        game, project = native.checked(self.game_root), native.checked(self.project)
        deployment._assert_disjoint(game, project)
        for path in (game / RELATIVE, deployment._backup_path(game), deployment._marker_path(game)):
            native.checked(path)
        native.read_file(game / RELATIVE, MAX_ARCHIVE)
        marker_bytes = native.read_file(deployment._marker_path(game), 16384, optional=True)
        status = deployment.status(game, project)
        if marker_bytes is None and deployment._backup_path(game).exists():
            raise ValueError("An unmanaged parameter backup already exists")
        if status["everApplied"] and not status["backupOk"]:
            raise ValueError("The original parameter backup is missing or changed")
        if status["changedExternally"]:
            raise ValueError("The installed parameter archive changed outside Lexeditor")
        ItemDocument(source)

    def apply(self, document_store) -> dict:
        self.validate_save()
        if self.dirty_count or document_store.get().dirty_count:
            raise ValueError("Save or discard all changes before applying")
        document_store.validate_save()
        source = native.read_file(self.project / RELATIVE, MAX_ARCHIVE)
        target = project_overlay(source, self.saved)
        self._preflight_params(source)
        owned = (native.checked(self.game_root / native.BACKUP).exists()
                 or native.checked(self.game_root / native.OWNER).exists())
        touch_native = self.saved["enabled"] or self.saved["encumbranceEnabled"] or owned
        before = None
        if touch_native:
            before, old_rules, _ = native.inspect(self.game_root)
            native.ensure_game_closed()
        desired_rules = effective_rules(self.saved)

        def checked_overlay(current):
            self.validate_save()
            if current != source:
                raise ValueError("The saved project changed while Apply was being prepared")
            return target

        if touch_native:
            native.install(self.game_root, desired_rules, expected=before)
        try:
            deployment.apply(self.game_root, self.project, transform=checked_overlay)
        except Exception as error:
            if touch_native and old_rules != desired_rules:
                try:
                    # Roll back only our exact expected post-image, never an external change.
                    original = native.read_file(self.game_root / native.BACKUP, native.ORIGINAL_SIZE)
                    native.install(self.game_root, old_rules,
                                   expected=native.transform(original, desired_rules))
                except Exception as rollback_error:
                    raise RuntimeError(
                        "Apply stopped with incomplete installed changes. Retry Apply or Restore original. "
                        f"Parameter error: {error}; executable recovery error: {rollback_error}"
                    ) from error
            raise RuntimeError(
                "Parameter Apply did not finish. The executable was left at its previous rate; "
                "retry Apply or Restore original to reconcile the parameter archive. " + str(error)
            ) from error
        return self.deployment_status()

    def restore(self) -> dict:
        # Explicit restoration changes no project settings, including in Vanilla.
        owned = (native.checked(self.game_root / native.BACKUP).exists()
                 or native.checked(self.game_root / native.OWNER).exists())
        before = None
        if owned or self.saved["enabled"] or self.saved["encumbranceEnabled"]:
            before, _, _ = native.inspect(self.game_root)
            native.ensure_game_closed()
        deployment.disable(self.game_root)
        if owned:
            native.install(self.game_root, native.DEFAULT_RULES, expected=before)
        return self.deployment_status()

    def deployment_status(self) -> dict:
        result = deployment.status(self.game_root, self.project)
        snapshot = self.snapshot(refresh=True)
        if result["thisProjectActive"]:
            try:
                source = native.read_file(self.project / RELATIVE, MAX_ARCHIVE)
                expected = project_overlay(source, self.saved)
                live = native.read_file(self.game_root / RELATIVE, MAX_ARCHIVE)
                native_required = self.saved["enabled"] or self.saved["encumbranceEnabled"] or native.checked(self.game_root / native.BACKUP).exists()
                expected_rules = effective_rules(self.saved)
                result["stale"] = result["stale"] or live != expected or (
                    native_required and snapshot["native"].get("rules") != expected_rules)
            except (ValueError, RuntimeError, OSError) as error:
                result["stale"] = True
                snapshot["deploymentProblem"] = str(error)
        result["rebalance"] = snapshot
        return result
