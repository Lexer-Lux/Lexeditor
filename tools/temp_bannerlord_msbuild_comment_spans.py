from pathlib import Path

path = Path('games/bannerlord/project_data.py')
text = path.read_text(encoding='utf-8')

marker = '''def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
'''
addition = '''def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _mask_xml_non_markup(value: str) -> str:
    """Blank comment/CDATA bodies while preserving all character offsets."""
    pattern = re.compile(r"<!--.*?-->|<!\\[CDATA\\[.*?\\]\\]>", re.DOTALL)
    def mask(match: re.Match) -> str:
        return "".join("\\n" if char == "\\n" else "\\r" if char == "\\r" else " " for char in match.group(0))
    return pattern.sub(mask, value)
'''
if text.count(marker) != 1:
    raise SystemExit(f'local name marker count {text.count(marker)}')
text = text.replace(marker, addition, 1)

old = '''        pattern = re.compile(
            rf"(<{re.escape(name)}(?:\\s+[^>]*)?>)(.*?)(</{re.escape(name)}>)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(candidate)
        if match:
            current = html.unescape(match.group(2).strip())
            if current == value:
                continue
            candidate = (
                candidate[:match.start()]
                + match.group(1) + escaped + match.group(3)
                + candidate[match.end():]
            )
'''
new = '''        pattern = re.compile(
            rf"(<{re.escape(name)}(?:\\s+[^>]*)?>)(.*?)(</{re.escape(name)}>)",
            re.IGNORECASE | re.DOTALL,
        )
        masked = _mask_xml_non_markup(candidate)
        matches = list(pattern.finditer(masked))
        parsed_count = sum(1 for row in model.get("propertyRows", []) if row.get("name") == name)
        if parsed_count and len(matches) != parsed_count:
            raise ValueError(
                f"Cannot safely patch {name}: textual MSBuild spans do not match parsed property definitions"
            )
        match = matches[0] if matches else None
        if match:
            current = html.unescape(candidate[match.start(2):match.end(2)].strip())
            if current == value:
                continue
            candidate = (
                candidate[:match.start(2)]
                + escaped
                + candidate[match.end(2):]
            )
'''
if text.count(old) != 1:
    raise SystemExit(f'property patch block count {text.count(old)}')
text = text.replace(old, new, 1)

old = '''        group = None
        for candidate_group in property_group_pattern.finditer(candidate):
            opening = candidate_group.group(0).split(">", 1)[0]
            if re.search(r"\\bCondition\\s*=", opening, re.IGNORECASE):
                continue
            group = candidate_group
            break
'''
new = '''        group = None
        masked = _mask_xml_non_markup(candidate)
        parsed_groups = [group for group in parsed if _local_name(group.tag) == "PropertyGroup"]
        textual_groups = list(property_group_pattern.finditer(masked))
        if len(textual_groups) != len(parsed_groups):
            raise ValueError(
                f"Cannot add {name}: textual PropertyGroup spans do not match parsed MSBuild groups"
            )
        for candidate_group in textual_groups:
            opening = candidate[candidate_group.start():candidate_group.end()].split(">", 1)[0]
            if re.search(r"\\bCondition\\s*=", opening, re.IGNORECASE):
                continue
            group = candidate_group
            break
'''
if text.count(old) != 1:
    raise SystemExit(f'property group span block count {text.count(old)}')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
