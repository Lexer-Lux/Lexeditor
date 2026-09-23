"use strict";
  function settingKey(section,setting){return `${section.name}\u0000${setting.key}`;}
  function settingValue(section,setting){const key=settingKey(section,setting);return Object.prototype.hasOwnProperty.call(state.settingEdits,key)?state.settingEdits[key]:setting.value;}
  function editSetting(section,setting,value){const key=settingKey(section,setting);if(value===setting.value)delete state.settingEdits[key];else state.settingEdits[key]=value;shell.refresh();}
  function settingControl(section,setting){
    const value=settingValue(section,setting);
    if(setting.control==="checkbox")return el("input",{type:"checkbox",checked:value.toLowerCase()==="true",onchange:event=>editSetting(section,setting,event.target.checked?"true":"false"),"aria-label":setting.key});
    if(setting.control==="number")return el("input",{type:"number",min:setting.minimum,max:setting.maximum,step:setting.step,value,oninput:event=>editSetting(section,setting,event.target.value)});
    if(setting.control==="select")return el("select",{onchange:event=>editSetting(section,setting,event.target.value)},...(setting.options||[]).map(option=>el("option",{value:option,selected:String(option)===String(value)},option)));
    return el("input",{type:"text",value,oninput:event=>editSetting(section,setting,event.target.value),spellcheck:false});
  }
  async function saveSettings(){
    validateSettings();
    const edits=Object.entries(state.settingEdits).map(([identity,value])=>{const [section,key]=identity.split("\u0000");return {section,key,value};});if(!edits.length)return;
    await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};shell.history.clear();setStatus("Saved LexerRDR.ini in the workspace; runtime loading is not verified");renderSettings();shell.refresh();
  }
  function discardSettings(){state.settingEdits={};setStatus("Restored the last saved settings");renderSettings();shell.refresh()}
  function renderSettings(){
    $("#toolbar").replaceChildren(el("span",{},state.settings?.available?"LexerRDR.ini — project settings for LexerRDR.asi":"LexerRDR.ini is not available"),el("span",{},state.settings?.file||""),LexeditorUI.settingsSaveControl({pendingChanges:()=>(state.settings?.sections||[]).flatMap(section=>section.settings.filter(setting=>Object.prototype.hasOwnProperty.call(state.settingEdits,settingKey(section,setting))).map(setting=>({label:`${section.name} / ${setting.key}`,before:setting.value,after:settingValue(section,setting)}))),dirtyCount:()=>Object.keys(state.settingEdits).length,save:saveSettings,discard:discardSettings,readonly:()=>!state.settings?.available}));
    if(!state.settings?.available){$("#main").replaceChildren(unavailable("LexerRDR.ini is missing",state.settings?.reason||"The runtime settings file must be present before its values can be edited."));shell.refresh();return;}
    const sections=state.settings.sections.map(section=>LexeditorUI.detailSection({title:section.name,body:[section.help?LexeditorUI.detailNote(section.help):null,
      ...section.settings.map(setting=>LexeditorUI.detailField({label:setting.key,description:setting.help||"",control:settingControl(section,setting)}))]}));
    $("#main").replaceChildren(LexeditorUI.settingsColumns(sections));shell.refresh();
  }
