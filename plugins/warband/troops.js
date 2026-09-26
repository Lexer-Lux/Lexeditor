"use strict";
  function openTroop(troopId){
    const troop=state.troops.rows.find(row=>row.id===troopId);if(!troop)return;
    state.filters.troops="";state.filters.cut=false;state.selectedTroop=troop.id;
    state.pages.troops=0;navigate("troops");
  }
  function troopLink(troopId,label){
    if(!state.troops.rows.some(row=>row.id===troopId))return label;
    return hoverable({targetType:"warband-troop",targetId:troopId,targetLabel:label,label,activate:()=>openTroop(troopId)});
  }
  function renderTroops(){
    const base=state.filters.cut?state.troops.rows.filter(row=>row.status==="CUT"):state.troops.rows;
    const cutFilter=el("label",{class:"lex-bottom-filter"},el("input",{type:"checkbox",checked:state.filters.cut,onchange:event=>{state.filters.cut=event.target.checked;state.pages.troops=0;render();}})," Cut only");
    renderTableView("troops",base,[{key:"status",label:"State",render:row=>row.status==="CUT"?"Cut":"Active"},{key:"id",label:"ID"},{key:"name",label:"Name"},{key:"level",label:"Level"},{key:"faction",label:"Faction"},{key:"line",label:"Line"}],{key:troop=>troop.id,selected:()=>state.selectedTroop,setSelected:value=>{state.selectedTroop=value;},filters:[cutFilter],detail:troopEditorPanel});
  }
  function troopTreeDetail(node){
    if(!node)return detailPanel({title:"Select a troop"});
    // A troop has no mesh of its own: it is a body, a face built from morph
    // keys and a list of equipment. The equipment is the part that resolves to
    // meshes, so the viewer opens the troop's gear - which is what there is to
    // look at - rather than staying shut because a troop is not one model.
    // The tree node carries only the upgrade graph, so the troop's own record
    // is what holds its equipment.
    const record=state.troops?.rows?.find(row=>row.id===node.id)||node;
    // module_troops.py names an item "itm_leather_cap"; the item table's own id
    // is "leather_cap". Matching the two without stripping the prefix found
    // nothing, so the viewer stayed shut on every troop in the game.
    const gear=(record.items||[])
      .map(id=>{const bare=String(id).replace(/^itm_/,"");
        return state.items?.rows?.find(row=>row.id===bare||row.id===id);})
      .filter(item=>item&&item.inventoryMesh)
      .slice(0,12);
    // The shared viewer control lives in the heading's icon slot, so a panel
    // without an icon has nowhere to put it. A troop's icon is the first piece
    // of equipment it carries, which is also the first thing the drawer shows.
    const icon=gear.length?LexeditorUI.iconSlot({className:"warband-item-thumbnail",content:warbandPreviewStage(gear[0])}):null;
    return detailPanel({className:"warband-tree-detail",icon,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(node.name||node.id,24)),identity:node.id,
      modelPreview:gear.length?{
        label:`${node.name||node.id} equipment`,
        openLabel:`Open ${node.name||node.id}'s equipment`,
        closeLabel:`Close ${node.name||node.id}'s equipment`,
        content:LexeditorUI.figureGrid(gear.map(item=>({media:warbandPreviewStage(item),caption:item.name||item.id}))),
      }:null,
      body:node.missing?[LexeditorUI.notice({tone:"warning",message:"This upgrade refers to a troop missing from the parsed active source."})]:[
        ...troopFields(record)
      ]});
  }
  function renderUpgrades(keep){
    const all=WarbandTroopTrees.build(state.troops.rows,state.upgrades.rows);
    const factions=[...new Set(all.flatMap(t=>t.factions))].sort();
    if(!factions.includes(state.treeFaction))state.treeFaction=factions[0]||"";
    const trees=all.filter(t=>t.factions.includes(state.treeFaction));
    const tree=trees.find(t=>t.id===state.treeId)||trees[0];state.treeId=tree?.id||"";
    const factionSelect=el("select",{"aria-label":"Troop tree faction",onchange:e=>{state.treeFaction=e.target.value;state.treeId="";renderUpgrades();}},
      ...factions.map(f=>el("option",{value:f,selected:f===state.treeFaction},f)));
    // Each tree is its own subtab. A dropdown hid how many trees a faction has
    // and made moving between two of them a two-step gesture; a bar shows the
    // whole set and switches in one press. A faction with a single tree shows
    // no bar at all, which the shared control handles.
    const treeTabs=LexeditorUI.subtabBar({
      tabs:trees.map(t=>({id:t.id,label:t.label})),
      active:tree?.id,label:"Troop trees",
      change:value=>{state.treeId=value;renderUpgrades();},
    });
    $("#toolbar").replaceChildren(el("label",{},"Faction ",factionSelect));
    if(!tree){$("#main").replaceChildren(detailPanel({className:"lex-information-panel",title:"Troop trees",body:[LexeditorUI.detailNote("No upgrade trees are available in the selected project's Module System source.")]}));return;}
    const graph=WarbandTroopTrees.layout(tree), byId=new Map(graph.nodes.map(n=>[n.id,n]));
    let selected=byId.get(state.selectedUpgrade)||byId.get(tree.roots[0])||graph.nodes[0];state.selectedUpgrade=selected.id;
    const master=LexeditorUI.treeGraph({width:graph.width,height:graph.height,edges:graph.edges,selected:selected.id,label:"Bottom-up troop upgrade tree",
      nodes:graph.nodes.map(node=>({id:node.id,x:node.x,y:node.y,label:node.name||node.id,sub:node.id,missing:node.missing})),
      note:graph.cyclic?LexeditorUI.notice({tone:"warning",message:"Cyclic upgrade links detected. Cycle members share a row; arrows preserve the source links."}):null,
      // A new selection redraws the page with its detail; the tree stays
      // scrolled where the reader left it, with the pressed node focused.
      select:node=>{state.selectedUpgrade=node.id;renderUpgrades({left:master.scrollLeft,top:master.scrollTop});}});
    $("#main").replaceChildren(LexeditorUI.stack(treeTabs,
      masterDetail(master,troopTreeDetail(selected),"warband-trees",{splitKey:"warband-troop-trees",defaultSplit:65})));
    if(keep){master.scrollLeft=keep.left;master.scrollTop=keep.top;master.querySelector(`[data-node="${CSS.escape(selected.id)}"]`)?.focus();}
    else requestAnimationFrame(()=>{if(master.isConnected)master.scrollTop=master.scrollHeight;});
  }
