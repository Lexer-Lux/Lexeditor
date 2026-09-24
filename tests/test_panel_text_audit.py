"""Panel text audit: no clipped columns, no cropped descenders (F1/F10)."""
import base64

from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401  (pytest fixture)


AUDIT = (ROOT / "tests/panel_text_audit.js").read_text(encoding="utf-8")
FONT_B64 = base64.b64encode(
    (ROOT / "ui/assets/fonts/Lexend-Variable.ttf").read_bytes()).decode("ascii")


def lexend(page):
    # The shared fixture serves every URL as the page shell, so the face
    # arrives as a data URL instead of a routed request. Same bytes as the
    # shipped variable font, so canvas ink matches production rendering.
    framework(page)
    page.add_script_tag(content=AUDIT)
    page.evaluate("""(b64) => {
      const face = new FontFace('Lexend',
        `url(data:font/ttf;base64,${b64}) format('truetype-variations')`,
        {weight: '100 900'});
      document.fonts.add(face);
      face.load().then(() => { window.__lexFontReady = true; },
                       error => { window.__lexFontError = String(error); });
    }""", FONT_B64)
    page.wait_for_function(
        "window.__lexFontReady === true || window.__lexFontError !== undefined",
        timeout=15000)
    assert page.evaluate("window.__lexFontReady === true"), \
        page.evaluate("window.__lexFontError")


def test_descenders_fit_list_cells(page):
    lexend(page)
    page.evaluate("""() => {
      document.querySelector('main').append(LexeditorUI.columnList({
        // FF7's master list renders names as bare custom spans, not the
        // padded .lex-column-cell-text wrapper bare strings get. That is
        // the cell that sheared Tiger Fang's g's.
        columns: [{key: 'id', label: 'ID', numberedId: true},
                  {key: 'name', label: 'Name',
                   render: row => LexeditorUI.el('span', {title: row.name}, row.name)}],
        rows: [{id: 20, name: 'Tiger Fang'}, {id: 14, name: 'Ragnarok'},
               {id: 22, name: 'Dragon Claw'}, {id: 8, name: 'Mythril Claw'}],
      }));
    }""")
    assert page.evaluate("window.__lexPanelTextAudit(document)") == []


def test_stat_bonus_ids_fit_their_column(page):
    lexend(page)
    page.evaluate("""() => {
      const {el, columnList, detailPanel, detailSection, detailField,
        recordId, infoHelp, readonlyField, provenanceControl} = LexeditorUI;
      window.__lexStub = {el, columnList, detailPanel, detailSection, detailField,
        recordId, infoHelp, readonlyField, provenanceControl};
      window.__lexLoad = (sources) => {
        const script = document.createElement('script');
        script.textContent = `"use strict"; { const {el, columnList, detailPanel,
          detailSection, detailField, recordId, infoHelp, readonlyField,
          provenanceControl} = window.__lexStub;
          var state = window.__lexState;
          const labels = window.__lexLabels;
          const readonly = () => false;
          const render = () => {}; const navigate = () => {};
          const shellRefresh = () => {};
          const category = () => window.__lexState.fakeCategory;
          const rowById = (group, id, source) =>
            (((source === undefined ? window.__lexState.records : source)[group]) || [])
              .find(r => r.id === id);
        ` + sources.join("\\n") + `
          window.__lexApi = {equipmentDetail}; }`;
        document.head.append(script);
      };
    }""")
    controls = (ROOT / "plugins/ff7/controls.js").read_text(encoding="utf-8")
    details = (ROOT / "plugins/ff7/details.js").read_text(encoding="utf-8")
    page.evaluate("""() => {
      const fields = [];
      for (let i = 1; i <= 4; i++) {
        fields.push({key: `boostedStat${i}`, label: `Stat ${i}`,
          dataType: 'enum', choices: [{value: 0, label: 'None'}]});
        fields.push({key: `boostedStat${i}Bonus`, label: `Bonus ${i}`,
          minimum: 0, maximum: 255});
      }
      for (let i = 1; i <= 8; i++)
        fields.push({key: `materiaSlot${i}`, label: `Slot ${i}`,
          minimum: 0, maximum: 7});
      const values = {name: 'Bronze Bangle'};
      for (const f of fields) values[f.key] = 0;
      window.__lexLabels = {armor: 'Armor'};
      window.__lexState = {
        tab: 'armor', invalid: {},
        records: {armor: [{id: 0, name: 'Bronze Bangle', description: '', values}]},
        data: {categories: [], vanilla: {armor: [{id: 0, values: {...values}}]}},
        fakeCategory: {fields, descriptionEditable: false},
      };
    }""")
    page.evaluate("(sources) => window.__lexLoad(sources)", [controls, details])
    page.evaluate("""() => {
      // The real page renders the armor master first, whose whole-set floor
      // (ids 0..31) pads these slot numbers to #01..#04. Without the floor
      // the cells render unpadded and the test passes trivially.
      document.querySelector('main').append(LexeditorUI.columnList({
        columns: [{key: 'id', label: 'ID', numberedId: true}],
        rows: [{id: 31}],
        idFloor: 2,
      }));
      const row = window.__lexState.records.armor[0];
      document.querySelector('main').replaceChildren(
        window.__lexApi.equipmentDetail(row));
    }""")
    table = page.locator('[data-concept="equipment-stat-bonuses"]')
    assert table.count() == 1
    audit = page.evaluate(
        """(el) => window.__lexPanelTextAudit(el, ['.lex-numbered-id-cell'])""",
        table.element_handle())
    assert audit == [], audit


def test_audit_catches_a_narrow_id_column(page):
    lexend(page)
    page.evaluate("""() => {
      // Armor's whole-set id floor is 2 (ids 0..31), so the slot numbers
      // render padded (#01) and shear in the fixed 44px track. An unpadded
      // #1 would fit, which is why this control must set the floor.
      document.querySelector('main').append(LexeditorUI.columnList({
        template: '44px minmax(120px,1fr) minmax(90px,.8fr)',
        columns: [{key: 'key', label: '#', numberedId: true},
                  {key: 'stat', label: 'Stat'}, {key: 'amount', label: 'Amount'}],
        rows: [{key: 1, stat: 'Strength', amount: 0}],
        idFloor: 2,
      }));
    }""")
    audit = page.evaluate(
        "window.__lexPanelTextAudit(document, ['.lex-numbered-id-cell'])")
    assert any(finding["axis"] == "horizontal" for finding in audit), audit


def test_grow_columns_keep_declared_width_floor(page):
    # Grow tracks default to minmax(0, Nfr): a narrow panel crushes the
    # summary numbers instead of the name. A declared width floors them.
    framework(page)
    page.evaluate("""() => {
      const main = document.querySelector('main');
      main.style.width = '420px';
      main.append(LexeditorUI.columnList({
        columns: [{key: 'id', label: 'ID', numberedId: true},
                  {key: 'name', label: 'Name', grow: 2},
                  {key: 'foes', label: 'FOES', grow: .42,
                   width: 'minmax(80px,.42fr)'}],
        rows: [{id: 1, name: 'A very long formation name here', foes: 6}],
      }));
    }""")
    widths = page.evaluate("""() => {
      const row = document.querySelector('.lex-column-list-row');
      return [...row.children].map(
        cell => Math.round(cell.getBoundingClientRect().width));
    }""")
    assert widths[2] >= 80, widths


def test_ff7_summary_columns_declare_width_floors():
    source = (ROOT / "plugins/ff7/workspace.js").read_text(encoding="utf-8")
    assert 'width:"minmax(80px,.42fr)"' in source
    assert 'width:"minmax(80px,.48fr)"' in source

