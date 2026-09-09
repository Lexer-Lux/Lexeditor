"use strict";

let palBuildState=null,palWorkshopState=null,palLoaderState=null,palBuildLoading=false,palBuildError="";

async function refreshPalBuild(){
  palBuildLoading=true;palBuildError="";render();
  try{
    const results=await Promise.all([api("/api/build"),api("/api/workshop"),api("/api/loader-state")]);
    palBuildState=results[0];palWorkshopState=results[1];palLoaderState=results[2];
    const errors=[];
    if(palBuildState?.ready===false)errors.push(palBuildState.error||"Package build is not ready.");
    if(palWorkshopState?.ready===false)errors.push(palWorkshopState.error||"Local Workshop deployment is not ready.");
    if(palLoaderState?.error)errors.push(palLoaderState.error);
    palBuildError=errors.join(" ");
  }catch(error){palBuildError=error.message}
  finally{palBuildLoading=false;render()}
}
async function runPalBuild(action){
  palBuildLoading=true;palBuildError="";render();
  try{palBuildState=await api(`/api/build/${action}`,{method:"POST",body:"{}"});palWorkshopState=await api("/api/workshop");palLoaderState=await api("/api/loader-state")}
  catch(error){palBuildError=error.message}
  finally{palBuildLoading=false;render()}
}
async function runPalWorkshop(action){
  palBuildLoading=true;palBuildError="";render();
  try{palWorkshopState=await api(`/api/workshop/${action}`,{method:"POST",body:"{}"});palBuildState=await api("/api/build");palLoaderState=await api("/api/loader-state")}
  catch(error){palBuildError=error.message}
  finally{palBuildLoading=false;render()}
}
function palBuildStatusText(){
  if(palBuildLoading)return "Working…";
  if(palBuildError)return palBuildError;
  if(!palBuildState)return "Not checked";
  if(palBuildState.ready===false)return palBuildState.error||"Build is not ready";
  if(palBuildState.unownedTarget)return "Build path exists but is not owned by Lexeditor";
  if(palBuildState.built&&!palBuildState.currentMatchesManifest)return "Built package changed outside Lexeditor";
  if(palBuildState.current)return "Current clean package snapshot";
  if(palBuildState.built)return "Owned snapshot is stale; project sources changed";
  return "No package snapshot built";
}
function palWorkshopStatusText(){
  const state=palWorkshopState;
  if(palBuildLoading)return "Working…";
  if(!state)return "Not checked";
  if(state.ready===false)return state.error||"Local Workshop deployment is not ready";
  if(!state.workshopRootReady)return "Steam Workshop content root not found";
  if(state.externallyChanged)return "Local deployment changed outside Lexeditor — actions blocked";
  if(state.owned&&!state.deployed)return "Owned local deployment folder is missing — repair/remove ownership state manually";
  if(state.current)return "Current local test deployment";
  if(state.deployed)return state.buildCurrent?"Local deployment differs from current clean build":"Local deployment is stale; rebuild then update it";
  return "No local test deployment";
}
function palLoaderStatusText(){
  const state=palLoaderState;
  if(!state)return "Not checked";
  if(state.error)return state.error;
  if(!state.available)return state.reason||"PalModSettings.ini not available";
  if(state.active)return "Active";
  if(state.listed)return "Listed, but mods are globally disabled";
  return "Not active — enable through Palworld Mod Management";
}
function palBuildPanel(){
  const state=palBuildState||{},workshop=palWorkshopState||{};
  const unsafe=!!(state.unownedTarget||(state.built&&!state.currentMatchesManifest));
  const canBuild=!palBuildLoading&&!unsafe&&state.ready!==false;
  const canRevert=!palBuildLoading&&state.built&&state.currentMatchesManifest;
  const workshopOwnershipBroken=!!(workshop.owned&&!workshop.deployed);
  const canDeploy=!palBuildLoading&&state.current&&workshop.ready!==false&&workshop.workshopRootReady&&!workshop.externallyChanged&&!workshopOwnershipBroken;
  const canRemove=!palBuildLoading&&workshop.deployed&&workshop.owned&&!workshop.externallyChanged;
  return detailPanel({className:"pal-detail",title:"Official Package Build",identity:state.packageName||model?.PackageName||"PACKAGE",meta:"Clean package snapshot + Pocketpair-style local test deployment",body:[
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
    detailSection({title:"BUILD ACTIONS",body:[
      detailField({label:"PACKAGE",control:el("div",{class:"pal-actions"},
        el("button",{type:"button",class:"primary",disabled:!canBuild,onclick:()=>runPalBuild("create")},state.current?"Rebuild package":"Build package"),
        el("button",{type:"button",disabled:!canRevert,onclick:()=>runPalBuild("revert")},"Revert build"),
        el("button",{type:"button",disabled:palBuildLoading,onclick:refreshPalBuild},"Refresh")
      )}),
    ]}),
    detailSection({title:"LOCAL WORKSHOP TEST",body:[
      detailField({label:"STATUS",control:readonlyField(palWorkshopStatusText()),help:infoHelp("Pocketpair's uploader supports Shift+Create New Mod for local testing, using an unregistered random 10-digit Workshop folder. Lexeditor mirrors that local-only pattern and owns only the folder it creates.")}),
      detailField({label:"WORKSHOP ROOT",control:readonlyField(workshop.workshopRoot||"Not detected")}),
      detailField({label:"LOCAL FOLDER",control:readonlyField(workshop.folder||"Not deployed")}),
      detailField({label:"TARGET",control:readonlyField(workshop.targetPath||"Not deployed")}),
      detailField({label:"ACTIONS",control:el("div",{class:"pal-actions"},
        el("button",{type:"button",class:"primary",disabled:!canDeploy,onclick:()=>runPalWorkshop("deploy")},workshop.deployed?"Update local test":"Deploy local test"),
        el("button",{type:"button",disabled:!canRemove,onclick:()=>runPalWorkshop("remove")},"Remove local deployment")
      )}),
    ]}),
    detailSection({title:"LOADER STATE — READ ONLY",body:[
      detailField({label:"GLOBAL MODS",control:readonlyField(palLoaderState?.globalEnabled===true?"Enabled":palLoaderState?.globalEnabled===false?"Disabled":"Unknown")}),
      detailField({label:"PACKAGE",control:readonlyField(palLoaderStatusText()),help:infoHelp("Read-only view of Mods/PalModSettings.ini. Lexeditor never changes ActiveModList or the global enable flag for the Windows client.")}),
      detailField({label:"WORKSHOP ROOT",control:readonlyField(palLoaderState?.workshopRootDir||"Not available")}),
      detailField({label:"CONFIG",control:readonlyField(palLoaderState?.path||"Not available")}),
      detailField({label:"ACTIVATION",control:readonlyField("Enable/disable through Palworld Options → Mod Management. Lexeditor does not write activation settings.")}),
    ]}),
    detailSection({title:"PUBLISHING",body:[
      detailField({label:"STEAM",control:readonlyField("Not implemented. Use Pocketpair's official Palworld Mod Uploader to register/upload a Workshop item.")}),
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
