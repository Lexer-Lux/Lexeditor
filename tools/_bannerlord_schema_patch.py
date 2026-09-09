from pathlib import Path


def replace(path_text: str, old: str, new: str) -> None:
    path = Path(path_text)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected patch context missing in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Modern ModuleCategory supersedes the legacy booleans. If modern metadata is
# absent, keep legacy compatibility; if neither legacy flag exists, Bannerlord's
# documented modern default is Singleplayer.
replace(
    "games/bannerlord/module_data.py",
    '''def is_singleplayer_module(module: dict) -> bool:
    """Accept both legacy SingleplayerModule and modern ModuleCategory metadata."""
    return bool(module.get("singleplayer")) or str(module.get("moduleCategory") or "").strip().casefold() == "singleplayer"
''',
    '''def is_singleplayer_module(module: dict) -> bool:
    """Resolve modern ModuleCategory first, then legacy flags/defaults."""
    category = str(module.get("moduleCategory") or "").strip().casefold()
    if category:
        return category == "singleplayer"
    if module.get("singleplayer"):
        return True
    if module.get("multiplayer"):
        return False
    # ModuleCategory replaced the legacy flags and defaults to Singleplayer.
    return True
''',
)

# Parse additional submodule assemblies.
replace(
    "games/bannerlord/module_data.py",
    '''        for index, element in enumerate(_element_children(submodule_root, "SubModule")):
            tags = []
            tags_root = element.find("Tags")
''',
    '''        for index, element in enumerate(_element_children(submodule_root, "SubModule")):
            assemblies = []
            assemblies_root = element.find("Assemblies")
            if assemblies_root is not None:
                for assembly_index, assembly in enumerate(_element_children(assemblies_root, "Assembly")):
                    assemblies.append(
                        {
                            "index": assembly_index,
                            "value": assembly.attrib.get("value", ""),
                            "attributes": dict(assembly.attrib),
                        }
                    )
            tags = []
            tags_root = element.find("Tags")
''',
)
replace(
    "games/bannerlord/module_data.py",
    '''                    "dllName": _value(element, "DLLName"),
                    "classType": _value(element, "SubModuleClassType"),
                    "tags": tags,
''',
    '''                    "dllName": _value(element, "DLLName"),
                    "classType": _value(element, "SubModuleClassType"),
                    "assemblies": assemblies,
                    "tags": tags,
''',
)

# Add a loss-minimizing editor for the Assembly value list.
replace(
    "games/bannerlord/module_data.py",
    '''def _edit_submodules(root: ET.Element, rows: list[dict]) -> int:
''',
    '''def _edit_assemblies(parent: ET.Element, rows: list[dict]) -> int:
    assemblies_root = parent.find("Assemblies")
    if assemblies_root is None and not rows:
        return 0
    assemblies_root = assemblies_root if assemblies_root is not None else ET.SubElement(parent, "Assemblies")
    existing = _element_children(assemblies_root, "Assembly")
    changes = 0
    reused: set[int] = set()
    output = []
    for position, row in enumerate(rows):
        value = str(row.get("value", "")).strip()
        if not value:
            raise ValueError(f"Submodule assembly {position + 1} needs a value")
        element, created = _reuse(existing, row.get("index"), reused, "Assembly")
        changes += int(created)
        before = dict(element.attrib)
        element.set("value", value)
        changes += int(before != element.attrib)
        output.append(element)
    if len(existing) != len(output) or any(a is not b for a, b in zip(existing, output)):
        changes += 1
    _remove_tagged_children(assemblies_root, "Assembly")
    for element in output:
        assemblies_root.append(element)
    return changes


def _edit_submodules(root: ET.Element, rows: list[dict]) -> int:
''',
)
replace(
    "games/bannerlord/module_data.py",
    '''        changes += int(_set_value(element, "SubModuleClassType", class_type))
        changes += _edit_tags(element, list(row.get("tags") or []))
''',
    '''        changes += int(_set_value(element, "SubModuleClassType", class_type))
        changes += _edit_assemblies(element, list(row.get("assemblies") or []))
        changes += _edit_tags(element, list(row.get("tags") or []))
''',
)

# Make the Data Map statement precise instead of claiming the entire descriptor.
replace(
    "games/bannerlord/module_data.py",
    '''            "controls": "Module identity, compatibility, dependencies, submodules, and XML registrations",
''',
    '''            "controls": "Module identity/category, dependency and inverse-load relations, incompatibilities, submodule DLL/class/assemblies/tags, and XML registrations",
''',
)
replace(
    "games/bannerlord/module_data.py",
    '''            "notes": "Full structured SubModule.xml editor." if submodule.is_file() else "SubModule.xml is required for a Bannerlord module project.",
''',
    '''            "notes": (
                "Structured editor for identity/category, dependency/load-order relations, incompatibilities, "
                "submodule DLL/class/assemblies/tags, and XML registrations; unsupported or unknown nodes are "
                "preserved and remain source-editable."
                if submodule.is_file()
                else "SubModule.xml is required for a Bannerlord module project."
            ),
''',
)

# Structured UI for the assembly list.
replace(
    "games/bannerlord/editor_core.js",
    '''  function addSubmodule(){
    state.module.submodules.push({index:null,name:"",dllName:"",classType:"",tags:[]});
''',
    '''  function addAssembly(submodule){
    submodule.assemblies=submodule.assemblies||[];
    submodule.assemblies.push({index:null,value:"",attributes:{}});
    render();refresh();
  }
  function renderAssemblies(submodule){
    return el("div",{class:"bl-tags"},
      ...(submodule.assemblies||[]).map((assembly,index)=>el("div",{class:"bl-tag-row",style:"grid-template-columns:minmax(180px,1fr) auto"},
        textInput(assembly.value,value=>assembly.value=value,{placeholder:"Additional assembly DLL"}),
        el("button",{type:"button",onclick:()=>{submodule.assemblies.splice(index,1);render();refresh()},title:"Remove assembly"},"×")
      )),
      el("div",{class:"bl-actions"},el("button",{type:"button",onclick:()=>addAssembly(submodule)},"+ Add assembly"))
    );
  }
  function addSubmodule(){
    state.module.submodules.push({index:null,name:"",dllName:"",classType:"",assemblies:[],tags:[]});
''',
)
replace(
    "games/bannerlord/editor_core.js",
    '''        el("div",{class:"bl-grid"},
          ...fieldRow("Name",textInput(record.name,value=>record.name=value)),
          ...fieldRow("DLL name",textInput(record.dllName,value=>record.dllName=value)),
          ...fieldRow("Class type",textInput(record.classType,value=>record.classType=value))
        ),
        el("h2",{},"Tags"),renderTags(record)
''',
    '''        el("div",{class:"bl-grid"},
          ...fieldRow("Name",textInput(record.name,value=>record.name=value)),
          ...fieldRow("DLL name",textInput(record.dllName,value=>record.dllName=value)),
          ...fieldRow("Class type",textInput(record.classType,value=>record.classType=value))
        ),
        el("h2",{},"Assemblies"),renderAssemblies(record),
        el("div",{class:"bl-note"},"Additional assemblies declared under this SubModule are preserved and edited as explicit DLL names."),
        el("h2",{},"Tags"),renderTags(record)
''',
)

# Explain that hosted builds pin their standard Bannerlord paths regardless of
# project-local values.
replace(
    "games/bannerlord/editor_build.js",
    '''      el("div",{class:"bl-note"},`SDK: ${project.sdk||"(classic MSBuild)"} · ${project.references.length} assembly references · ${project.packages.length} packages`)
''',
    '''      el("div",{class:"bl-note"},`SDK: ${project.sdk||"(classic MSBuild)"} · ${project.references.length} assembly references · ${project.packages.length} packages`),
      el("div",{class:"bl-note"},"Lexeditor-hosted builds pin BannerlordDir, GameBin, ModuleDir, and OutputPath to the selected Bannerlord installation. Project-local values remain editable for external builds but cannot redirect Lexeditor Build / Build + deploy.")
''',
)
