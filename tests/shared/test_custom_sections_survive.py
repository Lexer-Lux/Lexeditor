"""Custom sections survive a rebuild when the shared page order is stale.

Lexer customized his AI records (custom Navigation section with the nav
flags, an empty spare section, field moves, one removed section), then
changed the master ROWS count and every custom section vanished. The
page-level section order is shared across record shapes, so it named
another shape's customs; this shape's customs never joined the pager's
cards, and the next deal dropped them from the page. The saved layout
below is his own ds1-ai.property-layout.179fdeb1, verbatim: seeding it
with a stale page order must still show both customs with their fields.
"""
import json

from test_shared_ui_feedback import framework, page  # noqa: F401
from test_tab_rename import mount_shell

LAYOUT_179FDEB1 = '{"Combat:0":["Combat:0/TeamAttackEffectivity:0","Effects & references:0/callHelp_ReplyBehaviorType:0"],"Effects & references:0":[],"Properties:0":["Properties:0/nearDist:0","Properties:0/midDist:0","Properties:0/farDist:0","Properties:0/outDist:0","Properties:0/BackHomeLife_OnHitEneWal:0","Properties:0/eye_dist:0","Properties:0/ear_dist:0","Properties:0/ear_soundcut_dist:0","Properties:0/nose_dist:0","Properties:0/maxBackhomeDist:0","Properties:0/backhomeDist:0","Properties:0/backhomeBattleDist:0","Properties:0/nonBattleActLife:0","Properties:0/BackHome_LookTargetTime:0","Properties:0/BackHome_LookTargetDist:0","Properties:0/SightTargetForgetTime:0","Properties:0/SoundTargetForgetTime:0","Properties:0/BattleStartDist:0","Properties:0/targetSys_DmgEffectRate:0","Properties:0/eye_angX:0","Properties:0/eye_angY:0","Properties:0/ear_angX:0","Properties:0/ear_angY:0","Properties:0/callHelp_CallValidMinDistTarget:0","Properties:0/callHelp_CallValidRange:0","Properties:0/callHelp_ForgetTimeByArrival:0","Properties:0/callHelp_MinWaitTime:0","Properties:0/callHelp_MaxWaitTime:0","Properties:0/goalAction_ToCaution:0","Properties:0/goalAction_ToFind:0","Properties:0/skipArrivalVisibleCheck:0","Properties:0/thinkAttr_doAdmirer:0"],"custom-mvbnseas:0":["Properties:0/disablePathMove:0","Properties:0/enableNaviFlg_Edge:0","Properties:0/enableNaviFlg_InSideWall:0","Properties:0/enableNaviFlg_Door:0","Properties:0/enableNaviFlg_Hole:0","Properties:0/enableNaviFlg_Ladder:0","Properties:0/enableNaviFlg_LargeSpace:0"],"custom-mvda79th:0":[],"hidden":[],"sections":[{"id":"custom-mvbnseas","title":"Navigation","after":"Properties:0"},{"id":"custom-mvda79th","title":"New section","after":"Properties:0"}],"removed":["Effects & references:0"],"order":["Combat:0","custom-mvda79th:0","custom-mvbnseas:0","Effects & references:0","Properties:0"]}'

HOMES = {
    'Combat': ['TeamAttackEffectivity'],
    'Properties': ['nearDist', 'midDist', 'farDist', 'outDist', 'BackHomeLife_OnHitEneWal',
                   'eye_dist', 'ear_dist', 'ear_soundcut_dist', 'nose_dist', 'maxBackhomeDist',
                   'backhomeDist', 'backhomeBattleDist', 'nonBattleActLife',
                   'BackHome_LookTargetTime', 'BackHome_LookTargetDist',
                   'SightTargetForgetTime', 'SoundTargetForgetTime', 'BattleStartDist',
                   'targetSys_DmgEffectRate', 'eye_angX', 'eye_angY', 'ear_angX', 'ear_angY',
                   'callHelp_CallValidMinDistTarget', 'callHelp_CallValidRange',
                   'callHelp_ForgetTimeByArrival', 'callHelp_MinWaitTime', 'callHelp_MaxWaitTime',
                   'goalAction_ToCaution', 'goalAction_ToFind', 'skipArrivalVisibleCheck',
                   'thinkAttr_doAdmirer', 'disablePathMove', 'enableNaviFlg_Edge',
                   'enableNaviFlg_InSideWall', 'enableNaviFlg_Door', 'enableNaviFlg_Hole',
                   'enableNaviFlg_Ladder', 'enableNaviFlg_LargeSpace'],
    'Effects & references': ['callHelp_ReplyBehaviorType'],
}

MOUNT = """() => {
  const U = LexeditorUI;
  const field = prop => U.detailField({label: prop, property: prop,
    control: U.el('input', {value: prop})});
  const homes = %s;
  document.querySelector('main').replaceChildren(U.detailPanel({title: 'Record',
    paginate: {unpaged: true},
    body: Object.entries(homes).map(([title, props]) =>
      U.detailSection({title, body: props.map(field)}))}));
}""" % json.dumps(HOMES)

# Another record shape's customs, as the shared page order held them: names,
# like the app stores, none matching this shape's custom-mvbnseas/mvda79th.
STALE_PAGE_ORDER = '["Combat", "custom-mvdaj59j", "custom-mvdadd4d", "Effects & references", "Properties"]'


def test_custom_sections_survive_a_stale_page_order(page):
    framework(page)
    mount_shell(page, True)
    page.evaluate('''() => {
      window.__seenKeys = [];
      const origGet = localStorage.getItem.bind(localStorage);
      localStorage.getItem = key => { window.__seenKeys.push(key); return origGet(key); };
    }''')
    page.evaluate(MOUNT)
    page.wait_for_timeout(200)
    seen = page.evaluate('window.__seenKeys')
    keys = [key for key in seen if '.property-layout.' in key]
    assert len(keys) == 1, seen
    page.evaluate('''([layoutKey, layout, orderKey, order]) => {
      localStorage.setItem(layoutKey, layout);
      localStorage.setItem(orderKey, order);
    }''', [keys[0], LAYOUT_179FDEB1, 'fixture-items.section-order', STALE_PAGE_ORDER])
    # A rebuild (record switch, ROWS change, reselect) re-applies the seeds.
    page.evaluate(MOUNT)
    page.wait_for_timeout(300)
    customs = page.locator('[data-lex-custom-section="true"]')
    assert customs.count() == 2, page.evaluate(
        "() => document.querySelector('.lex-tweaks-paged').lexCards().length")
    nav = page.locator('[data-lex-layout-section="custom-mvbnseas"]')
    assert nav.locator('.lex-detail-section-title-text').inner_text() == 'Navigation'
    assert nav.locator('.lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>n.dataset.lexLayoutField)') == [
        'disablePathMove', 'enableNaviFlg_Edge', 'enableNaviFlg_InSideWall', 'enableNaviFlg_Door',
        'enableNaviFlg_Hole', 'enableNaviFlg_Ladder', 'enableNaviFlg_LargeSpace']
    assert page.locator('[data-lex-layout-section="custom-mvda79th"] '
                        '.lex-detail-section-title-text').inner_text() == 'New section'
    # The rest of the layout applied too: emptied section removed from view,
    # moved field in its new home.
    assert page.locator('[data-lex-layout-section="Effects & references"]').evaluate(
        'n=>n.hidden') is True
    assert page.locator('[data-lex-layout-section="Combat"] .lex-detail-field').evaluate_all(
        'ns=>ns.map(n=>n.dataset.lexLayoutField)') == [
        'TeamAttackEffectivity', 'callHelp_ReplyBehaviorType']
