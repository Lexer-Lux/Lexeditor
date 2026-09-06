'use strict';
// Execute the production global-save and catalog-save functions, not a copied implementation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../games/rdr2/editor.html'), 'utf8');
const stateSource = html.slice(html.indexOf('const state = {'), html.indexOf('\n};', html.indexOf('const state = {')) + 3);
const globalSave = html.slice(html.indexOf('async function saveAllChanges()'), html.indexOf('\nfunction savebar('));
const catalogSave = html.slice(html.indexOf('async function saveCatalog()'), html.indexOf('// ----- GameplayTweaks settings -----'));
async function run(fail) {
  const calls = [], messages = [], errors = [];
  let saved = { available: true, vanilla: {CONSUMABLE_RUM: 0.17, CONSUMABLE_MOONSHINE: 0.3}, overrides: {CONSUMABLE_MOONSHINE: 1} };
  const context = vm.createContext({
    console, structuredClone, isRO: () => false, dirtyCount: () => 1,
    saveLoot: async () => {}, saveLocalization: async () => 0,
    render() {}, refreshGlobalSave() {},
    rdr2Shell: { history: { clear() {} } },
    toast: message => messages.push(message),
    showSaveFailure: error => { errors.push(error.message); return error; },
    api: async (url, opts) => {
      calls.push({url, body: opts?.body ? JSON.parse(opts.body) : null});
      if (url === '/api/alcohol-strengths/save') {
        if (fail) throw new Error('read-only CSV fixture');
        Object.assign(saved.overrides, JSON.parse(opts.body).entries);
        return {saved: 1};
      }
      if (url === '/api/alcohol-strengths') return structuredClone(saved);
      if (url === '/api/catalog/save') return {saved: 0};
      throw new Error('Unexpected save endpoint: ' + url);
    }
  });
  vm.runInContext(stateSource + '\n' + globalSave + '\n' + catalogSave, context);
  vm.runInContext("state.ds='mine';state.catalog={items:[],effects:[]};state.alcoholEdits={CONSUMABLE_RUM:0.23};", context);
  await context.saveAllChanges();
  const posts = calls.filter(row => row.url === '/api/alcohol-strengths/save');
  assert.equal(posts.length, 1, 'header Save must dispatch alcohol-only edits');
  assert.deepEqual(posts[0].body, {entries: {CONSUMABLE_RUM: 0.23}}, 'never send unrelated drinks');
  const dirty = vm.runInContext('Object.keys(state.alcoholEdits).length', context);
  if (fail) {
    assert.equal(dirty, 1, 'failed edits must remain available to retry');
    assert(!messages.includes('All changes saved to mod files'), 'failure cannot display success');
    assert(errors.includes('read-only CSV fixture'));
    assert(!calls.some(row => row.url === '/api/catalog/save'), 'stop the remaining save after failure');
  } else {
    assert.equal(dirty, 0);
    assert.equal(saved.overrides.CONSUMABLE_MOONSHINE, 1);
    assert.equal(saved.overrides.CONSUMABLE_RUM, 0.23);
    assert(messages.includes('All changes saved to mod files'));
  }
}
(async () => {
  await run(false); console.log('PASS: header Save dispatches an alcohol-only sparse edit');
  await run(true); console.log('PASS: rejected alcohol save preserves edits and cannot report success');
})().catch(error => {console.error(error);process.exitCode = 1;});
