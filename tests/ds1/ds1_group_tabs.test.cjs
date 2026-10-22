// Item detail tabs come from groupFor in the DS1 editor: backend groups win,
// otherwise the field key decides. Covenant-usability flags are requirements,
// and backend-grouped tables never reach the key regexes.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

function groupFor() {
  const source = readFileSync(join(__dirname, '../../plugins/ds1/editor.js'), 'utf8');
  const head = source.indexOf('const GROUP_ORDER=');
  const start = source.indexOf('function groupFor(field,table){');
  assert.ok(head >= 0 && start > head, 'groupFor block not found');
  let depth = 0, end = -1;
  for (let i = source.indexOf('{', start); i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') depth--;
    if (depth === 0) { end = i + 1; break; }
  }
  assert.ok(end > start, 'groupFor end not found');
  const context = {};
  vm.runInNewContext(source.slice(head, end), context);
  return vm.runInNewContext('groupFor', context);
}

const tab = groupFor();

test('covenant-usability flags land on Requirements & costs', () => {
  assert.equal(tab({key: 'vowType1', group: ''}, 'EquipParamGoods'), 'Requirements & costs');
  assert.equal(tab({key: 'vowType9', group: ''}, 'Magic'), 'Requirements & costs');
  assert.equal(tab({key: 'vowType0', group: ''}, 'EquipParamGoods'), 'Requirements & costs');
});

test('backend-grouped tables keep their own tab', () => {
  assert.equal(tab({key: 'vowType', group: 'Starting kit'}, 'CharaInitParam'), 'Starting kit');
});

test('neighbour mappings are unchanged', () => {
  assert.equal(tab({key: 'properStrength', group: ''}, 'EquipParamWeapon'), 'Requirements & costs');
  assert.equal(tab({key: 'attackBasePhysics', group: ''}, 'EquipParamWeapon'), 'Combat');
  assert.equal(tab({key: 'trophySeqId', group: ''}, 'EquipParamWeapon'), 'Value & rewards');
  assert.equal(tab({key: 'description', group: 'Description'}, 'EquipParamGoods'), 'Description');
});
