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
  };
  let finish;
  const loaded = new Promise(resolve => finish = resolve);
  let confirm = true;
  const ui = {el: node, clone: structuredClone, finishPluginLoading: finish,
    mountShell: () => ({refresh(){}})};
  for (const name of ['columnList','columnPreferences','detailPanel','detailSection','detailField','readonlyField','recordId','pagedListDetail','booleanMark','subtabBar','infoHelp','infoIcon'])
    ui[name] = (...args) => node(name, args[0]);
  const context = vm.createContext({LexeditorUI: ui, structuredClone,
    document: {querySelector: selector => targets[selector] ||= node('target', {})},
    window: {confirm: () => confirm, addEventListener: (event, fn) => listeners[event] = fn},
    fetch: async (path, request) => {
      calls.push([path, request?.method || 'GET']);
      assert.ok(!path.startsWith('/api/platform-config'), 'FF9 must not access the embedded Memoria settings API');
      if (request?.method === 'POST' && path === '/api/runtime/install')
        data['/api/runtime'] = {installed: true, version: 'fixture', pinned: 'v2025.07.04'};
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

test('Memoria subtab displays the requested message without settings controls', async () => {
  const e = await editor();
  e.run('navigate("tweaks")');
  const strip = e.targets['#toolbar'].children[0];
  assert.equal(strip.tag, 'subtabBar');
  assert.equal(strip.attrs.active, 'memoria');
  assert.equal(strip.attrs.tabs.length, 1);
  assert.equal(strip.attrs.tabs[0].label, 'Memoria');
  const card = e.targets['#main'].children[0];
  assert.equal(card.tag, 'section');
  assert.equal(card.children[0].tag, 'h2');
  assert.equal(card.children[1].tag, 'p');
  assert.equal(card.children[1].children[0], message);
  assert.equal(card.children.length, 2);
  assert.doesNotMatch(source, /platformConfigView|platformChanges|platform-config/);
});

test('startup, Tweaks, save and discard never request an INI editor', async () => {
  const e = await editor();
  e.run('navigate("tweaks")');
  e.listeners.focus();
  await e.run('save()');
  await e.run('discard()');
  assert.deepEqual(e.calls.map(call => call[0]), ['/api/dashboard','/api/datamap','/api/catalog']);
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

test('new character data views remain registered', async () => {
  const e = await editor();
  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','character-parameters','default-equipment','leveling']);
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
