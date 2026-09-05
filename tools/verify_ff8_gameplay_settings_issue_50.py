"""Static and generated-patch contract for Lexeditor issue 50."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import (  # noqa: E402
    battle_shortcuts,
    better_targeting_issue_64,
    fast_start,
    gameplay_settings,
    healing_rework,
    inventory_auto_sort,
    menu_qol_issue_61,
    modern_controls_issue_65,
    party_switch_issue_62,
    streamlined_draw,
    true_atb_wait_issue_63,
    vibration_consolidation_issue_66,
)


def expect_invalid(data: dict, fragment: str) -> None:
    installed = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-settings-invalid-", ignore_cleanup_errors=True) as name:
            gameplay_settings.save(data, game_root=installed, project_root=Path(name))
    except ValueError as error:
        assert fragment in str(error)
        return
    raise AssertionError(f"Invalid settings were accepted: {data!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-tweaks-default-a-", ignore_cleanup_errors=True) as first_name, \
         tempfile.TemporaryDirectory(prefix="lexeditor-ff8-tweaks-default-b-", ignore_cleanup_errors=True) as second_name:
        first = Path(first_name)
        second = Path(second_name)
        defaults = gameplay_settings.load(first)
        boolean_tweaks = (
            "flyingEvaEnabled", "autoSortInventory", "autoSortMagic",
            "enhancedAbilityMenu", "singleGf",
            "universalItem", "scannedTargetScan", "partySwitch", "drawOncePerEnemy",
            "streamlinedDraw", "formulaeRework",
            "fixedCommandMenu", "trueAtbWait", "modernControls",
            "vibrationConsolidation", "betterTargeting",
            "damageLimitRemoval", "betterCard",
            "fastStart", "xpBars", "hpBars",
            "flatStatAbilities", "maxSpellEnabled",
        )
        assert all(defaults[key] is False for key in boolean_tweaks), defaults
        assert defaults["flyingEvaBonus"] == 25
        assert defaults["maxSpell"] == 100
        assert all(gameplay_settings.load(second)[key] is False for key in boolean_tweaks)
        gameplay_settings.settings_path(second).write_text(
            json.dumps({"flyingEvaBonus": 25}), encoding="utf-8",
        )
        assert gameplay_settings.load(second)["flyingEvaEnabled"] is False
        gameplay_settings.initialize_project(first)
        initialized = gameplay_settings.load(first)
        assert all(initialized[key] is False for key in boolean_tweaks), initialized
        generated = gameplay_settings.patch_path(first).read_text(encoding="utf-8")
        assert f"{gameplay_settings.HIT_FORMULA_HOOK:X} =" not in generated
        gameplay_settings.settings_path(second).write_text(
            json.dumps({"spellHealingRework": True, "fullLuckAccuracy": False}),
            encoding="utf-8",
        )
        migrated = gameplay_settings.load(second)
        assert migrated["formulaeRework"] is False
        assert "spellHealingRework" not in migrated
        assert "fullLuckAccuracy" not in migrated

    default_patch = gameplay_settings.build_hext(25, False)
    assert "4BEB10 =" not in default_patch
    assert "4DF5D0 =" not in default_patch
    assert "4F8146 =" not in default_patch
    assert "Automatic inventory sorting is disabled" in default_patch
    no_flying_patch = gameplay_settings.build_hext(25, flying_eva_enabled=False)
    assert f"{gameplay_settings.HIT_FORMULA_HOOK:X} =" not in no_flying_patch
    assert "Flying EVA Bonus is disabled" in no_flying_patch
    patch = gameplay_settings.build_hext(25, True, True)
    inventory_patch = inventory_auto_sort.build_hext(True)
    assert inventory_patch.rstrip() in patch
    assert f"{inventory_auto_sort.ITEM_OPEN_SORT_HOOK:X} = " in patch
    assert "66 C7 46 10 4F 00" not in patch, "the broken controller-state injection returned"
    assert inventory_auto_sort.relative_branch(
        b"\xE9",
        inventory_auto_sort.CODE_CAVE + inventory_auto_sort.CODE_CAVE_LENGTH - 5,
        inventory_auto_sort.ITEM_INITIALIZER,
    ) in inventory_auto_sort.build_code_cave()
    assert "279EF60:15" in patch
    assert "4DF5D0 = E9 8B F9 2B 02 90 90 90" in patch
    assert "85 D2 0F 85" in patch, "the nonzero GF mask is not refused"
    magic_patch = gameplay_settings.build_hext(25, auto_sort_magic=True)
    assert menu_qol_issue_61.build_auto_sort_magic_hext(True).rstrip() in magic_patch
    ability_patch = gameplay_settings.build_hext(25, enhanced_ability_menu=True)
    assert menu_qol_issue_61.build_enhanced_ability_menu_hext(True).rstrip() in ability_patch

    # Every gameplay feature shares one generated Hext file. Feature-local
    # checks cannot detect two components reserving the same code-cave bytes.
    all_patch = gameplay_settings.build_hext(
        25,
        auto_sort=True,
        single_gf_enabled=True,
        universal_item=True,
        draw_once_per_enemy=True,
        better_card_enabled=True,
        scanned_target_scan=True,
        party_switch=False,
        fixed_command_menu_enabled=True,
        auto_sort_magic=True,
        enhanced_ability_menu=True,
        true_atb_wait=True,
        modern_controls=False,
        vibration_consolidation=True,
        better_targeting=True,
        fast_start_enabled=True,
        streamlined_draw_enabled=True,
        formulae_rework=True,
    )
    assignments = [
        int(match.group(1), 16)
        for match in re.finditer(r"(?m)^([0-9A-F]+) =", all_patch)
    ]
    assert len(assignments) == len(set(assignments)), "duplicate Hext address assignment"
    reservations = sorted(
        (int(match.group(1), 16), int(match.group(2), 16))
        for match in re.finditer(r"(?m)^([0-9A-F]+):([0-9A-F]+)$", all_patch)
    )
    for current, following in zip(reservations, reservations[1:]):
        assert current[0] + current[1] <= following[0], (
            f"Hext reservation overlap: {current!r} and {following!r}"
        )
    assert battle_shortcuts.build_hext(
        universal_item=True, scanned_target_scan=True, party_switch=False,
    ).rstrip() in all_patch
    assert "A8 04" not in all_patch, "the unsafe Party Switch input hook returned"
    assert not any(0x027A0900 <= address < 0x027A0A00 for address in assignments), (
        "a retired Party Switch code cave returned"
    )
    assert not any(0x027A0900 <= address < 0x027A0A00 for address, _ in reservations), (
        "a retired Party Switch reservation returned"
    )
    assert f"{true_atb_wait_issue_63.ATB_WAIT_HOOK:X} = E8" in all_patch
    assert f"{modern_controls_issue_65.CAMERA_YAW_HOOK:X} =" not in all_patch
    assert f"{modern_controls_issue_65.REJECTED_NORMAL_INPUT_FIELD:X} =" not in all_patch
    assert f"{modern_controls_issue_65.REJECTED_SPECIAL_MODE_READ:X} =" not in all_patch
    assert f"{vibration_consolidation_issue_66.FIELD_HOOK:X} = E9" in all_patch
    assert f"{vibration_consolidation_issue_66.BATTLE_HOOK:X} = E9" in all_patch
    assert f"{better_targeting_issue_64.TARGET_ICON_HOOK:X} = E8" in all_patch
    assert fast_start.build_hext(True).rstrip() in all_patch
    assert streamlined_draw.build_hext(True).rstrip() in all_patch
    assert healing_rework.build_hext(True).rstrip() in all_patch
    assert f"{menu_qol_issue_61.ABILITY_LIST_RETURN_HOOK:X} = E9" in all_patch
    assert f"{menu_qol_issue_61.ABILITY_PALETTE_HOOK:X} = E9" in all_patch

    installed = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII")
    if (installed / "FF8_EN.exe").is_file():
        with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-settings-", ignore_cleanup_errors=True) as name:
            project = Path(name)
            legacy = gameplay_settings.legacy_patch_path(project)
            legacy.parent.mkdir(parents=True)
            legacy.write_text("obsolete", encoding="utf-8")
            wrong_edition = gameplay_settings.obsolete_english_patch_path(project)
            wrong_edition.parent.mkdir(parents=True)
            wrong_edition.write_text("wrong edition", encoding="utf-8")
            result = gameplay_settings.save({
                "flyingEvaBonus": 25,
                "flyingEvaEnabled": False,
                "autoSortInventory": False,
                "singleGf": True,
                "universalItem": True,
            }, game_root=installed, project_root=project)
            assert result["saved"] == 1
            assert json.loads(gameplay_settings.settings_path(project).read_text()) == {
                "autoSortInventory": False,
                "autoSortMagic": False,
                "enhancedAbilityMenu": False,
                "flyingEvaBonus": 25,
                "flyingEvaEnabled": False,
                "singleGf": True,
                "universalItem": True,
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
                "maxSpell": gameplay_settings.DEFAULT_MAX_SPELL,
            }
            assert gameplay_settings.patch_path(project).read_text(encoding="utf-8") == gameplay_settings.build_hext(
                25, auto_sort=False, single_gf_enabled=True,
                universal_item=True,
                flying_eva_enabled=False,
            )
            assert gameplay_settings.patch_path(project).parent == project / "hext" / "ff8" / "en_nv"
            assert not legacy.exists(), "the obsolete base-directory patch would never be read by FFNx"
            assert not wrong_edition.exists(), "the Nvidia executable does not scan the plain en directory"

            game = project / "game"
            game.mkdir()
            runtime = project / ".lexeditor-runtime"
            shutil.copy2(installed / "FF8_EN.exe", game / "FF8_EN.exe")
            config = game / "FFNx.toml"
            config.write_text(
                f'hext_patching_path = "{(runtime / "hext").as_posix()}"\n',
                encoding="utf-8",
            )
            activation = gameplay_settings.activate(
                game_root=game, project_root=project,
            )
            assert activation["ready"] is True
            assert Path(activation["hextRoot"]) == runtime / "hext" / "ff8" / "en_nv"
            assert Path(activation["runtimeRoot"]) == runtime
            assert Path(activation["runtimePatch"]).read_bytes() == gameplay_settings.patch_path(project).read_bytes()
            assert not (game / "lexeditor-direct").resolve() == (project / "direct").resolve(), (
                "FFNx must not read the editable mod folder directly"
            )
            assert (game / "lexeditor-direct").resolve() == (runtime / "direct").resolve()

            log = game / "FFNx.log"
            log.write_text(
                f"[00000000] TRACE: Applied Hext patch: "
                f"{activation['runtimePatch']}\n",
                encoding="utf-8",
            )
            future = time.time_ns() + 2_000_000_000
            os.utime(log, ns=(future, future))
            runtime = gameplay_settings.runtime_status(
                game_root=game, project_root=project,
            )
            assert runtime["loaded"] is True, runtime
            assert runtime["logReady"] is True, runtime

        base = {"flyingEvaBonus": 25, "flyingEvaEnabled": False,
                "autoSortInventory": False,
                "singleGf": False}
        for value in (0, 1, "true", None):
            expect_invalid({**base, "flyingEvaEnabled": value}, "true or false")
        for value in (0, 1, "true", None):
            expect_invalid({**base, "autoSortInventory": value}, "true or false")
        for value in (0, 1, "true", None):
            expect_invalid({**base, "autoSortMagic": value}, "true or false")
        for value in (0, 1, "true", None):
            expect_invalid({**base, "enhancedAbilityMenu": value}, "true or false")
        for value in (0, 1, "true", None):
            expect_invalid({**base, "singleGf": value}, "Monogamy")
        for key, label in (
            ("trueAtbWait", "True ATB Wait"),
            ("formulaeRework", "Formulae Rework"),
            ("partySwitch", "FF10-style Party Switch"),
            ("modernControls", "Modern Controls"),
            ("vibrationConsolidation", "Vibration Rationalization"),
            ("betterTargeting", "Better Targeting"),
            ("damageLimitRemoval", "Damage Limit Removal"),
            ("betterCard", "Better Card"),
            ("streamlinedDraw", "Streamlined Draw"),
            ("fastStart", "Fast Start"),
            ("xpBars", "XP Bars"),
            ("hpBars", "HP Bars"),
        ):
            for value in (0, 1, "true", None):
                expect_invalid({**base, key: value}, label)
        expect_invalid({**base, "formulaeRework": True}, "Formulae Rework is not available")

        with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-new-settings-", ignore_cleanup_errors=True) as name:
            project = Path(name)
            result = gameplay_settings.save({
                **base,
                "flyingEvaEnabled": True,
                "autoSortInventory": True,
                "autoSortMagic": True,
                "singleGf": True,
                "universalItem": True,
                "scannedTargetScan": True,
                "drawOncePerEnemy": True,
                "fixedCommandMenu": True,
                "trueAtbWait": True,
                "formulaeRework": False,
                "partySwitch": False,
                "modernControls": False,
                "vibrationConsolidation": True,
                "betterTargeting": True,
                "enhancedAbilityMenu": True,
                "betterCard": True,
                "streamlinedDraw": True,
                "damageLimitRemoval": True,
                "fastStart": True,
                "xpBars": True,
                "hpBars": True,
                "sharedMagicInventory": True,
                "flatStatAbilities": True,
                "maxSpellEnabled": True,
                "maxSpell": 100,
            }, game_root=installed, project_root=project)
            assert result["saved"] == 1
            saved = json.loads(gameplay_settings.settings_path(project).read_text())
            for key in (
                "flyingEvaEnabled", "autoSortInventory", "autoSortMagic",
                "enhancedAbilityMenu", "singleGf", "universalItem", "scannedTargetScan",
                "drawOncePerEnemy", "fixedCommandMenu",
                "trueAtbWait", "formulaeRework", "partySwitch", "modernControls", "vibrationConsolidation",
                "betterTargeting",
                "enhancedAbilityMenu",
                "betterCard", "streamlinedDraw", "damageLimitRemoval",
                "fastStart", "xpBars", "hpBars",
                "flatStatAbilities", "maxSpellEnabled",
            ):
                expected = key not in {"formulaeRework", "partySwitch", "modernControls"}
                assert saved[key] is expected, (key, saved[key], expected)
                assert result[key] is expected
            generated = gameplay_settings.patch_path(project).read_text(encoding="utf-8")
            assert result["sharedMagicInventory"] is True
            assert (project / "direct" / "lexeditor" / "gameplay.toml").read_text(
                encoding="utf-8",
            ) == "schemaVersion = 1\nsharedMagicInventory = true\nmagicStockLimit = 100\n"
            assert true_atb_wait_issue_63.build_hext(True).rstrip() in generated
            assert battle_shortcuts.build_hext(
                universal_item=True, scanned_target_scan=True, party_switch=False,
            ).rstrip() in generated
            assert "A8 04" not in generated
            assert f"{modern_controls_issue_65.CAMERA_YAW_HOOK:X} =" not in generated
            assert vibration_consolidation_issue_66.build_hext(True).rstrip() in generated
            assert better_targeting_issue_64.build_hext(True).rstrip() in generated
            assert menu_qol_issue_61.build_auto_sort_magic_hext(True).rstrip() in generated
            assert menu_qol_issue_61.build_enhanced_ability_menu_hext(True).rstrip() in generated
            assert inventory_auto_sort.build_hext(True).rstrip() in generated
            assert fast_start.build_hext(True).rstrip() in generated
            assert streamlined_draw.build_hext(True).rstrip() in generated
            assert healing_rework.build_hext(True).rstrip() not in generated

        for key in ("partySwitch", "modernControls"):
            with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-native-control-", ignore_cleanup_errors=True) as name:
                project = Path(name)
                result = gameplay_settings.save({**base, key: True}, game_root=installed,
                                                project_root=project, install_runtime=False)
                assert result[key] is True
                assert gameplay_settings.load(project)[key] is True
                generated = gameplay_settings.patch_path(project).read_text(encoding="utf-8")
                assert "557634 =" not in generated and "558676 =" not in generated
                config = project / "FFNx.toml"
                config.write_text("enable_devtools = false\ncustom_option = 17\n")
                for enabled in (True, False):
                    gameplay_settings._set_ffnx_runtime_tweaks(config, xp_bars=False,
                        hp_bars=False, better_targeting=False,
                        modern_controls=enabled, party_switch=enabled)
                    saved_config = config.read_text()
                    assert "custom_option = 17" in saved_config
                    for flag in ("enable_ff8_modern_controls", "enable_ff8_party_switch"):
                        assert saved_config.count(flag + " =") == 1
                        assert f"{flag} = {str(enabled).lower()}" in saved_config

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    assert "MONOGAMY" in editor
    assert "lex-setting-default-control" not in editor
    assert "maximumGfsPerCharacter" not in editor
    assert 'type:"checkbox",checked:settings.singleGf' in editor
    warning = "when gameplay starts, any character who already has several GFs junctioned will have all of those GFs unequipped"
    assert warning in editor
    assert "Existing multi-GF setups remain intact" not in editor
    gameplay_view = editor[editor.index("function renderGameplaySettings"):editor.index("function renderPlatformSettings")]
    for label, key in (
        ("AUTO-SORT MAGIC MENU", "autoSortMagic"),
        ("ENHANCED SCAN", "scannedTargetScan"),
        ("TRUE ATB WAIT", "trueAtbWait"),
        ("FF10-STYLE PARTY SWITCH", "partySwitch"),
        ("BETTER TARGETING", "betterTargeting"),
        ("MODERN CONTROLS", "modernControls"),
        ("VIBRATION RATIONALIZATION", "vibrationConsolidation"),
        ("ENHANCED ABILITY MENU", "enhancedAbilityMenu"),
        ("STREAMLINED DRAW", "streamlinedDraw"),
        ("XP BARS", "xpBars"),
        ("HP BARS", "hpBars"),
    ):
        assert f'row("{label}"' in gameplay_view
        assert f'{key}:state.data.settings.{key}' in editor
    assert "FULL LUCK ACCURACY" not in gameplay_view
    assert "SPELL HEALING REWORK" not in gameplay_view
    assert 'row("FORMULAE REWORK"' not in gameplay_view
    assert 'row("FAST START"' in gameplay_view
    assert 'row("MONOGAMY"' in gameplay_view
    assert 'row("UNIVERSAL ITEM"' in gameplay_view
    assert "healing_rework.build_hext(formulae_rework)" in (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(encoding="utf-8")
    assert "luck_accuracy.build_hext(formulae_rework)" in (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(encoding="utf-8")

    print("FF8 visible Tweak persistence and composition passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
