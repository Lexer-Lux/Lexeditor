from pathlib import Path

EDITOR = Path("games/ff7/editor.html")
RENDERED = Path("tools/verify_ff7_rendered.py")
text = EDITOR.read_text(encoding="utf-8")
tests = RENDERED.read_text(encoding="utf-8")


def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return source.replace(old, new, 1)


def replace_between(source, start_marker, end_marker, replacement, label):
    start = source.find(start_marker)
    if start < 0:
        raise SystemExit(f"{label}: start marker missing")
    end = source.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"{label}: end marker missing")
    return source[:start] + replacement + source[end:]


if "function aiDetail(row)" in text or "materia-level-progression" in text:
    raise SystemExit("FF7 detail refinement already present; refusing to apply twice")

text = replace_once(
    text,
    'query:{},sort:{},mapQuery:""',
    'query:{},sort:{},aiEvent:{},mapQuery:""',
    "AI event state",
)

old_description = '    if(metadata.descriptionEditable)body.push(detailSection({title:"TEXT",body:detailField({label:"DESCRIPTION",help:infoHelp("The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes."),control:descriptionControl(row),dataType:"TEXT"})}));'
new_description = '''    if(metadata.descriptionEditable){
      const help="The in-game description stored in this FF7 KERNEL.BIN. Byte escapes are preserved for game control codes.",control=descriptionControl(row);control.style.width="100%";
      body.push(detailSection({title:"DESCRIPTION",attrs:{"data-concept":"editable-description"},help:infoHelp(help),body:el("div",{style:"padding:10px;min-width:0"},control)}));
    }'''
text = replace_once(text, old_description, new_description, "full-width description")

extra_details = r'''  function materiaDetail(row){
    const apKeys=["level2Ap","level3Ap","level4Ap","level5Ap"],body=ordinarySections(row,new Set(apKeys)),entries=apKeys.map((key,index)=>({key:index+2,level:index+2,field:fieldByKey(key)}));
    const progression=detailSection({title:"LEVEL PROGRESSION",attrs:{"data-concept":"materia-level-progression"},help:infoHelp("AP thresholds are cumulative. The final column shows the additional AP required after the preceding level threshold."),body:conceptTable(entries,"62px minmax(110px,1fr) minmax(110px,.8fr)",[
      {key:"level",label:"Level",render:entry=>entry.level},
      {key:"total",label:"Total AP",render:entry=>semanticControl(row,{...entry.field,rerenderOnChange:true})},
      {key:"increment",label:"From prior",render:entry=>{const previous=entry.level===2?0:Number(row.values[`level${entry.level-1}Ap`]);return Number(row.values[entry.field.key])-previous}},
    ],"Materia AP level progression")});
    body.splice(category().descriptionEditable?1:0,0,progression);return conceptPanel(row,body);
  }
  function aiEventFields(){return category().fields.filter(field=>/^script\d+$/.test(field.key)).sort((a,b)=>Number(a.key.slice(6))-Number(b.key.slice(6)))}
  function aiUsedCount(row){return aiEventFields().filter(field=>String(row.values[field.key]||"").trim()).length}
  function aiDetail(row){
    const fields=aiEventFields(),eventKey=`${state.tab}/${row.id}`;let selected=Number(state.aiEvent[eventKey]);
    if(!Number.isInteger(selected)||selected<0||selected>=fields.length){const firstUsed=fields.findIndex(field=>String(row.values[field.key]||"").trim());selected=firstUsed>=0?firstUsed:0;state.aiEvent[eventKey]=selected}
    const selector=el("select",{"aria-label":`AI event for ${row.name}`,disabled:readonly(),onchange:event=>{state.aiEvent[eventKey]=Number(event.target.value);render()}},...fields.map((field,index)=>{const source=String(row.values[field.key]||""),lines=source.trim()?source.split(/\r?\n/).filter(line=>line.trim()).length:0;return el("option",{value:index},`${field.label} — ${lines?`${lines} line${lines===1?"":"s"}`:"Empty"}`)}));selector.value=String(selected);
    const field=fields[selected],editor=semanticControl(row,field);editor.style.width="100%";
    const eventHelp=field.help||"Edit this FF7 battle-AI event as FF7 game-VM assembly. Invalid opcodes, bad jumps, and missing END instructions are rejected on save.";
    return conceptPanel(row,[
      detailSection({title:"AI EVENT",attrs:{"data-concept":"ai-event-editor"},help:infoHelp("Choose one of FF7's sixteen battle-AI event hooks. Empty events are valid and can be filled here; saving an empty event removes that script."),body:[detailField({label:"EVENT",control:selector,dataType:"SELECT"}),detailField({label:"USED",control:readonlyField(`${aiUsedCount(row)} / ${fields.length}`),dataType:"VALUE"})]}),
      detailSection({title:field.label.toUpperCase(),help:infoHelp(eventHelp),body:el("div",{style:"padding:10px;min-width:0"},editor)}),
    ]);
  }
'''
text = replace_once(text, '  function recordDetail(row){', extra_details + '  function recordDetail(row){', "specialized detail editors")

text = replace_once(
    text,
    '    if(state.tab==="growthBonuses")return growthBonusDetail(row);\n    if(state.tab==="characters")return characterDetail(row);',
    '    if(state.tab==="growthBonuses")return growthBonusDetail(row);\n    if(state.tab==="materia")return materiaDetail(row);\n    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return aiDetail(row);\n    if(state.tab==="characters")return characterDetail(row);',
    "record detail routing",
)

old_summary = r'''  function summaryColumns(){
    return (MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label])=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:false,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
  }
  function listSortValue(row,key){
    if(key==="name")return displayRowName(row);
    if(key==="description")return row.description||"";
    if(String(key).startsWith("value:"))return row.values?.[String(key).slice(6)];
    return row[key];
  }
'''
new_summary = r'''  function derivedListValue(row,key){
    if(key==="derived:aiScripts")return aiUsedCount(row);
    if(key==="derived:growthKind")return {primary:0,hp:1,mp:2,exp:3}[growthCurveKind(row)]??9;
    if(key==="derived:encounterEnemies")return Array.from({length:6},(_,i)=>Number(row.values[`slot${i}_enemy`])!==0xFFFF).filter(Boolean).length;
    if(key==="derived:textLength")return String(row.values?.text||"").length;
    return undefined;
  }
  function derivedSummaryColumns(){
    if(["characterAI","enemyAI","formationAI"].includes(state.tab))return[{key:"derived:aiScripts",label:"Scripts",sortable:true,grow:.55,pinned:false,render:row=>`${aiUsedCount(row)}/16`}];
    if(state.tab==="growthCurves")return[{key:"derived:growthKind",label:"Type",sortable:true,grow:.65,pinned:false,render:row=>({primary:"Primary",hp:"HP",mp:"MP",exp:"EXP"}[growthCurveKind(row)])}];
    if(state.tab==="encounters")return[{key:"derived:encounterEnemies",label:"Enemies",sortable:true,grow:.55,pinned:false,render:row=>derivedListValue(row,"derived:encounterEnemies")}];
    if(["texts","exeText"].includes(state.tab))return[{key:"derived:textLength",label:"Chars",sortable:true,grow:.5,pinned:false,render:row=>derivedListValue(row,"derived:textLength")}];
    return[];
  }
  function summaryColumns(){
    const fields=(MASTER_SUMMARY_FIELDS[state.tab]||[]).flatMap(([fieldKey,label])=>{
      const field=fieldByKey(fieldKey);if(!field)return[];
      return[{key:`value:${fieldKey}`,label,sortable:true,grow:.65,pinned:false,render:row=>{const full=semanticListValue(row,field);return el("span",{title:full},compactListValue(full))}}];
    });
    return[...fields,...derivedSummaryColumns()];
  }
  function listSortValue(row,key){
    if(key==="name")return displayRowName(row);
    if(key==="description")return row.description||"";
    if(String(key).startsWith("value:"))return row.values?.[String(key).slice(6)];
    if(String(key).startsWith("derived:"))return derivedListValue(row,key);
    return row[key];
  }
'''
text = replace_once(text, old_summary, new_summary, "derived master summaries")

if text.count('state.sort[state.tab]||{key:"name",dir:1}') != 1:
    raise SystemExit("master default sort marker drifted")
text = text.replace('state.sort[state.tab]||{key:"name",dir:1}', 'state.sort[state.tab]||{key:"id",dir:1}', 1)
if text.count('state.sort[group]||{key:"name",dir:1}') != 1:
    raise SystemExit("integrated default sort marker drifted")
text = text.replace('state.sort[group]||{key:"name",dir:1}', 'state.sort[group]||{key:"id",dir:1}', 1)

old_control = '''    def control(self,group,key):
        self.navigate(group)
        name=self.page.evaluate('([group,key])=>{const row=state.records[group].find(r=>r.id===state.selected[group]);return state.data.categories.find(c=>c.id===group).fields.find(f=>f.key===key).label+" for "+row.name}',[group,key])
        return self.page.get_by_label(name,exact=True).first
'''
new_control = '''    def control(self,group,key):
        self.navigate(group)
        row_name=self.page.evaluate('(group)=>state.records[group].find(r=>r.id===state.selected[group]).name',group)
        if group in ("characterAI","enemyAI","formationAI") and key.startswith("script"):
            self.page.get_by_label(f"AI event for {row_name}",exact=True).select_option(key[6:])
            self.page.wait_for_timeout(20)
        name=self.page.evaluate('([group,key])=>{const row=state.records[group].find(r=>r.id===state.selected[group]);return state.data.categories.find(c=>c.id===group).fields.find(f=>f.key===key).label+" for "+row.name}',[group,key])
        return self.page.get_by_label(name,exact=True).first
'''
tests = replace_once(tests, old_control, new_control, "rendered AI control helper")

EDITOR.write_text(text, encoding="utf-8")
RENDERED.write_text(tests, encoding="utf-8")
print("Applied FF7 detail editor, ordering, and AI refinement")
