# Dark Souls III PR #493 candidate

This is an isolated source candidate for the open **Dark Souls 3 Plugin** PR.
It is not a replacement for an existing Lexeditor installation.

## Start

1. Extract the artifact to a **new** folder, for example
   \`C:\Temp\Lexeditor-DS3-PR493\`. Do not extract it over \`C:\Lexeditor\`.
2. Have Python 3 installed and internet access available for the first launch.
3. Run \`Run-DS3-Candidate.ps1\`.
4. The script creates \`.venv-ds3-candidate\` inside this extracted folder,
   installs Lexeditor's declared Python requirements once, runs the candidate
   self-check, then opens only the DS3 plugin.
5. In Lexeditor, locate the Steam Dark Souls III installation and create a new
   DS3 mod project somewhere outside the game installation.

The normal \`install.ps1\` is intentionally not used because it targets
\`C:\Lexeditor\`.

## Output and safety

The installed \`Game\Data0.bdt\` is read-only. Save writes only
\`<selected project>\Data0.bdt\`. The plugin does not install a mod loader,
change online/anti-cheat settings, or write game saves/executables.

Follow \`games\ds3\ACCEPTANCE.md\` for the final offline real-game check.
The browser/source test evidence in this artifact is not a substitute for that
in-game acceptance.
