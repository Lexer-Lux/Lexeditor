import subprocess

PAYLOAD_COMMIT = "ab1d2398235aba282bab231d60e9b8eb1a87e962"
subprocess.run(
    ["git", "fetch", "--depth=12", "origin", "feature/bannerlord-plugin"],
    check=True,
)
payload = subprocess.check_output(
    ["git", "show", f"{PAYLOAD_COMMIT}:tools/temp_bannerlord_final_hardening.py"],
    text=True,
)
old = '''    if count != 1:\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    path.write_text(text.replace(old, new, 1), encoding="utf-8")\n'''
new = '''    if count < 1:\n        raise SystemExit(f"{label}: expected a match, found {count}")\n    if count != 1 and not label.endswith(" read"):\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    path.write_text(text.replace(old, new, 1), encoding="utf-8")\n'''
if payload.count(old) != 1:
    raise SystemExit("could not patch final hardening matcher")
payload = payload.replace(old, new, 1)
exec(compile(payload, "temp_bannerlord_final_hardening_payload.py", "exec"))
