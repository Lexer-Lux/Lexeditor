"use strict";
  async function renderDataMap(){
    if(!state.dataMap)state.dataMap=await api("/api/datamap");
    const view=LexeditorUI.dataMap({
      rows:state.dataMap.rows||[],query:state.mapQuery,status:state.mapStatus,page:state.mapPage,
      sort:state.dataMapSort,pageSize:100,
      changeQuery:value=>{state.mapQuery=value;state.mapPage=0;renderDataMap();},
      changeStatus:value=>{state.mapStatus=value;state.mapPage=0;renderDataMap();},
      changePage:page=>{state.mapPage=page;renderDataMap();},
      changeSort:key=>{const [active,direction]=state.dataMapSort;state.dataMapSort=[key,active===key?-direction:1];renderDataMap();},
      open:row=>{if(row.target)navigate(row.target);}
    });
    state.mapPage=view.page;
    $("#toolbar").replaceChildren(...view.controls);
    $("#main").replaceChildren(view.content);
    shell.refresh();
  }
