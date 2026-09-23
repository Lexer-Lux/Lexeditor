// ----- Data map -----
async function renderDataMap() {
  const current=renderScope("renderDataMap");
  if(!state.datamap)state.datamap=await api("/api/datamap");
  if(!current())return;
  const f=state.filters,view=LexeditorUI.dataMap({
    rows:state.datamap.rows,query:f.mapQ,status:f.mapStatus,page:f.mapPage,
    sort:state.dataMapSort,pageSize:100,
    changeQuery:value=>{f.mapQ=value;f.mapPage=0;renderDataMap();},
    changeStatus:value=>{f.mapStatus=value;f.mapPage=0;renderDataMap();},
    changePage:page=>{f.mapPage=page;renderDataMap();},
    changeSort:key=>{const [active,direction]=state.dataMapSort;state.dataMapSort=[key,active===key?-direction:1];renderDataMap();},
    open:row=>{if(row.target)navigate(row.target,row.filename==="projectile_speed_multipliers.csv"?{weaponSection:"velocity"}:row.filename==="honor_actions.csv"?{crimeSection:"honor"}:{});}
  });
  f.mapPage=view.page;
  $("#toolbar").replaceChildren(...view.controls);
  $("#main").replaceChildren(view.content);
}

async function saveMatrix() {
  if (isRO() || !state.matrixDirty.size) return;
  const edits = [...state.matrixDirty].map(key => {
    const a = state.matrix.animals.find(x => x.key === key);
    return { animalKey: key, rows: a.rows.filter(r => r.item) };
  });
  try {
    const r = await api("/api/matrix/save", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ edits }) });
    state.matrixDirty = new Set();
    toast(`Saved ${r.saved} animal(s) to loot_items_matrix.meta`);
    renderMatrix();
  } catch (ex) { throw showSaveFailure(ex); }
}
