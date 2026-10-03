// ----- Challenges (goals_sp.meta) -----
function validateChallengeDrafts(){
  const data=refStore(state.ds).challenges,vanilla=refStore('vanilla').challenges||data;
  const goalFor=name=>{const matches=(data?.goals||[]).filter(goal=>goal.name===name);return matches.length===1?matches[0]:null;};
  const requirementFor=key=>{
    const cut=key.lastIndexOf('|'),name=key.slice(0,cut),rawIndex=key.slice(cut+1),index=Number(rawIndex);
    const requirements=(goalFor(name)?.requirements||[]).filter(req=>req.index===index);
    if(cut<1||!/^(?:0|[1-9]\d*)$/.test(rawIndex)||!Number.isSafeInteger(index)||requirements.length!==1||requirements[0].readonly||dispatchNumericError(requirements[0].value))throw new Error(`${key} is read-only or unavailable.`);
    return requirements[0];
  };
  const exactShape=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
  const sourcePairs=vanilla?.allowedSourcePairs||[];
  const knownSource=source=>sourcePairs.some(pair=>pair.base===(source.base||'')&&pair.permutation===(source.permutation||''));
  const removedBranches=new Map();
  for(const [key,value] of Object.entries(state.challengeEdits)){
    requirementFor(key);
    const error=dispatchNumericError(value);if(error)throw new Error(`${key}: ${error}`);
  }
  for(const [key,edit] of Object.entries(state.challengeSourceEdits)){
    const cut=key.lastIndexOf('|'),target=key.slice(0,cut),rawIndex=key.slice(cut+1),index=Number(rawIndex),req=requirementFor(target);
    const source=req.sources?.[index],remove=edit?.remove===true;
    if(cut<1||!/^(?:0|[1-9]\d*)$/.test(rawIndex)||!Number.isSafeInteger(index)||!source||source.readonly||!knownSource(source)||
       !exactShape(edit,remove?['index','remove']:['index','base','permutation'])||edit.index!==index||
       (!remove&&(typeof edit.base!=='string'||typeof edit.permutation!=='string'||!knownSource(edit))))throw new Error(`${key}: invalid or read-only challenge score source.`);
    if(remove){
      const meta=source.removal;
      if(!meta||![meta.group,meta.branch,meta.count].every(Number.isSafeInteger)||meta.group<0||meta.branch<0||meta.branch>=meta.count||meta.count<2)throw new Error(`${key}: unmodeled challenge score branch.`);
      const groupKey=`${target}|${meta.group}`,removed=removedBranches.get(groupKey)||{branches:new Set(),count:meta.count};
      if(removed.branches.has(meta.branch)||removed.count!==meta.count)throw new Error(`${key}: duplicate or ambiguous challenge score branch.`);
      const members=req.sources.filter(row=>row.removal?.group===meta.group&&row.removal?.branch===meta.branch);
      if(members.some(row=>row.readonly||!knownSource(row)))throw new Error(`${key}: read-only challenge score branch.`);
      removed.branches.add(meta.branch);removedBranches.set(groupKey,removed);
    }
  }
  for(const [key,removed] of removedBranches)if(removed.branches.size>=removed.count)throw new Error(`${key}: cannot remove every challenge score branch.`);
  for(const [key,edit] of Object.entries(state.challengeSourceEdits))if(!edit.remove){
    const cut=key.lastIndexOf('|'),target=key.slice(0,cut),source=requirementFor(target).sources[edit.index],meta=source.removal;
    if(meta&&removedBranches.get(`${target}|${meta.group}`)?.branches.has(meta.branch))throw new Error(`${key}: cannot edit a removed challenge score branch.`);
  }
  for(const [key,edit] of Object.entries(state.challengeConditionEdits)){
    if(!exactShape(edit,['goal','index','type','field','value'])||typeof edit.goal!=='string'||!Number.isSafeInteger(edit.index)||edit.index<0||
       typeof edit.type!=='string'||typeof edit.field!=='string'||typeof edit.value!=='string'||key!==`${edit.goal}|${edit.index}|${edit.field}`)throw new Error(`${key}: invalid challenge condition draft.`);
    const conditions=(goalFor(edit.goal)?.conditions||[]).filter(condition=>condition.index===edit.index),condition=conditions.length===1?conditions[0]:null;
    const known=vanilla?.allowedConditionValues?.find(row=>row.type===edit.type&&row.field===edit.field)?.values||[];
    if(!condition||condition.type!==edit.type||!Object.hasOwn(condition.fields,edit.field)||!known.includes(condition.fields[edit.field])||!known.includes(edit.value))throw new Error(`${key}: invalid or read-only challenge condition.`);
  }
  for(const [key,rewards] of Object.entries(state.challengeRewardEdits)){
    const cut=key.lastIndexOf('|'),name=key.slice(0,cut),rawRank=key.slice(cut+1),rank=Number(rawRank);
    const strands=(data?.strands||[]).filter(strand=>strand.name===name),ranks=strands.length===1?strands[0].ranks.filter(row=>row.rank===rank):[];
    const allowed=vanilla?.allowedRewards||[],known=reward=>allowed.some(row=>row.type===reward.type&&row.value===reward.value);
    if(cut<1||!/^[1-9]\d*$/.test(rawRank)||!Number.isSafeInteger(rank)||ranks.length!==1||ranks[0].rewardsReadonly||!ranks[0].rewards.every(known)||!Array.isArray(rewards))throw new Error(`${key}: read-only or unavailable challenge rewards.`);
    if(rewards.some(reward=>!exactShape(reward,['type','value'])||typeof reward.type!=='string'||typeof reward.value!=='string'||!known(reward)||reward.value.includes('CHALLENGE_REWARD_TYPE_MONEY_')))throw new Error(`${key}: invalid challenge reward draft.`);
  }
  for(const [name,mode] of Object.entries(state.challengeModeEdits)){
    if(mode!=='series'||(data?.strands||[]).filter(strand=>strand.name===name).length!==1)throw new Error(`${name}: unsupported challenge strand mode.`);
  }
}
function challengeRemovedBranch(req,source,key){
  const meta=source.removal;
  return !!meta&&req.sources.some((row,index)=>row.removal?.group===meta.group&&row.removal?.branch===meta.branch&&state.challengeSourceEdits[`${key}|${index}`]?.remove);
}
function challengeCanRemoveSource(req,index,key,known){
  const source=req.sources[index],meta=source.removal;
  if(!meta||meta.count<2||req.sources.findIndex(row=>row.removal?.group===meta.group&&row.removal?.branch===meta.branch)!==index)return false;
  const members=req.sources.filter(row=>row.removal?.group===meta.group&&row.removal?.branch===meta.branch);
  if(members.some(row=>row.readonly||!known.some(pair=>pair.base===(row.base||'')&&pair.permutation===(row.permutation||''))))return false;
  const removed=new Set(req.sources.filter(row=>row.removal?.group===meta.group&&challengeRemovedBranch(req,row,key)).map(row=>row.removal.branch));
  return removed.size+1<meta.count;
}
function challengeSaveBody(){
  const keys=new Set([...Object.keys(state.challengeEdits), ...Object.keys(state.challengeSourceEdits).map(key=>key.slice(0,key.lastIndexOf('|')))]);
  const edits=[...keys].map(key=>{const cut=key.lastIndexOf('|'),name=key.slice(0,cut),index=Number(key.slice(cut+1));
    const req=refStore(state.ds).challenges.goals.find(goal=>goal.name===name).requirements.find(row=>row.index===index);
    return {name,index,value:state.challengeEdits[key]??req.value,sources:Object.entries(state.challengeSourceEdits).filter(([sourceKey])=>sourceKey.slice(0,sourceKey.lastIndexOf('|'))===key).map(([,value])=>value)};});
  const rewards=Object.entries(state.challengeRewardEdits).map(([key,list])=>{const cut=key.lastIndexOf('|'),challenge=key.slice(0,cut),rank=Number(key.slice(cut+1));
    const rankRow=refStore(state.ds).challenges.strands.find(strand=>strand.name===challenge).ranks.find(row=>row.rank===rank);
    return {challenge,rank,owner:rankRow.owner,ownerRank:rankRow.ownerRank,rewards:list};});
  return {edits,rewards,conditions:Object.values(state.challengeConditionEdits),uiEdits:Object.values(state.challengeUiEdits),
    modes:Object.entries(state.challengeModeEdits).map(([challenge,mode])=>({challenge,mode}))};
}
async function preflightChallengeSave(){
  validateChallengeDrafts();
  const body=challengeSaveBody();
  if(Object.values(body).some(rows=>rows.length))await api('/api/challenges/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return body;
}
function challengeUiInput(key,base,meta){const cur=state.challengeUiEdits[key]?.value??base;return el("input",{class:"key",value:cur,title:"Localization key, not literal English text. The displayed wording lives in localization resources.",onchange:ev=>{if(ev.target.value===base)delete state.challengeUiEdits[key];else state.challengeUiEdits[key]={...meta,value:ev.target.value};renderToolbarOnly();}});}
const CHALLENGE_XP_AMOUNTS={FIRST:25,SECOND:50,THIRD:100,FOURTH:150};
function challengeRewardLabel(reward){
  if(!reward.value)return reward.type||'(empty reward)';
  const m=reward.value.match(/^CHALLENGE_REWARD_TYPE_XP_(HEALTH|STAMINA|DEADEYE)_(FIRST|SECOND|THIRD|FOURTH)_RANK$/);
  if(m)return `${m[1]==="DEADEYE"?"Dead Eye":m[1][0]+m[1].slice(1).toLowerCase()} XP +${CHALLENGE_XP_AMOUNTS[m[2]]}`;
  return reward.value.replace("CHALLENGE_REWARD_TYPE_","").replaceAll("_"," ");
}
function challengeRewardId(reward){return `${reward.type}::${reward.value}`;}
function challengeConditionLabel(c){
  const context={CHAL_CTX_ON_MOVING_TRAIN:"On a moving train",CHAL_CTX_SCOPED_KIT:"Using binoculars / scoped observation"};
  if(c.type==="CAIConditionGoalContext")return context[c.fields.ContextHash]||c.fields.ContextHash||"Required goal context";
  if(c.type==="CAIConditionIsOnMount")return "While mounted";
  if(c.type==="CAIConditionPlayerIsDeadeyeActive")return "While Dead Eye is active";
  if(c.type==="CAIConditionPedIsInVolume")return `Inside ${c.fields.VolumeName||"required region"}`;
  if(c.type==="CAIConditionIsInWater")return "While in water";
  if(c.type==="CAIConditionIsFollowingRoute")return "While following a route";
  if(c.type==="CAIConditionNot")return "NOT the nested condition below";
  if(c.type==="CAIConditionAnd")return "All nested conditions must be true";
  return c.type.replace("CAICondition","").replace(/([a-z])([A-Z])/g,"$1 $2");
}
function challengeLocalizationRef(key){
  return refLine([["V","vtag",state.localization?.vanilla?.[key]]],String,(value,ev)=>applyToInput(ev,value));
}
function challengeTextField(label,key){
  const input=localizationInput(key),vanilla=state.localization?.vanilla?.[key];
  return LexeditorUI.detailField({label,control:refField(input,vanilla===undefined?[]:[["V","vtag",vanilla]],input.value,
    value=>{input.value=value;input.dispatchEvent(new Event("change"));},String)});
}

function mutateChallengeRewards(rewardKey,baseRewards,mutation){
  const current=state.challengeRewardEdits[rewardKey]??baseRewards;
  const next=current.map(reward=>({...reward}));
  mutation(next);
  state.challengeRewardEdits[rewardKey]=next;
}

async function renderChallenges() {
  const current=renderScope("renderChallenges");
  const tb = $("#toolbar"); tb.innerHTML = "";
  if (!dsInfo().challenges) return noData(`This dataset has no goals_sp.meta yet (${dsInfo().dir}).`);
  const st = refStore(state.ds);
  if (!st.challenges) st.challenges = await api("/api/challenges");
  const vanilla=refStore("vanilla");
  if(state.ds==="mine"&&!vanilla.challenges)vanilla.challenges=await api("/api/challenges",undefined,"vanilla");
  if(!current())return;
  const f=state.filters;
  if(!f.challengeStrand||!st.challenges.strands.some(s=>s.key===f.challengeStrand))f.challengeStrand=st.challenges.strands[0]?.key;
  const strandTabs=LexeditorUI.subtabBar({tabs:st.challenges.strands.map(strand=>({id:strand.key,label:localizedValue(strand.nameLabel)?.trim()||strand.key})),
    active:f.challengeStrand,change:key=>{f.challengeStrand=key;f.challengeRank=null;renderChallenges();}});
  tb.append(strandTabs,savebar(saveChallenges));
  const m=$("#main");m.replaceChildren();
  const strand=st.challenges.strands.find(s=>s.key===f.challengeStrand);if(!strand)return;
  const goalByName=Object.fromEntries(st.challenges.goals.map(g=>[g.name,g]));
  const vanillaGoal=Object.fromEntries((vanilla.challenges?.goals||[]).map(g=>[g.name,g]));
  const sourceValues=vanilla.challenges?.allowedSourcePairs||st.challenges.allowedSourcePairs;
  const allowedRewards=(vanilla.challenges?.allowedRewards||st.challenges.allowedRewards).filter(r=>state.ds!=="mine"||!r.value.includes("CHALLENGE_REWARD_TYPE_MONEY_"));
  const conditionValues=vanilla.challenges?.allowedConditionValues||st.challenges.allowedConditionValues||[];
  const rankPanel=rank=>{const goals=rank.goals.map(n=>goalByName[n]).filter(Boolean);
    const descriptions=LexeditorUI.stack({fill:false},challengeTextField("Rank description",rank.descriptionLabel));
    const conditionsBox=LexeditorUI.stack({fill:false});
    goals.forEach(goal=>{descriptions.append(challengeTextField("Goal description",goal.description));
      goal.requirements.forEach(req=>{const ek=`${goal.name}|${req.index}`,cur=state.challengeEdits[ek]??req.value,vg=vanillaGoal[goal.name],vreq=vg?.requirements.find(x=>x.index===req.index);
        const sourceCell=LexeditorUI.stack({fill:false});
        const roleLabel=req.role==="exclusion"?"EXCLUSION GUARD — MUST NOT INCREASE":req.role==="condition"?"REQUIRED CONDITION / TRIGGER":req.role==="reset"?"RESET WINDOW / TIME LIMIT":"COUNTS TOWARD GOAL";
        sourceCell.append(el("div",{class:"cat",title:req.behavior||"Primary challenge counter"},roleLabel));
        if(!req.sources.length)sourceCell.append(el("span",{class:"cat"},"Derived condition (not a stat selector)"));
        req.sources.forEach((source,sourceIndex)=>{const sk=`${goal.name}|${req.index}|${sourceIndex}`,edited=state.challengeSourceEdits[sk]||source;if(edited.remove||challengeRemovedBranch(req,source,ek))return;const current=`${edited.base||""}::${edited.permutation||""}`;
          const supported=!req.readonly&&!dispatchNumericError(req.value)&&!source.readonly&&sourceValues.some(value=>(value.base||'')===(source.base||'')&&(value.permutation||'')===(source.permutation||''));
          if(!supported){const locked=LexeditorUI.readonlyField([source.base,source.permutation].filter(Boolean).join(' + ')||'(empty score source)');locked.setAttribute('aria-label',`${goal.name} score source ${sourceIndex}`);sourceCell.append(locked);return;}
          const sel=el("select",{class:"key",onchange:ev=>{const [base,permutation]=ev.target.value.split("::");state.challengeSourceEdits[sk]={index:sourceIndex,base,permutation};renderChallenges();}},
            ...sourceValues.map(v=>{const value=`${v.base||""}::${v.permutation||""}`,label=v.label||[v.base,v.permutation].filter(Boolean).join(" + "),o=el("option",{value,title:value},label);if(value===current)o.selected=true;return o;}));
          sel.disabled=isRO();
          sel.setAttribute('aria-label',`${goal.name} score source ${sourceIndex}`);
          const vsource=vreq?.sources?.[sourceIndex],controls=LexeditorUI.actionRow(sel);if(!isRO()&&challengeCanRemoveSource(req,sourceIndex,ek,sourceValues))controls.append(closeButton({title:"Remove this counter from the summed requirement",onclick:()=>{
            for(const [index,row] of req.sources.entries())if(row.removal?.group===source.removal.group&&row.removal?.branch===source.removal.branch)delete state.challengeSourceEdits[`${ek}|${index}`];
            state.challengeSourceEdits[sk]={index:sourceIndex,remove:true};renderChallenges();
          }}));sourceCell.append(LexeditorUI.stack({fill:false},controls,vsource&&current!==`${vsource.base||""}::${vsource.permutation||""}`?refLine([["V","vtag",vsource.label||[vsource.base,vsource.permutation].filter(Boolean).join(" + ")]],String):""));});
        const editable=!isRO()&&!req.readonly&&!dispatchNumericError(req.value);
        const target=dispatchNumericError(req.value)?LexeditorUI.readonlyField(req.value):el("input",{type:"number",step:"any",required:true,disabled:!editable,"data-lex-validate-number":"true",value:cur,class:ek in state.challengeEdits?"edited":"",oninput:ev=>{if(!editable)return;const value=ev.target.value;ev.target.setCustomValidity(dispatchNumericError(value));if(value===String(req.value))delete state.challengeEdits[ek];else state.challengeEdits[ek]=value;renderToolbarOnly();}});
        target.setAttribute('aria-label',`${goal.name} target ${req.index}`);
        const amount=LexeditorUI.stack({fill:false},target);
        if(vreq&&String(cur)!==String(vreq.value)){const vr=el("span",{title:"Vanilla target — click to apply",onclick:()=>{if(!editable)return;state.challengeEdits[ek]=vreq.value;renderChallenges();}},el("b",{class:"vtag"},"V "),vreq.value);amount.append(el("div",{class:"ref"},vr));}
        conditionsBox.append(LexeditorUI.controlGroup([sourceCell,{label:"Target",control:amount}]));});
      for(const condition of goal.conditions||[]){const vg=vanillaGoal[goal.name],vc=vg?.conditions?.find(x=>x.index===condition.index),fields=LexeditorUI.stack({fill:false});
        for(const [field,base] of Object.entries(condition.fields)){const ck=`${goal.name}|${condition.index}|${field}`,cur=state.challengeConditionEdits[ck]?.value??base,known=conditionValues.find(x=>x.type===condition.type&&x.field===field)?.values||[],values=[...new Set([cur,...known])];
          const sel=el("select",{onchange:ev=>{if(ev.target.value===base)delete state.challengeConditionEdits[ck];else state.challengeConditionEdits[ck]={goal:goal.name,index:condition.index,type:condition.type,field,value:ev.target.value};renderToolbarOnly();}},...values.map(value=>{const o=el("option",{value},value);if(value===cur)o.selected=true;return o;}));
          sel.disabled=isRO()||!known.includes(base);
          sel.setAttribute('aria-label',`${goal.name} condition ${condition.index} ${field}`);
          fields.append(LexeditorUI.detailField({label:field,control:LexeditorUI.stack({fill:false},sel,refLine([["V","vtag",vc?.fields?.[field]]],String))}));
        }
        conditionsBox.append(LexeditorUI.detailSection({title:challengeConditionLabel(condition),body:fields}));
      }
    });
    const rewardKey=`${strand.name}|${rank.rank}`,rewards=state.challengeRewardEdits[rewardKey]??rank.rewards;
    const rewardsEditable=!isRO()&&!rank.rewardsReadonly&&rank.rewards.every(reward=>(vanilla.challenges?.allowedRewards||st.challenges.allowedRewards).some(row=>challengeRewardId(row)===challengeRewardId(reward)));
    const vrank=vanilla.challenges?.strands.find(s=>s.name===strand.name)?.ranks.find(r=>r.rank===rank.rank);
    const rewardBox=LexeditorUI.stack({fill:false});
    const rewardControl=(reward,editable)=>{
      const index=rewards.indexOf(reward),current=challengeRewardId(reward);
      const choices=allowedRewards.some(row=>challengeRewardId(row)===current)?allowedRewards:[reward,...allowedRewards];
      const select=el("select",{onchange:event=>{
        const [type,...parts]=event.target.value.split("::");
        mutateChallengeRewards(rewardKey,rank.rewards,next=>{next[index]={type,value:parts.join("::")};});renderChallenges();
      }},...choices.map(row=>{const value=challengeRewardId(row),option=el("option",{value},challengeRewardLabel(row));if(value===current)option.selected=true;return option;}));
      select.setAttribute('aria-label',`${strand.name} rank ${rank.rank} reward ${index}`);
      if(!editable)select.disabled=true;
      return LexeditorUI.actionRow(select,editable?closeButton({title:"Remove reward",onclick:()=>{
        mutateChallengeRewards(rewardKey,rank.rewards,next=>next.splice(index,1));renderChallenges();
      }}):el("span"));
    };
    const addReward=!rewardsEditable?"":newButton({title:"Add reward",onclick:()=>{
      const fallback=allowedRewards.find(row=>row.type==="CUnlockReward")||allowedRewards[0];
      if(fallback)mutateChallengeRewards(rewardKey,rank.rewards,next=>next.push({...fallback}));renderChallenges();
    }});
    rewardBox.append(multiValueReferences({
      kind:"challenge-rewards",current:rewards,references:vrank?[["V","vtag",vrank.rewards||[]]]:[],
      keyOf:challengeRewardId,sortKey:challengeRewardLabel,renderCurrent:reward=>rewardControl(reward,rewardsEditable),
      renderGhost:reward=>rewardControl(reward,false),emptyText:"no rewards",
    }));
    if(addReward)rewardBox.append(el("div",{class:"multi-ref-add"},addReward));
    const body=LexeditorUI.stack({fill:false},
      LexeditorUI.detailSection({title:"Strand",body:[challengeTextField("Name",strand.nameLabel),challengeTextField("Description",strand.descriptionLabel)]}),
      descriptions,LexeditorUI.detailSection({title:"Conditions",body:conditionsBox}),
      LexeditorUI.detailSection({title:"Rewards",body:rewardBox}));
    return LexeditorUI.detailPanel({title:`Rank ${rank.rank}`,identity:String(rank.rank),body});
  };
  m.append(LexeditorUI.pagedListDetail({addDisabledReason:"Lexeditor edits the existing challenge ranks. Adding another rank and its progression rules is not supported yet.",rows:strand.ranks,key:rank=>rank.rank,selected:f.challengeRank,
    slots:false,page:0,pageSize:strand.ranks.length,splitKey:"rdr2-challenges",defaultSplit:35,
    master:({rows,selected,select})=>LexeditorUI.columnList({rows,key:rank=>rank.rank,selected,select,columns:[
      {key:"rank",label:"Rank",numeric:true,width:"4em"},{key:"name",label:"Challenge",render:rank=>localizedValue(rank.descriptionLabel)?.trim()||rank.descriptionLabel,
        sortValue:rank=>localizedValue(rank.descriptionLabel)?.trim()||rank.descriptionLabel}]}),
    detail:rankPanel,sync:next=>{f.challengeRank=next.selected;},change:next=>{f.challengeRank=next.selected;renderChallenges();}}));

}

async function saveChallenges() {
  if (isRO()) return;
  const body=await preflightChallengeSave();
  const localizedSaved=await saveLocalization();const r=await api("/api/challenges/save", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  state.challengeEdits={}; state.challengeSourceEdits={};state.challengeConditionEdits={};state.challengeRewardEdits={};state.challengeUiEdits={};state.challengeModeEdits={}; refStore(state.ds).challenges=null; toast(`Saved ${r.saved} challenge + ${localizedSaved} in-game text field(s)`); renderChallenges();
}
