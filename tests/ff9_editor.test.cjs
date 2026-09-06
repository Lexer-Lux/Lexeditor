// Functional controller tests with a stubbed shared UI, NOT visual acceptance.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../games/ff9/editor.html'), 'utf8').match(/<script>\s*"use strict";([\s\S]*?)<\/script>/)[1];

async function editor() {
  const calls = [], listeners = {}, targets = {};
  const node = (tag, attrs, ...children) => ({tag, attrs, children,
    append(...values) { this.children.push(...values); },
    replaceChildren(...values) { this.children = values; }});
  const absent = {available: false, sha256: '', sections: []};
  const installed = {available: true, sha256: 'installed', sections: [{fields: [{id: 'Control.TurboDialog', value: false}]}]};
  const data = {
    '/api/dashboard': {game: {ready: true}, baseline: {}, project: {root: 'fixture'}, runtime: {installed: false}},
    '/api/catalog': {datasets: []}, '/api/datamap': {rows: []},
    '/api/platform-config': absent, '/api/runtime': {installed: false},
  };
  let finish;
  const loaded = new Promise(resolve => finish = resolve);
  let confirm = true;
  const ui = {el: node, clone: structuredClone, finishPluginLoading: finish,
    mountShell: () => ({refresh(){}}), platformConfigView: arg => node('config', arg)};
  for (const name of ['columnList','columnPreferences','detailPanel','detailSection','detailField','readonlyField','recordId','pagedListDetail','booleanMark','subtabBar','infoHelp','infoIcon'])
    ui[name] = (...args) => node(name, args[0]);
  const context = vm.createContext({LexeditorUI: ui, structuredClone,
    document: {querySelector: selector => targets[selector] ||= node('target', {})},
    window: {confirm: () => confirm, addEventListener: (event, fn) => listeners[event] = fn},
    fetch: async (path, request) => {
      calls.push([path, request?.method || 'GET']);
      if (request?.method === 'POST' && path === '/api/runtime/install') {
        data['/api/platform-config'] = installed;
        data['/api/runtime'] = {installed: true, version: 'fixture', pinned: 'v2025.07.04'};
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

test('install refreshes previously absent configuration without opening launcher', async () => {
  const e = await editor();
  await e.run('runtimeAction("install")');
  assert.equal(e.run('state.platformConfig.available'), true);
  assert.equal(e.run('state.savedPlatformConfig.sha256'), 'installed');
  assert.equal(e.run('state.dashboard.runtime.installed'), true);
  assert.deepEqual(e.calls.filter(call => call[1] === 'POST'), [['/api/runtime/install','POST']]);
});

test('cancelled install never posts', async () => {
  const e = await editor(); e.cancel();
  await e.run('runtimeAction("install")');
  assert.equal(e.calls.filter(call => call[1] === 'POST').length, 0);
});

test('settings launcher requires its own explicit action', async () => {
  const e = await editor();
  await e.run('runtimeAction("settings")');
  assert.deepEqual(e.calls.filter(call => call[1] === 'POST'), [['/api/runtime/settings','POST']]);
});

test('runtime changes are blocked while settings are dirty', async () => {
  const e = await editor();
  e.run('state.platformConfig={sections:[{fields:[{id:"x",value:2}]}]}; state.savedPlatformConfig={sections:[{fields:[{id:"x",value:1}]}]}');
  await e.run('runtimeAction("install")');
  assert.equal(e.calls.filter(call => call[1] === 'POST').length, 0);
  assert.match(e.run('state.runtimeError'), /Save or discard/);
});

test('refresh never replaces unsaved settings', async () => {
  const e = await editor();
  e.run('state.platformConfig={sections:[{fields:[{id:"x",value:2}]}]}; state.savedPlatformConfig={sha256:"old",sections:[{fields:[{id:"x",value:1}]}]}');
  e.data['/api/platform-config'] = {sha256: 'new', sections: [{fields: [{id:'x',value:3}]}]};
  await e.run('refreshRuntime()');
  assert.equal(e.run('state.platformConfig.sections[0].fields[0].value'), 2);
  assert.equal(e.run('state.savedPlatformConfig.sha256'), 'old');
});

test('discard reloads externally changed configuration, not a stale snapshot', async () => {
  const e = await editor();
  e.data['/api/platform-config'] = {sha256: 'fresh', sections: []};
  await e.run('discard()');
  assert.equal(e.run('state.savedPlatformConfig.sha256'), 'fresh');
});

test('new character data views are registered', async () => {
  const e = await editor();
  assert.deepEqual(Array.from(e.run('choices("characters")')), ['characters','character-parameters','default-equipment','leveling']);
});

test('controller does not truncate fractional edits to an integer', async () => {
  const e = await editor();
  const field = e.run('fieldControl({}, {values:{Value:1}}, {key:"Value",label:"Value",kind:"integer",editable:true,min:0,max:255})');
  const input = field.attrs.control;
  assert.equal(input.attrs.type, 'number');
  assert.equal(input.attrs.min, 0); assert.equal(input.attrs.max, 255);
  // The API rejects a fraction; it must not silently become an allowed integer.
  e.run('globalThis.result=null; setValue=(d,r,f,v)=>globalThis.result=v');
  input.attrs.oninput({target:{value:'1.5'}});
  assert.equal(e.run('result'), 1.5);
});
