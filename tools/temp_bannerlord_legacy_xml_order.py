from pathlib import Path

path = Path('games/bannerlord/module_data.py')
text = path.read_text(encoding='utf-8')
old = '''    return int(_set_value(element, "Id", xml_id)) + int(_set_value(element, "Path", xml_path))
'''
new = '''    def set_legacy_value(tag: str, value: str) -> int:
        child = element.find(tag)
        if child is None:
            child = ET.Element(tag)
            included = element.find("IncludedGameTypes")
            if included is None:
                element.append(child)
            else:
                element.insert(list(element).index(included), child)
            child.set("value", value)
            return 1
        before = child.attrib.get("value", (child.text or "").strip())
        if before == value:
            return 0
        child.set("value", value)
        return 1

    return set_legacy_value("Id", xml_id) + set_legacy_value("Path", xml_path)
'''
if text.count(old) != 1:
    raise SystemExit(f'legacy XML identity match count {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
