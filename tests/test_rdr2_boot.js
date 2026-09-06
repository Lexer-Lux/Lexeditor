'use strict';
// Execute the production boot/dataset code with deterministic API/render gates.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../games/rdr2/editor.html'),'utf8');
for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
const source=html.slice(html.indexOf('let datasetLoadVersion = 0;'),html.indexOf('\nfunction noData(msg)'));
assert(source.includes('async function boot()'));
const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
function fixture(){
 const calls=[],finishes=[],renders=[],pending=new Map(),nodes=new Map(),renderGate=deferred();
 const ds=(label)=>({label,dir:label,readonly:label!=='mine',catalog:true,lootFiles:[]});
 const config={datasets:{mine:ds('mine'),vanilla:ds('vanilla')}};
 const state={booting:true,ds:'mine',store:{},config:null,catalog:null};
 const ctx=vm.createContext({
  state,console,Promise,JSON,Object,LOOT_TAB_LABELS:{},
  LexeditorUI:{finishPluginLoading:()=>finishes.push({booting:state.booting,catalog:state.catalog})},
  document:{body:{classList:{toggle(){}}}},
  $:id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',append(){},replaceChildren(){},addEventListener(){}});return nodes.get(id);},
  el:()=>({}),rebuildTagMaps(){},
  dsInfo:()=>state.config.datasets[state.ds],isRO:()=>state.config.datasets[state.ds].readonly,
  api:(url,opts,id)=>{const key=url+'?'+id;calls.push(key);const d=deferred();pending.set(key,d);return d.promise;},
  render:async()=>{renders.push({booting:state.booting,catalog:state.catalog});await renderGate.promise;},
 });
 vm.runInContext(source,ctx);
 return{ctx,state,calls,finishes,renders,pending,renderGate,config};
}
const catalog=key=>({items:[{key}],effects:[{key:'EFFECT_'+key}]});
function baseResponses(f){
 f.pending.get('/api/config?mine').resolve(f.config);
 f.pending.get('/api/labels?mine').resolve({});
 f.pending.get('/api/alcohol-strengths?mine').resolve({available:true});
 f.pending.get('/api/custom-crafting?mine').resolve({custom:[]});
}
(async()=>{
 const f=fixture(),boot=f.ctx.boot();
 assert.equal(f.calls.length,5,'independent boot calls should start together');
 baseResponses(f);await tick();
 assert.equal(f.state.config,null,'do not publish partially loaded boot state');
 assert.equal(f.finishes.length,0);
 f.pending.get('/api/localization?mine').resolve({values:{}});await tick();
 assert(f.pending.has('/api/catalog?mine')&&f.pending.has('/api/quick-select?mine'));
 f.pending.get('/api/catalog?mine').resolve(catalog('MINE'));await tick();
 assert.equal(f.state.catalog,null);assert.equal(f.finishes.length,0);
 f.pending.get('/api/quick-select?mine').resolve({available:true});await tick();
 assert.equal(f.renders.length,1);assert.equal(f.renders[0].booting,false);
 assert.equal(f.finishes.length,0,'loading screen must wait for async rendering');
 f.renderGate.resolve();await boot;
 assert.equal(f.finishes.length,1);assert.equal(f.finishes[0].catalog.items[0].key,'MINE');
 console.log('PASS: required data and final render complete before loading-screen dismissal');

 const failed=fixture();const rejected=failed.ctx.boot();baseResponses(failed);
 const expected=new Error('localization failed');failed.pending.get('/api/localization?mine').reject(expected);
 await assert.rejects(rejected,/localization failed/);
 assert.equal(failed.state.loadError,expected);assert.equal(failed.state.booting,false);
 assert.equal(failed.state.config,null);assert.equal(failed.finishes.length,0);
 console.log('PASS: required API failure is surfaced without partially published state');

 const optional=fixture(),optionalBoot=optional.ctx.boot();
 optional.pending.get('/api/config?mine').resolve(optional.config);
 optional.pending.get('/api/labels?mine').resolve({});
 optional.pending.get('/api/localization?mine').resolve({values:{}});
 optional.pending.get('/api/alcohol-strengths?mine').reject(new Error('no runtime'));
 optional.pending.get('/api/custom-crafting?mine').reject(new Error('no recipes'));
 await tick();optional.pending.get('/api/catalog?mine').resolve(catalog('MINE'));
 optional.pending.get('/api/quick-select?mine').reject(new Error('no optional slots'));
 optional.renderGate.resolve();await optionalBoot;
 assert.equal(optional.state.alcohol.available,false);
 assert.equal(optional.state.alcohol.reason,'no runtime');
 assert.equal(optional.state.quickSelect.available,false);
 assert.equal(optional.finishes.length,1);
 console.log('PASS: optional runtime failures do not prevent standalone editor boot');

 const race=fixture();race.state.config=race.config;race.state.booting=false;race.renderGate.resolve();
 const first=race.ctx.switchDataset('mine'),second=race.ctx.switchDataset('vanilla');
 race.pending.get('/api/catalog?vanilla').resolve(catalog('REFERENCE'));
 race.pending.get('/api/quick-select?vanilla').resolve({});await second;
 race.pending.get('/api/catalog?mine').resolve(catalog('STALE'));
 race.pending.get('/api/quick-select?mine').resolve({});await first;
 assert.equal(race.state.ds,'vanilla');assert.equal(race.state.catalog.items[0].key,'REFERENCE');
 assert.equal(race.state.store.mine.catalog.items[0].key,'STALE');
 assert.equal(race.renders.length,1);
 console.log('PASS: late dataset responses cannot replace the latest selected dataset');
})().catch(error=>{console.error(error);process.exitCode=1;});
