"""Scan details follow related edits, without rewriting untouched enemies."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from test_shared_ui_feedback import page,ROOT


def test_scan_updates_are_selective_and_idempotent(page):
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    functions=source[source.index('  const enemyScanElementNames='):source.index('  function enemyScanSection(')]
    page.add_script_tag(content='''
      const signature=JSON.stringify;
      const state={activeSource:'mine',data:{enemies:{rows:[{id:1,available:true,scanDescription:'Original description'},{id:2,available:true,scanDescription:''}]},enemyTables:{choices:{devour:[{id:0,name:'Recovery'}]},rows:[1,2].map(id=>({id,tables:{elementDefence:[{slot:0,percent:100}],devour:[{slot:0,devourId:0}]}}))}}};
      state.base={enemies:structuredClone(state.data.enemies.rows),enemyTables:structuredClone(state.data.enemyTables.rows)};
      function enemyTableRow(dataset,id){return dataset.enemyTables.rows.find(row=>row.id===id);}
    '''+functions)
    page.evaluate('syncEnemyScanDetails()')
    assert page.evaluate('state.data.enemies.rows[0].scanDescription')=='Original description'
    assert page.evaluate('state.data.enemies.rows[1].scanDescription')==''
    page.evaluate('state.data.enemyTables.rows[0].tables.elementDefence[0].percent=0;syncEnemyScanDetails()')
    description=page.evaluate('state.data.enemies.rows[0].scanDescription')
    assert description.startswith('Original description{NewPage}DETAILS')
    assert 'Immune: Fire' in description
    page.evaluate('syncEnemyScanDetails()')
    assert page.evaluate('state.data.enemies.rows[0].scanDescription')==description
    page.evaluate('state.data.enemyTables.rows[1].tables.elementDefence[0].percent=50;syncEnemyScanDetails();syncEnemyScanDetails()')
    assert page.evaluate('state.data.enemies.rows[1].scanDescription').count('DETAILS')==1
    page.evaluate("state.activeSource='vanilla';state.data.enemyTables.rows[0].tables.elementDefence[0].percent=200;syncEnemyScanDetails()")
    assert page.evaluate('state.data.enemies.rows[0].scanDescription')==description
