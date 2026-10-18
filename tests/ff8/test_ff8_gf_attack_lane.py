"""The GF Attack tab keeps readable property names in its narrow center pane.

At 463px the name lane must fit every Attack property name without overflow
and without dropping below the shared 9px floor, and it must not reserve a
third of the panel for names again (todo: GF center-panel attack lane).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from test_shared_ui_feedback import page, framework, ROOT  # noqa: E402


ATTACK_FIELDS = {"attack_animation", "attack_type", "gf_power", "status_window_flags",
                 "target_info", "attack_flags_type", "attack_flags", "target_animation",
                 "hit_count", "element", "status_1", "status_2", "status_attack_enabler",
                 "power_mod", "level_mod", "boost_param_1", "boost_param_2",
                 "ability1_unlocker"}


def _attack_rows():
    schema = json.loads((ROOT / "plugins/ff8/schema/kernel_section_fields.json").read_text(encoding="utf-8"))
    lookups = json.loads((ROOT / "plugins/ff8/schema/kernel_lookups.json").read_text(encoding="utf-8"))
    rows = []
    for field in schema["3"]["fields"]:
        if field["name"] not in ATTACK_FIELDS:
            continue
        lookup = None
        if field.get("lookup") and field["lookup"] in lookups:
            source = lookups[field["lookup"]]
            lookup = {"name": field["lookup"], "type": source.get("type", "enum"),
                      "entries": source.get("entries", [])}
        size = int(field.get("size", 1))
        rows.append({
            "field": field["name"],
            "label": field.get("label") or field["name"].replace("_", " ").title(),
            "help": field.get("help", ""),
            "value": 0,
            "minimum": int(field.get("minimum", 0)),
            "maximum": int(field.get("maximum", (1 << (size * 8)) - 1)),
            "control": "boolean" if field.get("bool") else field.get("control"),
            "lookup": lookup,
        })
    assert len(rows) == len(ATTACK_FIELDS), len(rows)
    return rows


def test_attack_names_fit_a_463px_center_pane(page):
    framework(page)
    page.add_style_tag(path=str(ROOT / "plugins/ff8/editor.css"))
    for name in ("core.js", "records.js", "party.js"):
        page.add_script_tag(path=str(ROOT / "plugins/ff8" / name))
    page.evaluate("""rows => {
      state.gfDetailTab = 'attack';
      state.data.gfs = {rows: []};
      const main = document.querySelector('main');
      main.style.width = '463px';
      main.append(gfPanel('', rows, {id: 0, fields: rows}, 'attack'));
    }""", _attack_rows())
    page.wait_for_timeout(1200)
    report = page.evaluate("""() => {
      const pane = document.querySelector('[data-gf-panel="attack"]');
      const out = {panelWidth: pane.getBoundingClientRect().width, labels: []};
      for (const label of pane.querySelectorAll(':scope .lex-detail-field-label')) {
        const css = getComputedStyle(label);
        const text = label.querySelector(':scope > .lex-detail-field-label-text');
        const box = label.getBoundingClientRect();
        const tbox = text.getBoundingClientRect();
        out.labels.push({
          name: text.textContent.trim(),
          fontPx: parseFloat(css.fontSize),
          lanePx: box.width,
          overflow: label.scrollWidth > label.clientWidth + 1,
          outside: tbox.left < box.left - 1 || tbox.right > box.right + 1,
        });
      }
      return out;
    }""")
    assert len(report["labels"]) == len(ATTACK_FIELDS), report
    for label in report["labels"]:
        assert not label["overflow"], label
        assert not label["outside"], label
        assert label["fontPx"] >= 9, label
        assert label["lanePx"] / report["panelWidth"] < 0.25, label
