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
const dollarValidation = items.slice(items.indexOf('function catalogDollarCents('), items.indexOf('function catalogMoneyInput('));
const draftValidation = items.slice(items.indexOf('function validateCatalogQuantityDrafts('), items.indexOf('function purchaseQuantityCell('));
const loot = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/loot.js'), 'utf8');
const lootValidation = loot.slice(loot.indexOf('function lootNumericError('), loot.indexOf('// Saves every dirty loot file.'));
const matrixValidation = loot.slice(loot.indexOf('function matrixQuantityError('), loot.indexOf('async function renderMatrix()'));
const crime = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/crime.js'), 'utf8');
const dispatchValidation = crime.slice(crime.indexOf('function bountyCompareNumbers('), crime.indexOf('function bountyNumber(')) +
  crime.slice(crime.indexOf('function dispatchNumericError('), crime.indexOf('function dispatchSection()'));
const challenges = fs.readFileSync(path.join(__dirname, '../../plugins/rdr2/challenges.js'), 'utf8');
const challengeValidation = challenges.slice(challenges.indexOf('function validateChallengeDrafts('), challenges.indexOf('function challengeUiInput('));
const challengeSave = challenges.slice(challenges.indexOf('async function saveChallenges()'));

async function challengeSaveGuards() {
  const data={goals:[{name:'GOAL',requirements:[{index:0,value:'10',sources:[
    {index:0,base:'BASE',permutation:'PERM',removal:{group:0,branch:0,count:2}},
    {index:1,base:'SECOND',permutation:'',removal:{group:0,branch:1,count:2}}]}],
    conditions:[{index:0,type:'CAIConditionGoalContext',fields:{ContextHash:'TRAIN'}}]}],
    allowedSourcePairs:[{base:'BASE',permutation:'PERM'},{base:'SECOND',permutation:''}],
    allowedConditionValues:[{type:'CAIConditionGoalContext',field:'ContextHash',values:['TRAIN','WATER']} ],
    strands:[{name:'ROOT',mode:'series',ranks:[{rank:1,rewardsReadonly:false,rewards:[{type:'CUnlockReward',value:'UNLOCK'}]}]}],
    allowedRewards:[{type:'CUnlockReward',value:'UNLOCK'},{type:'CUnlockReward',value:'SECOND_UNLOCK'},
      {type:'CAttributeReward',value:'CHALLENGE_REWARD_TYPE_MONEY_FIRST_RANK'}]};
  const source={index:0,base:'SECOND',permutation:''};
  const condition={goal:'GOAL',index:0,type:'CAIConditionGoalContext',field:'ContextHash',value:'WATER'};
  const cases=[
    ['unknown source pair',s=>s.challengeSourceEdits['GOAL|0|0']={...source,base:'UNKNOWN'}],
    ['source index mismatch',s=>s.challengeSourceEdits['GOAL|0|0']={...source,index:1}],
    ['source extra fields',s=>s.challengeSourceEdits['GOAL|0|0']={...source,extra:true}],
    ['non-text source',s=>s.challengeSourceEdits['GOAL|0|0']={...source,permutation:null}],
    ['unknown source index',s=>s.challengeSourceEdits['GOAL|0|2']={...source,index:2}],
    ['noncanonical source key',s=>s.challengeSourceEdits['GOAL|0|00']=source],
    ['readonly original source',s=>{s.store.mine.challenges.goals[0].requirements[0].sources[0].readonly=true;s.challengeSourceEdits['GOAL|0|0']=source;}],
    ['unknown original source',s=>{s.store.mine.challenges.goals[0].requirements[0].sources[0].base='UNKNOWN';s.challengeSourceEdits['GOAL|0|0']=source;}],
    ['readonly requirement',s=>{s.store.mine.challenges.goals[0].requirements[0].readonly=true;s.challengeSourceEdits['GOAL|0|0']=source;}],
    ['ambiguous goal',s=>{s.store.mine.challenges.goals.push(structuredClone(s.store.mine.challenges.goals[0]));s.challengeSourceEdits['GOAL|0|0']=source;}],
    ['remove every source',s=>{s.challengeSourceEdits={'GOAL|0|0':{index:0,remove:true},'GOAL|0|1':{index:1,remove:true}};}],
    ['unmodeled branch removal',s=>{s.store.mine.challenges.goals[0].requirements[0].sources[0].removal=null;s.challengeSourceEdits['GOAL|0|0']={index:0,remove:true};}],
    ['duplicate branch removal',s=>{s.store.mine.challenges.goals[0].requirements[0].sources[1].removal={group:0,branch:0,count:2};s.challengeSourceEdits={'GOAL|0|0':{index:0,remove:true},'GOAL|0|1':{index:1,remove:true}};}],
    ['edit removed branch',s=>{s.store.mine.challenges.goals[0].requirements[0].sources[1].removal={group:0,branch:0,count:2};s.challengeSourceEdits={'GOAL|0|0':{index:0,remove:true},'GOAL|0|1':{index:1,base:'BASE',permutation:'PERM'}};}],
    ['condition key mismatch',s=>s.challengeConditionEdits['GOAL|0|WrongField']=condition],
    ['condition fractional index',s=>s.challengeConditionEdits['GOAL|0.5|ContextHash']={...condition,index:0.5}],
    ['condition unknown type',s=>s.challengeConditionEdits['GOAL|0|ContextHash']={...condition,type:'Unknown'}],
    ['condition unknown value',s=>s.challengeConditionEdits['GOAL|0|ContextHash']={...condition,value:'UNKNOWN'}],
    ['condition non-text value',s=>s.challengeConditionEdits['GOAL|0|ContextHash']={...condition,value:1}],
    ['condition extra fields',s=>s.challengeConditionEdits['GOAL|0|ContextHash']={...condition,extra:true}],
    ['condition unknown original',s=>{s.store.mine.challenges.goals[0].conditions[0].fields.ContextHash='UNKNOWN';s.challengeConditionEdits['GOAL|0|ContextHash']=condition;}],
    ['condition ambiguous index',s=>{s.store.mine.challenges.goals[0].conditions.push(structuredClone(s.store.mine.challenges.goals[0].conditions[0]));s.challengeConditionEdits['GOAL|0|ContextHash']=condition;}],
    ['reward rank missing',s=>s.challengeRewardEdits['ROOT|2']=[]],
    ['reward rank noncanonical',s=>s.challengeRewardEdits['ROOT|01']=[]],
    ['reward collection readonly',s=>{s.store.mine.challenges.strands[0].ranks[0].rewardsReadonly=true;s.challengeRewardEdits['ROOT|1']=[];}],
    ['reward owner ambiguous',s=>{s.store.mine.challenges.strands.push(structuredClone(s.store.mine.challenges.strands[0]));s.challengeRewardEdits['ROOT|1']=[];}],
    ['reward unknown original',s=>{s.store.mine.challenges.strands[0].ranks[0].rewards[0].value='UNKNOWN';s.challengeRewardEdits['ROOT|1']=[];}],
    ['reward non-list draft',s=>s.challengeRewardEdits['ROOT|1']={}],
    ['reward null entry',s=>s.challengeRewardEdits['ROOT|1']=[null]],
    ['reward extra fields',s=>s.challengeRewardEdits['ROOT|1']=[{type:'CUnlockReward',value:'UNLOCK',extra:true}]],
    ['reward unknown choice',s=>s.challengeRewardEdits['ROOT|1']=[{type:'CUnlockReward',value:'UNKNOWN'}]],
    ['reward money disabled',s=>s.challengeRewardEdits['ROOT|1']=[{type:'CAttributeReward',value:'CHALLENGE_REWARD_TYPE_MONEY_FIRST_RANK'}]],
    ['parallel mode unsupported',s=>s.challengeModeEdits.ROOT='parallel'],
    ['unknown mode owner',s=>s.challengeModeEdits.UNKNOWN='series'],
  ];
  for(const [label,mutate] of cases){
    const calls=[],errors=[];
    const context=vm.createContext({structuredClone,isRO:()=>false,dirtyCount:()=>1,
      api:async()=>calls.push('api'),saveLocalization:async()=>calls.push('localization'),
      saveLoot:async()=>calls.push('loot'),saveLootSounds:async()=>calls.push('sounds'),
      showSaveFailure:error=>{errors.push(error.message);return error;},
      render(){},refreshGlobalSave(){},toast(){},rdr2Shell:{history:{clear(){}}}});
    vm.runInContext(stateSource+'\nfunction refStore(ds){return state.store[ds]||{}}\n'+integerValidation+'\n'+dollarValidation+'\n'+draftValidation+'\n'+lootValidation+'\n'+matrixValidation+'\n'+dispatchValidation+'\n'+challengeValidation+'\n'+globalSave+'\n'+catalogSave+'\n'+challengeSave,context);
    const st=vm.runInContext('state',context);
    st.ds='mine';st.catalog={items:[],effects:[]};st.store.mine={challenges:structuredClone(data)};st.store.vanilla={challenges:structuredClone(data)};
    st.alcoholEdits={CONSUMABLE_RUM:0.23};st.localizationEdits={LABEL:'pending text'};
    mutate(st);
    const drafts=()=>JSON.stringify([st.challengeSourceEdits,st.challengeConditionEdits,st.challengeRewardEdits,st.challengeModeEdits,st.alcoholEdits,st.localizationEdits]);
    const before=drafts();
    await assert.rejects(context.saveChallenges(),undefined,label+' must reject direct Save');
    await context.saveAllChanges();
    assert.equal(calls.length,0,label+' must block localization and unrelated global writers');
    assert.equal(errors.length,1,label+' must report the global failure');
    assert.equal(drafts(),before,label+' must retain every draft');
    // Prove valid replacements and single-source removal still pass preflight.
    st.store.mine={challenges:structuredClone(data)};
    st.challengeRewardEdits={'ROOT|1':[{type:'CUnlockReward',value:'SECOND_UNLOCK'}]};st.challengeModeEdits={ROOT:'series'};
    st.challengeSourceEdits={'GOAL|0|0':source};st.challengeConditionEdits={'GOAL|0|ContextHash':condition};
    context.validateChallengeDrafts();
    st.challengeSourceEdits={'GOAL|0|0':{index:0,remove:true}};
    st.challengeRewardEdits={'ROOT|1':[]};
    context.validateChallengeDrafts();
  }
  console.log(`PASS: ${cases.length} invalid challenge source/condition/reward/mode drafts block direct and global Save without losing edits`);
}
async function run(fail, invalid=false, invalidLoot=false, invalidMatrix=false, invalidDispatch=false, invalidCrime=false, invalidChallenge=false, rejectedChallenge=null) {
  const calls = [], messages = [], errors = [];
  let saved = { available: true, vanilla: {CONSUMABLE_RUM: 0.17, CONSUMABLE_MOONSHINE: 0.3}, overrides: {CONSUMABLE_MOONSHINE: 1} };
  const context = vm.createContext({
    console, structuredClone, isRO: () => false, dirtyCount: () => 1,
    saveLoot: async () => {if(rejectedChallenge)calls.push({url:'loot'});},
    saveLocalization: async () => {if(rejectedChallenge)calls.push({url:'localization'});return 0;},
    saveLootSounds: async () => {if(rejectedChallenge)calls.push({url:'sounds'});return 0;},
    render() {}, refreshGlobalSave() {},
    rdr2Shell: { history: { clear() {} } },
    toast: message => messages.push(message),
    showSaveFailure: error => { errors.push(error.message); return error; },
    api: async (url, opts) => {
      calls.push({url, body: opts?.body ? JSON.parse(opts.body) : null});
      if(url==='/api/challenges/validate'&&rejectedChallenge)throw new Error('ambiguous challenge XML');
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
  vm.runInContext(stateSource + '\nfunction refStore(ds){return state.store[ds]||{}}\n' + integerValidation + '\n' + dollarValidation + '\n' + draftValidation + '\n' + lootValidation + '\n' + matrixValidation + '\n' + dispatchValidation + '\n' + challengeValidation + '\n' + globalSave + '\n' + catalogSave, context);
  vm.runInContext("state.ds='mine';state.catalog={items:[],effects:[]};state.alcoholEdits={CONSUMABLE_RUM:0.23};", context);
  if(invalid)vm.runInContext("state.yieldEdits={'fixture': '1.5'}",context);
  if(invalidLoot)vm.runInContext("state.lootDirty={fixture:new Set(['T'])};state.loot={fixture:{tables:[{key:'T',entries:[{min:'1.5'}]}]}}",context);
  if(invalidMatrix)vm.runInContext("state.catalog.items=[{key:'ITEM'}];state.matrixDirty=new Set(['ANIMAL']);state.matrix={animals:[{key:'ANIMAL',rows:[{damage:'Poor',skin:'Perfect',item:'ITEM',qty:'1.5'}]}]}",context);
  if(invalidDispatch)vm.runInContext("state.store.mine={dispatch:{rows:[{group:'',field:'ParoleDuration',value:'9000'}]}};state.dispatchEdits={'|ParoleDuration':''}",context);
  if(invalidCrime)vm.runInContext("state.store.mine={crime:{crimes:[{key:'CRIME',NumWitnesses:'2'}]}};state.crimeEdits={'CRIME|NumWitnesses':'1.5'}",context);
  if(invalidChallenge)vm.runInContext("state.store.mine={challenges:{goals:[{name:'GOAL',requirements:[{index:0,value:'10',readonly:false}]}]}};state.challengeEdits={'GOAL|0':''}",context);
  if(rejectedChallenge){
    vm.runInContext("state.localizationEdits={LABEL:'pending text'};state.store.mine={challenges:{goals:[],strands:[{name:'ROOT',mode:'parallel',ranks:[]}]}}",context);
    if(rejectedChallenge==='label')vm.runInContext("state.challengeUiEdits={label:{file:'challenges.meta',owner:'ROOT',field:'challengeDescLabel',value:'new label'}}",context);
    if(rejectedChallenge==='mode')vm.runInContext("state.challengeModeEdits={ROOT:'series'}",context);
    if(rejectedChallenge==='condition')vm.runInContext("state.store.mine.challenges.goals=[{name:'GOAL',conditions:[{index:0,type:'CAIConditionGoalContext',fields:{ContextHash:'TRAIN'}}]}];state.store.mine.challenges.allowedConditionValues=[{type:'CAIConditionGoalContext',field:'ContextHash',values:['TRAIN','WATER']}];state.challengeConditionEdits={'GOAL|0|ContextHash':{goal:'GOAL',index:0,type:'CAIConditionGoalContext',field:'ContextHash',value:'WATER'}}",context);
  }
  const challengeSnapshot=vm.runInContext('JSON.stringify([state.challengeUiEdits,state.challengeModeEdits,state.challengeConditionEdits,state.localizationEdits])',context);
  await context.saveAllChanges();
  if(rejectedChallenge){
    assert.equal(calls.length,1,'server XML rejection must precede every writer');
    assert.equal(calls[0].url,'/api/challenges/validate');
    assert.equal(vm.runInContext('JSON.stringify([state.challengeUiEdits,state.challengeModeEdits,state.challengeConditionEdits,state.localizationEdits])',context),challengeSnapshot);
    assert.equal(vm.runInContext('state.alcoholEdits.CONSUMABLE_RUM',context),0.23);
    assert(errors.includes('ambiguous challenge XML'));
    assert(!messages.includes('All changes saved to mod files'));
    await assert.rejects(context.preflightChallengeSave(),/ambiguous challenge XML/);
    return;
  }
  if(invalid||invalidLoot||invalidMatrix||invalidDispatch||invalidCrime||invalidChallenge){
    assert.equal(calls.length,0,'invalid catalog drafts must block unrelated pending writers');
    assert.equal(vm.runInContext(invalidChallenge?"state.challengeEdits['GOAL|0']":invalidCrime?"state.crimeEdits['CRIME|NumWitnesses']":invalidDispatch?"state.dispatchEdits['|ParoleDuration']":invalidMatrix?"state.matrix.animals[0].rows[0].qty":invalidLoot?"state.loot.fixture.tables[0].entries[0].min":"state.yieldEdits.fixture",context),invalidDispatch||invalidChallenge?'':'1.5');
    assert.equal(vm.runInContext("state.alcoholEdits.CONSUMABLE_RUM",context),0.23);
    assert(errors.some(message=>message.includes(invalidCrime?'whole number':invalidDispatch||invalidChallenge?'finite number':'whole quantity')));
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
  await run(false,false,false,false,false,true); console.log('PASS: invalid crime drafts block unrelated pending writers');
  await run(false,false,false,false,false,false,true); console.log('PASS: invalid challenge drafts block unrelated pending writers');
  await challengeSaveGuards();
  for(const kind of ['label','mode','condition'])await run(false,false,false,false,false,false,false,kind);
  console.log('PASS: server label/mode/condition XML rejection blocks localization and every global writer');
})().catch(error => {console.error(error);process.exitCode = 1;});
