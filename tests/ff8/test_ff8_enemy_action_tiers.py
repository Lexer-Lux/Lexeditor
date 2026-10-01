"""Enemy action tiers use the shared panel tabs and retain their selection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from test_shared_ui_feedback import ROOT, framework, page


def test_enemy_action_tiers_show_only_the_selected_table(page, tmp_path):
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    source = (ROOT / 'plugins/ff8/party.js').read_text(encoding='utf-8')
    panel = source[source.index('  function enemyActionsPanel('):source.index('  function enemyDetail(')]
    table = source[source.index('  function enemyAbilitiesSection('):source.index('  function enemyPairSection(')]
    page.add_script_tag(content='''
      const U=LexeditorUI,tabbedPanel=U.tabbedPanel,detailSection=U.detailSection,columnList=U.columnList;
      const state={data:{enemyTables:{choices:{abilityTypes:[]}}}};
      const row={name:'Test enemy',tables:{abilities:Object.fromEntries(
        ['low','medium','high'].map((tier,i)=>[tier,[{slot:0,type:0,abilityId:i,animation:0}]]))}};
      const selectControl=()=>U.el('select'),numberControl=value=>U.el('input',{type:'number',value,min:0,max:255});
      const enemyTableSource=control=>control,choiceName=()=>'';
      const enemyAbilityValueControl=(row,entry)=>U.el('span',{},'Ability '+entry.abilityId);
      function renderEnemies(){document.querySelector('main').replaceChildren(enemyActionsPanel(row))}
    ''' + table + panel)
    page.evaluate('renderEnemies()')
    assert page.locator('.enemy-ability-table').count() == 1
    assert 'Ability 0' in page.locator('.enemy-ability-table').inner_text()
    for label, ability in [('Medium', 1), ('High', 2), ('Low', 0)]:
        page.get_by_role('tab', name=label, exact=True).click()
        assert page.locator('.enemy-ability-table').count() == 1
        assert f'Ability {ability}' in page.locator('.enemy-ability-table').inner_text()
        page.evaluate('renderEnemies()')
        assert page.get_by_role('tab', name=label, exact=True).get_attribute('aria-selected') == 'true'
    page.screenshot(path=str(tmp_path / 'enemy-action-tiers.png'))
