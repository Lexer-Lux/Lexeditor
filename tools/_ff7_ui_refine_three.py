from pathlib import Path

PATH = Path("games/ff7/editor.html")
text = PATH.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


def replace_between(start_marker, end_marker, replacement, label):
    global text
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start < 0 or end < 0:
        raise SystemExit(f"{label}: markers missing")
    text = text[:start] + replacement + text[end:]


if "CHARACTER_AI_NAMES" in text:
    raise SystemExit("FF7 browsing polish already applied")

replace_once(
    '  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:row.values.name||row.name,identity:recordId(row.id),meta:null,body})}',
    '  function conceptPanel(row,body){return detailPanel({className:"ff7-detail",title:displayRowName(row),identity:recordId(row.id),meta:null,body})}',
    "semantic detail title",
)

ai_block = r'''  function aiDetail(row){
    const fields=aiEventFields(),eventKey=`${state.tab}/${row.id}`;let selected=Number(state.aiEvent[eventKey]);
    if(!Number.isInteger(selected)||selected<0||selected>=fields.length){const firstUsed=fields.findIndex(field=>String(row.values[field.key]||"").trim());selected=firstUsed>=0?firstUsed:0;state.aiEvent[eventKey]=selected}
    const selector=el("select",{"aria-label":`AI event for ${row.name}`,disabled:readonly(),onchange:event=>{state.aiEvent[eventKey]=Number(event.target.value);render()}},...fields.map((field,index)=>{const source=String(row.values[field.key]||""),lines=source.trim()?source.split(/\r?\n/).filter(line=>line.trim()).length:0;return el("option",{value:index},`${field.label} — ${lines?`${lines} line${lines===1?"":"s"}`:"Empty"}`)}));selector.value=String(selected);
    const field=fields[selected],editor=semanticControl(row,field),used=aiUsedCount(row);editor.style.width="100%";editor.style.fontFamily="ui-monospace, SFMono-Regular, Consolas, monospace";editor.style.lineHeight="1.35";editor.rows=12;
    const eventHelp=field.help||"Edit this FF7 battle-AI event as FF7 game-VM assembly. Invalid opcodes, bad jumps, and missing END instructions are rejected on save.";
    const toolbar=el("div",{style:"display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:8px 10px;align-items:center;padding:10px 10px 8px;min-width:0"},
      el("strong",{style:"font-size:.78rem;letter-spacing:.06em"},"EVENT"),selector,
      el("strong",{style:"font-size:.78rem;letter-spacing:.06em"},"EVENTS"),el("span",{style:"white-space:nowrap"},`${used} / ${fields.length} used`));
    return conceptPanel(row,[detailSection({title:"BATTLE AI",attrs:{"data-concept":"ai-event-editor"},help:infoHelp("Choose one of FF7's sixteen battle-AI event hooks. Empty events are valid and can be filled here; saving an empty event removes that script. "+eventHelp),body:el("div",{style:"min-width:0"},toolbar,el("div",{style:"padding:0 10px 10px;min-width:0"},editor))})]);
  }
'''
replace_between('  function aiDetail(row){', '  function recordDetail(row){', ai_block, "compact AI detail")

replace_once(
    '  function displayRowName(row){\n',
    '  const CHARACTER_AI_NAMES=["Cloud","Barret","Tifa","Aerith","Red XIII","Yuffie","Cait Sith","Vincent","Cid","Young Cloud","Sephiroth","Unknown owner"];\n  function displayRowName(row){\n',
    "character AI names",
)
replace_once(
    '    if(state.tab==="magicOrder"){\n      const record=rowById("playerAttacks",row.id);if(record)return candidateLabel(record);\n    }\n    return String(row.values?.name||row.name||`Record ${row.id}`);',
    '    if(state.tab==="magicOrder"){\n      const record=rowById("playerAttacks",row.id);if(record)return candidateLabel(record);\n    }\n    if(state.tab==="characterAI")return`${CHARACTER_AI_NAMES[row.id]||`Owner ${row.id}`} AI`;\n    if(state.tab==="enemyAI"){const scene=Math.floor(Number(row.id)/3),slot=Number(row.id)%3,enemy=(state.records.enemies||[]).find(candidate=>Number(candidate.id)===scene*3+slot);return enemy?`${candidateLabel(enemy)} — Scene ${scene}`:`Unused enemy slot ${slot+1} — Scene ${scene}`}\n    if(state.tab==="formationAI"){const formation=rowById("encounters",row.id);return formation?`${candidateLabel(formation)} AI`:`Battle ${row.id} AI`}\n    return String(row.values?.name||row.name||`Record ${row.id}`);',
    "AI display names",
)

replace_once(
    '    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"Scripts",sortable:true,grow:.55,pinned:false,render:row=>`${aiUsedCount(row)}/16`}];\n    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"Type",sortable:true,grow:.65,pinned:false,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];\n    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"Enemies",sortable:true,grow:.55,pinned:false,render:row=>derivedListValue(row,"derived:encounterEnemies")}];\n    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"Chars",sortable:true,grow:.5,pinned:false,render:row=>derivedListValue(row,"derived:textLength")}];',
    '    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"Scripts",sortable:true,grow:.55,render:row=>`${aiUsedCount(row)}/16`}];\n    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"Type",sortable:true,grow:.65,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];\n    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"Enemies",sortable:true,grow:.55,render:row=>derivedListValue(row,"derived:encounterEnemies")}];\n    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"Chars",sortable:true,grow:.5,render:row=>derivedListValue(row,"derived:textLength")}];',
    "show derived summaries by default",
)
replace_once(
    '    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label])=>{\n      const field=fieldByKey(fieldKey);if(!field)return[];\n      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:false,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];\n    });',
    '    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label],index)=>{\n      const field=fieldByKey(fieldKey);if(!field)return[];\n      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:index>=2?false:true,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];\n    });',
    "show primary summaries by default",
)
replace_once(
    '    const prefs=columnPreferences(`ff7-${state.tab}`,columns,()=>render());',
    '    const prefs=columnPreferences(`ff7-v2-${state.tab}`,columns,()=>render());',
    "version FF7 column defaults",
)

PATH.write_text(text, encoding="utf-8")
print("Applied FF7 AI browsing and list-summary polish")
