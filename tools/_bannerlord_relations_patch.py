from pathlib import Path

path = Path("games/bannerlord/module_data.py")
text = path.read_text(encoding="utf-8")
old = '''    incompatible_modules = []
    incompatible_root = root.find("IncompatibleModules")
    if incompatible_root is not None:
        for index, element in enumerate(_element_children(incompatible_root, "IncompatibleModule")):
            incompatible_modules.append(
                {"index": index, "id": element.attrib.get("Id", ""), "attributes": dict(element.attrib)}
            )

    submodules = []
'''
new = '''    modules_to_load_after_this = []
    load_after_root = root.find("ModulesToLoadAfterThis")
    if load_after_root is not None:
        for index, element in enumerate(_element_children(load_after_root, "Module")):
            modules_to_load_after_this.append(
                {"index": index, "id": element.attrib.get("Id", ""), "attributes": dict(element.attrib)}
            )

    incompatible_modules = []
    incompatible_root = root.find("IncompatibleModules")
    if incompatible_root is not None:
        elements = [
            child for child in list(incompatible_root)
            if child.tag in {"Module", "IncompatibleModule"}
        ]
        for index, element in enumerate(elements):
            incompatible_modules.append(
                {
                    "index": index,
                    "id": element.attrib.get("Id", ""),
                    "elementTag": element.tag,
                    "attributes": dict(element.attrib),
                }
            )

    submodules = []
'''
if old not in text:
    raise SystemExit("read_submodule relation context changed")
text = text.replace(old, new, 1)
old = '        "dependencies": dependencies,\n        "incompatibleModules": incompatible_modules,\n'
new = '        "dependencies": dependencies,\n        "modulesToLoadAfterThis": modules_to_load_after_this,\n        "incompatibleModules": incompatible_modules,\n'
if old not in text:
    raise SystemExit("read_submodule return context changed")
text = text.replace(old, new, 1)

start = text.index("def _edit_incompatible_modules(root: ET.Element, rows: list[dict]) -> int:\n")
end = text.index("\ndef _edit_tags(parent: ET.Element, rows: list[dict]) -> int:\n", start)
relation_editors = '''def _edit_module_id_rows(
    root: ET.Element,
    parent_tag: str,
    rows: list[dict],
    *,
    label: str,
    accepted_tags: set[str],
) -> int:
    parent = root.find(parent_tag)
    if parent is None and not rows:
        return 0
    parent = parent if parent is not None else ET.SubElement(root, parent_tag)
    existing = [child for child in list(parent) if child.tag in accepted_tags]
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        module_id = str(row.get("id", "")).strip()
        if not module_id:
            raise ValueError(f"{label} {position + 1} needs an ID")
        new_tag = str(row.get("elementTag") or "Module")
        if new_tag not in accepted_tags:
            new_tag = "Module"
        element, created = _reuse(existing, row.get("index"), reused, new_tag)
        changes += int(created)
        before = dict(element.attrib)
        element.set("Id", module_id)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    for child in list(parent):
        if child.tag in accepted_tags:
            parent.remove(child)
    for element in output:
        parent.append(element)
    return changes


def _edit_modules_to_load_after_this(root: ET.Element, rows: list[dict]) -> int:
    return _edit_module_id_rows(
        root,
        "ModulesToLoadAfterThis",
        rows,
        label="Load-after module",
        accepted_tags={"Module"},
    )


def _edit_incompatible_modules(root: ET.Element, rows: list[dict]) -> int:
    return _edit_module_id_rows(
        root,
        "IncompatibleModules",
        rows,
        label="Incompatible module",
        accepted_tags={"Module", "IncompatibleModule"},
    )

'''
text = text[:start] + relation_editors + text[end + 1:]
old = '    allowed = {"metadata", "dependencies", "incompatibleModules", "submodules", "xmls"}\n'
new = '    allowed = {"metadata", "dependencies", "modulesToLoadAfterThis", "incompatibleModules", "submodules", "xmls"}\n'
if old not in text:
    raise SystemExit("save_module allowed context changed")
text = text.replace(old, new, 1)
old = '    if "incompatibleModules" in payload:\n        changes += _edit_incompatible_modules(root, list(payload.get("incompatibleModules") or []))\n'
new = '    if "modulesToLoadAfterThis" in payload:\n        changes += _edit_modules_to_load_after_this(root, list(payload.get("modulesToLoadAfterThis") or []))\n    if "incompatibleModules" in payload:\n        changes += _edit_incompatible_modules(root, list(payload.get("incompatibleModules") or []))\n'
if old not in text:
    raise SystemExit("save_module relation context changed")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

path = Path("games/bannerlord/editor_core.js")
text = path.read_text(encoding="utf-8")
old = 'const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;'
new = 'const moduleEditable=m=>m?{metadata:metadata(m),dependencies:m.dependencies||[],modulesToLoadAfterThis:m.modulesToLoadAfterThis||[],incompatibleModules:m.incompatibleModules||[],submodules:m.submodules||[],xmls:m.xmls||[]}:null;'
if old not in text:
    raise SystemExit("moduleEditable context changed")
text = text.replace(old, new, 1)
old = '        ...fieldRow("Dependencies",String((m.dependencies||[]).length)),\n        ...fieldRow("Incompatible modules",String((m.incompatibleModules||[]).length)),\n'
new = '        ...fieldRow("Dependencies",String((m.dependencies||[]).length)),\n        ...fieldRow("Modules forced after this",String((m.modulesToLoadAfterThis||[]).length)),\n        ...fieldRow("Incompatible modules",String((m.incompatibleModules||[]).length)),\n'
if old not in text:
    raise SystemExit("module relation summary context changed")
text = text.replace(old, new, 1)
start = text.index("  function dependencyRows(){\n")
end = text.index("  function addTag(submodule){\n", start)
relation_ui = '''  function relationList(kind){
    if(kind==="incompatible")return state.module.incompatibleModules||[];
    if(kind==="loadAfter")return state.module.modulesToLoadAfterThis||[];
    return state.module.dependencies||[];
  }
  function dependencyRows(){
    return [
      ...(state.module.dependencies||[]).map((row,index)=>({kind:"dependency",index,row})),
      ...(state.module.modulesToLoadAfterThis||[]).map((row,index)=>({kind:"loadAfter",index,row})),
      ...(state.module.incompatibleModules||[]).map((row,index)=>({kind:"incompatible",index,row}))
    ];
  }
  function addDependency(kind){
    if(kind==="dependency"){
      state.module.dependencies.push({index:null,id:"",dependentVersion:"",optional:false,attributes:{}});
    }else if(kind==="loadAfter"){
      state.module.modulesToLoadAfterThis=state.module.modulesToLoadAfterThis||[];
      state.module.modulesToLoadAfterThis.push({index:null,id:"",attributes:{}});
    }else{
      state.module.incompatibleModules.push({index:null,id:"",elementTag:"Module",attributes:{}});
    }
    const list=relationList(kind);
    state.dependencySelection={kind,index:list.length-1};
    render();refresh();
  }
  function removeDependency(){
    const selection=state.dependencySelection;
    const list=relationList(selection.kind);
    if(!list.length)return;
    list.splice(selection.index,1);
    state.dependencySelection={kind:selection.kind,index:Math.max(0,Math.min(selection.index,list.length-1))};
    render();refresh();
  }
  function renderDependencies(){
    const rows=dependencyRows();
    const selection=state.dependencySelection;
    const list=relationList(selection.kind);
    const record=list[selection.index];
    const master=el("div",{class:"bl-master"},
      el("div",{class:"bl-master-head"},el("strong",{},"Module relations"),
        el("button",{type:"button",onclick:()=>addDependency("dependency"),title:"Add dependency"},"+ Dep"),
        el("button",{type:"button",onclick:()=>addDependency("loadAfter"),title:"Force another module to load after this module"},"+ After"),
        el("button",{type:"button",onclick:()=>addDependency("incompatible"),title:"Add incompatible module"},"+ Inc")),
      el("div",{class:"bl-list"},...rows.map(item=>{
        const active=item.kind===selection.kind&&item.index===selection.index;
        const label=item.kind==="dependency"?"Depends on":item.kind==="loadAfter"?"Loads after this":"Incompatible";
        return el("button",{type:"button",class:`bl-item${active?" active":""}`,onclick:()=>{state.dependencySelection={kind:item.kind,index:item.index};render()}},
          item.row.id||"(new module)",el("small",{},label+(item.row.dependentVersion?` · ${item.row.dependentVersion}`:"")));
      }))
    );
    let detail;
    if(!record)detail=el("div",{class:"bl-detail"},el("div",{class:"bl-empty"},"Select or add a module relation."));
    else if(selection.kind==="incompatible")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New incompatible module"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},...fieldRow("Module ID",textInput(record.id,value=>record.id=value))),
        el("div",{class:"bl-note"},"If this module is enabled too, Bannerlord treats the relation as incompatible. New rows use the current <Module Id=…> shape; older existing rows keep their original element shape.")));
    else if(selection.kind==="loadAfter")detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New inverse dependency"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},...fieldRow("Module ID",textInput(record.id,value=>record.id=value))),
        el("div",{class:"bl-note"},"Bannerlord will force this module to load after the current module. This is an ordering constraint, not a request to enable the target module.")));
    else detail=el("div",{class:"bl-detail"},
      el("section",{class:"bl-panel"},el("h2",{},record.id||"New dependency"),
        el("div",{class:"bl-actions"},el("button",{type:"button",class:"danger",onclick:removeDependency},"Remove")),
        el("div",{class:"bl-grid"},
          ...fieldRow("Module ID",textInput(record.id,value=>record.id=value)),
          ...fieldRow("Dependent version",textInput(record.dependentVersion,value=>record.dependentVersion=value,{placeholder:"Optional"})),
          ...fieldRow("Optional",checkbox(record.optional,value=>record.optional=value))
        ),
        el("div",{class:"bl-note"},"Optional dependencies constrain order only when already enabled; Lexeditor Play does not auto-enable an optional module merely because it is installed. Unknown dependency attributes are preserved when an existing row is edited.")
      ));
    main.replaceChildren(el("div",{class:"bl-split"},master,detail));
  }

'''
text = text[:start] + relation_ui + text[end:]
path.write_text(text, encoding="utf-8")
