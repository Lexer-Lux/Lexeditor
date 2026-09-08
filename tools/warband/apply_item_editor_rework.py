from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    result, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return result


def patch_server() -> None:
    path = ROOT / "games/warband/server.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "import json\n", "import ast\nimport json\n", "server ast import")

    item_block = r'''ITEM_FIELD_NAMES = ("id", "name", "meshes", "flags", "capabilities", "value", "stats", "modifierBits", "factions")


def _module_items_source() -> tuple[str, str, bytes]:
    source = MODULE_SYSTEM / "module_items.py"
    raw = source.read_bytes()
    for encoding in ("utf-8", "cp1254", "latin1"):
        try:
            return raw.decode(encoding), encoding, raw
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1"), "latin1", raw


def _skip_python_string(text: str, index: int) -> int:
    quote = text[index]
    triple = text.startswith(quote * 3, index)
    delimiter = quote * (3 if triple else 1)
    cursor = index + len(delimiter)
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text.startswith(delimiter, cursor):
            return cursor + len(delimiter)
        cursor += 1
    raise ValueError("Unterminated Python string in module_items.py")


def _item_record_spans(text: str) -> list[tuple[int, int]]:
    match = re.search(r"(?m)^\\s*items\\s*=\\s*\\[", text)
    if not match:
        raise ValueError("module_items.py does not contain an items = [...] list")
    outer = text.find("[", match.start(), match.end())
    depth = 1
    record_start = None
    spans: list[tuple[int, int]] = []
    cursor = outer + 1
    while cursor < len(text):
        char = text[cursor]
        if char in "'\\\"":
            cursor = _skip_python_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\\n", cursor)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if char == "[":
            if depth == 1:
                record_start = cursor
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 1 and record_start is not None:
                spans.append((record_start, cursor + 1))
                record_start = None
            elif depth == 0:
                return spans
            if depth < 0:
                break
        cursor += 1
    raise ValueError("module_items.py has an unterminated items list")


def _split_item_fields(text: str, start: int, end: int) -> list[tuple[int, int]]:
    fields: list[tuple[int, int]] = []
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = start + 1
    field_start = cursor
    while cursor < end - 1:
        char = text[cursor]
        if char in "'\\\"":
            cursor = _skip_python_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\\n", cursor, end)
            cursor = end - 1 if newline < 0 else newline + 1
            continue
        if char in "([{":[
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced item expression in module_items.py")
            stack.pop()
        elif char == "," and not stack:
            left, right = field_start, cursor
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                fields.append((left, right))
            field_start = cursor + 1
        cursor += 1
    left, right = field_start, end - 1
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        fields.append((left, right))
    if stack:
        raise ValueError("Unbalanced item expression in module_items.py")
    return fields


def _literal_string(expression: str, field: str, record_index: int) -> str:
    try:
        value = ast.literal_eval(expression)
    except Exception as error:
        raise ValueError(f"Item {record_index} has an invalid {field} string") from error
    if not isinstance(value, str):
        raise ValueError(f"Item {record_index} {field} must be a string")
    return value


def _item_records(text: str) -> list[dict]:
    records: list[dict] = []
    mesh_entry = re.compile(r"\\(\\s*['\\\"]([^'\\\"]+)['\\\"]\\s*,")
    for record_index, (start, end) in enumerate(_item_record_spans(text)):
        spans = _split_item_fields(text, start, end)
        if len(spans) < 8:
            raise ValueError(f"Item record {record_index} has only {len(spans)} fields")
        expressions = [text[left:right].strip() for left, right in spans]
        field_order = list(ITEM_FIELD_NAMES[:len(expressions)])
        if len(expressions) > len(ITEM_FIELD_NAMES):
            field_order += [f"extra{index + 1}" for index in range(len(expressions) - len(ITEM_FIELD_NAMES))]
        fields = dict(zip(field_order, expressions))
        fields["id"] = _literal_string(expressions[0], "id", record_index)
        fields["name"] = _literal_string(expressions[1], "name", record_index)
        meshes = mesh_entry.findall(fields.get("meshes", ""))
        flags = fields.get("flags", "")
        stats = fields.get("stats", "")
        item_type = re.search(r"\\bitp_type_([a-z0-9_]+)\\b", flags, re.I)
        weight = re.search(r"\\bweight\\(([^)]+)\\)", stats)
        records.append({
            "recordIndex": record_index,
            "id": fields["id"],
            "name": fields["name"],
            "type": item_type.group(1) if item_type else "",
            "value": fields.get("value", ""),
            "weight": weight.group(1).strip() if weight else "",
            "line": text.count("\\n", 0, start) + 1,
            "meshes": meshes,
            "inventoryMesh": meshes[0] if meshes else "",
            "fields": fields,
            "fieldOrder": field_order,
            "_fieldSpans": spans,
        })
    return records


def item_rows() -> list[dict]:
    source = MODULE_SYSTEM / "module_items.py"
    if not source.is_file():
        return []
    text, _encoding, _raw = _module_items_source()
    rows = []
    for record in _item_records(text):
        rows.append({key: value for key, value in record.items() if not key.startswith("_")})
    return rows


def _validate_item_expression(expression: str) -> str:
    expression = str(expression).strip()
    if not expression:
        raise ValueError("Item expressions cannot be empty")
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = 0
    while cursor < len(expression):
        char = expression[cursor]
        if char in "'\\\"":
            cursor = _skip_python_string(expression, cursor)
            continue
        if char == "#":
            newline = expression.find("\\n", cursor)
            cursor = len(expression) if newline < 0 else newline + 1
            continue
        if char in "([{":[
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced item expression")
            stack.pop()
        elif char == "," and not stack:
            raise ValueError("A single item field cannot contain a top-level comma")
        cursor += 1
    if stack:
        raise ValueError("Unbalanced item expression")
    return expression


def _python_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _validate_module_items_candidate(text: str, encoding: str) -> bytes:
    records = _item_records(text)
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Saving would create duplicate item IDs")
    encoded = text.encode(encoding)
    python27 = Path(r"C:\\Python27\\python.exe")
    if python27.is_file():
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temporary:
            temporary.write(encoded)
            temporary_path = Path(temporary.name)
        try:
            check = subprocess.run(
                [str(python27), "-c", "import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')", str(temporary_path)],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if check.returncode:
                raise ValueError((check.stderr or check.stdout).strip())
        finally:
            temporary_path.unlink(missing_ok=True)
    return encoded


def save_item_edits(edits: list[dict]) -> dict:
    source = MODULE_SYSTEM / "module_items.py"
    if not source.is_file():
        raise FileNotFoundError(source)
    if not edits:
        return {"saved": 0, "backup": ""}
    text, encoding, raw = _module_items_source()
    records = _item_records(text)
    by_index = {record["recordIndex"]: record for record in records}
    replacements: list[tuple[int, int, str]] = []
    edited_records: set[int] = set()
    for edit in edits:
        record_index = int(edit.get("recordIndex", -1))
        record = by_index.get(record_index)
        if record is None:
            raise ValueError(f"Item record {record_index} no longer exists")
        original_id = str(edit.get("originalId", ""))
        if original_id and original_id != record["id"]:
            raise ValueError(f"Item record {record_index} changed from {original_id} to {record['id']}; reload before saving")
        field_order = record["fieldOrder"]
        for field, value in dict(edit.get("fields") or {}).items():
            if field not in field_order:
                raise ValueError(f"Item {record['id']} has no field named {field}")
            if field == "id":
                value = str(value).strip()
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    raise ValueError("Item IDs must contain only letters, digits, and underscores and cannot start with a digit")
                replacement = _python_string(value)
            elif field == "name":
                replacement = _python_string(str(value))
            else:
                replacement = _validate_item_expression(str(value))
            field_index = field_order.index(field)
            left, right = record["_fieldSpans"][field_index]
            replacements.append((left, right, replacement))
            edited_records.add(record_index)
    candidate = text
    for left, right, replacement in sorted(replacements, reverse=True):
        candidate = candidate[:left] + replacement + candidate[right:]
    candidate_records = _item_records(candidate)
    if len(candidate_records) != len(records):
        raise ValueError("Saving changed the number of item records; refusing the write")
    encoded = _validate_module_items_candidate(candidate, encoding)
    backup = source.with_name(source.name + ".lexeditor.bak")
    backup.write_bytes(raw)
    source.write_bytes(encoded)
    return {"saved": len(edited_records), "backup": str(backup)}
'''
    text = regex_once(text, r"def item_rows\(\) -> list\[dict\]:.*?\n\ndef upgrade_rows\(\) -> list\[dict\]:", item_block + "\n\ndef upgrade_rows() -> list[dict]:", "server item parser")

    text = replace_once(
        text,
        '    browsers = {"module_items.py": "items", "module_troops.py": "troops"}\n',
        '    browsers = {"module_troops.py": "troops"}\n',
        "data map browser set",
    )
    text = replace_once(
        text,
        '            elif filename in browsers and source_available:\n                coverage, status, view = "view", "partial", browsers[filename]\n                notes = "Read-only record browser. Changing records currently requires editing the Python source; this is not a structured data editor."\n',
        '            elif filename == "module_items.py" and source_available:\n                coverage, status, view = "structured", "integrated", "items"\n                notes = "Structured item records can be edited in Items. The complete Module System source remains available for fields Lexeditor does not interpret."\n            elif filename in browsers and source_available:\n                coverage, status, view = "view", "partial", browsers[filename]\n                notes = "Read-only record browser. Changing records currently requires editing the Python source; this is not a structured data editor."\n',
        "data map items structured",
    )
    text = replace_once(
        text,
        '"capabilities": ["build", "catalog", "data-map", "game-font", "item-preview", "items", "manuals", "settings", "troops", "upgrades"]',
        '"capabilities": ["build", "catalog", "data-map", "game-font", "item-edit", "item-preview", "items", "manuals", "settings", "troops", "upgrades"]',
        "item edit capability",
    )
    text = replace_once(
        text,
        '            if path == "/api/settings/save":\n                self.json_response(save_settings(body.get("edits", [])))\n            elif path == "/api/catalog/file/save":\n',
        '            if path == "/api/settings/save":\n                self.json_response(save_settings(body.get("edits", [])))\n            elif path == "/api/items/save":\n                self.json_response(save_item_edits(body.get("edits", [])))\n            elif path == "/api/catalog/file/save":\n',
        "items save endpoint",
    )
    path.write_text(text, encoding="utf-8")


def patch_icons() -> None:
    path = ROOT / "games/warband/item_icons.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'RENDER_VERSION = "inventory-orthographic-three-quarter-v1"', 'RENDER_VERSION = "inventory-auto-principal-three-quarter-v2"', "icon render version")
    helper = r'''

def _canonical_yaw(positions) -> float:
    """Derive one stable horizontal presentation angle from the mesh itself.

    Warband assets do not share one authoring yaw: a fixed camera makes some
    armor and footwear appear sideways while other meshes look fine.  The
    dominant horizontal principal axis gives every mesh the same presentation
    convention without maintaining an item-by-item correction table.
    """
    horizontal = [(float(row[0]), -float(row[1])) for row in positions]
    if len(horizontal) < 2:
        return .64
    mean_x = sum(row[0] for row in horizontal) / len(horizontal)
    mean_z = sum(row[1] for row in horizontal) / len(horizontal)
    xx = sum((x - mean_x) ** 2 for x, _z in horizontal) / len(horizontal)
    zz = sum((z - mean_z) ** 2 for _x, z in horizontal) / len(horizontal)
    xz = sum((x - mean_x) * (z - mean_z) for x, z in horizontal) / len(horizontal)
    trace = xx + zz
    discriminant = math.hypot(xx - zz, 2 * xz)
    if trace < 1e-10 or discriminant / trace < .08:
        return .64
    principal = .5 * math.atan2(2 * xz, xx - zz)
    # A slight deterministic three-quarter bias keeps depth readable while the
    # geometry, rather than a hand-curated item list, chooses the base yaw.
    return principal + math.radians(12)
'''
    text = replace_once(text, '\n\ndef render_icon(data: dict, texture: Path, destination: Path) -> None:\n', helper + '\n\ndef render_icon(data: dict, texture: Path, destination: Path) -> None:\n', "canonical icon yaw helper")
    text = replace_once(text, '    yaw, pitch = .64, -.30\n', '    yaw, pitch = _canonical_yaw(g["positions"]), -.30\n', "icon yaw use")
    path.write_text(text, encoding="utf-8")


def patch_editor() -> None:
    path = ROOT / "games/warband/editor.html"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '.warband-mesh-list{padding:9px 2px;color:var(--lex-muted)}.warband-mesh-list b{color:#651919}',
        '.warband-mesh-list{padding:9px 2px;color:var(--lex-muted)}.warband-mesh-list b{color:#651919}.warband-item-detail .lex-detail-panel-body{overflow:auto}.warband-item-expression{min-height:72px!important;resize:vertical!important;font:12px/1.35 "Cascadia Mono",Consolas,monospace!important}',
        "item detail CSS",
    )
    text = replace_once(
        text,
        'const {el,columnList,list,masterDetail,pagedListDetail,pager,clone,showAlert,hoverable,detailPanel}=LexeditorUI;',
        'const {el,columnList,list,masterDetail,pagedListDetail,pager,clone,showAlert,hoverable,detailPanel,detailField,detailGroup}=LexeditorUI;',
        "detail primitive import",
    )
    text = replace_once(
        text,
        '    settingEdits:{},filters:{items:"",troops:"",cut:false,upgrades:"",settings:"",datamap:"",mapStatus:""},',
        '    settingEdits:{},itemEdits:{},filters:{items:"",troops:"",cut:false,upgrades:"",settings:"",datamap:"",mapStatus:""},',
        "item edit state",
    )
    text = replace_once(
        text,
        '  function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.settingEdits).length+(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text?1:0):0;}\n  function historyCapture(){return {settingEdits:clone(state.settingEdits),catalogDraft:state.catalogDraft,selectedFile:state.selectedFile,catalogFile:clone(state.catalogFile)};}\n  async function historyRestore(snapshot){state.settingEdits=clone(snapshot.settingEdits);state.catalogDraft=snapshot.catalogDraft;state.selectedFile=snapshot.selectedFile;state.catalogFile=clone(snapshot.catalogFile);}\n',
        '  function itemDirtyCount(){return Object.values(state.itemEdits).reduce((total,row)=>total+Object.keys(row.fields||{}).length,0);}\n  function dirtyCount(){return state.activeSource==="mine"?Object.keys(state.settingEdits).length+itemDirtyCount()+(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text?1:0):0;}\n  function historyCapture(){return {settingEdits:clone(state.settingEdits),itemEdits:clone(state.itemEdits),catalogDraft:state.catalogDraft,selectedFile:state.selectedFile,catalogFile:clone(state.catalogFile)};}\n  async function historyRestore(snapshot){state.settingEdits=clone(snapshot.settingEdits);state.itemEdits=clone(snapshot.itemEdits||{});state.catalogDraft=snapshot.catalogDraft;state.selectedFile=snapshot.selectedFile;state.catalogFile=clone(snapshot.catalogFile);}\n',
        "dirty and history state",
    )

    detail_block = r'''  function itemEditKey(item){return String(item.recordIndex??item.line??item.id);}
  function effectiveItemField(item,key){return state.itemEdits[itemEditKey(item)]?.fields?.[key]??item.fields?.[key]??"";}
  function setItemField(item,key,value){
    const recordKey=itemEditKey(item),base=String(item.fields?.[key]??""),next=String(value);
    if(next===base){const existing=state.itemEdits[recordKey];if(existing?.fields)delete existing.fields[key];if(existing&&!Object.keys(existing.fields).length)delete state.itemEdits[recordKey];}
    else{const existing=state.itemEdits[recordKey]||(state.itemEdits[recordKey]={recordIndex:item.recordIndex,originalId:item.id,fields:{}});existing.fields[key]=next;}
    shell.refresh();
  }
  function itemTypeFromFlags(flags){return (String(flags).match(/\bitp_type_([a-z0-9_]+)/i)||[])[1]||"";}
  function setItemType(item,value){
    const clean=String(value).trim().replace(/^itp_type_/i,""),flags=String(effectiveItemField(item,"flags"));if(!clean)return;
    const token=`itp_type_${clean}`,next=/\bitp_type_[a-z0-9_]+/i.test(flags)?flags.replace(/\bitp_type_[a-z0-9_]+/i,token):(flags.trim()?`${token}|${flags}`:token);
    setItemField(item,"flags",next);const control=document.querySelector('[data-lex-property="flags"] textarea');if(control)control.value=next;
  }
  function itemWeightFromStats(stats){return (String(stats).match(/\bweight\(([^)]+)\)/)||[])[1]?.trim()||"";}
  function setItemWeight(item,value){
    const clean=String(value).trim();if(!clean)return;const stats=String(effectiveItemField(item,"stats"));
    const next=/\bweight\([^)]+\)/.test(stats)?stats.replace(/\bweight\([^)]+\)/,`weight(${clean})`):(stats.trim()?`weight(${clean})|${stats}`:`weight(${clean})`);
    setItemField(item,"stats",next);const control=document.querySelector('[data-lex-property="stats"] textarea');if(control)control.value=next;
  }
  const ITEM_HELP={
    id:"Module System identifier referenced by troops, shops, scripts, and other records. Renaming it here does not rewrite those references.",
    name:"Player-facing item name compiled into the module's item data.",
    type:"The itp_type_* flag defines the item's fundamental equipment/use class and changes how Warband interprets its other stats.",
    value:"Base item price before merchant, trade-skill, abundance, and other economy adjustments.",
    weight:"Inventory/equipment weight from the weight(...) stat macro; Warband uses it for encumbrance and other weight-sensitive behavior.",
    meshes:"Meshes used to render the item. The first mesh is also the source for Lexeditor's generated inventory icon.",
    flags:"Item behavior flags control equipment class, merchandise/civilian availability, handedness, and other engine behavior.",
    capabilities:"Weapon capability expression controlling supported attacks and animations; non-weapons commonly leave this at zero.",
    stats:"Gameplay stat macros for weight, abundance, armor, speed, reach, damage, ammunition, and related item values.",
    modifierBits:"Controls which generated item modifiers such as rusty, balanced, masterwork, or lordly may apply.",
    factions:"Optional faction list restricting where merchandise for this item may appear."
  };
  function itemExpressionControl(item,key){return el("textarea",{class:"warband-item-expression",value:effectiveItemField(item,key),oninput:event=>setItemField(item,key,event.target.value)});}
  function itemFieldLabel(key){return ({meshes:"Meshes",flags:"Flags",capabilities:"Capabilities",value:"Value",stats:"Stats",modifierBits:"Modifier bits",factions:"Factions"})[key]||key.replace(/^extra/,"Extra field ");}
  function warbandItemDetail(item){
    disposeWarbandPreview();
    if(!item)return detailPanel({className:"warband-item-detail",title:"Select an item"});
    const thumbnailMessage=el("div",{class:"warband-icon-message"},item.inventoryMesh?"Preparing icon…":"No mesh"),thumbnail=el("div",{class:"warband-item-thumbnail"},thumbnailMessage);
    const readOnly=state.activeSource!=="mine";
    const core=detailGroup({title:"Item",body:[
      detailField({label:"ID",property:"id",dataType:"STRING",description:ITEM_HELP.id,control:el("input",{value:effectiveItemField(item,"id"),disabled:readOnly,oninput:event=>setItemField(item,"id",event.target.value)})}),
      detailField({label:"Name",property:"name",dataType:"STRING",description:ITEM_HELP.name,control:el("input",{value:effectiveItemField(item,"name"),disabled:readOnly,oninput:event=>setItemField(item,"name",event.target.value)})}),
      detailField({label:"Type",property:"type",dataType:"STRING",description:ITEM_HELP.type,control:el("input",{value:itemTypeFromFlags(effectiveItemField(item,"flags")),disabled:readOnly,onchange:event=>setItemType(item,event.target.value)})}),
      detailField({label:"Value",property:"value",dataType:"EXPR",description:ITEM_HELP.value,control:el("input",{value:effectiveItemField(item,"value"),disabled:readOnly,oninput:event=>setItemField(item,"value",event.target.value)})}),
      detailField({label:"Weight",property:"weight",dataType:"FLOAT",description:ITEM_HELP.weight,control:el("input",{type:"number",step:"any",value:itemWeightFromStats(effectiveItemField(item,"stats")),disabled:readOnly,onchange:event=>setItemWeight(item,event.target.value)})})
    ]});
    const sourceFields=(item.fieldOrder||[]).filter(key=>!["id","name","value"].includes(key));
    const source=detailGroup({title:"Module System fields",body:sourceFields.map(key=>detailField({label:itemFieldLabel(key),property:key,dataType:"EXPR",description:ITEM_HELP[key]||"",control:(()=>{const control=itemExpressionControl(item,key);control.disabled=readOnly;return control;})()}))});
    const detail=detailPanel({className:"warband-item-detail",icon:thumbnail,title:el("h2",{class:"lex-detail-panel-title"},bitmapText(item.name,24)),identity:item.id,body:[core,source]});
    if(item.inventoryMesh)requestAnimationFrame(()=>loadWarbandIcon(item,detail,thumbnail,thumbnailMessage));
    return detail;
  }
'''
    text = regex_once(text, r"  function warbandItemDetail\(item\)\{.*?\n  async function loadWarbandIcon", detail_block + "  async function loadWarbandIcon", "item detail replacement")

    old_save = '''  async function saveAll(){
    try{
      if(Object.keys(state.settingEdits).length){const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};setStatus(`Saved ${result.saved} settings`);}
      if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text){const result=await api("/api/catalog/file/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:state.catalogFile.filename,text:state.catalogDraft,encoding:state.catalogFile.encoding})});state.catalogFile.text=state.catalogDraft;setStatus(`Saved ${state.catalogFile.filename}; backup created`);}
      await buildSavedModule();
      shell.history.clear();shell.refresh();render();
    }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
'''
    new_save = '''  async function saveAll(){
    try{
      const itemSourceDirty=state.catalogFile?.filename==="module_items.py"&&state.catalogFile.editable&&state.catalogDraft!==state.catalogFile.text;
      if(itemDirtyCount()&&itemSourceDirty)throw new Error("Items has structured edits while module_items.py also has unsaved source edits. Save or discard one editing path before using the other.");
      if(Object.keys(state.settingEdits).length){const edits=Object.entries(state.settingEdits).map(([line,value])=>({line:+line,value}));const result=await api("/api/settings/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.settings=await api("/api/settings");state.settingEdits={};setStatus(`Saved ${result.saved} settings`);}
      if(itemDirtyCount()){
        const selectedRecord=state.items.rows.find(row=>row.id===state.selectedItem)?.recordIndex,edits=Object.values(state.itemEdits);
        const result=await api("/api/items/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({edits})});state.items=await api("/api/items");state.itemEdits={};
        if(selectedRecord!==undefined)state.selectedItem=state.items.rows.find(row=>row.recordIndex===selectedRecord)?.id||"";
        if(state.catalogFile?.filename==="module_items.py"){state.catalogFile=await api("/api/catalog/file?name=module_items.py");state.catalogDraft=state.catalogFile.text;}
        setStatus(`Saved ${result.saved} item records`);
      }
      if(state.catalogFile?.editable&&state.catalogDraft!==state.catalogFile.text){const result=await api("/api/catalog/file/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:state.catalogFile.filename,text:state.catalogDraft,encoding:state.catalogFile.encoding})});state.catalogFile.text=state.catalogDraft;setStatus(`Saved ${state.catalogFile.filename}; backup created`);}
      await buildSavedModule();
      shell.history.clear();shell.refresh();render();
    }catch(error){setStatus("Save failed");showAlert({title:"Save failed",items:[{item:"Save",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
'''
    text = replace_once(text, old_save, new_save, "save all item edits")
    path.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "tests/test_warband_batch.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "    def test_only_structured_settings_count_integrated(self):\n", "    def test_structured_settings_and_items_count_integrated(self):\n", "coverage test name")
    text = replace_once(text, "        self.assertEqual(rows['module_items.py']['coverage'],'view')\n", "        self.assertEqual(rows['module_items.py']['coverage'],'structured')\n        self.assertEqual(rows['module_items.py']['status'],'integrated')\n        self.assertEqual(rows['module_items.py']['view'],'items')\n", "items coverage assertion")
    text = replace_once(text, "        self.assertEqual(server.data_map_rows()['counts']['integrated'],1)\n", "        self.assertEqual(server.data_map_rows()['counts']['integrated'],2)\n", "integrated count")
    icon_test = '''    def test_geometry_chooses_yaw_without_per_item_overrides(self):
        base=[[-3,-1,0],[3,-1,0],[3,1,0],[-3,1,0]]
        rotated=[[-y,x,z] for x,y,z in base]
        def projected_variance(points):
            yaw=icons._canonical_yaw(points);c,s=__import__('math').cos(yaw),__import__('math').sin(yaw)
            projected=[(c*x+s*(-y),-s*x+c*(-y)) for x,y,_z in points]
            mx=sum(x for x,_ in projected)/len(projected);mz=sum(z for _,z in projected)/len(projected)
            return sum((x-mx)**2 for x,_ in projected),sum((z-mz)**2 for _,z in projected)
        for points in (base,rotated):
            wide,deep=projected_variance(points)
            self.assertGreater(wide,deep*5)
        square=[[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]]
        self.assertAlmostEqual(icons._canonical_yaw(square),.64)

'''
    text = replace_once(text, "    def test_renderer_revision_part_of_identity(self):\n", icon_test + "    def test_renderer_revision_part_of_identity(self):\n", "canonical yaw test")
    path.write_text(text, encoding="utf-8")

    new_test = ROOT / "tests/test_warband_items_editor.py"
    new_test.write_text(r'''from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.warband import server


SOURCE = ''' + '"""' + r'''from header_items import *
items = [
  ["sword", "Old Sword", [("sword_mesh", 0)],
   itp_type_one_handed_wpn|itp_merchandise,
   itc_longsword, 120,
   weight(1.5)|spd_rtng(97)|weapon_length(90), imodbits_sword],
  ["boots", "Old Boots", [("boot_mesh", 0)], itp_type_foot_armor,
   0, 75, weight(1.0)|leg_armor(12), imodbits_cloth],
]
''' + '"""' + r'''


class WarbandItemEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.mkdir(exist_ok=True)
        self.path = self.root / "module_items.py"; self.path.write_text(SOURCE, encoding="utf-8")
        patcher = patch.object(server, "MODULE_SYSTEM", self.root); patcher.start(); self.addCleanup(patcher.stop)

    def test_multiline_records_expose_actual_fields(self):
        rows = server.item_rows()
        self.assertEqual([row["id"] for row in rows], ["sword", "boots"])
        sword = rows[0]
        self.assertEqual(sword["type"], "one_handed_wpn")
        self.assertEqual(sword["weight"], "1.5")
        self.assertEqual(sword["inventoryMesh"], "sword_mesh")
        self.assertEqual(sword["fields"]["capabilities"], "itc_longsword")
        self.assertIn("weapon_length(90)", sword["fields"]["stats"])
        self.assertEqual(sword["fieldOrder"][:8], ["id","name","meshes","flags","capabilities","value","stats","modifierBits"])

    def test_structured_save_changes_only_requested_fields_and_makes_backup(self):
        original = self.path.read_bytes()
        result = server.save_item_edits([{
            "recordIndex": 0, "originalId": "sword", "fields": {
                "name": "New Sword", "value": "250",
                "flags": "itp_type_two_handed_wpn|itp_merchandise",
                "stats": "weight(2.25)|spd_rtng(91)|weapon_length(115)",
            }
        }])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        rows = server.item_rows(); sword, boots = rows
        self.assertEqual(sword["name"], "New Sword")
        self.assertEqual(sword["value"], "250")
        self.assertEqual(sword["type"], "two_handed_wpn")
        self.assertEqual(sword["weight"], "2.25")
        self.assertEqual(boots["name"], "Old Boots")
        self.assertIn('itp_type_foot_armor', boots["fields"]["flags"])

    def test_stale_record_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "changed from wrong"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "wrong", "fields": {"value": "1"}}])

    def test_invalid_expression_and_duplicate_id_are_rejected_without_write(self):
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"stats": "weight(1), bad"}}])
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "duplicate item IDs"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"id": "boots"}}])
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

    browser = ROOT / "tests/warband_browser_check.py"
    text = browser.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "ITEMS=[{'id':f'fixture_{i:03}','name':f'Fixture sword {i:03}','type':'one_handed_wpn','meshes':['fixture_sword'],'inventoryMesh':'fixture_sword','line':i+1} for i in range(65)]\nITEMS.append({'id':'broken','name':'Missing texture fixture','type':'goods','meshes':['broken'],'inventoryMesh':'broken','line':100})",
        "def fixture_item(i,mesh='fixture_sword'):\n    item_id=f'fixture_{i:03}';name=f'Fixture sword {i:03}'\n    fields={'id':item_id,'name':name,'meshes':f'[(\\\"{mesh}\\\", 0)]','flags':'itp_type_one_handed_wpn|itp_merchandise','capabilities':'itc_longsword','value':'120','stats':'weight(1.5)|spd_rtng(97)|weapon_length(90)','modifierBits':'imodbits_sword'}\n    return {'recordIndex':i,'id':item_id,'name':name,'type':'one_handed_wpn','value':'120','weight':'1.5','meshes':[mesh],'inventoryMesh':mesh,'line':i+1,'fields':fields,'fieldOrder':list(fields)}\nITEMS=[fixture_item(i) for i in range(65)]\nbroken=fixture_item(100,'broken');broken.update({'id':'broken','name':'Missing texture fixture','type':'goods'});broken['fields'].update({'id':'broken','name':'Missing texture fixture','flags':'itp_type_goods','capabilities':'0'});ITEMS.append(broken)",
        "browser item fixtures",
    )
    text = regex_once(
        text,
        r"                    page.wait_for_function\('document.querySelector\(\"\.warband-item-thumbnail img\"\)\?\.naturalWidth>0'\).*?                    page.screenshot\(path=str\(ARTIFACTS/f'items-\{width\}\.png'\),full_page=True\)\n",
        '''                    page.wait_for_function('document.querySelector(".warband-item-thumbnail img")?.naturalWidth>0')
                    assert page.locator('.warband-item-detail [data-lex-property="id"] input').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="name"] input').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="flags"] textarea').count()==1
                    assert page.locator('.warband-item-detail [data-lex-property="stats"] textarea').count()==1
                    assert page.get_by_role('button',name='Open model preview',exact=True).count()==0
                    assert page.locator('.lex-model-preview-drawer').count()==0
                    name_field=page.locator('.warband-item-detail [data-lex-property="name"] input')
                    name_field.fill('Edited fixture name')
                    assert page.evaluate('itemDirtyCount()')==1
                    assert page.evaluate('Object.values(state.itemEdits)[0].fields.name')=='Edited fixture name'
                    name_field.fill('Fixture sword 000')
                    assert page.evaluate('itemDirtyCount()')==0
                    page.screenshot(path=str(ARTIFACTS/f'items-{width}.png'),full_page=True)
''',
        "browser preview section",
    )
    text = replace_once(
        text,
        '''                    # Missing dependencies never enable the preview action.
                    page.evaluate('state.filters.items="Missing texture fixture";navigate("items")')
                    page.get_by_role('button',name='Open model preview',exact=True).click()
                    page.wait_for_function('document.querySelector(".warband-preview-message")?.textContent.includes("Missing diffuse")')
                    assert page.locator('.lex-model-preview-drawer').is_visible()
                    assert page.evaluate('!window.__warbandPreview')
''',
        '''                    # A missing render dependency affects only the thumbnail; the actual item editor remains usable.
                    page.evaluate('state.filters.items="Missing texture fixture";navigate("items")')
                    page.wait_for_function('document.querySelector(".warband-icon-message")?.textContent.includes("Icon unavailable")')
                    assert page.locator('.warband-item-detail [data-lex-property="name"] input').is_enabled()
                    assert page.locator('.warband-item-detail [data-lex-property="stats"] textarea').is_enabled()
                    assert page.get_by_role('button',name='Open model preview',exact=True).count()==0
''',
        "browser missing icon behavior",
    )
    browser.write_text(text, encoding="utf-8")

    workflow = ROOT / ".github/workflows/warband-checks.yml"
    text = workflow.read_text(encoding="utf-8")
    text = replace_once(text, "      - run: python tests/warband_browser_check.py out/warband-browser\n        env:\n          WARBAND_REQUIRE_WEBGL: '1'\n", "      - run: python tests/warband_browser_check.py out/warband-browser\n", "remove obsolete WebGL requirement")
    workflow.write_text(text, encoding="utf-8")


def main() -> None:
    patch_server()
    patch_icons()
    patch_editor()
    patch_tests()


if __name__ == "__main__":
    main()
