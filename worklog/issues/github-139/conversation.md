# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356293234 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139

Created: 2026-08-06T02:17:18Z; updated: 2026-09-05T06:56:59Z

Exact metadata: [source record](sources/issue-5356293234-eef07cb18f121842b4cfc583416fa7876bb6b31454db99cb8923309cd5ce2304.json).

REMOVE THE ONLINE BUTTON — kill the Red Dead Online entry from the pause
     menu so I stop looking at it. There is an existing mod that does exactly
     this (rdr2mods downloads, "Online Button Remover", /rdr2/other/351-);
     install it as-is if it still works on the current game version, otherwise
     do it ourselves.


## issue 5356293234 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139

Created: 2026-08-06T02:17:18Z; updated: 2026-09-06T12:47:15Z

Exact metadata: [source record](sources/issue-5356293234-56b2228f90e8215f8f8fa2ebefc1c840f62ba06b713c6d8830d0fdc8360a75a0.json).

Remove only Online and Social Club; keep the other pause-menu entries intact.

**Status: The installed replacement emptied the entire menu.** A corrected file is prepared but was not installed because builds/installations were on hold. Deliver that correction before requesting another pause-menu test.

## comment 5550120236 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120236

Created: 2026-08-06T05:21:24Z; updated: 2026-08-06T05:21:24Z

Exact metadata: [source record](sources/comment-5550120236-efe3accf55cda6cd67297b59cefa1a9ac726c89d30ab877e35819b498244d9ef.json).

Swarm research completed, but implementation is blocked safely. The 2023 reference mod targets `update:/x64/data/ui/screens/0xA900038B.ymt` and explicitly forbids reupload, modification, or asset reuse. Current vanilla extraction failed with the available RPF tooling, so no stale/guessed override was shipped. Next step: manually export the current vanilla asset through OpenIV while RDR2 is closed, then recreate and validate the narrow Online-button removal from that file. Full hashes and extraction evidence are recorded in `worklog/issues/github-39.md`.

## comment 5550120243 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120243

Created: 2026-08-10T12:32:23Z; updated: 2026-08-10T12:32:23Z

Exact metadata: [source record](sources/comment-5550120243-87d038cee00860ae1bb69367c4e0c183a043e4826478c55f27c26cde0ba0d00f.json).

While you're at it delete the social club button too

## comment 5550120255 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120255

Created: 2026-08-17T03:40:57Z; updated: 2026-08-17T03:40:57Z

Exact metadata: [source record](sources/comment-5550120255-4051b88a1b3d0757d182f2db96b4be81c28bc42410b6fd5097763830a032ed34.json).

The extraction blocker is fixed. The reader was skipping 256 payload bytes on signature-protected entries; it now keeps the recorded offset and removes only the trailing signature allowance. Lexeditor RpfCli 1.1 extracted and decoded the current ROOT_INDEX asset, and the new isolated package removes exactly Online and Social Club while preserving the other ten pause items. It is built but not installed, so this is actionable until installation is authorized.

## comment 5550120271 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120271

Created: 2026-08-19T12:34:18Z; updated: 2026-08-19T12:34:18Z

Exact metadata: [source record](sources/comment-5550120271-b17b67c4888da3ea9715668f456cac4e850ce0e787d39c5f4639666b94caa1cb.json).

**The package was built on 2026-08-15 and never installed, because nothing in the install pipeline knew it existed.**

`RemovePauseButtons/` has been sitting complete in the repo the whole time: `install.xml` plus the rebuilt `data/ui/screens/0xA900038B.ymt`. `Install-When-RDR2-Closes.ps1` had no entry for it, so every install since then quietly skipped it. That, not the extraction work, is why the buttons are still on screen.

Verified the asset directly rather than trusting the worklog:

- SHA-256 `17A5FF7D95A9953675463A7F1DB4116D568D72DEBF64FF8B7C30038F12BDBC3C`, matching the recorded hash exactly.
- Parses as XML, and the pause items are: **MAP, HUB, HELP, PROG, ABIL, PLYR, GAME, STORE, SET, QUIT** — ten entries, in order.
- `PM_SCR_MIS` (Online) and `PM_SCR_SOC` (Social Club) are both absent. Social Club removal is per Lexer's comment on this issue, not an assumption.
- Rebuilt from the CURRENT extracted `ROOT_INDEX`, not from the restricted 2023 reference mod, so no third-party asset is redistributed.

Both files are now installed by `Install-When-RDR2-Closes.ps1` into `lml/RemovePauseButtons/`. `mods.xml` is deliberately NOT edited — LML registers a new folder itself on the next launch (`Crime Tweaks` is currently on disk and not yet listed, which is that mechanism mid-flight), and mods.xml is the loader's file, not ours.

Not installed yet only because RDR2 was running when the install ran; the installer aborts rather than touching a live game folder.

**Acceptance, and one falsifiable check worth doing given Lexer-Lux/Lexeditor#194.** LML silently discarding a package is exactly what Lexer-Lux/Lexeditor#194 turned out to be, and it went unnoticed for three attempts because nobody read the loader's own log. So after the next launch:

```
grep -i removepausebuttons "<game>/vfs.log"
```

A line means LML bound the replacement; no line means it did not, regardless of what the pause menu looks like. Then in Story Mode: open Pause, confirm Online and Social Club are gone, the other ten entries still select and navigate, Back resumes, and reopening Pause is stable.


## comment 5550120295 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120295

Created: 2026-08-20T06:15:00Z; updated: 2026-08-20T06:15:00Z

Exact metadata: [source record](sources/comment-5550120295-9a988c4fbef7d3f22c29ac3b9bd427df1150c77adc161123e0a20089cc6d5a10.json).

<img width="829" height="1440" alt="Image" src="https://github.com/user-attachments/assets/4ae637fa-160a-4ba7-b647-aea133192a89" />

WTF DID YOU DO THE WHOLE THING IS EMPTY NOW EVERY SINGLE BUTTON IS GONE

## comment 5550120309 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/139#issuecomment-5550120309

Created: 2026-08-20T07:18:32Z; updated: 2026-08-20T07:18:32Z

Exact metadata: [source record](sources/comment-5550120309-86dc785739c7b655f074e662701e24486604c90095e09fa9f3bb6d94814c38ad.json).

The empty pause menu came from the replacement file format. LML loaded the file, but it was XML; the current game asset is binary RBF, so the game received an empty screen stack. I replaced it with a valid binary RBF file that removes only Online and Social Club and keeps the other ten entries in their original order. The independent parser, byte round-trip, focused contract, and known-bad mutations pass. I did not install it because the build and installation are on hold, so the game still has the old file and this remains actionable.
