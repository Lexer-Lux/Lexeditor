from pathlib import Path

path = Path("tools/temp_bannerlord_source_dialog_hardening.py")
text = path.read_text(encoding="utf-8")
if text.count("page.evaluate('''") != 2:
    raise SystemExit("Expected two embedded page.evaluate triple-quote blocks")
text = text.replace("page.evaluate('''", 'page.evaluate("""')
if text.count("            ''')\\n") != 2:
    raise SystemExit("Expected two embedded page.evaluate closers")
text = text.replace("            ''')\\n", '            """)\\n')
path.write_text(text, encoding="utf-8")
