from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/verify_ff7_rendered_neutral.py"
text = path.read_text(encoding="utf-8")
old = '''    self.navigate("weapons")
    self.page.get_by_label("Materia AP growth for Record0", exact=True).select_option("2")
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertEqual(data['records']['weapons'][0]['values']['growthRate'],2)
'''
new = '''    self.navigate("weapons")
    weapon_id=self.page.evaluate("state.selected.weapons")
    self.page.get_by_label(f"Materia AP growth for Record{weapon_id}", exact=True).select_option("2")
    self.save()
    status,data=self.backend.request('/api/data');self.assertEqual(status,200)
    self.assertEqual(data['records']['weapons'][weapon_id]['values']['growthRate'],2)
'''
if old not in text:
    raise SystemExit("FF7 selected-weapon semantic assertion anchor changed")
path.write_text(text.replace(old,new,1), encoding="utf-8")
