from pathlib import Path


ROOT = Path(__file__).parents[1]
RUNTIME = ROOT / "games/ff9/runtime"


def source(name):
    return (RUNTIME / name).read_text(encoding="utf-8")


def test_better_eat_override_is_script_65_and_checks_before_kill():
    text = source("BetterEatScript.cs")
    assert "[BattleScript(65)]" in text
    enabled = text[text.index("public void Perform()") : text.index("private void PerformVanilla()")]
    assert enabled.index("BlueMagicId") < enabled.index("_v.Target.Kill")
    assert enabled.index("FF9Abil_IsMaster") < enabled.index("_v.Target.Kill")
    vanilla = text[text.index("private void PerformVanilla()") : text.index("private void Learn")]
    assert vanilla.index("_v.Target.Kill") < vanilla.index("FF9Abil_IsMaster")
    assert "public Single RateTarget()" in text


def test_improved_interface_does_not_rebind_memoria_dialog_buttons():
    text = source("Runtime.cs")
    assert "DialogProgressButtons" not in text
    assert "Control.Cancel" in text and "AdvanceProgressToMax" in text
    assert "Control.Special" in text and "!hasChoice" in text
    assert "Control.LeftTrigger" in text
    assert "CurrentParser.ParsedText" in text
    assert "QuadmistWinList.Contains" in text
    assert "DrawBarRightToLeft" in text


def test_better_eat_glow_and_target_filter_are_present():
    text = source("Runtime.cs")
    assert 'GlowName = "Lexeditor Blue Magic Glow"' in text
    assert "FF9Abil_IsMaster" in text
    assert "ButtonGroupState.SetButtonEnable" in text
    assert "CanLearnFrom" in text


def test_new_ui_tweaks_anchor_to_memoria_widgets():
    text = source("UIEnhancements.cs")
    assert "characterBRInfoHudList" in text
    assert "_partyDetail" in text
    assert "NGUITools.FindCameraForLayer" in text
    assert "worldCorners" in text
    assert "ExperienceFraction" in text
    assert "CharacterLevelUps" in text
    assert "new Color(0.92f, 0.18f, 0.18f" in text
    assert "new Color(0.18f, 0.48f, 1.0f" in text


def test_mognet_highlight_uses_vanilla_delivery_choice_mask():
    text = source("UIEnhancements.cs")
    assert "Moogle_Make_SpeakBTN" in text
    assert "VAR_B3_1 >= 0" in text
    assert "(mask & 0x47) != 0x47" in text
    assert "(mask & 0x08) == 0" in text
    assert "choices[2]" in text
    assert "dialog.ChooseMask" in text


def test_bootstrap_defers_unity_work_to_game_loop_update():
    text = source("Bootstrap.cs")
    ctor = text[text.index("public LexeditorBootstrapAttribute()") : text.index("internal static class LexeditorBootstrap")]
    assert "LexeditorBootstrap.Install" in ctor
    install = text[text.index("public static void Install()") : text.index("private static void OnUpdate()")]
    assert "GameLoopManager.Update += OnUpdate" in install
    assert "new GameObject" not in install
    update = text[text.index("private static void OnUpdate()") :]
    assert "new GameObject" in update
    assert "LexeditorUIEnhancements" in update


def test_feature_config_has_independent_xp_and_hpmp_toggles():
    text = source("Bootstrap.cs")
    assert "public static Boolean XPBars" in text
    assert "public static Boolean HPMPBars" in text
    assert 'key.Equals("XPBars"' in text
    assert 'key.Equals("HPMPBars"' in text


def test_runtime_uses_mod_specific_scriptsloader_filename():
    from games.ff9 import features
    assert features.RUNTIME_NAME == "Memoria.Scripts.Lexeditor.dll"
    assert not (RUNTIME / "Memoria.Scripts.dll").exists()


def test_shipped_runtime_is_mod_specific_memoria_script_and_real_pe():
    binary = RUNTIME / "Memoria.Scripts.Lexeditor.dll"
    assert binary.is_file(), "runtime build must ship Memoria's mod-specific ScriptsLoader filename"
    data = binary.read_bytes()
    assert data.startswith(b"MZ") and len(data) > 10_000
    assert b"BetterEatScript" in data and b"LexeditorBootstrap" in data
    assert b"LexeditorUIEnhancements" in data
