'use strict';
// Execute the production global-save and catalog-save functions, not a copied implementation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = ['core.js','crafting.js','tweaks.js'].map(name=>fs.readFileSync(path.join(__dirname, '../../plugins/rdr2', name), 'utf8')).join('\n');
const stateSource = html.slice(html.indexOf('const state = {'), html.indexOf('\n};', html.indexOf('const state = {')) + 3);
const globalSave = html.slice(html.indexOf('async function saveAllChanges()'), html.indexOf('\nfunction savebar('));
const catalogSave = html.slice(html.indexOf('async function saveCatalog()'), html.indexOf('// ----- GameplayTweaks settings -----'));
const items = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/items.js'), 'utf8');
const integerValidation = items.slice(items.indexOf('function catalogQuantityIsValid('), items.indexOf('function catalogQuantityInput('));
const draftValidation = items.slice(items.indexOf('function validateCatalogQuantityDrafts('), items.indexOf('function purchaseQuantityCell('));
const loot = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/loot.js'), 'utf8');
const lootValidation = loot.slice(loot.indexOf('function lootNumericError('), loot.indexOf('// Saves every dirty loot file.'));
const matrixValidation = loot.slice(loot.indexOf('function matrixQuantityError('), loot.indexOf('async function renderMatrix()'));
const crime = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/crime.js'), 'utf8');
const dispatchValidation = crime.slice(crime.indexOf('function dispatchNumericError('), crime.indexOf('function dispatchSection()'));
async function run(fail, invalid=false, invalidLoot=false, invalidMatrix=false, invalidDispatch=false) {
  const calls = [], messages = [], errors = [];
  let saved = { available: true, vanilla: {CONSUMABLE_RUM: 0.17, CONSUMABLE_MOONSHINE: 0.3}, overrides: {CONSUMABLE_MOONSHINE: 1} };
  const context = vm.createContext({
    console, structuredClone, isRO: () => false, dirtyCount: () => 1,
    saveLoot: async () => {}, saveLocalization: async () => 0, saveLootSounds: async () => 0,
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
  vm.runInContext(stateSource + '\n' + integerValidation + '\n' + draftValidation + '\n' + lootValidation + '\n' + matrixValidation + '\n' + dispatchValidation + '\n' + globalSave + '\n' + catalogSave, context);
  vm.runInContext("state.ds='mine';state.catalog={items:[],effects:[]};state.alcoholEdits={CONSUMABLE_RUM:0.23};", context);
  if(invalid)vm.runInContext("state.yieldEdits={'fixture': '1.5'}",context);
  if(invalidLoot)vm.runInContext("state.lootDirty={fixture:new Set(['T'])};state.loot={fixture:{tables:[{key:'T',entries:[{min:'1.5'}]}]}}",context);
  if(invalidMatrix)vm.runInContext("state.catalog.items=[{key:'ITEM'}];state.matrixDirty=new Set(['ANIMAL']);state.matrix={animals:[{key:'ANIMAL',rows:[{damage:'Poor',skin:'Perfect',item:'ITEM',qty:'1.5'}]}]}",context);
  if(invalidDispatch)vm.runInContext("state.store.mine={dispatch:{rows:[{group:'',field:'ParoleDuration',value:'9000'}]}};state.dispatchEdits={'|ParoleDuration':''}",context);
  await context.saveAllChanges();
  if(invalid||invalidLoot||invalidMatrix||invalidDispatch){
    assert.equal(calls.length,0,'invalid catalog drafts must block unrelated pending writers');
    assert.equal(vm.runInContext(invalidDispatch?"state.dispatchEdits['|ParoleDuration']":invalidMatrix?"state.matrix.animals[0].rows[0].qty":invalidLoot?"state.loot.fixture.tables[0].entries[0].min":"state.yieldEdits.fixture",context),invalidDispatch?'':'1.5');
    assert.equal(vm.runInContext("state.alcoholEdits.CONSUMABLE_RUM",context),0.23);
    assert(errors.some(message=>message.includes(invalidDispatch?'finite number':'whole quantity')));
    assert(!messages.includes('All changes saved to mod files'));
    return;
  }
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
  await run(false,true); console.log('PASS: invalid catalog drafts block alcohol and all other writers');
  await run(false,false,true); console.log('PASS: invalid loot drafts block unrelated pending writers');
  await run(false,false,false,true); console.log('PASS: invalid skinning drafts block unrelated pending writers');
  await run(false,false,false,false,true); console.log('PASS: invalid dispatch drafts block unrelated pending writers');
})().catch(error => {console.error(error);process.exitCode = 1;});
