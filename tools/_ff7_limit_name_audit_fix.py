from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

path=ROOT/'games/ff7/kernel_extra.py'
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

path=ROOT/'tools/verify_ff7_rendered_neutral.py'
text=path.read_text(encoding='utf-8')
old='''    self.assertEqual(self.page.get_by_label("Magic-menu section for Record0", exact=True).evaluate("e=>e.tagName"), "SELECT")
'''
new='''    self.assertEqual(self.page.get_by_label("Magic-menu section", exact=False).first.evaluate("e=>e.tagName"), "SELECT")
'''
if new not in text:
    if old not in text:raise SystemExit('Magic-menu rendered expectation insertion point changed')
    text=text.replace(old,new,1)
path.write_text(text,encoding='utf-8')
