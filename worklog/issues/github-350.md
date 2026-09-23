# Issue 350 — Skip the startup epilepsy warning (toggle)

## Requirements
Default-off toggleable tweak that skips the epilepsy warning in the normal
startup path. No unconditional suppression. Disabling restores the warning.
Preserve Fast Start behavior.

## Findings (static analysis, 2026-09-22)
- Owner: `FF8_Launcher.exe`, not the game. It embeds a Qt `NoticeWindow`
  (`Notice`, `NoticeWindowJa1/Ja2`, `videoNoticeLbl`, `okButton`, `es/de/it/fr`
  language buttons) with `notice/notice_{en,fr,it,de,es}.html` resources.
  English text verified at file offset 0x5AE7DF: "A very small percentage
  of people may experience a seizure...".
- `FF8_EN.exe` (22 MB) contains no epilepsy/seizure strings: the game itself
  shows no warning.
- No acceptance persistence exists: no QSettings, no registry keys, no
  agreed/accepted/don't-show strings. The notice shows on every launcher run.
- No existing warning-suppression code in the plugin (searched plugins/ff8).
- Lexeditor launches `FF8_EN.exe` directly and never runs the launcher, so
  its path already avoids the warning — but nothing disables the warning
  itself, exactly as the issue states.

## Why this needs Lexer
The only skip mechanism is a binary patch to `FF8_Launcher.exe` (Qt C++,
no settings hook). That touches a Steam-verified executable and cannot be
verified headless: confirming the skip and the restore needs a visible
launcher run, which needs explicit approval.

## Next work
Waiting on the checklist posted to the issue.

## Correction to the prior handoff note
The earlier stub said plugin.py launches through FF8_Launcher.exe. Current
code shows no game-process launch through the launcher (server.py only
references the exe names for process status; the plugin launches FF8_EN.exe
directly). The launcher-bypass avoidance stands, verified.
