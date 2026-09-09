from pathlib import Path

path = Path('games/bannerlord/module_data.py')
text = path.read_text(encoding='utf-8')

marker = 'def _child_or_create(parent: ET.Element, tag: str) -> ET.Element:\n'
end = '\n\ndef _remove_tagged_children(parent: ET.Element, tag: str) -> None:\n'
if text.count(marker) != 1 or text[text.index(marker):].count(end) != 1:
    raise SystemExit('child helper markers changed')
start = text.index(marker)
stop = text.index(end, start)
replacement = '''_MODULE_SECTION_ORDER = (
    "DependedModules",
    "ModulesToLoadAfterThis",
    "IncompatibleModules",
    "DependedModuleMetadatas",
    "SubModules",
    "Xmls",
)
_SUBMODULE_CHILD_ORDER = ("Name", "DLLName", "SubModuleClassType", "Assemblies", "Tags")


def _insert_ordered_child(parent: ET.Element, element: ET.Element, order: tuple[str, ...]) -> ET.Element:
    """Insert a newly-created known child before the next known schema sibling.

    Existing elements are never moved. Unknown/comment nodes keep their relative
    positions; this only prevents Lexeditor-created nodes from being appended
    after later structural sections.
    """
    try:
        target_rank = order.index(element.tag)
    except ValueError:
        parent.append(element)
        return element
    for index, child in enumerate(list(parent)):
        try:
            child_rank = order.index(child.tag)
        except ValueError:
            continue
        if child_rank > target_rank:
            parent.insert(index, element)
            return element
    parent.append(element)
    return element


def _child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = _insert_ordered_child(parent, ET.Element(tag), _MODULE_SECTION_ORDER)
    return child


def _submodule_child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = _insert_ordered_child(parent, ET.Element(tag), _SUBMODULE_CHILD_ORDER)
    return child
'''
text = text[:start] + replacement + text[stop:]

old = '''def _set_value(parent: ET.Element, tag: str, value: str) -> bool:
    element = parent.find(tag)
    if element is None:
        element = ET.SubElement(parent, tag)
        element.set("value", value)
        return True
'''
new = '''def _set_value(parent: ET.Element, tag: str, value: str, *, submodule_order: bool = False) -> bool:
    element = parent.find(tag)
    if element is None:
        element = _submodule_child_or_create(parent, tag) if submodule_order else ET.SubElement(parent, tag)
        element.set("value", value)
        return True
'''
if text.count(old) != 1:
    raise SystemExit(f'_set_value match count {text.count(old)}')
text = text.replace(old, new, 1)

replacements = {
    'parent = parent if parent is not None else ET.SubElement(root, "DependedModuleMetadatas")':
        'parent = parent if parent is not None else _insert_ordered_child(root, ET.Element("DependedModuleMetadatas"), _MODULE_SECTION_ORDER)',
    'parent = parent if parent is not None else ET.SubElement(root, parent_tag)':
        'parent = parent if parent is not None else _insert_ordered_child(root, ET.Element(parent_tag), _MODULE_SECTION_ORDER)',
    'parent = parent if parent is not None else ET.SubElement(root, "Xmls")':
        'parent = parent if parent is not None else _insert_ordered_child(root, ET.Element("Xmls"), _MODULE_SECTION_ORDER)',
}
for old_value, new_value in replacements.items():
    if text.count(old_value) != 1:
        raise SystemExit(f'section creator match count for {old_value}: {text.count(old_value)}')
    text = text.replace(old_value, new_value, 1)

old = '''        changes += int(_set_value(element, "Name", name))
        changes += int(_set_value(element, "DLLName", dll_name))
        changes += int(_set_value(element, "SubModuleClassType", class_type))
'''
new = '''        changes += int(_set_value(element, "Name", name, submodule_order=True))
        changes += int(_set_value(element, "DLLName", dll_name, submodule_order=True))
        changes += int(_set_value(element, "SubModuleClassType", class_type, submodule_order=True))
'''
if text.count(old) != 1:
    raise SystemExit(f'submodule fields match count {text.count(old)}')
text = text.replace(old, new, 1)

for old_value, new_value, label in (
    (
        'assemblies_root = assemblies_root if assemblies_root is not None else ET.SubElement(parent, "Assemblies")',
        'assemblies_root = assemblies_root if assemblies_root is not None else _submodule_child_or_create(parent, "Assemblies")',
        'assemblies creator',
    ),
    (
        'tags_root = tags_root if tags_root is not None else ET.SubElement(parent, "Tags")',
        'tags_root = tags_root if tags_root is not None else _submodule_child_or_create(parent, "Tags")',
        'tags creator',
    ),
):
    if text.count(old_value) != 1:
        raise SystemExit(f'{label} match count {text.count(old_value)}')
    text = text.replace(old_value, new_value, 1)

path.write_text(text, encoding='utf-8')
