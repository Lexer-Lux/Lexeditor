// Functional controller tests with a stubbed shared UI, NOT visual acceptance.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../games/ff9/editor.html'), 'utf8').match(/<script>\s*"use strict";([\s\S]*?)<\/script>/)[1];
const message = "can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up";

async function editor() {
  const calls = [], listeners = {}, targets = {};
  const node = (tag, attrs, ...children) => ({tag, attrs, children,
    append(...values) { this.children.push(...values); },
    replaceChildren(...values) { this.children = values; }});
  const data = {
    '/api/dashboard': {game: {ready: true}, baseline: {}, project: {root: 'fixture'}, runtime: {installed: false}},
    '/api/catalog': {datasets: []}, '/api/datamap': {rows: []},
    '/api/runtime': {installed: false},
    '/api/features': {features: {ImprovedInterface:false, BetterEat:false, XPBars:false, HPMPBars:false, RowRework:false}, sha256:'feature-fixture'},
    '/api/deployment': {deployed:false, runtimeReady:true, runtimeCurrent:false},
  };
  let finish;
  const loaded = new Promise(resolve => finish = resolve);
  let confirm = true;
  const ui = {el: node, clone: structuredClone, finishPluginLoading: finish,
    // The editor asks the desktop host for its ReShade state; there is no host
    // here, so the call fails and the section falls back to its empty state,
    // which is exactly what the browser preview does.
    callWindow: async () => { throw new Error('no desktop host in tests'); },
    mountShell: () => ({refresh(){}})};
  // The shared components are stubbed as nodes that KEEP the controls handed
  // to them, so a test can still find a checkbox after the page moved from a
  // bespoke card to the shared settings panel. Dropping the arguments was why
  // reaching for a toggle broke on a purely presentational change.
  const carried = value => {
    if (!value || typeof value !== 'object') return [];
    if (Array.isArray(value)) return value.flatMap(carried);
    if ('tag' in value) return [value];
    return Object.values(value).flatMap(carried);
  };
  for (const name of ['columnList','columnPreferences','detailPanel','detailSection','detailField','readonlyField','recordId','pagedListDetail','booleanMark','subtabBar','infoHelp','infoIcon','modLoaderSection','reshadeSection','pagerToggle','pagerSelect','confirmAction','showToast'])
    ui[name] = (...args) => node(name, args[0], ...carried(args[0]));
  const context = vm.createContext({LexeditorUI: ui, structuredClone,
    document: {querySelector: selector => targets[selector] ||= node('target', {})},
    window: {confirm: () => confirm, addEventListener: (event, fn) => listeners[event] = fn},
    fetch: async (path, request) => {
      calls.push([path, request?.method || 'GET']);
      assert.ok(!path.startsWith('/api/platform-config'), 'FF9 must not access the embedded Memoria settings API');
      if (request?.method === 'POST' && path === '/api/runtime/install')
        data['/api/runtime'] = {installed: true, version: 'fixture', pinned: 'v2025.07.04'};
      if (request?.method === 'POST' && path === '/api/features/save') {
        const payload=JSON.parse(request.body); data['/api/features']={features:structuredClone(payload.features),sha256:'saved'};
        return {ok:true,json:async()=>structuredClone(data['/api/features'])};
      }
      if (request?.method === 'POST' && path === '/api/deployment/deploy') {
        data['/api/deployment']={deployed:true,runtimeReady:true,runtimeCurrent:true};
        return {ok:true,json:async()=>structuredClone(data['/api/deployment'])};
      }
      if (request?.method === 'POST' && path === '/api/deployment/revert') {
        data['/api/deployment']={deployed:false,runtimeReady:true,runtimeCurrent:false};
        return {ok:true,json:async()=>structuredClone(data['/api/deployment'])};
      }
      const payload = data[path];
      return {ok: true, json: async () => structuredClone(payload || {})};
    },
  });
  vm.runInContext(source, context);
  await loaded;
  vm.runInContext('state.tab="info"', context);
  return {context, calls, data, listeners, targets, run: code => vm.runInContext(code, context),
    cancel: () => confirm = false};
}

function dirtyRecord(e) {
  e.run('installData({key:"items",label:"Items",fields:[{key:"Value",editable:true}],rows:[{line:1,id:0,values:{Value:1}}]}); state.datasets.items.rows[0].values.Value=2');
}

test('Memoria subtab keeps launcher handoff while Lexeditor features are separate', async () => {
  const e = await editor();
  // Opening Tweaks reads the mod's ReShade state, so navigate is async now.
  await e.run('navigate("tweaks")');
  const strip = e.targets['#toolbar'].children[0];
  assert.equal(strip.tag, 'subtabBar');
  assert.equal(strip.attrs.active, 'memoria');
  assert.deepEqual(Array.from(strip.attrs.tabs.map(tab=>tab.label)), ['Memoria','Improved Interface','Better Eat','XP Bars','HP/MP Bars','Row Rework']);
  // The Memoria page says the settings live in Memoria's own launcher; how it
  // is laid out is the shared settings panel's business, so the assertion is
  // that the handoff is stated, not where in a tree it sits.
  const text = JSON.stringify(e.targets['#main']);
  assert.ok(text.includes('Memoria'), 'the Memoria handoff is not named');
  assert.ok(/launcher/i.test(text), 'the Memoria launcher handoff is not explained');
  assert.ok(!text.includes(message.slice(0, 40)),
    'the placeholder note should have become a real explanation');
  assert.doesNotMatch(source, /platformConfigView|platformChanges|platform-config/);
});

test('startup and project lifecycle use only Lexeditor-owned feature APIs', async () => {
  const e = await editor();
  e.run('navigate("tweaks")');
  e.listeners.focus();
  await e.run('save()');
  await e.run('discard()');
  const paths=e.calls.map(call=>call[0]);
  assert.deepEqual(paths.slice(0,5), ['/api/dashboard','/api/datamap','/api/catalog','/api/features','/api/deployment']);
  assert.ok(paths.every(path=>!path.startsWith('/api/platform-config')));
});

test('all five Lexeditor runtime toggles are project-owned and independently saveable', async () => {
  const e=await editor();
  for (const [tweak,key] of [['improved','ImprovedInterface'],['eat','BetterEat'],['xp','XPBars'],['hpmp','HPMPBars'],['row','RowRework']]) {
    e.run(`navigate("tweaks"); state.tweak="${tweak}"; tweaks()`);
    // Find the switch wherever the settings page puts it, rather than at a
    // fixed position in a markup shape that is allowed to change.
    const find=(root,match)=>{
      if(!root||typeof root!=='object')return null;
      if(match(root))return root;
      for(const child of root.children||[]){const hit=find(child,match);if(hit)return hit;}
      return null;
    };
    const toggle=find(e.targets['#main'],n=>n.attrs&&n.attrs.type==='checkbox');
    assert.ok(toggle,`no switch on the ${tweak} tweak page`);
    toggle.attrs.onchange({target:{checked:true}});
    assert.equal(e.run(`state.features.features.${key}`),true);
  }
  assert.equal(e.run('dirtyCount()'),5);
  await e.run('save()');
  assert.equal(e.run('state.savedFeatures.features.ImprovedInterface'),true);
  assert.equal(e.run('state.savedFeatures.features.BetterEat'),true);
  assert.equal(e.run('state.savedFeatures.features.XPBars'),true);
  assert.equal(e.run('state.savedFeatures.features.HPMPBars'),true);
  assert.equal(e.run('state.savedFeatures.features.RowRework'),true);
  assert.deepEqual(e.calls.filter(call=>call[1]==='POST').map(call=>call[0]), ['/api/features/save']);
});

test('install refreshes runtime status without opening the launcher automatically', async () => {
  const e = await editor();
  await e.run('runtimeAction("install")');
  assert.equal(e.run('state.dashboard.runtime.installed'), true);
  assert.deepEqual(e.calls.filter(call => call[1] === 'POST'), [['/api/runtime/install','POST']]);
});

test('cancelled install never posts', async () => {
  const e = await editor(); e.cancel();
  await e.run('runtimeAction("install")');
  assert.equal(e.calls.filter(call => call[1] === 'POST').length, 0);
});

test('Information settings action delegates to the existing launcher', async () => {
  const e = await editor();
  await e.run('runtimeAction("settings")');
  assert.deepEqual(e.calls.filter(call => call[1] === 'POST'), [['/api/runtime/settings','POST']]);
});

test('runtime changes are blocked while CSV edits are dirty', async () => {
  const e = await editor(); dirtyRecord(e);
  await e.run('runtimeAction("install")');
  assert.equal(e.calls.filter(call => call[1] === 'POST').length, 0);
  assert.match(e.run('state.runtimeError'), /Save or discard/);
});

test('runtime refresh never replaces unsaved CSV data', async () => {
  const e = await editor(); dirtyRecord(e);
  await e.run('refreshRuntime()');
  assert.equal(e.run('state.datasets.items.rows[0].values.Value'), 2);
  assert.equal(e.run('dirtyCount()'), 1);
});

test('information help describes launcher-first Play', async () => {
  const e = await editor(); e.run('info()');
  const description = JSON.stringify(e.targets['#main']);
  assert.match(description, /Play opens Memoria's launcher/);
  assert.doesNotMatch(description, /Play starts FF9 directly/);
});

test('catalog-driven views combine character implementation tables behind conceptual navigation', async () => {
  const e = await editor();
  e.run('state.catalog=[{key:"characters",tab:"characters"},{key:"character-parameters",tab:"characters"},{key:"default-equipment",tab:"characters"},{key:"leveling",tab:"characters"},{key:"world-weather",tab:"world"}]');
  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','leveling']);
  assert.deepEqual(Array.from(e.run('choices("world")')), ['world-weather']);
});

test('controller does not truncate fractional edits to an integer', async () => {
  const e = await editor();
  const field = e.run('fieldControl({}, {values:{Value:1}}, {key:"Value",label:"Value",kind:"integer",editable:true,min:0,max:255})');
  const input = field.attrs.control;
  assert.equal(input.attrs.type, 'number');
  assert.equal(input.attrs.min, 0); assert.equal(input.attrs.max, 255);
  e.run('globalThis.result=null; setValue=(d,r,f,v)=>globalThis.result=v');
  input.attrs.oninput({target:{value:'1.5'}});
  assert.equal(e.run('result'), 1.5);
});



test('FF9 uses shared multi-boolean properties and conceptual character/equipment views', async () => {
  const e = await editor();
  assert.match(source, /toggleRow/);
  assert.match(source, /ITEM_CATEGORY_FLAGS/);
  assert.match(source, /ITEM_PARTY_FLAGS/);
  assert.match(source, /renderCharacterComposite/);
  assert.match(source, /renderEquipmentComposite/);
  e.run('state.catalog=[{key:"characters",tab:"characters"},{key:"character-parameters",tab:"characters"},{key:"default-equipment",tab:"characters"},{key:"leveling",tab:"characters"}]');
  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','leveling']);
});
