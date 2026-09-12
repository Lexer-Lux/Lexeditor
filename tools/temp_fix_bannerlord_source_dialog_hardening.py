from pathlib import Path

path = Path("tools/temp_bannerlord_source_dialog_hardening.py")
text = path.read_text(encoding="utf-8")
if text.count("page.evaluate('''") != 2:
    raise SystemExit(f"Expected two embedded page.evaluate triple-quote blocks, found {text.count(\"page.evaluate('''\")}")
text = text.replace("page.evaluate('''", 'page.evaluate("""')
if text.count("            ''')\\n") != 2:
    raise SystemExit(f"Expected two embedded page.evaluate closers, found {text.count(\"            ''')\\\\n\")}")
text = text.replace("            ''')\\n", '            """)\\n')
path.write_text(text, encoding="utf-8")
