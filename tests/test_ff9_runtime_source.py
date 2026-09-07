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


def test_bootstrap_defers_unity_work_to_game_loop_update():
    text = source("Bootstrap.cs")
    ctor = text[text.index("public LexeditorBootstrapAttribute()") : text.index("internal static class LexeditorBootstrap")]
    assert "LexeditorBootstrap.Install" in ctor
    install = text[text.index("public static void Install()") : text.index("private static void OnUpdate()")]
    assert "GameLoopManager.Update += OnUpdate" in install
    assert "new GameObject" not in install
    assert "new GameObject" in text[text.index("private static void OnUpdate()") :]


def test_shipped_runtime_is_exact_memoria_script_filename_and_real_pe():
    binary = RUNTIME / "Memoria.Scripts.dll"
    assert binary.is_file(), "runtime build must ship Memoria's exact ScriptsLoader filename"
    data = binary.read_bytes()
    assert data.startswith(b"MZ") and len(data) > 10_000
    # The compile workflow builds this file from the three audited source units
    # against the pinned publisher assemblies on every FF9 change.
    assert b"BetterEatScript" in data and b"LexeditorBootstrap" in data
