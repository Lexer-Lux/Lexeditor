from pathlib import Path
root = Path.cwd()
p = root / 'games/rdr/server.py'
s = p.read_text()
s = s.replace('import mimetypes\n', 'import mimetypes\nimport math\n')
start=s.index('def _validate_scalar(')
end=s.index('\ndef save_item(',start)
s=s[:start]+'''def _edit_list(edits: list[dict]) -> list[dict]:
    if not isinstance(edits, list) or any(not isinstance(edit, dict) for edit in edits):
        raise ValueError("Edits must be a list of objects")
    return edits


def _number(value, label: str, minimum=None, maximum=None, *, integer=False) -> float:
    """Validate before converting: bool and empty text are not numeric edits."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be a number") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    if integer and not number.is_integer():
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and number < minimum or maximum is not None and number > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _validate_scalar(original: str, kind: str, value: str, field: str) -> str:
    if "\\x00" in value or len(value) > 4096:
        raise ValueError(f"{field} contains an invalid value")
    if kind == "bool":
        lowered = value.strip().casefold()
        if lowered not in {"true", "false"}:
            raise ValueError(f"{field} must be true or false")
        return lowered
    if kind == "number":
        limits = ITEM_NUMBER_CONTROLS.get(field, {})
        integer = limits.get("step") == 1 if limits else bool(re.fullmatch(r"[+-]?\\d+", original.strip()))
        _number(value, field, limits.get("minimum"), limits.get("maximum"), integer=integer)
    return value

''' + s[end:]
s=s.replace('    _source, vanilla, project, active = _inventory_paths(source_id)\n', '    _integer(index, "Inventory item index", 0, 2147483647)\n    _source, vanilla, project, active = _inventory_paths(source_id)\n',1)
s=s.replace('    for edit in edits:\n','    for edit in _edit_list(edits):\n')
needle='''        value = _validate_scalar(scalar["value"], scalar["kind"], str(edit.get("value", "")), field)
'''
s=s.replace(needle,needle+'''        if field in ITEM_SELECT_FIELDS:
            # Observed enum values from the prepared source and current project.
            options = {candidate["value"] for dataset in (True, False)
                       for row in items_payload(dataset)["rows"] for candidate in row["fields"]
                       if candidate["field"] == field}
            if value not in options:
                raise ValueError(f"Unsupported {field} choice: {value}")
''')
s=s.replace('''    relative, raw, packed, project = _shop_paths(source)
    data = bytearray''','''    _integer(item_index, "Shop item index", 0, 2147483647)
    relative, raw, packed, project = _shop_paths(source)
    data = bytearray''',1)
start=s.index('        if kind == "float":',s.index('def save_shop('))
end=s.index('        wanted[field] = ',start)
s=s[:start]+'''        if field not in record["_offsets"]:
            raise ValueError(f"This shop record has no editable {field}")
        if kind == "float":
            parsed = _number(value, "PriceModifier", 0, 1000)
            # WGD stores IEEE float32. Compare the encoded value, not float64 input.
            parsed = struct.unpack("<f", struct.pack("<f", parsed))[0]
        else:
            minimum = 0 if field == "QuantityPerPurchase" else -1
            parsed = int(_number(value, field, minimum, 2147483647, integer=True))
''' + s[end:]
s=s.replace('''    backup = backup_file(project)
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-shop-save-")''','''    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-shop-save-")''',1)
start=s.index('        atomic_bytes(project, output.read_bytes())',s.index('def save_shop('))
end=s.index('    return {',start)
s=s[:start]+'''        # Never publish an unverified repack. Unpack the temporary candidate and
        # compare every byte, including fields/components that were not edited.
        verified_data = _active_shop_bytes(raw, output)
        if verified_data != bytes(data):
            raise RuntimeError("Packed shop verification failed; project override was not changed")
        payload = output.read_bytes()
    backup = backup_file(project)
    atomic_bytes(project, payload)
''' + s[end:]
needle='''    changed = 0
    for identity, value in wanted.items():
'''
rep='''    for identity, value in wanted.items():
        original = final[identity]["value"]
        label = "/".join(identity)
        if original.casefold() in {"true", "false"}:
            value = _validate_scalar(original, "bool", value, label)
        elif identity in SETTING_CONTROLS:
            limits = SETTING_CONTROLS[identity]
            _number(value, label, limits["minimum"], limits["maximum"],
                    integer=limits.get("step") == 1)
        wanted[identity] = value.strip()
    changed = 0
    for identity, value in wanted.items():
'''
assert needle in s
s=s.replace(needle,rep,1)
needle='''    payload = "".join(lines).encode(encoding)
    backup = backup_file(SETTINGS_FILE)
'''
rep='''    candidate = "".join(lines)
    _sections, parsed = _parse_ini(candidate)
    if any(parsed.get(identity, {}).get("value") != value for identity, value in wanted.items()):
        raise ValueError("INI edit changes the setting structure; no settings were written")
    payload = candidate.encode(encoding)
    backup = backup_file(SETTINGS_FILE)
'''
assert needle in s
s=s.replace(needle,rep,1)
s=s.replace('if not isinstance(document, dict) or document.get("schemaVersion") != 1:', 'if not isinstance(document, dict) or type(document.get("schemaVersion")) is not int or document["schemaVersion"] != 1:',1)
start=s.index('    try:\n        minimum = float(value_range.get("minimum"))',s.index('def validate_loot_document'))
end=s.index('    paths = money.get(',start)
s=s[:start]+'''    minimum = _number(value_range.get("minimum"), "Money minimum", 0, 100000)
    maximum = _number(value_range.get("maximum"), "Money maximum", 0, 100000)
    if minimum > maximum:
        raise ValueError("Money range must be ordered and non-negative")
''' + s[end:]
s=s.replace('''    actual_paths = {(path.get("decorator"), path.get("operation"))
                    for path in paths if isinstance(path, dict)} if isinstance(paths, list) else set()
''','''    if (not isinstance(paths, list) or len(paths) != len(expected_paths)
            or any(not isinstance(path, dict) for path in paths)):
        raise ValueError("Money decorator paths must contain exactly the three proven paths")
    actual_paths = {(path.get("decorator"), path.get("operation")) for path in paths}
''',1)
s=s.replace('json.dumps(document, indent=2, ensure_ascii=False)', 'json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)')
s=s.replace('''        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
''','''        def reject_constant(value):
            raise ValueError(f"Invalid JSON number: {value}")
        document = json.loads(self.rfile.read(length).decode("utf-8"),
                              parse_constant=reject_constant) if length else {}
        if not isinstance(document, dict):
            raise ValueError("Request body must be a JSON object")
        return document
''',1)
s=s.replace('int(body.get("index", -1)),','body.get("index", -1),',1)
s=s.replace('int(body.get("itemIndex", -1)),','body.get("itemIndex", -1),',1)
p.write_text(s)
p=root/'games/rdr/mission_rewards.py'
s=p.read_text().replace('asset_path.split("/")[3]','asset_path.split("/")[2]')
s=s.replace('''    if document.get("schemaVersion") != 1:
''','''    if (not isinstance(document, dict) or type(document.get("schemaVersion")) is not int
            or document["schemaVersion"] != 1):
''',1)
s=s.replace('''    for row in document.get("overrides", []):
''','''    overrides = document.get("overrides", [])
    if not isinstance(overrides, list):
        raise ValueError("Mission overrides must be a list")
    for row in overrides:
''',1)
s=s.replace('if not isinstance(mission_id, int) or mission_id not in valid_ids:', 'if type(mission_id) is not int or mission_id not in valid_ids:')
p.write_text(s)
