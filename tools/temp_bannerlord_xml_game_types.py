from pathlib import Path

module_path = Path('games/bannerlord/module_data.py')
text = module_path.read_text(encoding='utf-8')
old = '''        changes += _set_xml_registration_identity(element, xml_id, xml_path)
        changes += _edit_game_types(element, list(row.get("includedGameTypes") or []))
        output.append(element)
'''
new = '''        game_types = list(row.get("includedGameTypes") or [])
        if created and not game_types:
            raise ValueError(f"New XML registration {position + 1} needs at least one included game type")
        changes += _set_xml_registration_identity(element, xml_id, xml_path)
        changes += _edit_game_types(element, game_types)
        output.append(element)
'''
if text.count(old) != 1:
    raise SystemExit(f'XML game-type insertion match count {text.count(old)}')
module_path.write_text(text.replace(old, new, 1), encoding='utf-8')

ui_path = Path('games/bannerlord/editor_core.js')
ui = ui_path.read_text(encoding='utf-8')
old = '''        el("h2",{},"Included game types"),renderGameTypes(record)
      ));
'''
new = '''        el("h2",{},"Included game types"),renderGameTypes(record),
        el("div",{class:"bl-note"},"New XML registrations require at least one IncludedGameTypes/GameType entry; Lexeditor will not guess Campaign or another game type for you.")
      ));
'''
if ui.count(old) != 1:
    raise SystemExit(f'XML UI note match count {ui.count(old)}')
ui_path.write_text(ui.replace(old, new, 1), encoding='utf-8')
