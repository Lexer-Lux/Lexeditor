# #80 — Improved Interface

## 2026-09-06 — upstream audit, no fake feature toggle

Read the pinned launcher Steam preset and Control/Interface configuration
structures. Existing features include DialogProgressButtons, TurboDialog,
PSXBattleMenu, ThickerATBBar, menu/detail layout and text-fade settings.
Findings and pinned references: `codex/ff9-memoria-integration.md`.

Important differences: DialogProgressButtons advances messages, so adding Circle
there is not reveal-only behavior. The documented turbo hold uses Shift+Confirm
or Right Bumper+Confirm, not the requested Square-only mapping. Layout settings
are not proof of the requested full-row ATB/Trance and HP/MP bars.

Status: actionable. Full launcher/input behavior audit, new history and HUD
hooks, action-time drain and durable Tetra Master opponent state remain. No
runtime implementation or in-game verification is claimed, and no misleading
all-in-one checkbox was added. Better Eat (#83) remains explicitly parked.
