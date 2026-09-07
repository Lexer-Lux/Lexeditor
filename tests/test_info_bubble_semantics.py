"""Info bubbles explain semantics; visible property metadata stays out of them."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path):
    return (ROOT / path).read_text("utf-8")

def test_detail_field_never_fabricates_info_bubbles_from_metadata():
    framework = text("ui/framework.js")
    assert 'options.help || infoHelp(helpText)' not in framework
    assert 'const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);' in framework
    semantic_block = framework[framework.index('const suppliedHelp = options.help instanceof Element'):framework.index('const typeRail = element("div", {class: "lex-field-type-rail"}')]
    for forbidden in ('Allowed range:', 'Minimum:', 'Maximum:', 'Whole numbers only.', 'Step:', 'Unit:', 'Edit the stored', 'Enable or disable', 'Choose ${labelText}'):
        assert forbidden not in semantic_block

def test_manual_defines_semantic_only_contract():
    manual = text("docs/UI-MANUAL.md")
    assert "Info-bubble text explains **meaning and consequences**" in manual
    assert "Never put the property's data type, allowed/storage numeric range, step size, displayed unit" in manual
    assert "If no useful semantic explanation is known, omit the info" in manual

def test_known_metadata_filler_is_gone_from_plugins():
    sources = "\n".join(text(path) for path in (
        "games/blank/editor.html", "games/ff7/editor.html", "games/ff8/editor.html",
        "games/ff9/editor.html", "games/rdr/editor.html", "games/rdr2/editor.html",
    ))
    for forbidden in (
        "Storage range:", "Editor range:", "This Memoria array is edited as a comma-separated list.",
        "Stored parameter 1.", "Stored parameter 2.", "These are the exact stored Renzokuken table values.",
        "A bounded whole-number property. Focus it to reveal its type and valid range.",
        "Both curves come from the routines the game uses",
        "across levels 1–100",
        "The first stop keypoint used by this train track.",
        "The second stop keypoint used by this train track.",
        "Probability from 0 to 1.",
    ):
        assert forbidden not in sources

def test_ff9_has_real_semantic_help_for_core_relationships():
    ff9 = text("games/ff9/editor.html")
    for key in (
        '"characters:Strength"', '"characters:Magic"', '"leveling:BonusHP"',
        '"leveling:BonusMP"', '"items:AbilityIds"', '"items:BonusId"',
        '"shops:Items"', '"abilities:Gems"', '"actions:scriptId"',
        '"status-data:ContiCount(duration)"',
    ):
        assert key in ff9
    assert 'return FIELD_HELP[`${dataKey}:${field.key}`]||"";' in ff9

def test_rdr2_setting_help_does_not_append_visible_metadata():
    rdr2 = text("games/rdr2/editor.html")
    block = rdr2[rdr2.index("function settingHelp(section,setting)"):rdr2.index("function settingUnit(section,key)")]
    assert "Editor range:" not in block
    assert "Unit:" not in block
    assert "has no field-specific behavior description" not in block
