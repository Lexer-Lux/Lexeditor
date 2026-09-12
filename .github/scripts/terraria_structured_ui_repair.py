from pathlib import Path

path=Path('.github/scripts/terraria_structured_ui_patch.py')
text=path.read_text(encoding='utf-8')
old='    return el("div",{class:"terraria-content-grid"},...groups.map(group=>el("div",{class:"terraria-content-group"},el("strong",{},group.name),...group.fields.map(field=>el("label",{class:"terraria-content-field",title:field.help||""},el("span",{},field.label),schemaFieldControl(field,values,value=>{values[field.name]=value;onchange();},disabled)))));'
new='    const cards=groups.map(group=>el("div",{class:"terraria-content-group"},el("strong",{},group.name),...group.fields.map(field=>el("label",{class:"terraria-content-field",title:field.help||""},el("span",{},field.label),schemaFieldControl(field,values,value=>{values[field.name]=value;onchange();},disabled)))));\n    return el("div",{class:"terraria-content-grid"},...cards);'
if text.count(old)!=1:
    raise SystemExit('structured UI syntax repair anchor missing')
path.write_text(text.replace(old,new,1),encoding='utf-8')
