from pathlib import Path

path = Path('games/bannerlord/project_data.py')
text = path.read_text(encoding='utf-8')

old = '''        if name == "PropertyGroup":
            for element in group:
                property_name = _local_name(element.tag)
                value = (element.text or "").strip()
                if property_name not in properties:
                    properties[property_name] = value
                property_rows.append(
                    {
                        "group": group_index,
                        "name": property_name,
                        "value": value,
                        "condition": element.attrib.get("Condition", ""),
                        "editable": property_name in EDITABLE_PROJECT_PROPERTIES,
                    }
                )
'''
new = '''        if name == "PropertyGroup":
            group_condition = group.attrib.get("Condition", "")
            for element in group:
                property_name = _local_name(element.tag)
                value = (element.text or "").strip()
                if property_name not in properties:
                    properties[property_name] = value
                property_rows.append(
                    {
                        "group": group_index,
                        "name": property_name,
                        "value": value,
                        "condition": element.attrib.get("Condition", ""),
                        "groupCondition": group_condition,
                        "editable": property_name in EDITABLE_PROJECT_PROPERTIES,
                    }
                )
'''
if text.count(old) != 1:
    raise SystemExit(f'property row block match count {text.count(old)}')
text = text.replace(old, new, 1)

old = '''    return {
        "path": str(path),
        "name": path.name,
        "sdk": root.attrib.get("Sdk", ""),
        "properties": properties,
        "propertyRows": property_rows,
        "editableProperties": list(EDITABLE_PROJECT_PROPERTIES),
        "references": references,
'''
new = '''    property_definitions: dict[str, list[dict]] = {}
    for row in property_rows:
        property_definitions.setdefault(row["name"], []).append(row)
    ambiguous_properties: dict[str, str] = {}
    editable_properties = []
    for property_name in EDITABLE_PROJECT_PROPERTIES:
        rows = property_definitions.get(property_name, [])
        if len(rows) > 1:
            ambiguous_properties[property_name] = f"defined {len(rows)} times in this project file"
            continue
        if rows and (rows[0].get("condition") or rows[0].get("groupCondition")):
            ambiguous_properties[property_name] = "defined under an MSBuild Condition"
            continue
        editable_properties.append(property_name)

    return {
        "path": str(path),
        "name": path.name,
        "sdk": root.attrib.get("Sdk", ""),
        "properties": properties,
        "propertyRows": property_rows,
        "editableProperties": editable_properties,
        "ambiguousProperties": ambiguous_properties,
        "references": references,
'''
if text.count(old) != 1:
    raise SystemExit(f'project return block match count {text.count(old)}')
text = text.replace(old, new, 1)

old = '''    raw = path.read_text(encoding="utf-8-sig")
    candidate = raw
    saved = 0

    for name, incoming in edits.items():
'''
new = '''    model = read_project_file(path)
    ambiguous = model.get("ambiguousProperties", {})
    blocked = sorted(name for name in edits if name in ambiguous)
    if blocked:
        details = "; ".join(f"{name}: {ambiguous[name]}" for name in blocked)
        raise ValueError(
            "Lexeditor cannot safely edit conditional or multiply-defined MSBuild properties without evaluating MSBuild: "
            + details
        )

    raw = path.read_text(encoding="utf-8-sig")
    candidate = raw
    saved = 0

    for name, incoming in edits.items():
'''
if text.count(old) != 1:
    raise SystemExit(f'save preflight match count {text.count(old)}')
text = text.replace(old, new, 1)

# For an absent property, insert only into an unconditional PropertyGroup.
old = '''        group = re.search(r"</PropertyGroup\\s*>", candidate, re.IGNORECASE)
        if not group:
            raise ValueError("MSBuild project has no PropertyGroup for editable properties")
        line_start = candidate.rfind("\\n", 0, group.start()) + 1
        indentation = re.match(r"\\s*", candidate[line_start:group.start()]).group(0)
        insertion = f"{indentation}  <{name}>{escaped}</{name}>\\n"
        candidate = candidate[:group.start()] + insertion + candidate[group.start():]
'''
new = '''        parsed = ET.fromstring(candidate)
        unconditional_groups = [
            group
            for group in parsed
            if _local_name(group.tag) == "PropertyGroup" and not group.attrib.get("Condition", "").strip()
        ]
        if not unconditional_groups:
            raise ValueError(
                f"Cannot add {name}: MSBuild project has no unconditional PropertyGroup"
            )
        # Use textual bounds for the first unconditional PropertyGroup so comments/formatting remain intact.
        property_group_pattern = re.compile(
            r"<PropertyGroup(?P<attrs>\\s+[^>]*)?>.*?</PropertyGroup\\s*>",
            re.IGNORECASE | re.DOTALL,
        )
        group = None
        for candidate_group in property_group_pattern.finditer(candidate):
            opening = candidate_group.group(0).split(">", 1)[0]
            if re.search(r"\\bCondition\\s*=", opening, re.IGNORECASE):
                continue
            group = candidate_group
            break
        if group is None:
            raise ValueError(
                f"Cannot add {name}: could not locate an unconditional PropertyGroup text span"
            )
        close = re.search(r"</PropertyGroup\\s*>", group.group(0), re.IGNORECASE)
        close_at = group.start() + close.start()
        line_start = candidate.rfind("\\n", 0, close_at) + 1
        indentation = re.match(r"\\s*", candidate[line_start:close_at]).group(0)
        insertion = f"{indentation}  <{name}>{escaped}</{name}>\\n"
        candidate = candidate[:close_at] + insertion + candidate[close_at:]
'''
if text.count(old) != 1:
    raise SystemExit(f'property insertion block match count {text.count(old)}')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')

ui_path = Path('games/bannerlord/editor_build.js')
ui = ui_path.read_text(encoding='utf-8')
old = '''      el("div",{class:"bl-note"},`SDK: ${project.sdk||"(classic MSBuild)"} · ${project.references.length} assembly references · ${project.packages.length} packages`),
      el("div",{class:"bl-note"},"Lexeditor-hosted builds pin BannerlordDir, GameBin, ModuleDir, and OutputPath to the selected Bannerlord installation. Project-local values remain editable for external builds but cannot redirect Lexeditor Build / Build + deploy.")
'''
new = '''      el("div",{class:"bl-note"},`SDK: ${project.sdk||"(classic MSBuild)"} · ${project.references.length} assembly references · ${project.packages.length} packages`),
      Object.keys(project.ambiguousProperties||{}).length?el("div",{class:"bl-note"},`Read-only ambiguous MSBuild properties: ${Object.entries(project.ambiguousProperties).map(([name,reason])=>`${name} (${reason})`).join("; ")}. Lexeditor does not evaluate MSBuild conditions.`):null,
      el("div",{class:"bl-note"},"Lexeditor-hosted builds pin BannerlordDir, GameBin, ModuleDir, and OutputPath to the selected Bannerlord installation. Project-local values remain editable for external builds but cannot redirect Lexeditor Build / Build + deploy.")
'''
if ui.count(old) != 1:
    raise SystemExit(f'build UI diagnostics match count {ui.count(old)}')
ui_path.write_text(ui.replace(old, new, 1), encoding='utf-8')
