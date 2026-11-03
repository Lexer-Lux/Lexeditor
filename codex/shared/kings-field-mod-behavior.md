# King's Field mod behavior contract

Use Japanese numbering: KF1 is the 1994 Japanese game; KF2 is the game released
as King's Field in the US (SLUS-00158); KF3 is US King's Field II (SLUS-00255).
This page defines the agreed behavior, not an implementation-completion claim.
Per-game evidence and remaining work belong in the game's worklog.

## Shared behavior and units

| Mod | Contract |
| --- | --- |
| Red N | Color only the compass N red. Keep its placement, visibility and other compass parts unchanged. |
| Better Poison | Independent flash peak intensity and frequency settings. Preserve native poison damage. Defaults must be less intense and less frequent than the previous implementation. A real cure can notify; death, reload, respawn, New Game and disabling the mod must not produce a cure notification. |
| XP Bar | Height in native render pixels, default 4, bounded 1–16. Keep full viewport width and anchor the bottom edge to the absolute screen bottom. Respect the game's HUD visibility and packet allocation. |
| Better Crystals | Intercept the actual Dragon Crystal auto-revive decision before consumption. Show the actual current count and offer Revive or reload the actual last save. Display current OK/cancel bindings, including keyboard equivalents. Revive follows native consumption and recovery. Reload performs a load, never a save, and does not consume a crystal in the abandoned state. |
| Better Sprint | “Do not consume magic energy” defaults on where running actually consumes a magic-power gauge. This does not mean MP. Preserve physical-power settings and movement-only charging. At exhaustion, latch running off until release and a fresh run press; regeneration while held must not restart it. |
| Forget Me Not | Small visible world sprite glints, with sensible surface placement, size and occlusion. White for unfinished loot, red after an actual locked attempt. Containers clear after confirmed empty search or taking contents; merely opening and declining/full pickup leaves a white glint. Successful unlocking clears red back to white until loot is resolved. Real doors clear after successful opening. Preserve save identity and never mark illusory walls. Object tinting is not a substitute. |
| Hit Feedback | Peak red strength = clamp(1 − HP after hit / max HP, 0, 1) × configured intensity. Default intensity 50%, range 0–100%. Duration = min(actual HP lost / max HP, 1) × maximum flash duration; maximum defaults to 0.6 seconds, range 0–5. Tween red strength to zero over that duration. |
| illusory wall | Exact lowercase display name. Three independently combinable booleans: on use, on attack, walk through. Preserve the native hidden-wall identification and keep it separate from exploration glints. |

For Hit Feedback, a target at 25% remaining HP with a 50% setting starts at
37.5% red strength. Losing 10% of maximum HP with a 1-second maximum gives a
0.1-second pulse. Each new damaging hit replaces the current pulse, using the
new post-hit HP and that hit's actual loss; pulses do not add or saturate.
Healing and zero damage do not start a pulse. Linked body parts resolve to the
native owner. Restore all lighting/color state after each affected draw.

Red strength mixes the final textured, lit and fogged RGB toward pure red
`(255, 0, 0)` before the renderer's output quantization. Preserve texture holes,
alpha, blending and depth. Multiplying a texture's lighting colour is insufficient:
a green texel with no red channel stays non-red under multiplication. Keep the
HP/timer policy in the mod; any required renderer API only carries the captured
per-model colour and strength. Per-game renderer support must be explicit.

For sprint, holding a controller button or keyboard key across exhaustion must
behave identically. Stationary frames do not charge movement-based drain. Death,
load, New Game, menu transitions and disable clear owned transient work without
turning a still-held input into a fresh run press. Native recovery remains active.
KF1 uses weapon power and its agreed default physical drain is zero; an
inapplicable magic-energy option must be documented rather than inventing an MP
cost. KF2's native running charges both 5000-point physical and magic power by
500 per 15 Hz tick (150% of a full gauge per second); its MP is a separate value.

KF2's former poison flash starts at a 2400/4096 Q12 intensity coefficient
(about 58.6% of that coefficient's full scale) on each native poison-damage
event, 0.5 Hz. Its revised defaults are a 35% peak coefficient and 0.25 Hz.
This coefficient scales incoming color; it is not a measured absolute screen
opacity. Keep units explicit and distinguish visual frequency from the unchanged
native damage cadence. Other games must measure their own native cadence instead
of copying KF2 addresses or assuming the same timer.

## Lifecycle and storage

Transient flashes, synthetic confirmations and pending choices are owned by one
mod and cleared on disable/load/New Game. Save-scoped exploration persists only
against the correct card, slot and save identity. A failed or unavailable load
must not overwrite a card or silently convert to a save.

Native source ports use their actual writable default mods folder through the
shared native adapter. For KF2 this is `LocalAppData/Verdite2/mods`, or
`VERDITE2_DATA/mods` when the same explicit override applies to the native port
and editor. `content/mods` seeds bundled mods; it is not the writable player
library. A mod is one folder with root `mod.json`; enablement comes from native
loader flags. Do not keep a second active Documents library or a second copy of
the same native ID. Move only after content/identity checks and with the game
closed, preserving saves, settings, existing native mods and current switches.

## Architecture boundary

Share behavior, formulas, units, settings controls and lifecycle policies where
they agree. Lexeditor already shares `core/native_source_mods.py`,
`core/native_port_settings.py` and `ui/native-port.js`; fix those components
instead of adding per-game editors. Native source-mod APIs are similar, but
addresses, record layouts, message encoding, input masks, collision semantics and
render submission differ. Keep those facts in game-specific adapters and prove
them against that game's routines. A copied address or condition is not a port.

For example, KF2's native pickup itself requires `record+0x38 == 0xFF`; a sibling
game's retail-record fix does not justify removing that guard here.

Runtime acceptance includes installed release behavior and actual rendered
effects. Counters and settings bounds alone do not prove visible extra scenery
or a sprite's placement/occlusion. Private tests must disable audio before
startup and verify absent audio output, isolate physical input, use copied saves,
and clean their entire owned process tree on success, failure and timeout.
