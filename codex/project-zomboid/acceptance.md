# Installed-game acceptance

Project Zomboid's synthetic service smoke is necessary but not sufficient for final plugin acceptance. The real acceptance boundary uses an actual installed Windows Build 42 game and a Lexeditor-owned deployment under the user's `Zomboid/mods/` tree.

Run the passive preflight from the repository root:

```text
python -m games.project_zomboid.acceptance --game-root "C:\\Program Files (x86)\\Steam\\steamapps\\common\\ProjectZomboid" --project-root "C:\\path\\to\\mod-project"
```

`--user-root` is optional and defaults to `LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT` or `~/Zomboid`. The game and project arguments can likewise come from `LEXEDITOR_PROJECT_ZOMBOID_ROOT` and `LEXEDITOR_PROJECT_ZOMBOID_PROJECT`.

The preflight is non-destructive. It verifies:

- the selected game root exists and contains `ProjectZomboid64.exe` plus `media/scripts`;
- the source project has a readable `mod.info` with non-empty `name` and `id`;
- Lexeditor still owns the current deployment according to its recorded file hashes;
- the recorded deployment target is exactly `<user-root>/mods/<project-folder-name>` and is not a symlink;
- the deployed `mod.info` name/id match the source project;
- the deployed ZedScript tree can still be inventoried without structural parse errors.

A successful preflight only means the filesystem/runtime handoff is ready for a human in-game test. It does **not** prove that Project Zomboid discovered, enabled, or loaded the mod.

Final installed-game acceptance still requires:

1. Launch the validated current Build 42 stable installation.
2. Confirm the deployed mod appears in Project Zomboid's Mods UI and enable it.
3. Start or load a disposable test world with the mod enabled.
4. Exercise representative edited content from the deployed project.
5. Treat a missing mod, script load error, or incorrect edited behavior as a failed installed-game acceptance.

This separation is deliberate: Lexeditor can prove the files it owns and the structure it emitted, but only Project Zomboid can prove that the live game accepted and executed those files.
