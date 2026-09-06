from pathlib import Path

exec(compile(Path('.github/ui-followup.py').read_text(encoding='utf-8'), '.github/ui-followup.py', 'exec'))

path = Path('ui/framework.css')
css = path.read_text(encoding='utf-8')
marker = '/* Keep the Detail header/icon above its body and preview drawer. */'
if marker not in css:
    css += '''

/* Keep the Detail header/icon above its body and preview drawer. */
.lex-detail-panel-heading { position:relative; z-index:21; }
.lex-detail-panel-body { position:relative; z-index:1; }
'''
    path.write_text(css, encoding='utf-8', newline='\n')
