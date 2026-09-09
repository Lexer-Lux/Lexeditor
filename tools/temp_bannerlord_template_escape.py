from pathlib import Path

path = Path('games/bannerlord/project_template.py')
text = path.read_text(encoding='utf-8')
text = text.replace('from pathlib import Path\nimport re\n', 'from pathlib import Path\nimport html\nimport re\n')
old = '''    replacements = {
        "{{MODULE_NAME}}": module_name,
        "{{MODULE_ID}}": module_id,
    }
    for relative in _TEMPLATE_FILES:
        path = target / relative
        if not path.is_file():
            raise FileNotFoundError(f"Bannerlord project template is missing {relative}")
        text = path.read_text(encoding="utf-8")
        for token, value in replacements.items():
            text = text.replace(token, value)
'''
new = '''    for relative in _TEMPLATE_FILES:
        path = target / relative
        if not path.is_file():
            raise FileNotFoundError(f"Bannerlord project template is missing {relative}")
        text = path.read_text(encoding="utf-8")
        xml_context = path.suffix.casefold() in {".xml", ".csproj", ".props", ".targets"}
        replacements = {
            "{{MODULE_NAME}}": html.escape(module_name, quote=True) if xml_context else module_name,
            "{{MODULE_ID}}": module_id,
        }
        for token, value in replacements.items():
            text = text.replace(token, value)
'''
if text.count(old) != 1:
    raise SystemExit(f'template replacement block count {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
