"use strict";

let palBuildState=null,palBuildLoading=false,palBuildError="";

async function refreshPalBuild(){
  palBuildLoading=true;palBuildError="";render();
  try{palBuildState=await api("/api/build");if(palBuildState?.ready===false)palBuildError=palBuildState.error||"Package build is not ready."}
  catch(error){palBuildState=null;palBuildError=error.message}
  finally{palBuildLoading=false;render()}
}
async function runPalBuild(action){
  palBuildLoading=true;palBuildError="";render();
  try{palBuildState=await api(`/api/build/${action}`,{method:"POST",body:"{}"})}
  catch(error){palBuildError=error.message}
  finally{palBuildLoading=false;render()}
}
function palBuildStatusText(){
  if(palBuildLoading)return "Working…";
  if(palBuildError)return palBuildError;
  if(!palBuildState)return "Not checked";
  if(palBuildState.unownedTarget)return "Build path exists but is not owned by Lexeditor";
  if(palBuildState.built&&!palBuildState.currentMatchesManifest)return "Built package changed outside Lexeditor";
  if(palBuildState.current)return "Current clean package snapshot";
  if(palBuildState.built)return "Owned snapshot is stale; project sources changed";
  return "No package snapshot built";
}
function palBuildPanel(){
  const state=palBuildState||{};
  const unsafe=!!(state.unownedTarget||(state.built&&!state.currentMatchesManifest));
  const canBuild=!palBuildLoading&&!unsafe&&state.ready!==false;
  const canRevert=!palBuildLoading&&state.built&&state.currentMatchesManifest;
  return detailPanel({className:"pal-detail",title:"Official Package Build",identity:state.packageName||model?.PackageName||"PACKAGE",meta:"Clean uploader / Workshop package snapshot",body:[
    detailSection({title:"SNAPSHOT",body:[
      detailField({label:"STATUS",control:readonlyField(palBuildStatusText()),help:infoHelp("Build creates a clean package snapshot from Info.json, Thumbnail and declared InstallRule targets. It does not activate a mod or publish to Steam.")}),
      detailField({label:"OUTPUT",control:readonlyField(state.packagePath||`${info?.project||"project"}/build/official-package`)}),
      detailField({label:"FILES",control:readonlyField(state.fileCount===undefined?"Not checked":String(state.fileCount))}),
      detailField({label:"DIGEST",control:readonlyField(state.currentDigest||state.desiredDigest||"Not built")}),
    ]}),
    detailSection({title:"OWNERSHIP & RECOVERY",body:[
      detailField({label:"OWNED",control:readonlyField(state.owned?"Yes":"No"),help:infoHelp("Lexeditor will replace or remove only snapshots tracked by its build manifest. An unowned directory is never overwritten.")}),
      detailField({label:"EXTERNAL CHANGES",control:readonlyField(state.built&&!state.currentMatchesManifest?"Detected — actions blocked":"None detected")}),
      detailField({label:"SOURCE PROJECT",control:readonlyField(info?.project||"Unavailable")}),
    ]}),
    detailSection({title:"ACTIONS",body:[
      detailField({label:"PACKAGE",control:el("div",{class:"pal-actions"},
        el("button",{type:"button",class:"primary",disabled:!canBuild,onclick:()=>runPalBuild("create")},state.current?"Rebuild package":"Build package"),
        el("button",{type:"button",disabled:!canRevert,onclick:()=>runPalBuild("revert")},"Revert build"),
        el("button",{type:"button",disabled:palBuildLoading,onclick:refreshPalBuild},"Refresh")
      )}),
      detailField({label:"NEXT STEP",control:readonlyField("Use the clean snapshot with Pocketpair's official uploader / Workshop flow. Activation remains loader-owned.")}),
    ]}),
  ]});
}

const palEditorRender=render;
render=function(){
  if(tab!=="build")return palEditorRender();
  if(!model)return;
  document.querySelector("#main").replaceChildren(panelLayout([palBuildPanel()],"pal-layout",{layoutKey:"palworld-build",defaultSizes:[100]}));
  refreshShell();
};
const palEditorNavigate=navigate;
navigate=function(value){
  tab=value;
  if(value==="build"&&!palBuildState&&!palBuildLoading)void refreshPalBuild();
  else render();
};
