# FF8 altered content (issue #319)

Optional restoration targets for the supported 2013 Steam /
old-PC-lineage English release. Remastered-only changes are out of scope.

## Restoration targets (Lexer-approved policy)

For targets 1-4, use uncensored textures from existing uncensor mods,
credit the authors, and ship them as Lexeditor mod content:

1. Gerogero battle model: blue organs to original Japanese red
   (`battle.fs` / `battle\c0m034.dat`).
2. Gerogero Card-menu art: blue to red (`menu.fs` / `menu\mc05.tex`).
   Must not blindly replace the in-match Triple Triad path, which is
   already red on original PC.
3. Ultimecia Castle Armory wall blood: green to red
   (`field.fs` / `field\mapdata\fe\febarac1.fs`, field `febarac1`).
4. General Caraway armband: blue to red (field-character texture/model).

Status: no 2013-Steam/old-PC-lineage uncensor mod with confirmed
redistribution rights has been found (only PSX-lineage or
Remastered-only releases), so no bytes are vendored. Blocked on
uncensor-mod archives plus per-target rights, or approval to extract
deltas from Lexer's own Japanese + Steam installs.

## Nunchaku check (verified 2026-09-23)

The Steam-English source already says `nunchaku`; there is no `shinobou`
string to restore. Decoded `mngrp.bin` hits: Weapon Monthly `nunchaku`
mentions (sections 38:14, 38:38, 38:48) and the test-seed question
`Selphie's weapon is the nunchaku` (45:2). No `nunchak`/`shinob` spelling
occurs anywhere in `FF8_EN.exe` or decoded `mngrp.bin`. No rename is
exposed: nothing differs from the requested wording.

## Not restoration candidates

- Siren's extra feathers: Remastered-only; nothing to restore in 2013.
- Selphie Scan rotation lock: same restriction across versions as far as
  known; the lock location (exe address or menu script) is still unknown.
- Devour's `Censored... please stand by` gag: intentional in every version.

## Safe implementation rule

Never commit or redistribute Square's Japanese game assets. Restorations
are optional per-mod FFNx overrides with strict source hashes and
rollback; never rewrite base archives in place.
