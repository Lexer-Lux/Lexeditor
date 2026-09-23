"use strict";
  function languages(){return [...new Set(textAssets().map(row=>row.language).filter(Boolean))].sort()}
  function textAssetsForLanguage(){return textAssets().filter(row=>row.language===state.textLanguage)}
  // Country flags for the shipped language codes; an unlisted code keeps its
  // own letters rather than showing a wrong flag.
  const LANGUAGE_FLAGS={US:"🇺🇸",UK:"🇬🇧",GB:"🇬🇧",FR:"🇫🇷",DE:"🇩🇪",IT:"🇮🇹",ES:"🇪🇸",JP:"🇯🇵",KR:"🇰🇷",CN:"🇨🇳",TW:"🇹🇼",BR:"🇧🇷",RU:"🇷🇺",PL:"🇵🇱"};
  function languageLabel(code){
    const flag=LANGUAGE_FLAGS[String(code||"").toUpperCase()];
    return flag?`${flag} ${code}`:String(code||"");
  }
  function textLanguageBar(){
    return LexeditorUI.subtabBar({
      tabs:languages().map(code=>({id:code,label:languageLabel(code)})),
      active:state.textLanguage,label:"FF7 Remake text languages",
      change:value=>selectTextLanguage(value),
    });
  }
  // Every resource is already loaded, so this narrows the one list rather than
  // deciding which resource you are allowed to see.
  function textResourceFilter(){
    return LexeditorUI.pagerSelect({
      label:"Resource","aria-label":"FF7 Remake text resource",
      title:"Narrow the list to one text resource",
      disabled:state.textBusy,
      value:state.textResource,
      options:[{id:"",label:"All resources"},...textAssetsForLanguage().map(item=>({id:item.asset,
        label:item.group&&item.group!=="Text"?`${item.group} / ${item.name}`:item.name}))],
      change:value=>{state.textResource=String(value||"");state.pages.text=0;render()},
    });
  }
  function textArea(value,oninput,sub=false){const area=LexeditorUI.textArea({rows:sub?3:5,value:value??"",disabled:state.activeSource!=="mine",oninput:event=>oninput(event.target.value)});area.value=value??"";return area}
  function textRecordPanel(view=selectedTextRecord()){
    if(!view)return detailPanel({className:"ff7r-detail",title:"No text entry",body:[detailSection({title:"TEXT",body:[detailField({label:"STATE",control:readonlyField("No text entries were loaded for this language.")})]})]});
    const row=view.row;
    const main=detailField({label:"TEXT",dataType:"STRING",control:textArea(row.text,value=>{row.text=value;refreshShell()}),pin:textPrefs.pinButton("text","Text")});
    const subs=(row.subentries||[]).map(sub=>detailField({label:sub.id,dataType:"STRING",control:textArea(sub.text,value=>{sub.text=value;refreshShell()},true),help:sub.id==="ACTOR"?infoHelp("Actor/speaker metadata stored as an existing text-resource sub-entry."):null}));
    // The resource is a property of the entry, not a mode the tab is in.
    const sections=[detailSection({title:"ENTRY",body:[
      detailField({label:"TEXT ID",dataType:"STRING",control:readonlyField(row.key)}),
      detailField({label:"RESOURCE",dataType:"STRING",control:readonlyField(view.resource||view.asset),
        help:infoHelp("Which text resource this entry lives in. Every resource for this language is loaded, so searching and sorting cross all of them; saving writes back only the resources you changed.")}),
      main]})];
    if(subs.length)sections.push(detailSection({title:"SUB-ENTRIES",body:subs}));
    return detailPanel({className:"ff7r-detail",title:row.key||`Text ${row.id}`,identity:recordId(row.id),meta:`${state.textLanguage} · ${view.resource||"Text resource"}`,body:sections});
  }
  function textTablePanel(){const rows=sortedTextRows();return columnList({rows,key:row=>row.id,selected:state.textSelected,select:row=>{state.textSelected=row.id;render()},sortState:state.textSort,sort:key=>{state.textSort=state.textSort.key===key?{key,dir:-state.textSort.dir}:{key,dir:1};render()},columnPreferences:textPrefs,columns:textColumns,class:"ff7r-table","aria-label":"FF7 Remake localized text entries"})}
  function textPanel(){if(!textAssets().length)return loadingPanel("No text resources","No paired GameContents/Text .uasset/.uexp resources were found in the indexed FF7R PAKs.");if(state.textBusy||!state.textPacks)return loadingPanel("Loading text","Reading every localized text resource for this language…");if(state.error&&!textRecords().length)return errorPanel(state.error);return LexeditorUI.stack(textLanguageBar(),pagedTable({id:"text",noun:"entries",
      filters:[textResourceFilter()],
      rows:sortedTextRows(),key:row=>row.id,selected:state.textSelected,
      setSelected:row=>{state.textSelected=row.id},
      query:state.textQuery,setQuery:value=>{state.textQuery=value},
      searchLabel:"Search FF7 Remake text",searchPlaceholder:"Search text IDs and contents",
      sortState:state.textSort,sort:key=>{state.textSort=state.textSort.key===key?{key,dir:-state.textSort.dir}:{key,dir:1};render()},
      prefs:textPrefs,columns:textColumns,ariaLabel:"FF7 Remake localized text entries",
      split:40,minLeft:360,minRight:420,detail:()=>textRecordPanel()}))}
