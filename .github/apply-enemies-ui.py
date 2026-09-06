"""Apply reviewed compact enemy UI sources to the exact tested base files."""
from pathlib import Path
import hashlib
import json
import subprocess


def blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def base(path: str) -> str:
    return subprocess.check_output(['git', 'show', '60eda056e233148debf6ef660bf19611ecf76518:' + path]).decode('utf-8')


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding='utf-8')


path = 'games/ff8/editor.html'
text = base(path)
assert blob(text.encode()) == 'b4a3060f6c82731c1c582aeaa4a72aa129567112'
for name, replacement in json.loads(Path('.github/enemies-functions.json').read_text(encoding='utf-8')).items():
    start = text.index('  function ' + ('enemyPropertyLabel' if name == 'enemyProperties' else name) + '(')
    function_start = text.index('  function ' + name + '(')
    end = text.index('\n  function ', function_start + 5)
    text = text[:start] + replacement + text[end:]
text = text.replace('  </style>', '\n' + Path('.github/enemies-style.css').read_text(encoding='utf-8') + '  </style>', 1)
write(path, text)

path = 'games/ff8/server.py'
text = base(path).replace('from . import cards,', 'from . import card_art, cards,', 1)
anchor = '            elif path.startswith("/assets/icons/") and path.endswith(".png"):'
assert text.count(anchor) == 1
text = text.replace(anchor, '''            elif path.startswith("/assets/cards/") and path.endswith(".png"):
                card_id = int(path.rsplit("/", 1)[-1].removesuffix(".png"))
                self.binary_response(card_art.png_bytes(card_id), "image/png")
''' + anchor, 1)
write(path, text)

path = 'games/ff8/paths.py'
text = base(path)
assert text.count('"cards_ui.js"') == 1
write(path, text.replace('"cards_ui.js"', '"cards_ui.js", "card_art.py"', 1))

path = 'tools/verify_ff8_enemies_editor_visual_39.py'
text = base(path)
text = text.replace('            assert result["scan"]["text"] and result["scan"]["pin"] == "false", result',
                    '            assert not result["scan"]["text"], "Scan belongs to Battle Text, not Stats"')
anchor = '            cdp.eval("""(()=>{const input=document.querySelector(\'.enemy-scan-section textarea\');'
text = text.replace(anchor, '''            cdp.eval("state.enemyPanelTab='battleText';renderEnemies()")
            wait_eval(cdp, "!!document.querySelector('.enemy-scan-section textarea')", 5)
            result["scan"] = cdp.eval("""(()=>({
              text:document.querySelector('.enemy-scan-section textarea').value,
              pin:document.querySelector('.enemy-scan-section .lex-column-pin')?.getAttribute('aria-pressed')
            }))()""")
            assert result["scan"]["text"] and result["scan"]["pin"] == "false", result
''' + anchor, 1)
text = text.replace('            before_path = cdp.eval(',
                    '            cdp.eval("state.enemyPanelTab=\'stats\';renderEnemies()")\n            wait_eval(cdp, "!!document.querySelector(\'.ff8-enemy-curve\')", 5)\n            before_path = cdp.eval(', 1)
write(path, text)

for path, expected in json.loads(Path('.github/enemies-expected.json').read_text()).items():
    actual = blob(Path(path).read_bytes())
    assert actual == expected, f'{path}: expected {expected}, got {actual}'
    print(f'Verified exact tested source: {path} ({actual})')
