"""FF7 name-sort order lives on each item, not on a separate subtab."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plugin_ui import plugin_ui  # noqa: E402
from test_shared_ui_feedback import ROOT, framework, page  # noqa: E402,F401  (pytest fixture)


class FF7NameSortTests(unittest.TestCase):
    def test_no_name_sort_subtab_wiring(self):
        ui = plugin_ui("ff7")
        self.assertNotIn('"Name sort"', ui)
        self.assertNotIn("itemSortOrder:\"Name sort\"", ui)
        self.assertIn('items:["items","keyItems"]', ui)
        self.assertIn("Name-sort position", ui)
        self.assertIn("item-name-sort", ui)

    def test_data_map_points_sort_table_at_items(self):
        from plugins.ff7 import server
        from tests.verify_ff7_datasets import write_kernel
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            write_kernel(root / "game/data/lang-en/kernel/KERNEL.BIN")
            with patch.object(server, "GAME_ROOT", root / "game"), \
                    patch.object(server, "PROJECT_ROOT", root / "project"):
                rows = {row["id"]: row for row in server.data_map()["rows"]}
        row = rows["itemSortOrder"]
        self.assertEqual(row["target"], "items")
        self.assertIn("Name-sort position", row["notes"])


STUB_HOST = """() => {
  const {el, columnList, detailPanel, detailSection, detailField, recordId,
    infoHelp, readonlyField, provenanceControl} = LexeditorUI;
  Object.assign(window, {el, columnList, detailPanel, detailSection, detailField,
    recordId, infoHelp, readonlyField, provenanceControl});
  window.LexStub = {el, columnList, detailPanel, detailSection, detailField,
    recordId, infoHelp, readonlyField, provenanceControl};
}"""


def test_sort_position_binds_across_categories(page):
    (ROOT / "plugins/ff7/details.js").read_text(encoding="utf-8")
    framework(page)
    page.evaluate(STUB_HOST)
    # details.js/controls.js are declaration-only at load; supply the host
    # globals the FF7 editor page normally provides, then load the modules.
    page.evaluate("""() => {
      window.__lexLoad = (sources) => {
        const script = document.createElement('script');
        script.textContent = `"use strict";
        {
          const {el, columnList, detailPanel, detailSection, detailField,
            recordId, infoHelp, readonlyField, provenanceControl} = window.LexStub;
          var state = window.__lexState;
          const labels = window.__lexLabels;
          const readonly = () => !!window.__lexReadonly;
          const render = () => {};
          const navigate = () => {};
          const shellRefresh = () => {};
          const category = () => window.__lexState.fakeCategory;
          const rowById = (group, id, source) =>
            (((source === undefined ? window.__lexState.records : source)[group]) || [])
              .find(r => r.id === id);
        ` + sources.join("\\n") + `
          window.__lexApi = {equipmentDetail, itemsDetail, nameSortRow};
        }`;
        document.head.append(script);
      };
    }""")
    page.evaluate("""() => {
      const fields = [];
      for (let i = 1; i <= 4; i++) {
        fields.push({key: `boostedStat${i}`, label: `Stat bonus ${i}`, minimum: 0, maximum: 255});
        fields.push({key: `boostedStat${i}Bonus`, label: `Bonus ${i}`, minimum: 0, maximum: 255});
      }
      for (let i = 1; i <= 8; i++)
        fields.push({key: `materiaSlot${i}`, label: `Slot ${i}`, minimum: 0, maximum: 7});
      fields.push({key: 'attackStrength', label: 'Attack', minimum: 0, maximum: 255});
      const values = {};
      for (const f of fields) values[f.key] = 1;
      values.name = 'Tiger Fang';
      const weapon = {id: 5, name: 'Tiger Fang', description: '', values: {...values}};
      window.__lexLabels = {weapons: 'Weapons', items: 'Items'};
      window.__lexReadonly = false;
      window.__lexState = {
        tab: 'weapons', invalid: {},
        records: {
          weapons: [weapon],
          itemSortOrder: [{id: 133, values: {position: 42}}],
        },
        data: {
          categories: [{id: 'itemSortOrder',
            fields: [{key: 'position', label: 'Name-sort position', minimum: 0, maximum: 65535}]}],
          vanilla: {
            weapons: [{id: 5, values: {...values}}],
            itemSortOrder: [{id: 133, values: {position: 42}}],
          },
        },
        fakeCategory: {fields, descriptionEditable: false},
      };
    }""")
    controls = (ROOT / "plugins/ff7/controls.js").read_text(encoding="utf-8")
    details = (ROOT / "plugins/ff7/details.js").read_text(encoding="utf-8")
    page.evaluate("(sources) => window.__lexLoad(sources)", [controls, details])
    panel = page.evaluate("""() => {
      const row = window.__lexState.records.weapons[0];
      const panel = window.__lexApi.equipmentDetail(row);
      document.querySelector('main').replaceChildren(panel);
      const sections = [...panel.querySelectorAll('.lex-detail-section-title')]
        .map(e => e.textContent.trim());
      const sort = panel.querySelector('[data-concept="item-name-sort"]');
      return {sections, hasSort: !!sort,
        input: sort ? sort.querySelector('input').value : null,
        help: sort ? sort.querySelector('.lex-info-help') !== null : false};
    }""")
    assert panel["sections"][0].startswith("MENU ORDERING"), panel["sections"]
    assert panel["input"] == "42", panel
    assert panel["help"], panel
    assert "STAT BONUSES" in panel["sections"]
    # Editing the property writes the shared executable sort table.
    page.locator('[data-concept="item-name-sort"] input').fill("43")
    assert page.evaluate("window.__lexState.records.itemSortOrder[0].values.position") == 43
    # Cleared input is repaired to the last valid value by the shared
    # detail-field machinery, like every other numeric property.
    page.evaluate("""() => {
      const input = document.querySelector('[data-concept="item-name-sort"] input');
      input.value = '';
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    assert page.evaluate(
        "document.querySelector('[data-concept=\"item-name-sort\"] input').value") == "43"
    assert page.evaluate("window.__lexState.records.itemSortOrder[0].values.position") == 43
    assert page.evaluate("window.__lexState.records.itemSortOrder[0].values.position") == 43
    # Vanilla revert restores the installed value.
    page.evaluate("""() => {
      const sort = document.querySelector('[data-concept="item-name-sort"]');
      sort.querySelector('.lex-source-control').lexRevert();
    }""")
    assert page.evaluate("window.__lexState.records.itemSortOrder[0].values.position") == 42


if __name__ == "__main__":
    unittest.main()
