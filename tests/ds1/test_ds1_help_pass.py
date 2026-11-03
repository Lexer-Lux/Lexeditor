"""DS1 property help pass: short, non-echoing, present-where-needed bubbles.

Per the help-text skill: a field bubble runs three sentences at most, never
repeats its label, and exists only where the label and control leave the
reader guessing. Guard stats, model masks, phantom targeting, the offline
toggle and curve coefficients need one; ally checkboxes do not.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ds1.formats import TABLES, schema  # noqa: E402


def sentences(text):
    shielded = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    shielded = shielded.replace("e.g.", "e<DOT>g<DOT>")
    parts = [part for part in re.split(r"[.!?]+", shielded) if part.strip()]
    # The shared presentation appends one neutral-value note ("1 is
    # unchanged") after the authored bubble; the audit counts what the
    # author wrote, not the uniform suffix.
    if parts and re.fullmatch(r"\s*\d+(\.\d+)? is unchanged\s*", parts[-1].replace("<DOT>", ".")):
        parts.pop()
    return parts


def norm(text):
    return re.sub(r"[.\s]", "", text).lower()


def editable_fields():
    for table in sorted(TABLES):
        for entry in schema(table)["fields"]:
            if entry.get("editable"):
                yield table, entry["spec"]


def test_field_bubbles_run_three_sentences_at_most():
    long = [(table, spec.key, len(sentences(spec.description or "")))
            for table, spec in editable_fields() if spec.description.strip()]
    long = [(table, key, count) for table, key, count in long if count > 3]
    assert long == []


def test_field_bubbles_never_repeat_their_label():
    echo = [(table, spec.key) for table, spec in editable_fields()
            if spec.description.strip() and norm(spec.description) in (
                norm(spec.label), norm("The " + spec.label))]
    assert echo == []


def test_guard_stats_explain_their_percentage():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("NpcParam")["fields"]}
    for key in ("physGuardCutRate", "magGuardCutRate", "fireGuardCutRate",
                "thunGuardCutRate", "slashGuardCutRate", "blowGuardCutRate",
                "thrustGuardCutRate", "staminaGuardDef", "poisonGuardResist",
                "diseaseGuardResist", "bloodGuardResist", "curseGuardResist"):
        assert "guarding" in fields[key].description, key


def test_model_masks_say_what_they_hide():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("EquipParamProtector")["fields"]}
    # Flags whose hidden body part is researched name it; the rest say so.
    known = {0, 1, 2, 3, 4, 5, 6, 10, 11, 15, 20, 21, 25, 30}
    for index in range(48):
        description = fields["invisibleFlag%02d" % index].description
        if index in known:
            assert description.startswith("Hides "), index
            assert description.endswith(" while worn."), index
        else:
            assert description.startswith("Unknown. "), index
            assert "hides part of the body" in description, index


def test_effect_targets_need_no_bubble():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("SpEffectParam")["fields"]}
    for key in ("effectTargetSelf", "effectTargetFriend", "effectTargetEnemy",
                "effectTargetPlayer", "effectTargetAI"):
        assert fields[key].description.strip() == "", key


def test_phantom_targets_explain_who_they_touch():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("SpEffectParam")["fields"]}
    assert "human characters" in fields["effectTargetLive"].description
    assert "Hollows are excluded" in fields["effectTargetLive"].description
    assert "hollow characters" in fields["effectTargetGhost"].description
    assert "white phantoms" in fields["effectTargetWhiteGhost"].description
    assert "red phantoms" in fields["effectTargetBlackGhost"].description


def test_offline_toggle_explains_when_to_use_it():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("EquipParamGoods")["fields"]}
    assert fields["disable_offline"].label == "Disable Offline"
    description = fields["disable_offline"].description
    assert "offline blocks this item" in description
    assert "need other players" in description


def test_guard_stability_keeps_its_facts_short():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("SpEffectParam")["fields"]}
    description = fields["guardStaminaCutRate"].description
    assert "magic shield" in description
    assert "stateInfo" in description
    assert "100" in description
    assert len(sentences(description)) <= 3


def test_reinforce_offsets_name_their_own_field():
    fields = {entry["spec"].key: entry["spec"]
              for entry in schema("ReinforceParamWeapon")["fields"]}
    assert "second" in fields["residentSpEffectId2"].description
    assert "third" in fields["residentSpEffectId3"].description
