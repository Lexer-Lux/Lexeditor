# RDR1 issue #341

## 2026-09-06

Reproduced decimal PriceModifier failure: Python float64 input 1.1 differs from WGD float32 readback, and the old path published before reporting failure. Fixed canonical comparison, shortest round-trip decimal display, and unpack/full-byte verification before backup/publish. Tests corrupt an unedited byte and preserve both override and prior backup. Codec fixtures do not prove RSC85/game delivery. Named shop/item, actual deployment/revert and game check remain incomplete.

Branch: `fix/rdr1-editor-runtime-handoff`.


## Preserved source records

[Full request and discussion archive](github-341/conversation.md)
