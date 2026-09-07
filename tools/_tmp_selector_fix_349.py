from pathlib import Path
p=Path('tests/global_controls_check.py')
s=p.read_text('utf-8')
old="unit=page.locator('.lex-unit').bounding_box();box=page.locator('.lex-unit-field').bounding_box()"
new="unit=page.locator('.lex-unit-field:has(#quantity) .lex-unit').bounding_box();box=page.locator('.lex-unit-field:has(#quantity)').bounding_box()"
if old not in s:
    raise SystemExit('unit locator anchor missing')
p.write_text(s.replace(old,new,1),'utf-8')
