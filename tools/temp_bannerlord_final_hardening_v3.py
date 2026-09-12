import subprocess

from pathlib import Path

V2_COMMIT = "99ee30c0a339851bd95b1227065974205bc103ee"
subprocess.run(
    ["git", "fetch", "--depth=24", "origin", "feature/bannerlord-plugin"],
    check=True,
)
payload = subprocess.check_output(
    ["git", "show", f"{V2_COMMIT}:tools/temp_bannerlord_final_hardening_v2.py"],
    text=True,
)
exec(compile(payload, "temp_bannerlord_final_hardening_v2_payload.py", "exec"))

# Preserve CRLF byte-for-byte while still letting the MCM field scanner match
# a line ending in \r\n. The lookahead observes (but does not consume) \r.
settings = Path("games/bannerlord/settings_data.py")
text = settings.read_text(encoding="utf-8")
old = '''    rf"(?:[ \\t]*=[ \\t]*(?P<value>[^;\\r\\n]+?))?[ \\t]*;[ \\t]*$"\n'''
new = '''    rf"(?:[ \\t]*=[ \\t]*(?P<value>[^;\\r\\n]+?))?[ \\t]*;[ \\t]*(?=\\r?$)"\n'''
if text.count(old) != 1:
    raise SystemExit(f"settings CRLF field anchor: expected one match, found {text.count(old)}")
settings.write_text(text.replace(old, new, 1), encoding="utf-8")
