from pathlib import Path

path = Path("games/terraria/structured_content.py")
text = path.read_text(encoding="utf-8")
old = '    if v["echoArguments"]: out.append("    caller.Reply(string.Join(" ", args));")\n'
new = '    if v["echoArguments"]: out.append(\'    caller.Reply(string.Join(" ", args));\')\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one generated command echo line, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
