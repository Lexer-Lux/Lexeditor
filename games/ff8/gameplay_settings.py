"""Structured FF8 gameplay settings and the verified FFNx Hext patch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time

from . import paths, formats
from . import ffnx_manager
from . import runtime_layout
from . import inventory_auto_sort
from . import menu_qol_issue_61
from . import single_gf
from . import battle_shortcuts
from . import party_switch_issue_62
from . import battle_issue_54
from . import better_card
from . import fixed_command_menu
from . import true_atb_wait_issue_63
from . import flying_eva
from . import character_growth
from . import luck_accuracy
from . import modern_controls_issue_65
from . import vibration_consolidation_issue_66
from . import better_targeting_issue_64
from . import damage_limit
from . import fast_start
from . import streamlined_draw
from . import healing_rework
from . import flat_stat_abilities
from . import max_spell
from .ffnx_issue_51 import runtime_config as shared_magic_runtime_config


DEFAULT_FLYING_EVA_BONUS = 25
DEFAULT_FLYING_EVA_ENABLED = False
DEFAULT_AUTO_SORT_INVENTORY = inventory_auto_sort.DEFAULT_AUTO_SORT_INVENTORY
DEFAULT_AUTO_SORT_MAGIC = menu_qol_issue_61.DEFAULT_AUTO_SORT_MAGIC
DEFAULT_ENHANCED_ABILITY_MENU = menu_qol_issue_61.DEFAULT_ENHANCED_ABILITY_MENU
DEFAULT_SINGLE_GF = single_gf.DEFAULT_SINGLE_GF
DEFAULT_UNIVERSAL_ITEM = battle_shortcuts.DEFAULT_UNIVERSAL_ITEM
DEFAULT_SCANNED_TARGET_SCAN = battle_shortcuts.DEFAULT_SCANNED_TARGET_SCAN
DEFAULT_PARTY_SWITCH = party_switch_issue_62.DEFAULT_PARTY_SWITCH
DEFAULT_DRAW_ONCE_PER_ENEMY = battle_issue_54.DEFAULT_DRAW_ONCE_PER_ENEMY
DEFAULT_BETTER_CARD = better_card.DEFAULT_BETTER_CARD
DEFAULT_FIXED_COMMAND_MENU = False
DEFAULT_TRUE_ATB_WAIT = true_atb_wait_issue_63.DEFAULT_TRUE_ATB_WAIT
DEFAULT_FORMULAE_REWORK = False
DEFAULT_MODERN_CONTROLS = modern_controls_issue_65.DEFAULT_MODERN_CONTROLS
DEFAULT_VIBRATION_CONSOLIDATION = vibration_consolidation_issue_66.DEFAULT_VIBRATION_CONSOLIDATION
DEFAULT_BETTER_TARGETING = better_targeting_issue_64.DEFAULT_BETTER_TARGETING
DEFAULT_DAMAGE_LIMIT_REMOVAL = damage_limit.DEFAULT_DAMAGE_LIMIT_REMOVAL
DEFAULT_FAST_START = fast_start.DEFAULT_FAST_START
DEFAULT_STREAMLINED_DRAW = streamlined_draw.DEFAULT_STREAMLINED_DRAW
DEFAULT_SHARED_MAGIC_INVENTORY = False
DEFAULT_XP_BARS = False
DEFAULT_HP_BARS = False
DEFAULT_FLAT_STAT_ABILITIES = flat_stat_abilities.DEFAULT_FLAT_STAT_ABILITIES
DEFAULT_MAX_SPELL_ENABLED = max_spell.DEFAULT_MAX_SPELL_ENABLED
DEFAULT_MAX_SPELL = max_spell.DEFAULT_MAX_SPELL
# These are the Tweaks shown by the current editor. They remain off by default.
# Formulae Rework is not in this set because its requested behavior is not
# complete; it must not be saved through a stale client.
ACCEPTED_TWEAKS = frozenset({
    "flyingEvaEnabled", "autoSortInventory", "autoSortMagic",
    "enhancedAbilityMenu", "singleGf", "universalItem", "scannedTargetScan",
    "sharedMagicInventory", "partySwitch", "drawOncePerEnemy",
    "streamlinedDraw", "betterCard", "fixedCommandMenu", "trueAtbWait",
    "modernControls", "vibrationConsolidation", "betterTargeting",
    "damageLimitRemoval", "fastStart", "xpBars", "hpBars",
    "flatStatAbilities", "maxSpellEnabled",
})
MIN_FLYING_EVA_BONUS = 0
MAX_FLYING_EVA_BONUS = 100
SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
PATCH_NAME = "Lexeditor.FLYING_EVA.txt"
FFNX_HEXT_SUFFIX = Path("ff8") / "en_nv"
_last_activation_ns = 0

# FF8_EN.exe 2013 Steam EN, SHA-256 above.
ALWAYS_HIT_BRANCH = 0x00492E66
HIT_FORMULA_HOOK = 0x00492EF5
CODE_CAVE = 0x0279EF00
CODE_CAVE_LENGTH = len(flying_eva.build_payload(0))
SINGLE_GF_CAVE = 0x0279EF60

# Flying EVA shares this reserved block with Monogamy; its payload must fit.
assert CODE_CAVE_LENGTH <= SINGLE_GF_CAVE - CODE_CAVE

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bounded_bonus(value) -> int:
    if isinstance(value, bool):
        raise ValueError("Flying EVA Bonus must be a whole number from 0 to 100")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Flying EVA Bonus must be a whole number from 0 to 100") from error
    if str(value).strip() not in {str(result), f"{result}.0"}:
        raise ValueError("Flying EVA Bonus must be a whole number from 0 to 100")
    if not MIN_FLYING_EVA_BONUS <= result <= MAX_FLYING_EVA_BONUS:
        raise ValueError("Flying EVA Bonus must be from 0 to 100")
    return result


def _boolean(value, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def settings_path(project_root: Path | None = None) -> Path:
    return (project_root or paths.PROJECT_ROOT) / "lexeditor-settings.json"


def patch_path(project_root: Path | None = None) -> Path:
    # FFNx treats hext_patching_path as a base directory. It always appends the
    # game and detected executable edition before it scans files. The supported
    # Steam executable is FFNx's English Nvidia build, so it scans ff8/en_nv.
    return (project_root or paths.PROJECT_ROOT) / "hext" / FFNX_HEXT_SUFFIX / PATCH_NAME


def runtime_patch_path(runtime_root: Path | None = None) -> Path:
    """Return the logical pre-composition path for the generated patch."""
    return (runtime_root or paths.RUNTIME_ROOT) / "hext" / FFNX_HEXT_SUFFIX / PATCH_NAME


def materialized_runtime_patch_path(runtime_root: Path | None = None) -> Path:
    """Resolve this editable mod's ordered filename from composition.json."""
    active = Path(runtime_root or paths.RUNTIME_ROOT).resolve()
    logical = runtime_patch_path(active).relative_to(active).as_posix()
    manifest = runtime_layout.read(active)
    selected_ids = {
        str(row.get("id")) for row in manifest.get("mods", [])
        if row.get("selected") is True
    }
    matches = []
    for row in manifest.get("files", []):
        if str(row.get("sourcePath") or row.get("path")).casefold() != logical.casefold():
            continue
        if selected_ids and str(row.get("winner")) not in selected_ids:
            continue
        candidate = (active / str(row.get("path", ""))).resolve()
        if candidate == active or active not in candidate.parents:
            raise RuntimeError("The composed gameplay patch path escapes the FF8 runtime")
        matches.append(candidate)
    if len(matches) > 1:
        raise RuntimeError("The FF8 composition contains more than one editable gameplay patch")
    return matches[0] if matches else runtime_patch_path(active).resolve()


def legacy_patch_path(project_root: Path | None = None) -> Path:
    """Return the old base-directory file that FFNx never scanned."""
    return (project_root or paths.PROJECT_ROOT) / "hext" / PATCH_NAME


def obsolete_english_patch_path(project_root: Path | None = None) -> Path:
    """Return the wrong non-Nvidia path used by the previous contract."""
    return (project_root or paths.PROJECT_ROOT) / "hext" / "ff8" / "en" / PATCH_NAME


def _runtime_root(value: Path | None = None,
                  project_root: Path | None = None) -> Path:
    if value is not None:
        return Path(value).resolve()
    if project_root is not None:
        project = Path(project_root).resolve()
        if project != paths.PROJECT_ROOT.resolve():
            # Explicit temporary/test projects must never compose into the
            # player's real active runtime. The private child is not copied,
            # because composition reads only direct/ and hext/.
            return project / ".lexeditor-runtime"
    return paths.RUNTIME_ROOT.resolve()


def _shared_magic_payload(project: Path, game: Path,
                          runtime_root: Path | None = None) -> dict:
    runtime_direct = _runtime_root(runtime_root, project) / "direct"
    runtime = ffnx_manager.status(
        game, ffnx_manager.STATE_PATH, direct_root=runtime_direct,
    )
    try:
        configured = shared_magic_runtime_config.load(project)["sharedMagicInventory"]
        config_error = ""
    except shared_magic_runtime_config.RuntimeConfigError as error:
        configured = False
        config_error = str(error)
    # A verified package makes the request selectable. Launch then installs
    # and verifies that package before FF8 starts. Requiring an installed
    # runtime here creates a circular gate: the runtime is installed only
    # after the user can select and save the request.
    package_available = bool(runtime.get("sharedMagicInventoryPackageAvailable"))
    installed = bool(runtime.get("sharedMagicInventoryRuntime"))
    return {
        "sharedMagicInventory": bool(configured),
        "sharedMagicInventoryConfigured": bool(configured),
        "sharedMagicInventoryAvailable": package_available,
        "sharedMagicInventoryRuntimeInstalled": installed,
        "sharedMagicInventoryMessage": (
            config_error or runtime.get("sharedMagicInventoryRuntimeMessage", "")
        ),
    }


def _validate_shared_magic_launch(project: Path, game: Path,
                                  runtime_root: Path | None = None) -> bool:
    try:
        enabled = shared_magic_runtime_config.load(project)["sharedMagicInventory"]
    except shared_magic_runtime_config.RuntimeConfigError as error:
        raise RuntimeError(
            "The Shared Party Magic Inventory configuration is invalid. "
            "Save Tweaks with the setting off before launch."
        ) from error
    if enabled and not ffnx_manager.status(
        game, ffnx_manager.STATE_PATH,
        direct_root=_runtime_root(runtime_root, project) / "direct",
    ).get("sharedMagicInventoryRuntime"):
        raise RuntimeError(
            "Shared Party Magic Inventory is selected, but the complete verified "
            "Lexeditor FFNx runtime is not installed. The game was not launched."
        )
    return enabled


def load(project_root: Path | None = None, game_root: Path | None = None,
         runtime_root: Path | None = None) -> dict:
    target = settings_path(project_root)
    project = (project_root or paths.PROJECT_ROOT).resolve()
    game = (game_root or paths.GAME_ROOT).resolve()
    data = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
    try:
        bonus = _bounded_bonus(data.get("flyingEvaBonus", DEFAULT_FLYING_EVA_BONUS))
    except ValueError:
        bonus = DEFAULT_FLYING_EVA_BONUS
    # A stored numeric bonus is configuration, not consent to activate the
    # gameplay patch. Old projects which predate the explicit toggle remain off.
    flying_enabled = data.get("flyingEvaEnabled", DEFAULT_FLYING_EVA_ENABLED)
    if not isinstance(flying_enabled, bool):
        flying_enabled = DEFAULT_FLYING_EVA_ENABLED
    auto_sort = data.get("autoSortInventory", DEFAULT_AUTO_SORT_INVENTORY)
    if not isinstance(auto_sort, bool):
        auto_sort = DEFAULT_AUTO_SORT_INVENTORY
    auto_sort_magic = data.get("autoSortMagic", DEFAULT_AUTO_SORT_MAGIC)
    if not isinstance(auto_sort_magic, bool):
        auto_sort_magic = DEFAULT_AUTO_SORT_MAGIC
    enhanced_ability_menu = data.get(
        "enhancedAbilityMenu", DEFAULT_ENHANCED_ABILITY_MENU,
    )
    if not isinstance(enhanced_ability_menu, bool):
        enhanced_ability_menu = DEFAULT_ENHANCED_ABILITY_MENU
    single_gf = data.get("singleGf", DEFAULT_SINGLE_GF)
    if not isinstance(single_gf, bool):
        single_gf = DEFAULT_SINGLE_GF
    universal_item = data.get("universalItem", DEFAULT_UNIVERSAL_ITEM)
    if not isinstance(universal_item, bool):
        universal_item = DEFAULT_UNIVERSAL_ITEM
    scanned_target_scan = data.get("scannedTargetScan", DEFAULT_SCANNED_TARGET_SCAN)
    if not isinstance(scanned_target_scan, bool):
        scanned_target_scan = DEFAULT_SCANNED_TARGET_SCAN
    if not battle_shortcuts.ENHANCED_SCAN_AVAILABLE:
        scanned_target_scan = False
    party_switch = data.get("partySwitch", DEFAULT_PARTY_SWITCH)
    if not isinstance(party_switch, bool):
        party_switch = DEFAULT_PARTY_SWITCH
    if not party_switch_issue_62.PARTY_SWITCH_AVAILABLE:
        party_switch = False
    draw_once = data.get("drawOncePerEnemy", DEFAULT_DRAW_ONCE_PER_ENEMY)
    if not isinstance(draw_once, bool):
        draw_once = DEFAULT_DRAW_ONCE_PER_ENEMY
    streamlined_draw_enabled = data.get(
        "streamlinedDraw", DEFAULT_STREAMLINED_DRAW,
    )
    if not isinstance(streamlined_draw_enabled, bool):
        streamlined_draw_enabled = DEFAULT_STREAMLINED_DRAW
    formulae_rework = data.get("formulaeRework")
    if not isinstance(formulae_rework, bool):
        # Merge the two short-lived legacy switches into their one owning
        # formula feature. This preserves an enabled old mod on first load.
        formulae_rework = bool(
            data.get("spellHealingRework", False)
            or data.get("fullLuckAccuracy", False)
        )
    better_card_enabled = data.get("betterCard", DEFAULT_BETTER_CARD)
    if not isinstance(better_card_enabled, bool):
        better_card_enabled = DEFAULT_BETTER_CARD
    fixed_command_menu_enabled = data.get(
        "fixedCommandMenu", data.get("irvineShoot", DEFAULT_FIXED_COMMAND_MENU),
    )
    if not isinstance(fixed_command_menu_enabled, bool):
        fixed_command_menu_enabled = DEFAULT_FIXED_COMMAND_MENU
    if not single_gf:
        fixed_command_menu_enabled = False
    true_atb_wait = data.get("trueAtbWait", DEFAULT_TRUE_ATB_WAIT)
    if not isinstance(true_atb_wait, bool):
        true_atb_wait = DEFAULT_TRUE_ATB_WAIT
    modern_controls = data.get("modernControls", DEFAULT_MODERN_CONTROLS)
    if not isinstance(modern_controls, bool):
        modern_controls = DEFAULT_MODERN_CONTROLS
    if not modern_controls_issue_65.MODERN_CONTROLS_AVAILABLE:
        modern_controls = False
    vibration_consolidation = data.get(
        "vibrationConsolidation", DEFAULT_VIBRATION_CONSOLIDATION,
    )
    if not isinstance(vibration_consolidation, bool):
        vibration_consolidation = DEFAULT_VIBRATION_CONSOLIDATION
    better_targeting = data.get("betterTargeting", DEFAULT_BETTER_TARGETING)
    if not isinstance(better_targeting, bool):
        better_targeting = DEFAULT_BETTER_TARGETING
    damage_limit_removal = data.get(
        "damageLimitRemoval", DEFAULT_DAMAGE_LIMIT_REMOVAL,
    )
    if not isinstance(damage_limit_removal, bool):
        damage_limit_removal = DEFAULT_DAMAGE_LIMIT_REMOVAL
    fast_start_enabled = data.get("fastStart", DEFAULT_FAST_START)
    if not isinstance(fast_start_enabled, bool):
        fast_start_enabled = DEFAULT_FAST_START
    xp_bars = data.get("xpBars", DEFAULT_XP_BARS)
    if not isinstance(xp_bars, bool):
        xp_bars = DEFAULT_XP_BARS
    hp_bars = data.get("hpBars", DEFAULT_HP_BARS)
    if not isinstance(hp_bars, bool):
        hp_bars = DEFAULT_HP_BARS
    flat_stat_abilities_enabled = data.get(
        "flatStatAbilities", DEFAULT_FLAT_STAT_ABILITIES,
    )
    if not isinstance(flat_stat_abilities_enabled, bool):
        flat_stat_abilities_enabled = DEFAULT_FLAT_STAT_ABILITIES
    max_spell_enabled = data.get("maxSpellEnabled", DEFAULT_MAX_SPELL_ENABLED)
    if not isinstance(max_spell_enabled, bool):
        max_spell_enabled = DEFAULT_MAX_SPELL_ENABLED
    try:
        max_spell_value = max_spell.bounded_limit(
            data.get("maxSpell", DEFAULT_MAX_SPELL),
        )
    except ValueError:
        max_spell_value = DEFAULT_MAX_SPELL
    # The complete Formulae Rework is not implemented. Old files can contain
    # its short-lived key, but loading it must not arm a hidden partial patch.
    # Every visible Tweak keeps its stored value.
    formulae_rework = False
    shared_magic = _shared_magic_payload(project, game, runtime_root)
    return {
        "flyingEvaBonus": bonus,
        "flyingEvaEnabled": flying_enabled,
        "autoSortInventory": auto_sort,
        "autoSortMagic": auto_sort_magic,
        "enhancedAbilityMenu": enhanced_ability_menu,
        "singleGf": single_gf,
        "universalItem": universal_item,
        "scannedTargetScan": scanned_target_scan,
        "enhancedScanAvailable": battle_shortcuts.ENHANCED_SCAN_AVAILABLE,
        "partySwitch": party_switch,
        "partySwitchAvailable": party_switch_issue_62.PARTY_SWITCH_AVAILABLE,
        "drawOncePerEnemy": draw_once,
        "streamlinedDraw": streamlined_draw_enabled,
        "formulaeRework": formulae_rework,
        "formulaeReworkAvailable": False,
        "betterCard": better_card_enabled,
        "fixedCommandMenu": fixed_command_menu_enabled,
        "trueAtbWait": true_atb_wait,
        "modernControls": modern_controls,
        "modernControlsAvailable": modern_controls_issue_65.MODERN_CONTROLS_AVAILABLE,
        "modernControlsBlocker": modern_controls_issue_65.MODERN_CONTROLS_BLOCKER,
        "vibrationConsolidation": vibration_consolidation,
        "betterTargeting": better_targeting,
        "damageLimitRemoval": damage_limit_removal,
        "fastStart": fast_start_enabled,
        "xpBars": xp_bars,
        "hpBars": hp_bars,
        "flatStatAbilities": flat_stat_abilities_enabled,
        "maxSpellEnabled": max_spell_enabled,
        "maxSpell": max_spell_value,
        "maxSpellMinimum": max_spell.MIN_MAX_SPELL,
        "maxSpellMaximum": max_spell.MAX_MAX_SPELL,
        **shared_magic,
    }


def flying_bonus_applies(*, target_flying: bool, attacker_melee: bool,
                         attacker_float: bool) -> bool:
    """Mirror the three runtime branches for tests and UI explanations."""
    return bool(target_flying and attacker_melee and not attacker_float)


def effective_hit_value(hit_rate: int, bonus: int, *, target_flying: bool,
                        attacker_melee: bool, attacker_float: bool) -> int:
    """Show the new accuracy input; 255 has no special exemption."""
    penalty = bonus if flying_bonus_applies(
        target_flying=target_flying,
        attacker_melee=attacker_melee,
        attacker_float=attacker_float,
    ) else 0
    return min(100, int(hit_rate)) - int(penalty) if penalty else int(hit_rate)


def _verify_executable(game_root: Path) -> Path:
    executable = game_root / "FF8_EN.exe"
    if not executable.is_file():
        raise RuntimeError(f"FF8_EN.exe is missing from {game_root}")
    actual = _sha256(executable)
    if actual != SUPPORTED_EXE_SHA256:
        raise RuntimeError(
            "The installed FF8_EN.exe build is not yet supported by the Flying EVA patch "
            f"(SHA-256 {actual}). No executable patch was generated."
        )
    with executable.open("rb") as stream:
        stream.seek(ALWAYS_HIT_BRANCH - 0x400000)
        branch = stream.read(1)
        stream.seek(HIT_FORMULA_HOOK - 0x400000)
        displaced = stream.read(6)
        stream.seek(inventory_auto_sort.ITEM_OPEN_SORT_HOOK - 0x400000)
        item_open = stream.read(5)
        stream.seek(menu_qol_issue_61.MAGIC_OPEN_HOOK - 0x400000)
        magic_open = stream.read(len(menu_qol_issue_61.MAGIC_OPEN_HOOK_ORIGINAL))
        stream.seek(single_gf.ADD_GATE_HOOK - 0x400000)
        single_gf_gate = stream.read(single_gf.ADD_GATE_HOOK_LENGTH)
        verified_hooks = []
        for address, original in (
            (inventory_auto_sort.BATTLE_CACHE_HOOK, inventory_auto_sort.BATTLE_CACHE_ORIGINAL),
            (character_growth.HOOK, character_growth.ORIGINAL),
            (battle_issue_54.BATTLE_ENTER_HOOK, battle_issue_54.BATTLE_ENTER_ORIGINAL),
            (battle_issue_54.BATTLE_EXIT_HOOK, battle_issue_54.BATTLE_EXIT_ORIGINAL),
            (battle_issue_54.DRAW_RESULT_HOOK, battle_issue_54.DRAW_RESULT_ORIGINAL),
            (battle_issue_54.DRAW_SELECT_HOOK, battle_issue_54.DRAW_SELECT_ORIGINAL),
            (battle_issue_54.DRAW_TARGET_MASK_HOOK, battle_issue_54.DRAW_TARGET_MASK_ORIGINAL),
            (battle_issue_54.DRAW_RENDER_HOOK, battle_issue_54.DRAW_RENDER_ORIGINAL),
            (true_atb_wait_issue_63.ATB_WAIT_HOOK, true_atb_wait_issue_63.ATB_WAIT_HOOK_ORIGINAL),
            (luck_accuracy.LUCK_HALVE, luck_accuracy.LUCK_HALVE_ORIGINAL),
            (modern_controls_issue_65.CAMERA_YAW_HOOK, modern_controls_issue_65.CAMERA_YAW_HOOK_ORIGINAL),
            (modern_controls_issue_65.REJECTED_NORMAL_INPUT_FIELD, modern_controls_issue_65.REJECTED_NORMAL_INPUT_ORIGINAL),
            (modern_controls_issue_65.REJECTED_SPECIAL_MODE_READ, modern_controls_issue_65.REJECTED_SPECIAL_MODE_ORIGINAL),
            (vibration_consolidation_issue_66.FIELD_HOOK, vibration_consolidation_issue_66.FIELD_HOOK_ORIGINAL),
            (vibration_consolidation_issue_66.BATTLE_HOOK, vibration_consolidation_issue_66.BATTLE_HOOK_ORIGINAL),
            (better_targeting_issue_64.TARGET_ICON_HOOK, better_targeting_issue_64.TARGET_ICON_HOOK_ORIGINAL),
            (damage_limit.DAMAGE_LIMIT_FLAG_OPCODE, damage_limit.DAMAGE_LIMIT_FLAG_ORIGINAL),
            (healing_rework.HEALING_FORMULA_HOOK, healing_rework.HEALING_FORMULA_ORIGINAL),
            (menu_qol_issue_61.ABILITY_LIST_RETURN_HOOK, menu_qol_issue_61.ABILITY_LIST_RETURN_ORIGINAL),
            (menu_qol_issue_61.ABILITY_STATE_READ, menu_qol_issue_61.ABILITY_STATE_READ_ORIGINAL),
            (menu_qol_issue_61.ABILITY_ROW_BOUNDS_BRANCH, menu_qol_issue_61.ABILITY_ROW_BOUNDS_ORIGINAL),
            (menu_qol_issue_61.ABILITY_PALETTE_HOOK, menu_qol_issue_61.ABILITY_PALETTE_HOOK_ORIGINAL),
            (menu_qol_issue_61.ABILITY_TEXT_RENDER_CALL, menu_qol_issue_61.ABILITY_TEXT_RENDER_CALL_ORIGINAL),
        ):
            stream.seek(address - 0x400000)
            verified_hooks.append((stream.read(len(original)), original))
        flat_stat_abilities.verify_executable(stream)
        max_spell.verify_executable(stream)
    if branch != b"\x75" or displaced != bytes.fromhex("8A 8D D2 7B D2 01"):
        raise RuntimeError("The installed FF8 hit-check bytes do not match the verified build")
    if item_open != inventory_auto_sort.ITEM_OPEN_SORT_ORIGINAL:
        raise RuntimeError("The installed FF8 Item-menu bytes do not match the verified build")
    if magic_open != menu_qol_issue_61.MAGIC_OPEN_HOOK_ORIGINAL:
        raise RuntimeError("The installed FF8 Magic-menu bytes do not match the verified build")
    if single_gf_gate != single_gf.ADD_GATE_ORIGINAL:
        raise RuntimeError("The installed FF8 GF-junction add gate does not match the verified build")
    if any(actual != expected for actual, expected in verified_hooks):
        raise RuntimeError("The installed FF8 gameplay hook bytes do not match the verified build")
    return executable


def build_hext(bonus: int, auto_sort: bool = DEFAULT_AUTO_SORT_INVENTORY,
               single_gf_enabled: bool = DEFAULT_SINGLE_GF,
               universal_item: bool = DEFAULT_UNIVERSAL_ITEM,
               draw_once_per_enemy: bool = DEFAULT_DRAW_ONCE_PER_ENEMY,
               better_card_enabled: bool = DEFAULT_BETTER_CARD,
               scanned_target_scan: bool = DEFAULT_SCANNED_TARGET_SCAN,
               party_switch: bool = DEFAULT_PARTY_SWITCH,
               fixed_command_menu_enabled: bool = DEFAULT_FIXED_COMMAND_MENU,
               auto_sort_magic: bool = DEFAULT_AUTO_SORT_MAGIC,
               true_atb_wait: bool = DEFAULT_TRUE_ATB_WAIT,
               formulae_rework: bool = DEFAULT_FORMULAE_REWORK,
               modern_controls: bool = DEFAULT_MODERN_CONTROLS,
               vibration_consolidation: bool = DEFAULT_VIBRATION_CONSOLIDATION,
               better_targeting: bool = DEFAULT_BETTER_TARGETING,
               damage_limit_removal: bool = DEFAULT_DAMAGE_LIMIT_REMOVAL,
               fast_start_enabled: bool = DEFAULT_FAST_START,
               enhanced_ability_menu: bool = DEFAULT_ENHANCED_ABILITY_MENU,
               streamlined_draw_enabled: bool = DEFAULT_STREAMLINED_DRAW,
               flat_stat_abilities_enabled: bool = DEFAULT_FLAT_STAT_ABILITIES,
               max_spell_enabled: bool = DEFAULT_MAX_SPELL_ENABLED,
               max_spell_value: int = DEFAULT_MAX_SPELL,
               flying_eva_enabled: bool = True) -> str:
    bonus = _bounded_bonus(bonus)
    flying_eva_enabled = _boolean(flying_eva_enabled, "Flying EVA Bonus")
    auto_sort = _boolean(auto_sort, "Auto-sort Inventory")
    auto_sort_magic = _boolean(auto_sort_magic, "Auto-sort Magic Menu")
    enhanced_ability_menu = _boolean(
        enhanced_ability_menu, "Enhanced Ability Menu",
    )
    single_gf_enabled = _boolean(single_gf_enabled, "Monogamy")
    universal_item = _boolean(universal_item, "Universal Item")
    scanned_target_scan = _boolean(scanned_target_scan, "Enhanced Scan")
    party_switch = _boolean(party_switch, "FF10-style Party Switch")
    draw_once_per_enemy = _boolean(draw_once_per_enemy, "Draw Once per Enemy")
    better_card_enabled = _boolean(better_card_enabled, "Better Card")
    fixed_command_menu_enabled = _boolean(
        fixed_command_menu_enabled, "Command Menu Rework",
    )
    true_atb_wait = _boolean(true_atb_wait, "True ATB Wait")
    formulae_rework = _boolean(formulae_rework, "Formulae Rework")
    modern_controls = _boolean(modern_controls, "Modern Controls")
    vibration_consolidation = _boolean(
        vibration_consolidation, "Vibration Rationalization",
    )
    better_targeting = _boolean(better_targeting, "Better Targeting")
    damage_limit_removal = _boolean(
        damage_limit_removal, "Damage Limit Removal",
    )
    fast_start_enabled = _boolean(fast_start_enabled, "Fast Start")
    streamlined_draw_enabled = _boolean(
        streamlined_draw_enabled, "Streamlined Draw",
    )
    flat_stat_abilities_enabled = _boolean(
        flat_stat_abilities_enabled, "Flat +Stat Abilities",
    )
    max_spell_enabled = _boolean(max_spell_enabled, "Max Spell")
    max_spell_value = max_spell.bounded_limit(max_spell_value)
    header = [
        "# Generated by Lexeditor for FF8 2013 Steam EN.",
        "# Intrinsic flying targets gain the configured effective EVA.",
        "# Ranged attacks and Float-enabled melee attackers ignore the bonus.",
        "# A vanilla hit rate of 255 does not bypass this added EVA.",
    ]
    lines = list(header)
    lines.extend(character_growth.build_hext().rstrip().splitlines())
    if flying_eva_enabled and bonus:
        payload = flying_eva.build_payload(bonus)
        lines.extend([
            f"# Flying EVA Bonus: {bonus} percentage points",
            f"{CODE_CAVE:X}:{len(payload):X}",
            f"{ALWAYS_HIT_BRANCH:X} = EB",
            f"{HIT_FORMULA_HOOK:X} = E9 06 C0 30 02 90",
            f"{CODE_CAVE:X} = {payload.hex(' ').upper()}",
        ])
    else:
        lines.append("# Flying EVA Bonus is disabled.")
    inventory_patch = inventory_auto_sort.build_hext(auto_sort)
    if inventory_patch:
        lines.extend(inventory_patch.rstrip().splitlines())
    else:
        lines.append("# Automatic inventory sorting is disabled.")
    magic_sort_patch = menu_qol_issue_61.build_auto_sort_magic_hext(auto_sort_magic)
    if magic_sort_patch:
        lines.extend(magic_sort_patch.rstrip().splitlines())
    else:
        lines.append("# Automatic Magic-menu sorting is disabled.")
    ability_patch = menu_qol_issue_61.build_enhanced_ability_menu_hext(
        enhanced_ability_menu,
    )
    if ability_patch:
        lines.extend(ability_patch.rstrip().splitlines())
    else:
        lines.append("# Enhanced Ability Menu is disabled; GF ability order and palettes are unchanged.")
    single_gf_patch = single_gf.build_hext(single_gf_enabled, SINGLE_GF_CAVE)
    if single_gf_patch:
        lines.extend(single_gf_patch.rstrip().splitlines())
    else:
        lines.append("# Monogamy is disabled; vanilla junction additions are unchanged.")
    item_patch = battle_shortcuts.build_hext(
        universal_item=universal_item,
        scanned_target_scan=scanned_target_scan,
        party_switch=party_switch,
    )
    if item_patch:
        lines.extend(item_patch.rstrip().splitlines())
    else:
        lines.append("# Universal Item is disabled; Look Right keeps vanilla behavior.")
    if not scanned_target_scan:
        lines.append("# Enhanced Scan is disabled; camera and battle input remain vanilla.")
    if not party_switch:
        lines.append("# FF10-style Party Switch is disabled; Look Left keeps vanilla behavior.")
    draw_patch = battle_issue_54.build_command_eligibility_patch(
        draw_once=draw_once_per_enemy, better_card=better_card_enabled,
        streamlined_draw=streamlined_draw_enabled,
    )
    if draw_patch:
        lines.extend(draw_patch.rstrip().splitlines())
    else:
        lines.append("# Draw Once per Enemy and Better Card are disabled; command eligibility is vanilla.")
    active_stock_limit = max_spell_value if max_spell_enabled else max_spell.DEFAULT_MAX_SPELL
    streamlined_draw_patch = streamlined_draw.build_hext(
        streamlined_draw_enabled, active_stock_limit,
    )
    if streamlined_draw_patch:
        lines.extend(streamlined_draw_patch.rstrip().splitlines())
    else:
        lines.append("# Streamlined Draw is disabled; spell and Stock/Cast selection remain vanilla.")
    healing_patch = healing_rework.build_hext(formulae_rework)
    if healing_patch:
        lines.extend(healing_patch.rstrip().splitlines())
    else:
        lines.append("# Formulae Rework is disabled; curative-magic arithmetic remains vanilla.")
    fixed_commands = fixed_command_menu.build_patch(
        enabled=fixed_command_menu_enabled,
        single_gf_enabled=single_gf_enabled,
    )
    if fixed_commands:
        lines.extend(fixed_commands.rstrip().splitlines())
    else:
        lines.append("# Fixed Command Menu is disabled; command slots remain vanilla.")
    atb_patch = true_atb_wait_issue_63.build_hext(true_atb_wait)
    if atb_patch:
        lines.extend(atb_patch.rstrip().splitlines())
    else:
        lines.append("# True ATB Wait is disabled; the native ATB gate is unchanged.")
    luck_patch = luck_accuracy.build_hext(formulae_rework)
    if luck_patch:
        lines.extend(luck_patch.rstrip().splitlines())
    else:
        lines.append("# Formulae Rework is disabled; the attacker still contributes LUCK / 2.")
    controls_patch = modern_controls_issue_65.build_hext(modern_controls)
    if controls_patch:
        lines.extend(controls_patch.rstrip().splitlines())
    else:
        lines.append("# Modern Controls is disabled; world-map camera input is unchanged.")
    vibration_patch = vibration_consolidation_issue_66.build_hext(
        vibration_consolidation,
    )
    if vibration_patch:
        lines.extend(vibration_patch.rstrip().splitlines())
    else:
        lines.append("# Vibration Rationalization is disabled; FFNx pause screens are unchanged.")
    targeting_patch = better_targeting_issue_64.build_hext(better_targeting)
    if targeting_patch:
        lines.extend(targeting_patch.rstrip().splitlines())
    else:
        lines.append("# Better Targeting is disabled; native target indicators are unchanged.")
    limit_patch = damage_limit.build_hext(damage_limit_removal)
    if limit_patch:
        lines.extend(limit_patch.rstrip().splitlines())
    else:
        lines.append("# Damage Limit Removal is disabled; the native 9,999 cap is unchanged.")
    fast_start_patch = fast_start.build_hext(fast_start_enabled)
    if fast_start_patch:
        lines.extend(fast_start_patch.rstrip().splitlines())
    else:
        lines.append("# Fast Start is disabled; the native opening credits remain unchanged.")
    flat_stat_patch = flat_stat_abilities.build_hext(flat_stat_abilities_enabled)
    if flat_stat_patch:
        lines.extend(flat_stat_patch.rstrip().splitlines())
    else:
        lines.append("# Flat +Stat Abilities is disabled; percentage stat abilities remain vanilla.")
    max_spell_patch = max_spell.build_hext(max_spell_enabled, max_spell_value)
    if max_spell_patch:
        lines.extend(max_spell_patch.rstrip().splitlines())
    else:
        lines.append("# Max Spell is disabled; the native stock cap and junction scaling remain 100.")
    return "\n".join(lines + [""])


def _atomic_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(target)


def _atomic_bytes(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)


def _set_ffnx_runtime_tweaks(config: Path, *, xp_bars: bool, hp_bars: bool,
                             better_targeting: bool, fast_start: bool = False,
                             modern_controls: bool = False, party_switch: bool = False) -> None:
    """Set derivative options without changing unrelated FFNx settings."""
    text = config.read_text(encoding="utf-8", errors="strict")
    for key, enabled in (
        ("enable_ff8_xp_bars", xp_bars),
        ("enable_ff8_hp_bars", hp_bars),
        ("enable_ff8_better_targeting", better_targeting),
        ("enable_ff8_fast_start", fast_start),
        ("enable_ff8_modern_controls", modern_controls),
        ("enable_ff8_party_switch", party_switch),
    ):
        pattern = re.compile(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*(?:true|false)\s*$"
        )
        replacement = f"{key} = {'true' if enabled else 'false'}"
        if pattern.search(text):
            text = pattern.sub(replacement, text, count=1)
        else:
            text = text.rstrip() + f"\n\n{replacement}\n"
    _atomic_text(config, text)


def _snapshot_files(targets: list[Path]) -> list[tuple[Path, bool, bytes]]:
    snapshots = []
    for target in targets:
        path = Path(target)
        existed = path.is_file()
        snapshots.append((path, existed, path.read_bytes() if existed else b""))
    return snapshots


def _restore_files(snapshots: list[tuple[Path, bool, bytes]]) -> None:
    for path, existed, content in reversed(snapshots):
        if not existed:
            path.unlink(missing_ok=True)
            continue
        # A loaded FFNx driver is locked by Windows. Do not stage or replace it
        # when the failed transaction did not change its bytes.
        if path.is_file():
            try:
                if path.read_bytes() == content:
                    path.with_suffix(
                        path.suffix + ".lexeditor.rollback.tmp"
                    ).unlink(missing_ok=True)
                    continue
            except OSError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".lexeditor.rollback.tmp")
        temporary.write_bytes(content)
        temporary.replace(path)


def initialize_project(project_root: Path) -> None:
    """Reset copied gameplay Tweaks for one newly created mod."""
    project = project_root.resolve()
    settings_data = {
        "autoSortInventory": False,
        "autoSortMagic": False,
        "enhancedAbilityMenu": False,
        "flyingEvaBonus": DEFAULT_FLYING_EVA_BONUS,
        "flyingEvaEnabled": False,
        "singleGf": False,
        "universalItem": False,
        "scannedTargetScan": False,
        "partySwitch": False,
        "drawOncePerEnemy": False,
        "streamlinedDraw": False,
        "formulaeRework": False,
        "betterCard": False,
        "fixedCommandMenu": False,
        "trueAtbWait": False,
        "modernControls": False,
        "vibrationConsolidation": False,
        "betterTargeting": False,
        "damageLimitRemoval": False,
        "fastStart": False,
        "xpBars": False,
        "hpBars": False,
        "flatStatAbilities": False,
        "maxSpellEnabled": False,
        "maxSpell": DEFAULT_MAX_SPELL,
    }
    _atomic_text(settings_path(project), json.dumps(
        settings_data, indent=2, sort_keys=True,
    ) + "\n")
    shared_magic_runtime_config.write(
        project, shared_magic_inventory=DEFAULT_SHARED_MAGIC_INVENTORY,
        magic_stock_limit=DEFAULT_MAX_SPELL,
    )
    _atomic_text(patch_path(project), build_hext(
        DEFAULT_FLYING_EVA_BONUS,
        flying_eva_enabled=False,
    ))
    for old_patch in (legacy_patch_path(project), obsolete_english_patch_path(project)):
        if old_patch.is_file():
            old_patch.unlink()


def save(data: dict, game_root: Path | None = None,
         project_root: Path | None = None, *, install_runtime: bool = False,
         runtime_root: Path | None = None) -> dict:
    game = (game_root or paths.GAME_ROOT).resolve()
    project = (project_root or paths.PROJECT_ROOT).resolve()
    bonus = _bounded_bonus(data.get("flyingEvaBonus"))
    flying_enabled = _boolean(
        data.get("flyingEvaEnabled", DEFAULT_FLYING_EVA_ENABLED),
        "Flying EVA Bonus",
    )
    auto_sort = _boolean(
        data.get("autoSortInventory", DEFAULT_AUTO_SORT_INVENTORY),
        "Auto-sort Inventory",
    )
    auto_sort_magic = _boolean(
        data.get("autoSortMagic", DEFAULT_AUTO_SORT_MAGIC),
        "Auto-sort Magic Menu",
    )
    enhanced_ability_menu = _boolean(
        data.get("enhancedAbilityMenu", DEFAULT_ENHANCED_ABILITY_MENU),
        "Enhanced Ability Menu",
    )

    single_gf = _boolean(data.get("singleGf", DEFAULT_SINGLE_GF), "Monogamy")
    universal_item = _boolean(
        data.get("universalItem", DEFAULT_UNIVERSAL_ITEM), "Universal Item",
    )
    scanned_target_scan = _boolean(
        data.get("scannedTargetScan", DEFAULT_SCANNED_TARGET_SCAN),
        "Enhanced Scan",
    )
    party_switch = _boolean(
        data.get("partySwitch", DEFAULT_PARTY_SWITCH),
        "FF10-style Party Switch",
    )
    draw_once = _boolean(
        data.get("drawOncePerEnemy", DEFAULT_DRAW_ONCE_PER_ENEMY),
        "Draw Once per Enemy",
    )
    streamlined_draw_enabled = _boolean(
        data.get("streamlinedDraw", DEFAULT_STREAMLINED_DRAW),
        "Streamlined Draw",
    )
    formulae_rework = _boolean(
        data.get("formulaeRework", DEFAULT_FORMULAE_REWORK),
        "Formulae Rework",
    )
    better_card_enabled = _boolean(
        data.get("betterCard", DEFAULT_BETTER_CARD), "Better Card",
    )
    fixed_command_menu_enabled = _boolean(
        data.get("fixedCommandMenu", DEFAULT_FIXED_COMMAND_MENU),
        "Command Menu Rework",
    )
    true_atb_wait = _boolean(
        data.get("trueAtbWait", DEFAULT_TRUE_ATB_WAIT), "True ATB Wait",
    )
    modern_controls = _boolean(
        data.get("modernControls", DEFAULT_MODERN_CONTROLS), "Modern Controls",
    )
    vibration_consolidation = _boolean(
        data.get("vibrationConsolidation", DEFAULT_VIBRATION_CONSOLIDATION),
        "Vibration Rationalization",
    )
    better_targeting = _boolean(
        data.get("betterTargeting", DEFAULT_BETTER_TARGETING), "Better Targeting",
    )
    damage_limit_removal = _boolean(
        data.get("damageLimitRemoval", DEFAULT_DAMAGE_LIMIT_REMOVAL),
        "Damage Limit Removal",
    )
    fast_start_enabled = _boolean(
        data.get("fastStart", DEFAULT_FAST_START), "Fast Start",
    )
    xp_bars = _boolean(data.get("xpBars", DEFAULT_XP_BARS), "XP Bars")
    hp_bars = _boolean(data.get("hpBars", DEFAULT_HP_BARS), "HP Bars")
    flat_stat_abilities_enabled = _boolean(
        data.get("flatStatAbilities", DEFAULT_FLAT_STAT_ABILITIES),
        "Flat +Stat Abilities",
    )
    max_spell_enabled = _boolean(
        data.get("maxSpellEnabled", DEFAULT_MAX_SPELL_ENABLED), "Max Spell",
    )
    max_spell_value = max_spell.bounded_limit(
        data.get("maxSpell", DEFAULT_MAX_SPELL),
    )
    shared_magic_inventory = _boolean(
        data.get("sharedMagicInventory", DEFAULT_SHARED_MAGIC_INVENTORY),
        "Shared Party Magic Inventory",
    )
    # Do not let an old page or direct API call arm incomplete hidden features.
    # Visible Tweaks must keep the value the user selected.
    if formulae_rework:
        raise ValueError("Formulae Rework is not available")
    if party_switch and not party_switch_issue_62.PARTY_SWITCH_AVAILABLE:
        raise ValueError(party_switch_issue_62.PARTY_SWITCH_BLOCKER)
    if modern_controls and not modern_controls_issue_65.MODERN_CONTROLS_AVAILABLE:
        raise ValueError(modern_controls_issue_65.MODERN_CONTROLS_BLOCKER)
    if party_switch and shared_magic_inventory:
        raise ValueError("Party Switch cannot yet be used with Shared Magic. Turn off Shared Magic to use Party Switch.")
    active_root = _runtime_root(runtime_root, project)
    direct_root = active_root / "direct"
    shared_magic_status = ffnx_manager.status(
        game, ffnx_manager.STATE_PATH, direct_root=direct_root,
    )
    # Keep the selected mod's requested value even when the runtime is not yet
    # installed. Activation installs and verifies the runtime before launch.
    # Save must never turn an enabled feature off behind the user's back.
    if fixed_command_menu_enabled and not single_gf:
        raise ValueError("Fixed Command Menu requires Monogamy")
    if shared_magic_inventory and max_spell_enabled and max_spell_value != 100:
        raise ValueError(
            "Shared Party Magic Inventory currently requires Max Spell 100. "
            "Its managed FFNx runtime must be rebuilt to read the configured cap."
        )
    _verify_executable(game)
    hext = build_hext(
        bonus, auto_sort, single_gf, universal_item, draw_once,
        better_card_enabled,
        scanned_target_scan=scanned_target_scan,
        party_switch=party_switch,
        fixed_command_menu_enabled=fixed_command_menu_enabled,
        auto_sort_magic=auto_sort_magic,
        enhanced_ability_menu=enhanced_ability_menu,
        true_atb_wait=true_atb_wait,
        formulae_rework=formulae_rework,
        modern_controls=modern_controls,
        vibration_consolidation=vibration_consolidation,
        better_targeting=better_targeting,
        damage_limit_removal=damage_limit_removal,
        fast_start_enabled=fast_start_enabled,
        streamlined_draw_enabled=streamlined_draw_enabled,
        flat_stat_abilities_enabled=flat_stat_abilities_enabled,
        max_spell_enabled=max_spell_enabled,
        max_spell_value=max_spell_value,
        flying_eva_enabled=flying_enabled,
    )
    settings_data = {
        "autoSortInventory": auto_sort,
        "autoSortMagic": auto_sort_magic,
        "enhancedAbilityMenu": enhanced_ability_menu,
        "flyingEvaBonus": bonus,
        "flyingEvaEnabled": flying_enabled,
        "singleGf": single_gf,
        "universalItem": universal_item,
        "scannedTargetScan": scanned_target_scan,
        "partySwitch": party_switch,
        "drawOncePerEnemy": draw_once,
        "streamlinedDraw": streamlined_draw_enabled,
        "formulaeRework": formulae_rework,
        "betterCard": better_card_enabled,
        "fixedCommandMenu": fixed_command_menu_enabled,
        "trueAtbWait": true_atb_wait,
        "modernControls": modern_controls,
        "vibrationConsolidation": vibration_consolidation,
        "betterTargeting": better_targeting,
        "damageLimitRemoval": damage_limit_removal,
        "fastStart": fast_start_enabled,
        "xpBars": xp_bars,
        "hpBars": hp_bars,
        "flatStatAbilities": flat_stat_abilities_enabled,
        "maxSpellEnabled": max_spell_enabled,
        "maxSpell": max_spell_value,
    }
    settings_text = json.dumps(settings_data, indent=2, sort_keys=True) + "\n"
    runtime_text = shared_magic_runtime_config.build(
        shared_magic_inventory=shared_magic_inventory,
        magic_stock_limit=(max_spell_value if max_spell_enabled else 100),
    )
    install_needed = bool(
        install_runtime
        and
        (shared_magic_inventory or xp_bars or hp_bars or better_targeting or fast_start_enabled
         or modern_controls or party_switch)
        and not shared_magic_status.get("sharedMagicInventoryRuntime")
    )
    changed_files = [
        patch_path(project),
        legacy_patch_path(project),
        obsolete_english_patch_path(project),
        settings_path(project),
        shared_magic_runtime_config.path(project),
    ]
    flat_kernel_target = project / "direct" / "kernel.bin"
    flat_kernel_bytes = None
    if flat_stat_abilities_enabled or flat_kernel_target.is_file():
        flat_kernel_target, flat_kernel_bytes, _flat_text_changes = (
            flat_stat_abilities.transformed_kernel(
                project, paths.BASELINE_ROOT, flat_stat_abilities_enabled,
            )
        )
        changed_files.append(flat_kernel_target)
    if install_runtime:
        changed_files.append(game / "FFNx.toml")
    if install_needed:
        changed_files[:0] = [
            game / ffnx_manager.runtime_package.DRIVER_NAME,
            ffnx_manager.STATE_PATH,
        ]
    snapshots = _snapshot_files(changed_files)
    runtime_link_snapshots = (
        ffnx_manager._snapshot_runtime_links(game)
        if install_runtime else None
    )
    try:
        _atomic_text(patch_path(project), hext)
        for old_patch in (legacy_patch_path(project), obsolete_english_patch_path(project)):
            if old_patch.is_file():
                old_patch.unlink()
        _atomic_text(settings_path(project), settings_text)
        _atomic_text(shared_magic_runtime_config.path(project), runtime_text)
        if flat_kernel_bytes is not None:
            _atomic_bytes(flat_kernel_target, flat_kernel_bytes)
        runtime_layout.compose(
            project, active_root, runtime_layout.catalog(project, paths.MODS_ROOT),
            paths.BASELINE_ROOT, formats.SECTIONS,
            runtime_layout.prelaunch_condition_state(game / "FFNx.toml"),
        )
        if install_needed:
            ffnx_manager.install_derivative(
                game, state_path=ffnx_manager.STATE_PATH, direct_root=direct_root,
                game_running=ffnx_manager._game_running,
            )
            if not ffnx_manager.status(
                game, ffnx_manager.STATE_PATH, direct_root=direct_root,
            ).get("sharedMagicInventoryRuntime"):
                raise RuntimeError(
                    "The Lexeditor FFNx derivative did not verify after installation. "
                    "No enabled runtime configuration was written."
                )
        elif install_runtime:
            config = game / "FFNx.toml"
            if not config.is_file():
                raise RuntimeError("FFNx.toml is missing. FFNx cannot use the active runtime.")
            ffnx_manager._set_project_paths(config, direct_root)
            ffnx_manager._verify_project_path(config, direct_root)
        if install_runtime:
            _set_ffnx_runtime_tweaks(
                game / "FFNx.toml", xp_bars=xp_bars, hp_bars=hp_bars,
                better_targeting=better_targeting,
                fast_start=fast_start_enabled,
                modern_controls=modern_controls, party_switch=party_switch,
            )
    except Exception:
        _restore_files(snapshots)
        if runtime_link_snapshots is not None:
            ffnx_manager._restore_runtime_links(game, runtime_link_snapshots)
        try:
            runtime_layout.compose(
                project, active_root, runtime_layout.catalog(project, paths.MODS_ROOT),
                paths.BASELINE_ROOT, formats.SECTIONS,
                runtime_layout.prelaunch_condition_state(game / "FFNx.toml"),
            )
        except Exception:
            pass
        raise
    return payload(project, saved=1, game_root=game, runtime_root=active_root)


def ensure(game_root: Path | None = None, project_root: Path | None = None,
           *, install_runtime: bool = False,
           runtime_root: Path | None = None) -> dict:
    current = load(project_root, game_root, runtime_root)
    return save(
        current, game_root, project_root, install_runtime=install_runtime,
        runtime_root=runtime_root,
    )


def activate(game_root: Path | None = None,
             project_root: Path | None = None,
             runtime_root: Path | None = None) -> dict:
    """Write and verify the exact patch that FFNx will read before launch."""
    global _last_activation_ns
    game = (game_root or paths.GAME_ROOT).resolve()
    project = (project_root or paths.PROJECT_ROOT).resolve()
    active_root = _runtime_root(runtime_root, project)
    result = ensure(
        game, project, install_runtime=True, runtime_root=active_root,
    )
    _validate_shared_magic_launch(project, game, active_root)
    target = materialized_runtime_patch_path(active_root)
    config = game / "FFNx.toml"
    if not config.is_file():
        raise RuntimeError("FFNx.toml is missing. FFNx cannot load the gameplay patch.")
    text = config.read_text(encoding="utf-8", errors="strict")
    match = re.search(r'(?m)^\s*hext_patching_path\s*=\s*"([^"]+)"\s*$', text)
    configured_root = (active_root / "hext").resolve()
    if not match or Path(match.group(1)).resolve() != configured_root:
        actual = match.group(1) if match else "not configured"
        raise RuntimeError(
            f"FFNx uses {actual} as its Hext base, not {configured_root}."
        )
    effective_root = configured_root / FFNX_HEXT_SUFFIX
    if target.parent != effective_root:
        raise RuntimeError(
            f"The gameplay patch is in {target.parent}, but FFNx scans {effective_root}."
        )
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"The generated gameplay patch is missing: {target}")
    _last_activation_ns = time.time_ns()
    return {
        **result,
        "ready": True,
        "patchSha256": _sha256(target),
        "patchBytes": target.stat().st_size,
        "activatedAtNs": _last_activation_ns,
        "hextBase": str(configured_root),
        "hextRoot": str(effective_root),
    }


def _log_has_loaded_patch(text: str, target: Path) -> bool:
    expected = str(target.resolve()).replace("/", "\\").casefold()
    marker = "Applied Hext patch:"
    for line in text.splitlines():
        if marker.casefold() not in line.casefold():
            continue
        normalized = line.replace("/", "\\").casefold()
        if expected in normalized:
            return True
    return False


def runtime_status(game_root: Path | None = None,
                   project_root: Path | None = None,
                   runtime_root: Path | None = None,
                   game_running=ffnx_manager._game_running) -> dict:
    """Report whether FFNx loaded the patch from the latest launch barrier."""
    game = (game_root or paths.GAME_ROOT).resolve()
    log = game / "FFNx.log"
    if not log.is_file():
        return {"loaded": False, "logReady": False, "message": "FFNx.log is not ready."}
    text = log.read_text(encoding="utf-8", errors="replace")
    log_is_current = bool(_last_activation_ns) and log.stat().st_mtime_ns >= _last_activation_ns - 1_000_000_000
    target = materialized_runtime_patch_path(_runtime_root(runtime_root, project_root))
    loaded = log_is_current and _log_has_loaded_patch(text, target)
    hext_was_reached = log_is_current and "applied hext patch:" in text.casefold()
    running = bool(game_running())
    # FFNx writes its log before it scans Hext files. A fresh file that ends at
    # metadata initialization is not a failed patch scan. Another Hext file can
    # also appear before this patch. Keep waiting while the game process is
    # alive, and report a failure only after the process stops or the caller's
    # complete startup timeout expires.
    log_ready = loaded or (log_is_current and not running)
    last_line = next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")
    return {
        "loaded": loaded,
        "logReady": log_ready,
        "startupIncomplete": log_is_current and not log_ready,
        "gameRunning": running,
        "log": str(log),
        "message": (
            "FFNx loaded the Lexeditor gameplay patch."
            if loaded else
            "FFNx stopped after it applied other Hext files, but it did not apply the Lexeditor gameplay patch."
            if hext_was_reached and not running else
            f"The game stopped before FFNx reached Hext. Its last log entry was: {last_line or 'none'}."
            if log_is_current and not running else
            f"FFNx is still starting. Its last log entry is: {last_line or 'none'}."
            if log_is_current else
            "Waiting for FFNx to write a new log."
        ),
    }


def payload(project_root: Path | None = None, saved: int = 0,
            game_root: Path | None = None,
            runtime_root: Path | None = None) -> dict:
    project = (project_root or paths.PROJECT_ROOT).resolve()
    active_root = _runtime_root(runtime_root, project)
    current = load(project, game_root, active_root)
    bonus = current["flyingEvaBonus"]
    return {
        **current,
        "minimum": MIN_FLYING_EVA_BONUS,
        "maximum": MAX_FLYING_EVA_BONUS,
        "unit": "percentage points",
        "patch": str(patch_path(project)),
        "runtimePatch": str(materialized_runtime_patch_path(active_root)),
        "runtimeRoot": str(active_root),
        "enabled": current["flyingEvaEnabled"],
        "saved": saved,
    }
