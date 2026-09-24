"""Info bubbles explain semantics; visible property metadata stays out of them."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui, plugins_with_ui

PLUGIN_EDITORS = sorted((ROOT / "plugins").glob("*/editor.html"))

def text(path):
    return (ROOT / path).read_text("utf-8")

def test_detail_field_never_fabricates_info_bubbles_from_metadata():
    framework = text("ui/framework.js")
    assert 'options.help || infoHelp(helpText)' not in framework
    assert 'const helpMarker = options.help || (suppliedHelp ? infoHelp(suppliedHelp) : null);' in framework
    semantic_block = framework[framework.index('const suppliedHelp = options.help instanceof Element'):framework.index('const typeRail = element("div", {class: "lex-field-type-rail"}')]
    for forbidden in ('Allowed range:', 'Minimum:', 'Maximum:', 'Whole numbers only.', 'Step:', 'Unit:', 'Edit the stored', 'Enable or disable', 'Choose ${labelText}'):
        assert forbidden not in semantic_block

def test_known_metadata_filler_is_gone_from_plugins():
    sources = "\n".join(plugin_ui(name) for name in plugins_with_ui())
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
    ff9 = plugin_ui('ff9')
    for key in (
        '"characters:Strength"', '"characters:Magic"', '"leveling:BonusHP"',
        '"leveling:BonusMP"', '"items:AbilityIds"', '"items:BonusId"',
        '"shops:Items"', '"abilities:Gems"', '"actions:scriptId"',
        '"status-data:ContiCount(duration)"',
    ):
        assert key in ff9
    assert 'return FIELD_HELP[`${dataKey}:${field.key}`]||"";' in ff9

def test_rdr2_setting_help_does_not_append_visible_metadata():
    rdr2 = plugin_ui('rdr2')
    block = rdr2[rdr2.index("function settingHelp(section,setting)"):rdr2.index("function settingUnit(section,key)")]
    assert "Editor range:" not in block
    assert "Unit:" not in block
    assert "has no field-specific behavior description" not in block


def test_rdr_uses_shared_detail_fields_and_semantic_reward_help():
    rdr = plugin_ui('rdr')
    helper = rdr[rdr.index("function detailField"):rdr.index("function applyControlValue")]
    # RDR's rows now also carry the shared info bubble, so the helper forwards
    # both `description` (prose under the row) and `help` (the bubble). The
    # requirement is that it delegates to the shared field, not that it passes
    # exactly one argument.
    assert "LexeditorUI.detailField({label,control,description:help||\"\"" in helper
    assert "LexeditorUI.infoHelp(" in helper
    assert 'class:"detail-field"' not in helper
    assert "XML value attribute" not in rdr
    assert '"XML text"' not in rdr
    assert "Base value:" not in rdr
    assert "Integer range" not in rdr
    for phrase in (
        "Changes the cash awarded when this mission completes",
        "completion Fame award independently",
        "completion Honor adjustment independently",
    ):
        assert phrase in rdr
    # RDR theming may paint shared rows, but it may not restore a plugin-owned
    # fixed label lane or the legacy private generic Detail-row classes.
    assert ".detail-field{display:grid" not in rdr
    assert ".detail-field{grid-template-columns" not in rdr
    # The label is styled through the shared token now, not by naming the
    # shared class: see tests/shared/verify_shared_ui_budget.py.
    assert "--lex-field-label-fg" in rdr
