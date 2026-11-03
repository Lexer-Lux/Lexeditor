// Variable-length FF9 integer lists edit as one bounded box per entry.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../../plugins/ff9/editor.js'), 'utf8');

async function editor() {
  const listeners = {}, targets = {};
  const node = (tag, attrs, ...children) => ({tag, attrs, children,
    append(...values) { this.children.push(...values); },
    replaceChildren(...values) { this.children = values; }});
  const data = {
    '/api/dashboard': {game: {ready: true}, baseline: {}, project: {root: 'fixture'}, runtime: {installed: false},
      modCompatibility: {mods:[], unsupportedByPinnedMemoria:[], declaredConflicts:[], overlaps:[], projectScanTruncated:false}},
    '/api/catalog': {datasets: []}, '/api/datamap': {rows: []},
    '/api/runtime': {installed: false},
    '/api/mod-compat': {mods:[], unsupportedByPinnedMemoria:[], declaredConflicts:[], overlaps:[], projectScanTruncated:false},
    '/api/features': {features: {ImprovedInterface:false, BetterEat:false, XPBars:false, HPMPBars:false, RowRework:false}, sha256:'feature-fixture'},
    '/api/deployment': {deployed:false, runtimeReady:true, runtimeCurrent:false},
  };
  let finish;
  const loaded = new Promise(resolve => finish = resolve);
  const ui = {el: node, clone: structuredClone, finishPluginLoading: finish,
    callWindow: async () => { throw new Error('no desktop host in tests'); },
    mountShell: () => ({refresh(){}})};
  const carried = value => {
    if (!value || typeof value !== 'object') return [];
    if (Array.isArray(value)) return value.flatMap(carried);
    if ('tag' in value) return [value];
    return Object.values(value).flatMap(carried);
  };
  for (const name of ['columnList','detailPanel','detailSection','detailField','multiNumberRow','readonlyField','recordId','pagedListDetail','booleanMark','subtabBar','infoHelp','infoIcon','modLoaderSection','reshadeSection','pagerToggle','pagerSelect','showToast','notice','detailNote','detailText','loadingPanel','provenanceControl','statCard','choicePopover'])
    ui[name] = (...args) => node(name, args[0], ...carried(args[0]));
  ui.columnPreferences = () => ({pinButton:(key,label)=>node('pin',{key,label})});
  ui.tweaksPage = options => {
    const page = options.pages.find(entry => entry.id === options.active) || options.pages[0];
    return node('tweaksPage', options, ...[page.body()].flat());
  };
  ui.actionRow = (...args) => node('actionRow',{},...args);
  ui.confirmAction = async () => true;
  const context = vm.createContext({LexeditorUI: ui, structuredClone,
    document: {querySelector: selector => targets[selector] ||= node('target', {})},
    window: {confirm: () => true, addEventListener: (event, fn) => listeners[event] = fn},
    fetch: async path => ({ok: true, json: async () => structuredClone(data[path] || {})}),
  });
  vm.runInContext(source, context);
  await loaded;
  vm.runInContext('state.tab="info"', context);
  return {context, targets, run: code => vm.runInContext(code, context)};
}

const FIELD = `{key:'Items',label:'Items',kind:'list',itemKind:'integer',itemMin:0,itemMax:999,editable:true,declaredType:'Int32[]'}`;

function setup(e, initial) {
  e.run(`__row={line:1,id:0,name:'Shop',values:{Items:${JSON.stringify(initial)}}};__field=${FIELD};__view=listNumberControl({key:'shops'},__row,__field);`);
  return e.context.__view;
}

function find(root, match) {
  if (!root || typeof root !== 'object') return null;
  if (match(root)) return root;
  for (const child of root.children || []) {
    const hit = find(child, match);
    if (hit) return hit;
  }
  return null;
}

function findAll(root, match, hits = []) {
  if (!root || typeof root !== 'object') return hits;
  if (match(root)) hits.push(root);
  for (const child of root.children || []) findAll(child, match, hits);
  return hits;
}

test('one bounded number box per entry, stored as the same joined string', async () => {
  const e = await editor();
  const view = setup(e, '1, 2');
  const inputs = findAll(view, node => node.tag === 'input' && node.attrs.type === 'number');
  assert.equal(inputs.length, 2);
  assert.deepEqual(inputs.map(input => [input.attrs.min, input.attrs.max, input.attrs.step, input.attrs.value]),
    [[0, 999, 1, 1], [0, 999, 1, 2]]);
  inputs[0].attrs.oninput({target: {value: '5'}});
  assert.equal(e.run('__row.values.Items'), '5, 2');
});

test('blank input keeps the stored entry', async () => {
  const e = await editor();
  const view = setup(e, '1, 2');
  const inputs = findAll(view, node => node.tag === 'input' && node.attrs.type === 'number');
  inputs[1].attrs.oninput({target: {value: ''}});
  assert.equal(e.run('__row.values.Items'), '1, 2');
});

test('entries can be added and removed', async () => {
  const e = await editor();
  let view = setup(e, '1, 2');
  const remove = findAll(view, node => node.tag === 'button' && node.attrs.title.startsWith('Remove entry'));
  assert.equal(remove.length, 2);
  remove[0].attrs.onclick();
  assert.equal(e.run('__row.values.Items'), '2');
  view = setup(e, '1, 2');
  const add = find(view, node => node.tag === 'button' && node.attrs.title === 'Add an entry to this list');
  assert.ok(add, 'expected an add-entry button');
  add.attrs.onclick();
  assert.equal(e.run('__row.values.Items'), '1, 2, 0');
});

test('an empty list offers only the add button', async () => {
  const e = await editor();
  const view = setup(e, '');
  assert.equal(findAll(view, node => node.tag === 'input').length, 0);
  const add = find(view, node => node.tag === 'button' && node.attrs.title === 'Add an entry to this list');
  assert.ok(add, 'expected an add-entry button');
  add.attrs.onclick();
  assert.equal(e.run('__row.values.Items'), '0');
});

test('field wiring sends integer lists to boxes and token lists to text', async () => {
  const e = await editor();
  e.run(`__row={line:1,id:0,name:'Shop',values:{Items:'1, 2'}};__field=${FIELD};
    __data={key:'shops',fields:[__field],rows:[__row],originalByLine:{'1':{values:{Items:'1, 2'}}}};
    __panel=fieldControl(__data,__row,__field);`);
  assert.ok(find(e.context.__panel, node => node.tag === 'multiNumberRow'),
    'expected the integer list to render per-item boxes');
  e.run(`__tokens={key:'Tags',label:'Tags',kind:'list',itemKind:'token',editable:true,declaredType:'String[]'};
    __tokenRow={line:1,id:0,name:'Shop',values:{Tags:'a, b'}};
    __tokenData={key:'shops',fields:[__tokens],rows:[__tokenRow],originalByLine:{'1':{values:{Tags:'a, b'}}}};
    __tokenPanel=fieldControl(__tokenData,__tokenRow,__tokens);`);
  assert.equal(find(e.context.__tokenPanel, node => node.tag === 'multiNumberRow'), null);
  assert.ok(find(e.context.__tokenPanel, node => node.tag === 'input' && node.attrs.type === 'text'),
    'expected the token list to keep its free-text box');
});
