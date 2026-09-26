// Functional controller tests with a stubbed shared UI, NOT visual acceptance.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../../plugins/ff9/editor.js'), 'utf8');
const message = "can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up";

async function editor() {
  const calls = [], listeners = {}, targets = {};
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
  let confirm = true;
  let shellOptions = null;
  const ui = {el: node, clone: structuredClone, finishPluginLoading: finish,
    // The editor asks the desktop host for its ReShade state; there is no host
    // here, so the call fails and the section falls back to its empty state,
    // which is exactly what the browser preview does.
    callWindow: async () => { throw new Error('no desktop host in tests'); },
    mountShell: options => { shellOptions = options; return {refresh(){}}; }};
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
  for (const name of ['columnList','detailPanel','detailSection','detailField','multiNumberRow','readonlyField','recordId','pagedListDetail','booleanMark','subtabBar','infoHelp','infoIcon','modLoaderSection','reshadeSection','pagerToggle','pagerSelect','showToast','notice','detailNote','detailText','provenanceControl','statCard','choicePopover'])
    ui[name] = (...args) => node(name, args[0], ...carried(args[0]));
  ui.columnPreferences = () => ({pinButton:(key,label)=>node('pin',{key,label})});
  ui.actionRow = (...args) => node('actionRow',{},...args);
  // Lexeditor asks its own questions now instead of calling window.confirm, so
  // the answer this test wants comes from the same flag it always did.
  ui.confirmAction = async () => confirm;
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
  return {context, calls, data, listeners, targets, shell: () => shellOptions, run: code => vm.runInContext(code, context),
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

test('information help describes launcher-first Play and read-only external mod audit', async () => {
  const e = await editor(); e.run('info()');
  const description = JSON.stringify(e.targets['#main']);
  assert.match(description, /Play opens Memoria's launcher/);
  assert.match(description, /EXTERNAL MOD COMPATIBILITY/);
  assert.match(description, /exact path/i);
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
  // Every editable property is wrapped in the shared provenance control, so
  // the reset can put the record's own value back; the box is inside it.
  const input = field.attrs.control.attrs.control;
  assert.equal(input.attrs.type, 'number');
  assert.equal(input.attrs.min, 0); assert.equal(input.attrs.max, 255);
  e.run('globalThis.result=null; setValue=(d,r,f,v)=>globalThis.result=v');
  input.attrs.oninput({target:{value:'1.5'}});
  assert.equal(e.run('result'), 1.5);
});

test('an editable property carries the value its record can be restored to', async () => {
  const e = await editor();
  e.run(`installData({key:"items",label:"Items",source:"project",
    fields:[{key:"Price",label:"Buy price",kind:"integer",editable:true,declaredType:"UInt32",min:0,max:4294967295}],
    rows:[{line:3,id:0,name:"Hammer",values:{Price:250}}],
    vanilla:{"3":{Price:250}}})`);
  const field = e.run('fieldControl(state.datasets.items,state.datasets.items.rows[0],state.datasets.items.fields[0])');
  const source = field.attrs.control;
  assert.equal(source.tag, 'provenanceControl');
  assert.equal(source.attrs.vanilla, 250);
  assert.equal(source.attrs.current(), 250);
  assert.equal(typeof source.attrs.apply, 'function');
  // A record whose own values are the loaded ones still resets to those.
  const plain = e.run(`installData({key:"shops",label:"Shop inventories",source:"baseline",
    fields:[{key:"Price",label:"Price",kind:"integer",editable:true,declaredType:"UInt32",min:0,max:4294967295}],
    rows:[{line:1,id:0,name:"Shop",values:{Price:7}}]});
    fieldControl(state.datasets.shops,state.datasets.shops.rows[0],state.datasets.shops.fields[0])`);
  assert.equal(plain.attrs.control.attrs.vanilla, 7);
});

test('the Items tab repeats no file name under the record', async () => {
  const e = await editor();
  e.run(`installData({key:"items",label:"Items",source:"project",
    fields:[{key:"Value",label:"Value",kind:"integer",editable:true,min:0,max:255}],
    rows:[{line:0,id:0,name:"Hammer",values:{Value:1}}]})`);
  const items = e.run('detail(state.datasets.items,state.datasets.items.rows[0])');
  assert.ok(!items.attrs.meta, 'the Items panel still repeats the file name');
  // Its sibling screens on the same tab keep the same treatment.
  e.run(`installData({key:"item-stats",label:"Equipment stats",source:"project",
    fields:[{key:"Strength",label:"Strength",kind:"integer",editable:true,min:0,max:255}],
    rows:[{line:0,id:0,name:"Bonus 1",values:{Strength:1}}]})`);
  const stats = e.run('detail(state.datasets["item-stats"],state.datasets["item-stats"].rows[0])');
  assert.ok(!stats.attrs.meta, 'the Equipment stats panel still repeats the file name');
});

test('a Tetra Master card reads as the game draws it', async () => {
  const e = await editor();
  e.run(`installData({key:"tetra-cards",label:"Tetra Master cards",source:"project",fields:[
    {key:"Id",label:"Id",kind:"integer",editable:false,declaredType:"Int32"},
    {key:"ATK(UP)",label:"ATK (UP)",kind:"integer",editable:true,declaredType:"UInt8",min:1,max:10},
    {key:"MDEF(RIGHT)",label:"MDEF (RIGHT)",kind:"integer",editable:true,declaredType:"UInt8",min:1,max:10},
    {key:"MATK(DOWN)",label:"MATK (DOWN)",kind:"integer",editable:true,declaredType:"UInt8",min:1,max:10},
    {key:"PDEF(LEFT)",label:"PDEF (LEFT)",kind:"integer",editable:true,declaredType:"UInt8",min:1,max:10},
    {key:"Icon",label:"Icon",kind:"enum",editable:true,declaredType:"String",choices:["MONSTER","SUMMON"]}
  ],rows:[{line:0,id:0,name:"Goblin",values:{Id:0,"ATK(UP)":2,"MDEF(RIGHT)":5,"MATK(DOWN)":1,"PDEF(LEFT)":3,Icon:"MONSTER"}}]})`);
  const card = e.run('detail(state.datasets["tetra-cards"],state.datasets["tetra-cards"].rows[0])');
  const find = (node, tag) => {
    if (!node || typeof node !== 'object') return null;
    if (node.tag === tag) return node;
    for (const child of node.children || []) {
      const hit = find(child, tag);
      if (hit) return hit;
    }
    return null;
  };
  const drawn = find(card, 'statCard');
  assert.ok(drawn, 'the card is not drawn on the shared card');
  // The four values in card order: attack up, defence left, defence right,
  // attack down - the same edges QuadMist draws them on.
  assert.deepEqual(Array.from(drawn.attrs.ranks.map(button => String(button.children[0]))), ['2', '3', '5', '1']);
  assert.equal(String(drawn.attrs.corner.children[0].children[0]), 'MONSTER');
  // The face is the game's own art, and the card stands beside its values.
  assert.equal(drawn.attrs.image, '/assets/cards/0.png');
  assert.equal(card.attrs.bodyLayout, 'beside');
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


test('semantic CSV controls and source identity stay truthful', async () => {
  const e=await editor();
  e.run(`installData({key:"actions",label:"Actions",source:"baseline",fields:[
    {key:"Id",label:"Id",kind:"integer",editable:false,declaredType:"Int32"},
    {key:"targets",label:"targets",kind:"enum",editable:true,declaredType:"UInt8",choices:["SingleEnemy(2)","ManyAny(3)"]},
    {key:"Offset",label:"Offset",kind:"fixed-list",editable:true,declaredType:"Vector3",length:3,itemKind:"number",vector3:true}
  ],rows:[{line:7,id:4,name:"Fire",values:{Id:4,targets:"SingleEnemy(2)",Offset:[1,2,3]}}]})`);
  const enumField=e.run('fieldControl(state.datasets.actions,state.datasets.actions.rows[0],state.datasets.actions.fields[1])');
  const vectorField=e.run('fieldControl(state.datasets.actions,state.datasets.actions.rows[0],state.datasets.actions.fields[2])');
  assert.ok(JSON.stringify(enumField).includes('SingleEnemy(2)'));
  assert.ok(JSON.stringify(vectorField).includes('multiNumberRow'));
  assert.deepEqual(Array.from(e.run('columnsFor(state.datasets.actions,"actions").map(column=>column.key)')),['id','name','targets','Offset']);

  e.run(`installData({key:"leveling",label:"Leveling",source:"baseline",fields:[
    {key:"Experience",label:"Experience",kind:"integer",editable:true,declaredType:"UInt32",min:0,max:4294967295}
  ],rows:[{line:7,id:1,name:"Level 1",values:{Experience:0}}]})`);
  assert.deepEqual(Array.from(e.run('columnsFor(state.datasets.leveling,"leveling").map(column=>column.key)')),['name','Experience']);
  const detailNode=e.run('detail(state.datasets.leveling,state.datasets.leveling.rows[0])');
  assert.ok(!JSON.stringify(detailNode).includes('recordId'));
});


test('Mod Loading explains real Memoria priority and format-specific overlap', async () => {
  const e = await editor();
  e.run('info()');
  const info = JSON.stringify(e.targets['#main']);
  assert.match(info, /highest-priority first/);
  assert.match(info, /CSV, battle raw16, and field-walkmesh BGI replacements are first-hit whole-file overrides/);
  assert.match(info, /patch files may compose low-to-high/);
  assert.match(info, /MergeScripts/);
  assert.doesNotMatch(info, /later one wins/);
});


test('field walkmesh detail labels BGI and exposes only the active bit as editable', async () => {
  const e = await editor();
  e.run(`state.datasets['field-walkmesh']={key:'field-walkmesh',label:'Field walkmesh floors',source:'vanilla/project',fields:[
    {key:'Field',label:'Field',kind:'stored',editable:false,declaredType:'Path'},
    {key:'Active',label:'Floor active',kind:'boolean',editable:true,declaredType:'Boolean'},
    {key:'OtherFlags',label:'Other flag bits',kind:'stored',editable:false,declaredType:'UInt16'}
  ],rows:[{line:0,name:'FBG_TEST · Floor 0',source:'project',values:{Field:'FBG_TEST',Active:true,OtherFlags:64}}]};`);
  const node=e.run(`detail(state.datasets['field-walkmesh'],state.datasets['field-walkmesh'].rows[0])`);
  const text=JSON.stringify(node);
  assert.doesNotMatch(text,/project BGI/);
  assert.match(text,/BGI_FLOOR_ACTIVE/);
  assert.match(text,/STORED DATA/);
});

test('field walkmesh triangle detail exposes documented pathing flags as editable', async () => {
  const e = await editor();
  e.run(`state.datasets['field-walkmesh-triangles']={key:'field-walkmesh-triangles',label:'Field walkmesh triangles',source:'vanilla/project',fields:[
    {key:'Field',label:'Field',kind:'stored',editable:false,declaredType:'Path'},
    {key:'Triangle',label:'Triangle',kind:'stored',editable:false,declaredType:'UInt16'},
    {key:'Floor',label:'Floor',kind:'stored',editable:false,declaredType:'Int16'},
    {key:'Active',label:'Triangle active',kind:'boolean',editable:true,declaredType:'Boolean'},
    {key:'AlternateFootstep',label:'Alternate footstep',kind:'boolean',editable:true,declaredType:'Boolean'},
    {key:'PreventNPC',label:'Prevent NPC pathing',kind:'boolean',editable:true,declaredType:'Boolean'},
    {key:'PreventPC',label:'Prevent PC pathing',kind:'boolean',editable:true,declaredType:'Boolean'},
    {key:'OtherFlags',label:'Other flag bits',kind:'stored',editable:false,declaredType:'UInt16'}
  ],rows:[{line:0,id:0,name:'Triangle 0',source:'project',values:{Field:'FBG_TEST',Triangle:0,Floor:2,Active:true,AlternateFootstep:true,PreventNPC:true,PreventPC:true,OtherFlags:32}}]};`);
  const node=e.run(`detail(state.datasets['field-walkmesh-triangles'],state.datasets['field-walkmesh-triangles'].rows[0])`);
  const text=JSON.stringify(node);
  assert.doesNotMatch(text,/project BGI/);
  assert.match(text,/BGI_TRI_ACTIVE/);
  assert.match(text,/Alternate footstep/);
  assert.match(text,/Prevent NPC pathing/);
  assert.match(text,/Prevent PC pathing/);
  assert.match(text,/STORED DATA/);
});

test('a record panel carries no file-format subtitle', async () => {
  const e = await editor();
  e.run('installData({key:"enemies",label:"Enemies",source:"vanilla",fields:[{key:"MaxHP",label:"Max HP",kind:"integer",editable:true,min:0,max:65535}],rows:[{line:0,id:"B3_001:0",name:"B3_001 · Enemy 1",values:{MaxHP:1234}}]})');
  const panel = e.run('detail(state.datasets.enemies,state.datasets.enemies.rows[0])');
  const rendered = JSON.stringify(panel);
  assert.ok(!panel.attrs.meta, 'the Enemies panel still names its file format');
  assert.doesNotMatch(rendered, /BattleScene raw16|vanilla CSV/);
});

test('enemy attack detail offers the verified target enum and keeps legacy bits stored', async () => {
  const e = await editor();
  e.run(`installData({key:"enemy-attacks",label:"Enemy attacks",source:"vanilla",fields:[
    {key:"Target",label:"Target",kind:"enum",editable:true,declaredType:"TargetType",choices:["SingleAny(0)","SingleAlly(1)","SingleEnemy(2)","ManyAny(3)","ManyAlly(4)","ManyEnemy(5)","All(6)","AllAlly(7)","AllEnemy(8)","Random(9)","RandomAlly(10)","RandomEnemy(11)","Everyone(12)","Self(13)","Automatic(14)","Special(15)"]},
    {key:"Power",label:"Power",kind:"integer",editable:true,declaredType:"B",min:0,max:255},
    {key:"LegacySfx",label:"Legacy sound bits",kind:"stored",editable:false,declaredType:"UInt32"}
  ],rows:[{line:0,id:"B3_002:0",name:"B3_002 · Attack 1",source:"vanilla",values:{Target:"SingleEnemy(2)",Power:80,LegacySfx:2748}}]})`);
  const panel = e.run('detail(state.datasets["enemy-attacks"],state.datasets["enemy-attacks"].rows[0])');
  const rendered = JSON.stringify(panel);
  assert.ok(!panel.attrs.meta);
  assert.match(rendered, /SingleEnemy\(2\)/);
  assert.match(rendered, /STORED DATA/);
  const target = e.run('fieldControl(state.datasets["enemy-attacks"],state.datasets["enemy-attacks"].rows[0],state.datasets["enemy-attacks"].fields[0])');
  // The enum's box sits inside the shared provenance control now.
  assert.equal(target.attrs.control.attrs.control.tag, 'select');
  assert.equal(target.attrs.control.attrs.control.children.length, 16);
});

test('battle scene flag detail exposes verified Memoria rules as editable toggles', async () => {
  const e = await editor();
  e.run(`installData({key:"scene-flags",label:"Battle scene flags",source:"vanilla",fields:[
    {key:"BackAttack",label:"Back attack",kind:"boolean",editable:true,declaredType:"Boolean"},
    {key:"OtherFlags",label:"Other flag bits",kind:"stored",editable:false,declaredType:"UInt16"}
  ],rows:[{line:0,id:"B3_002:0",name:"B3_002 · Scene 1",source:"vanilla",values:{BackAttack:true,OtherFlags:5}}]})`);
  const panel = e.run('detail(state.datasets["scene-flags"],state.datasets["scene-flags"].rows[0])');
  const rendered = JSON.stringify(panel);
  assert.ok(!panel.attrs.meta);
  assert.match(rendered, /SB2_FLG_BACKATK/);
  assert.match(rendered, /STORED DATA/);
  const toggle = e.run('fieldControl(state.datasets["scene-flags"],state.datasets["scene-flags"].rows[0],state.datasets["scene-flags"].fields[0])');
  assert.equal(toggle.attrs.control.attrs.control.attrs.type, 'checkbox');
});

test('battle dataset navigation covers attacks and scene flags', async () => {
  const e = await editor();
  e.run('state.catalog=[{key:"enemies",tab:"enemies"},{key:"enemy-attacks",tab:"enemies"},{key:"encounters",tab:"encounters"},{key:"scene-flags",tab:"encounters"}]');
  assert.deepEqual(Array.from(e.run('choices("enemies")')), ['enemies','enemy-attacks']);
  assert.deepEqual(Array.from(e.run('choices("encounters")')), ['encounters','scene-flags']);
});

test('FF9 shell carries the game-window theme with no bundled proprietary assets', async () => {
  const e = await editor();
  const plugin = e.shell().plugin;
  assert.equal(plugin.id, 'ff9');
  assert.equal(plugin.themeName, 'ff9');
  const theme = plugin.theme;
  for (const key of ['bg', 'panel', 'panel-2', 'border', 'text', 'muted',
                     'accent', 'accent-text', 'highlight', 'success',
                     'font', 'heading-font'])
    assert.ok(typeof theme[key] === 'string' && theme[key].length > 0, key);
  // Provenance boundary: the theme names faces, it never points at a file.
  // The faces are served privately from the player's install (game_font.py),
  // and each stack ends in a system font for when there is no install.
  for (const value of Object.values(theme))
    assert.doesNotMatch(value, /url\(|https?:|data:|\.ttf|\.woff|\.otf/i);
  assert.match(theme.font, /^"FF9 Menu",.*sans-serif$/);
  assert.match(theme['heading-font'], /^"FF9 Heading",.*sans-serif$/);
  // FF9 identity lock: the Gray Atlas window stone and the Blue Atlas bevel.
  assert.equal(theme.panel, '#575a59');
  assert.equal(theme.border, '#707878');
  assert.equal(theme.accent, '#4060b0');
  // The shell theme and the stylesheet tokens are one palette.
  const css = readFileSync(join(__dirname, '..', '..', 'plugins', 'ff9', 'editor.css'), 'utf8');
  for (const key of ['bg', 'panel', 'panel-2', 'border', 'text', 'muted', 'accent', 'font', 'heading-font'])
    assert.ok(css.includes(`--lex-${key}:${theme[key]};`), key);
});
