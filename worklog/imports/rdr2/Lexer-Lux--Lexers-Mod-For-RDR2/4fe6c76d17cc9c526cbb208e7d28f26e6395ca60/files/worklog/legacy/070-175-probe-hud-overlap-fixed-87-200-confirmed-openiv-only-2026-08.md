# Worklog: 070 175 Probe Hud Overlap Fixed 87 200 Confirmed Openiv Only 2026 08

## #175 probe HUD overlap fixed; #87/#200 confirmed OpenIV-only — 2026-08-04

StealthProbe build `95B61D5C45BC41C318F39702542B92EF2E84C762580540F0C85FE98075D08C9F`.

#175 HUD. `drawHud()` advanced y by 0.035 per line, which is smaller than the
default HUD text height, so every line rendered over the one above it — visible
in Lexer's screenshot, where the title and the instruction line were unreadable.
Measured against that screenshot: 0.048 clears it. Comment left in place so the
next person does not re-tighten it.
The harness REPLACEMENT still requires the game running and is not attempted
unattended.
The stale prompt text said "follow the yellow line" although the probe draws no
line; both the HUD prompt and QUESTS handoff now say "follow the on-screen
instruction". Rebuilt and hash-verified into the game root for the next restart.

#87 / #200 — CLI route closed off conclusively.
`Rpf8Extract` cannot resolve a PLAIN path in ANY archive, not just the nested
encrypted one. Tested and all missed:
  common_0.rpf :: data/ai/weaponcomponents.meta
  update_1.rpf :: common/packs/base/data/ai/weaponcomponents.meta
  update_1.rpf :: common/data/ai/weaponcomponents.meta
  update_4.rpf :: x64/data/ui/blipdata.ymt
Also probed update_3/update_4/common_0/data_0 for the `dlcpacks` 004 layer under
three path forms — no hits. The ONLY thing that ever resolved was the top-level
hashed entry `0x800AFF13.rpf`, so every entry name is hashed and the scheme is
not plain JOAAT of the name or of the virtual path (both tested earlier).
Conclusion: #87's vanilla 003 layer and #200's packed UI texture dictionaries
both require OpenIV. Not an assumption — four archives x multiple path forms.

Worth trying for #200 when OpenIV is available: the #8 result shows that once a
texture is extracted, our own `lex_blips.ytd` pipeline can ship and register it
without any further engine support. So #200 is purely an EXTRACTION problem now,
not a registration one.

