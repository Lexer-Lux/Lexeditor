from pathlib import Path

path=Path(__file__).resolve().parents[1]/'games/ff7/kernel_extra.py'
text=path.read_text(encoding='utf-8')
old="""        kernel.sections[18]=bytearray(pack_strings(next_names));kernel.sections[10]=bytearray(pack_strings(next_descriptions));return
"""
new="""        if next_names!=names:kernel.sections[18]=bytearray(pack_strings(next_names))
        if next_descriptions!=descriptions:kernel.sections[10]=bytearray(pack_strings(next_descriptions))
        return
"""
if new not in text:
    if old not in text:raise SystemExit('Limit text preservation insertion point changed')
    text=text.replace(old,new,1)
path.write_text(text,encoding='utf-8')
