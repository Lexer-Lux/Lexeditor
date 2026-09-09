from pathlib import Path

module_path = Path('games/bannerlord/module_data.py')
text = module_path.read_text(encoding='utf-8')

old = '''def _edit_tags(parent: ET.Element, rows: list[dict]) -> int:
    tags_root = parent.find("Tags")
    if tags_root is None and not rows:
        return 0
'''
new = '''def _edit_tags(parent: ET.Element, rows: list[dict], *, ensure: bool = False) -> int:
    tags_root = parent.find("Tags")
    if tags_root is None and not rows and not ensure:
        return 0
'''
if text.count(old) != 1:
    raise SystemExit(f'tags signature match count {text.count(old)}')
text = text.replace(old, new, 1)

old = '''def _edit_assemblies(parent: ET.Element, rows: list[dict]) -> int:
    assemblies_root = parent.find("Assemblies")
    if assemblies_root is None and not rows:
        return 0
'''
new = '''def _edit_assemblies(parent: ET.Element, rows: list[dict], *, ensure: bool = False) -> int:
    assemblies_root = parent.find("Assemblies")
    if assemblies_root is None and not rows and not ensure:
        return 0
'''
if text.count(old) != 1:
    raise SystemExit(f'assemblies signature match count {text.count(old)}')
text = text.replace(old, new, 1)

old = '''        changes += _edit_assemblies(element, list(row.get("assemblies") or []))
        changes += _edit_tags(element, list(row.get("tags") or []))
'''
new = '''        changes += _edit_assemblies(element, list(row.get("assemblies") or []), ensure=created)
        changes += _edit_tags(element, list(row.get("tags") or []), ensure=created)
'''
if text.count(old) != 1:
    raise SystemExit(f'submodule container calls match count {text.count(old)}')
text = text.replace(old, new, 1)
module_path.write_text(text, encoding='utf-8')

template_path = Path('games/bannerlord/template/SubModule.xml')
template = template_path.read_text(encoding='utf-8')
old = '''      <SubModuleClassType value="{{MODULE_ID}}.SubModule" />
      <Tags>
'''
new = '''      <SubModuleClassType value="{{MODULE_ID}}.SubModule" />
      <Assemblies />
      <Tags>
'''
if template.count(old) != 1:
    raise SystemExit(f'template insertion match count {template.count(old)}')
template_path.write_text(template.replace(old, new, 1), encoding='utf-8')
