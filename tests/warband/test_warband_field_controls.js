'use strict';
// The shared controls that turn a Module System expression into named choices.
// They run in the plugin's page, so this loads the same file with a stub UI.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const node=()=>({classList:{contains:()=>false}});
const context={window:{},Node:{ELEMENT_NODE:1},console,
  LexeditorUI:{el:node,detailField:node,detailSection:node,readonlyField:node,infoHelp:node,actionRow:node}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','..','plugins','warband','field_controls.js'),'utf8'),context);
const C=context.window.WarbandFieldControls;

const flags=[{name:'itp_merchandise',value:2,label:'merchandise'},
             {name:'itp_civilian',value:16,label:'civilian'},
             {name:'itp_unique',value:32,label:'unique'}];

// A flag box adds the name the project's header defines, and taking it off
// again returns the expression to exactly what it was.
let expression='itp_merchandise';
assert.equal(C.hasToken(expression,'itp_merchandise'),true);
assert.equal(C.hasToken(expression,'itp_civilian'),false);
expression=C.toggle(expression,flags,'itp_civilian',true);
assert.equal(expression,'itp_merchandise|itp_civilian');
assert.equal(C.hasToken(expression,'itp_civilian'),true);
expression=C.toggle(expression,flags,'itp_civilian',false);
assert.equal(expression,'itp_merchandise');
expression=C.toggle(expression,flags,'itp_merchandise',false);
assert.equal(expression,'0');
assert.equal(C.hasToken('0','itp_merchandise'),false);

// A value written as a number still reads as the named flags it stands for,
// and toggling it keeps every bit the flags do not cover.
assert.equal(C.hasToken('3','itp_merchandise'),false);
assert.equal((C.reduce('3',{itp_merchandise:2})&2)===2,true);
assert.equal(C.toggle('3',flags,'itp_merchandise',false),'1');
assert.equal(C.toggle('3',flags,'itp_unique',true),'itp_merchandise|itp_unique|1');
assert.equal(C.toggle('4',flags,'itp_merchandise',true),'itp_merchandise|4');

// An expression the flags do not own is never rewritten into something else.
assert.equal(C.toggle('sf_base_att_str|itp_merchandise',flags,'itp_civilian',true),
             'sf_base_att_str|itp_merchandise|itp_civilian');
assert.equal(C.toggle('imodbits_sword',flags,'itp_civilian',false),'(imodbits_sword) & ~itp_civilian');

// Stats are rows of name(number|number).
// The controls run inside the page's realm, so compare their plain data by
// value rather than by object identity.
const plain=value=>JSON.parse(JSON.stringify(value));
const calls=C.parseCalls('weight(1.5)|spd_rtng(97)|thrust_damage(26, 24)');
assert.deepEqual(plain(calls),[{name:'weight',args:['1.5']},{name:'spd_rtng',args:['97']},
                               {name:'thrust_damage',args:['26','24']}]);
assert.equal(C.callExpression(calls),'weight(1.5)|spd_rtng(97)|thrust_damage(26, 24)');
assert.equal(C.parseCalls('weight(1.5)+1'),null);

// Meshes are pairs of (name, flags), and the list round-trips.
const meshes=C.parseMeshes('[("fixture_sword", 0), ("other", 1)]');
assert.deepEqual(plain(meshes),[{name:'fixture_sword',flag:'0'},{name:'other',flag:'1'}]);
assert.equal(C.meshExpression(meshes),'[("fixture_sword", 0), ("other", 1)]');
assert.equal(C.parseMeshes('0'),null);
assert.equal(C.meshExpression([]),'[]');

console.log('Warband field controls passed: flags, numeric flags, unowned parts, stats, meshes.');
