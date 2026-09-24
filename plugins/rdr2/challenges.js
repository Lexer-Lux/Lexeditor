// ----- Challenges (goals_sp.meta) -----
function challengeUiInput(key,base,meta){const cur=state.challengeUiEdits[key]?.value??base;return el("input",{class:"key",value:cur,title:"Localization key, not literal English text. The displayed wording lives in localization resources.",onchange:ev=>{if(ev.target.value===base)delete state.challengeUiEdits[key];else state.challengeUiEdits[key]={...meta,value:ev.target.value};renderToolbarOnly();}});}
const CHALLENGE_XP_AMOUNTS={FIRST:25,SECOND:50,THIRD:100,FOURTH:150};
function challengeRewardLabel(reward){
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
        const activeSourceCount=req.sources.filter((source,sourceIndex)=>!state.challengeSourceEdits[`${goal.name}|${req.index}|${sourceIndex}`]?.remove).length;
        req.sources.forEach((source,sourceIndex)=>{const sk=`${goal.name}|${req.index}|${sourceIndex}`,edited=state.challengeSourceEdits[sk]||source;if(edited.remove)return;const current=`${edited.base||""}::${edited.permutation||""}`;
          const sel=el("select",{class:"key",onchange:ev=>{const [base,permutation]=ev.target.value.split("::");state.challengeSourceEdits[sk]={index:sourceIndex,base,permutation};renderChallenges();}},
            ...sourceValues.map(v=>{const value=`${v.base||""}::${v.permutation||""}`,label=v.label||[v.base,v.permutation].filter(Boolean).join(" + "),o=el("option",{value,title:value},label);if(value===current)o.selected=true;return o;}));
          const vsource=vreq?.sources?.[sourceIndex],controls=LexeditorUI.actionRow(sel);if(activeSourceCount>1&&!isRO())controls.append(closeButton({title:"Remove this counter from the summed requirement",onclick:()=>{state.challengeSourceEdits[sk]={index:sourceIndex,remove:true};renderChallenges();}}));sourceCell.append(LexeditorUI.stack({fill:false},controls,vsource&&current!==`${vsource.base||""}::${vsource.permutation||""}`?refLine([["V","vtag",vsource.label||[vsource.base,vsource.permutation].filter(Boolean).join(" + ")]],String):""));});
        const amount=LexeditorUI.stack({fill:false},el("input",{type:"number",step:"any",value:cur,class:ek in state.challengeEdits?"edited":"",onchange:ev=>{state.challengeEdits[ek]=ev.target.value;renderChallenges();}}));
        if(vreq&&Number(cur)!==Number(vreq.value)){const vr=el("span",{title:"Vanilla target — click to apply",onclick:()=>{state.challengeEdits[ek]=vreq.value;renderChallenges();}},el("b",{class:"vtag"},"V "),vreq.value);amount.append(el("div",{class:"ref"},vr));}
        conditionsBox.append(LexeditorUI.controlGroup([sourceCell,{label:"Target",control:amount}]));});
      for(const condition of goal.conditions||[]){const vg=vanillaGoal[goal.name],vc=vg?.conditions?.find(x=>x.index===condition.index),fields=LexeditorUI.stack({fill:false});
        for(const [field,base] of Object.entries(condition.fields)){const ck=`${goal.name}|${condition.index}|${field}`,cur=state.challengeConditionEdits[ck]?.value??base,known=conditionValues.find(x=>x.type===condition.type&&x.field===field)?.values||[],values=[...new Set([cur,...known])];
          const sel=el("select",{onchange:ev=>{if(ev.target.value===base)delete state.challengeConditionEdits[ck];else state.challengeConditionEdits[ck]={goal:goal.name,index:condition.index,type:condition.type,field,value:ev.target.value};renderToolbarOnly();}},...values.map(value=>{const o=el("option",{value},value);if(value===cur)o.selected=true;return o;}));
          fields.append(LexeditorUI.detailField({label:field,control:LexeditorUI.stack({fill:false},sel,refLine([["V","vtag",vc?.fields?.[field]]],String))}));
        }
        conditionsBox.append(LexeditorUI.detailSection({title:challengeConditionLabel(condition),body:fields}));
      }
    });
    const rewardKey=`${strand.name}|${rank.rank}`,rewards=state.challengeRewardEdits[rewardKey]??rank.rewards;
    const vrank=vanilla.challenges?.strands.find(s=>s.name===strand.name)?.ranks.find(r=>r.rank===rank.rank);
    const rewardBox=LexeditorUI.stack({fill:false});
    const rewardControl=(reward,editable)=>{
      const index=rewards.indexOf(reward),current=challengeRewardId(reward);
      const choices=allowedRewards.some(row=>challengeRewardId(row)===current)?allowedRewards:[reward,...allowedRewards];
      const select=el("select",{onchange:event=>{
        const [type,...parts]=event.target.value.split("::");
        mutateChallengeRewards(rewardKey,rank.rewards,next=>{next[index]={type,value:parts.join("::")};});renderChallenges();
      }},...choices.map(row=>{const value=challengeRewardId(row),option=el("option",{value},challengeRewardLabel(row));if(value===current)option.selected=true;return option;}));
      if(!editable)select.disabled=true;
      return LexeditorUI.actionRow(select,editable?closeButton({title:"Remove reward",onclick:()=>{
        mutateChallengeRewards(rewardKey,rank.rewards,next=>next.splice(index,1));renderChallenges();
      }}):el("span"));
    };
    const addReward=isRO()?"":newButton({title:"Add reward",onclick:()=>{
      const fallback=allowedRewards.find(row=>row.type==="CUnlockReward")||allowedRewards[0];
      if(fallback)mutateChallengeRewards(rewardKey,rank.rewards,next=>next.push({...fallback}));renderChallenges();
    }});
    rewardBox.append(multiValueReferences({
      kind:"challenge-rewards",current:rewards,references:vrank?[["V","vtag",vrank.rewards||[]]]:[],
      keyOf:challengeRewardId,sortKey:challengeRewardLabel,renderCurrent:reward=>rewardControl(reward,!isRO()),
      renderGhost:reward=>rewardControl(reward,false),emptyText:"no rewards",
    }));
    if(addReward)rewardBox.append(el("div",{class:"multi-ref-add"},addReward));
    const body=LexeditorUI.stack({fill:false},
      LexeditorUI.detailSection({title:"Strand",body:[challengeTextField("Name",strand.nameLabel),challengeTextField("Description",strand.descriptionLabel)]}),
      descriptions,LexeditorUI.detailSection({title:"Conditions",body:conditionsBox}),
      LexeditorUI.detailSection({title:"Rewards",body:rewardBox}));
    return LexeditorUI.detailPanel({title:`Rank ${rank.rank}`,identity:String(rank.rank),body});
  };
  m.append(LexeditorUI.pagedListDetail({rows:strand.ranks,key:rank=>rank.rank,selected:f.challengeRank,
    slots:false,page:0,pageSize:strand.ranks.length,splitKey:"rdr2-challenges",defaultSplit:35,
    master:({rows,selected,select})=>LexeditorUI.columnList({rows,key:rank=>rank.rank,selected,select,columns:[
      {key:"rank",label:"Rank",numeric:true,width:"4em"},{key:"name",label:"Challenge",render:rank=>localizedValue(rank.descriptionLabel)?.trim()||rank.descriptionLabel,
        sortValue:rank=>localizedValue(rank.descriptionLabel)?.trim()||rank.descriptionLabel}]}),
    detail:rankPanel,sync:next=>{f.challengeRank=next.selected;},change:next=>{f.challengeRank=next.selected;renderChallenges();}}));

}

async function saveChallenges() {
  if (isRO()) return;
  const keys=new Set([...Object.keys(state.challengeEdits), ...Object.keys(state.challengeSourceEdits).map(k=>k.split("|").slice(0,2).join("|"))]);
  const edits=[...keys].map(key=>{const cut=key.lastIndexOf("|"); const name=key.slice(0,cut), index=+key.slice(cut+1); const goal=refStore(state.ds).challenges.goals.find(g=>g.name===name); const req=goal.requirements.find(r=>r.index===index);
    return {name,index,value:state.challengeEdits[key] ?? req.value,sources:Object.entries(state.challengeSourceEdits).filter(([k])=>k.startsWith(key+"|")).map(([,v])=>v)};});
  const rewards=Object.entries(state.challengeRewardEdits).map(([key,list])=>{const cut=key.lastIndexOf("|"),challenge=key.slice(0,cut),rank=+key.slice(cut+1),strand=refStore(state.ds).challenges.strands.find(s=>s.name===challenge),rankRow=strand?.ranks.find(r=>r.rank===rank);return{challenge,rank,owner:rankRow?.owner,ownerRank:rankRow?.ownerRank,rewards:list};});
  const conditions=Object.values(state.challengeConditionEdits);
  const uiEdits=Object.values(state.challengeUiEdits);
  const modes=Object.entries(state.challengeModeEdits).map(([challenge,mode])=>({challenge,mode}));
  const localizedSaved=await saveLocalization();const r=await api("/api/challenges/save", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits,rewards,conditions,uiEdits,modes})});
  state.challengeEdits={}; state.challengeSourceEdits={};state.challengeConditionEdits={};state.challengeRewardEdits={};state.challengeUiEdits={};state.challengeModeEdits={}; refStore(state.ds).challenges=null; toast(`Saved ${r.saved} challenge + ${localizedSaved} in-game text field(s)`); renderChallenges();
}
