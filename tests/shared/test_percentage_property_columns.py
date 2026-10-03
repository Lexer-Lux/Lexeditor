"""Columns adapt to readable names without changing the shared name percentage."""
import json
from test_shared_ui_feedback import framework, page


def test_percentage_columns_refit_without_clipping_or_losing_edits(page, tmp_path):
    page.set_viewport_size({'width':3000,'height':800})
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').style.height='700px';
      document.querySelector('main').append(U.settingsColumns(['One','Two','Three'].map(title=>
        U.detailPanel({title,body:['TEXT','Number','Attack power'].map(label=>U.detailField({
          label,help:U.infoHelp('Damage applied by this attack.'),control:U.el('input',{value:22})}))}))));
    }''')
    page.wait_for_timeout(250)
    control=page.locator('input').first
    control.fill('31')
    counts=[]
    for width in (3000,1000,3000):
        page.set_viewport_size({'width':width,'height':800})
        page.wait_for_timeout(250)
        counts.append(page.locator('.lex-tweak-card-grid > .lex-tweak-column').count())
        geometry=page.locator('.lex-detail-field').evaluate_all('''fields=>fields.map(field=>{
          const label=field.querySelector('.lex-detail-field-label'),name=label.firstElementChild;
          const range=document.createRange();range.selectNodeContents(name);
          return {field:field.getBoundingClientRect().toJSON(),label:label.getBoundingClientRect().toJSON(),
            ink:range.getBoundingClientRect().toJSON(),help:label.querySelector('.lex-info-help').getBoundingClientRect().toJSON(),
            font:parseFloat(getComputedStyle(label).fontSize)};
        })''')
        assert len(geometry)==9
        for row in geometry:
            assert row['field']['width']>0, geometry
            assert .07<=row['label']['width']/row['field']['width']<=.08, geometry
            assert row['ink']['right']<=row['help']['left']-3, geometry
            assert row['help']['right']<=row['label']['right']+1, geometry
            assert row['ink']['top']>=row['label']['top']-1, geometry
            assert row['ink']['bottom']<=row['label']['bottom']+1, geometry
            assert row['font']>=9 and row['field']['height']<80, geometry
        assert control.input_value()=='31'
        page.screenshot(path=str(tmp_path/f'columns-{width}.png'))
    assert counts[0]>counts[1] and counts[2]==counts[0], counts


def test_pane_minimum_preserves_percentage_and_complete_words(page, tmp_path):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').style.height='700px';
      document.querySelector('main').append(U.panelLayout([
        U.el('div',{},'Records'),U.detailPanel({title:'Selected record',body:[
          U.detailField({label:'Record key',control:U.el('input',{value:'FixtureCrop'})})]})
      ],{minSizes:[240,300],defaultSizes:[1,1]}));
    }''')
    for width in (1200,900,1200):
        page.set_viewport_size({'width':width,'height':800})
        page.wait_for_timeout(250)
        geometry=page.locator('.lex-detail-field').evaluate('''field=>{
          const label=field.querySelector('.lex-detail-field-label'),name=label.firstElementChild;
          const range=document.createRange();range.selectNodeContents(name);
          return {field:field.getBoundingClientRect().toJSON(),label:label.getBoundingClientRect().toJSON(),
            ink:range.getBoundingClientRect().toJSON(),font:getComputedStyle(label).font,
            nameFont:getComputedStyle(name).font,span:name.getBoundingClientRect().toJSON(),html:label.outerHTML};
        }''')
        assert .07<=geometry['label']['width']/geometry['field']['width']<=.08, geometry
        assert geometry['ink']['left']>=geometry['label']['left']-1, geometry
        assert geometry['ink']['right']<=geometry['label']['right']+1, json.dumps(geometry)
        assert geometry['ink']['bottom']<=geometry['label']['bottom']+1, geometry
        page.screenshot(path=str(tmp_path/f'pane-{width}.png'))
