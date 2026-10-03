"""Protect unresolved weapon data and reject invalid saves before changing a tree."""
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_rdr2_issue_repairs import ProjectFixture, s


class WeaponScalarValidation(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.filename = 'weapons_mp.ymt'
        self.path = self.mine / self.filename
        self.path.write_text('''<Root><Item type="CWeaponInfo"><Name>WEAPON_TEST</Name>
          <Damage value="37"/><Enabled value="false"/>
          <UNK_MEMBER_0x12345678 value="7"/>
          <UNK_MEMBER_0x87654321><Damage value="99"/></UNK_MEMBER_0x87654321>
          <UNK_MEMBER_0x8E00F0C6 value="0.5"/>
        </Item></Root>''', encoding='utf-8')
        self.layers = patch.object(s, 'weapon_layer_files', return_value=[self.filename])
        self.layers.start()
        self.addCleanup(self.layers.stop)
        self.entry = s.load_file(self.filename)
        record = self.entry['root'].find('Item')
        self.rows = {row['field']: row for row in s._weapon_rows(record)}

    def edit(self, field, value):
        row = self.rows[field]
        return {'path': row['path'], 'kind': row['kind'], 'value': value}

    def apply(self, edits):
        return s.apply_weapon_edits('weapons', 'WEAPON_TEST', edits, self.filename)

    def test_unknown_fields_and_their_descendants_stay_protected(self):
        self.assertFalse(self.rows['UNK_MEMBER_0x12345678']['writable'])
        self.assertFalse(self.rows['UNK_MEMBER_0x87654321/Damage']['writable'])
        self.assertTrue(self.rows['DegradeOnTotalShots']['writable'])
        original = self.path.read_bytes()
        cached = ET.tostring(self.entry['root'])
        for field in ('UNK_MEMBER_0x12345678', 'UNK_MEMBER_0x87654321/Damage'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.apply([self.edit('Damage', '42'), self.edit(field, '0')])
            self.assertEqual(original, self.path.read_bytes())
            self.assertEqual(cached, ET.tostring(self.entry['root']))

    def test_invalid_numeric_boolean_and_paths_do_not_leak_into_later_saves(self):
        original = self.path.read_bytes()
        cached = ET.tostring(self.entry['root'])
        invalid = [self.edit('Damage', value) for value in ('NaN', 'Infinity', '1e400', 'oops', True)]
        invalid += [self.edit('Enabled', '2'), {'path': [-1], 'kind': 'attr', 'value': '2'}]
        for edit in invalid:
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                self.apply([self.edit('Damage', '42'), edit])
            self.assertEqual(original, self.path.read_bytes())
            self.assertEqual(cached, ET.tostring(self.entry['root']))
        self.assertEqual(2, self.apply([self.edit('Damage', '41.5'), self.edit('Enabled', True)]))
        disk = ET.parse(self.path).getroot()
        self.assertEqual('41.5', disk.find('./Item/Damage').get('value'))
        self.assertEqual('true', disk.find('./Item/Enabled').get('value'))
        self.assertEqual('7', disk.find('./Item/UNK_MEMBER_0x12345678').get('value'))
        s._files.clear()
        reopened = s.load_file(self.filename)['root']
        self.assertEqual(ET.tostring(disk), ET.tostring(reopened))


def test_weapon_boolean_and_protected_controls_render(tmp_path):
    from playwright.sync_api import sync_playwright

    repo = Path(__file__).resolve().parents[2]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 900, 'height': 620})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(repo / 'ui/framework.css'))
            page.add_script_tag(path=str(repo / 'ui/framework.js'))
            page.add_script_tag(content='const el=LexeditorUI.el; const isRO=()=>false;')
            page.add_script_tag(path=str(repo / 'plugins/rdr2/weapons.js'))
            page.evaluate('''()=>{
              const U=LexeditorUI;
              window.value='false';
              const boolean=weaponValueControl({},'weapons',{writable:true},value,false,v=>value=v);
              const unknown=weaponValueControl({},'weapons',{writable:false},'7',false,()=>{throw Error('Protected edit')});
              document.querySelector('main').append(U.detailPanel({title:'Weapon',body:[
                U.detailField({label:'Enabled',control:boolean}),
                U.detailField({label:'Unknown field',control:unknown})]}));
            }''')
            page.locator('input[type=checkbox]').check()
            assert page.evaluate('value') == 'true'
            unknown = page.locator('input.lex-readonly-field')
            assert unknown.input_value() == '7'
            assert unknown.is_disabled() and unknown.is_visible()
            page.screenshot(path=str(tmp_path / 'rdr2-weapon-controls.png'))
        finally:
            browser.close()
