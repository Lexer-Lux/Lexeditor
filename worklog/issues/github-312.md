# #312: Finish the fixed character/GF command menu

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/312)

## Requirements and decisions

- The fixed menu must expose Attack, Magic, the character's fixed command, and the learned command from the single junctioned GF.
- Removing the GF must remove its learned command.
- #314 is now acceptance-only; it is no longer the implementation blocker for this issue.

## Current implementation and evidence

- `games/ff8/fixed_command_menu.py` implements the GF learned-command selection and the Siren/Treatment learning gate.
- Switch, Shoot, Defend, Draw, and Summon have concrete sources or custom payloads.
- Rinoa/Angelo is still explicitly unimplemented. That is the remaining functional blocker before #312 can enter player acceptance.

## Next agent work

Determine the correct native Angelo/Combine dispatcher/menu path from executable or source evidence, then implement a guarded candidate with executable-backed tests. Only after those checks pass should #312 move to `untested`.
