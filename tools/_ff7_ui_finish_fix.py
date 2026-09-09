"""Small follow-up for the FF7 UI one-shot before verification."""
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'games/ff7/editor.html'
text=path.read_text(encoding='utf-8')
old='''      detailSection({title:"GAME TEXT",attrs:{"data-concept":"text-editor"},help:infoHelp(semanticHelp(field)),body:el("div",{style:"padding:10px;min-width:0"},control)}),'''
new='''      detailSection({title:"GAME TEXT",attrs:{"data-concept":"text-editor"},help:(semanticHelp(field)?infoHelp(semanticHelp(field)):null),body:el("div",{style:"padding:10px;min-width:0"},control)}),'''
if text.count(old)!=1: raise SystemExit(f'text detail marker count {text.count(old)}')
path.write_text(text.replace(old,new),encoding='utf-8')
