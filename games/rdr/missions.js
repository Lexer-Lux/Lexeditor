"use strict";
  const MISSION_REWARDS=[
    {key:"cash",label:"Cash reward",help:"Changes the cash awarded when this mission completes; it does not alter prices, pickups, or other missions."},
    {key:"fame",label:"Fame reward",help:"Changes this mission's completion Fame award independently of its cash and Honor rewards."},
    {key:"honor",label:"Honor reward",help:"Changes this mission's completion Honor adjustment independently of its cash and Fame rewards."}
  ];
  function missionArea(mission){return String(mission.assetPath||"").split("/")[2]||"Unknown";}
  function matchingMissions(){const needle=state.missionQuery.trim().toLowerCase();return (state.missions?.missions||[]).filter(mission=>(!needle||[mission.id,mission.name,mission.scriptName,mission.localizationKey,mission.assetPath].some(value=>String(value||"").toLowerCase().includes(needle)))&&(!state.missionArea||missionArea(mission)===state.missionArea));}
  function missionValue(mission,reward){const key=`${mission.id}|${reward}`;return Object.prototype.hasOwnProperty.call(state.missionEdits,key)?state.missionEdits[key]:String(mission.rewards[reward]);}
  function editMission(mission,reward,value){const key=`${mission.id}|${reward}`;if(value===String(mission.rewards[reward]))delete state.missionEdits[key];else state.missionEdits[key]=value;shell.refresh();}
  function selectMission(mission){state.missionSelected=mission.id;renderMissions();}
  const MISSION_COLUMNS=[
    {key:"script",label:"ID / Script",width:"minmax(0,1.15fr)",render:mission=>cell(`#${mission.id} · ${mission.scriptName}`)},
    {key:"name",label:"Mission",width:"minmax(0,1.25fr)",render:mission=>cell(mission.name)},
    {key:"area",label:"Area",width:"minmax(0,.7fr)",render:mission=>cell(missionArea(mission))},
    {key:"rewards",label:"Cash / Fame / Honor",width:"minmax(0,.9fr)",render:mission=>cell(`$${mission.rewards.cash} / F${mission.rewards.fame} / H${mission.rewards.honor}`)}];
  function missionDetail(){
    const mission=(state.missions?.missions||[]).find(row=>row.id===state.missionSelected);
    if(!mission)return LexeditorUI.detailPanel({className:"record-detail mission-detail",title:"No mission selected"});
    const limits=state.missions.limits;
    return LexeditorUI.detailPanel({className:"record-detail mission-detail",title:mission.name,actions:projectBadge(mission),body:[
      detailField("Mission ID",shown(String(mission.id))),detailField("Script",shown(mission.scriptName)),detailField("Area",shown(missionArea(mission))),
      detailField("Localization key",shown(mission.localizationKey)),detailField("Archive path",shown(mission.archivePath)),
      detailField("Reward evidence",shown(`${mission.rewardSource.function} / ${mission.rewardSource.case}`)),
      LexeditorUI.notice({title:"The extracted mission table stays read-only.",message:"Save writes only cash, fame, or honor values that differ from the base into LexerRDR.missions.json."}),
      ...MISSION_REWARDS.map(reward=>{const rewardLimits=limits.rewards[reward.key],control=el("input",{type:"number",inputmode:"numeric",min:String(rewardLimits.minimum),max:String(rewardLimits.maximum),step:String(limits.step),value:missionValue(mission,reward.key),disabled:state.activeSource!=="mine",oninput:event=>editMission(mission,reward.key,event.target.value)});return detailField(reward.label,
        sourceControl(control,()=>missionValue(mission,reward.key),String(mission.baseRewards[reward.key]),value=>editMission(mission,reward.key,String(value))),
        reward.help);})
    ]});
  }
  function renderMissions(){
    const rows=matchingMissions();
    const areas=[...new Set((state.missions?.missions||[]).map(missionArea))].sort((a,b)=>a.localeCompare(b));
    $("#toolbar").replaceChildren();
    const areaFilter=el("select",{"aria-label":"Filter missions by area",onchange:event=>{state.missionArea=event.target.value;state.missionPage=0;renderMissions();}},el("option",{value:"",selected:!state.missionArea},"All areas"),...areas.map(area=>el("option",{value:area,selected:area===state.missionArea},area)));
    $("#main").replaceChildren(pagedListDetail({modOnly:modOnlySpec(state.missionEdits,()=>{state.missionPage=0}),rows,key:mission=>mission.id,slots:false,page:state.missionPage,pageSize:state.missionPageSize,selected:state.missionSelected,noun:"missions",splitKey:"rdr-missions",className:"rdr-split",defaultSplit:44,fit:{minRowHeight:32},
      search:{key:"rdr-missions",value:state.missionQuery,placeholder:"Search Story missions…",change:value=>{state.missionQuery=value;state.missionPage=0;renderMissions();}},filters:[areaFilter],
      master:({rows,selected,select})=>columnList({rows,key:mission=>mission.id,columns:MISSION_COLUMNS,selected,selectedClass:"sel",select,class:"rdr-record-list","aria-label":"RDR Story mission rewards"}),
      detail:()=>missionDetail(),sync:next=>{state.missionPage=next.page;state.missionPageSize=next.pageSize;state.missionSelected=next.selected||"";},change:next=>{state.missionPage=next.page;state.missionPageSize=next.pageSize;state.missionSelected=next.selected||"";renderMissions();}}));shell.refresh();
  }
