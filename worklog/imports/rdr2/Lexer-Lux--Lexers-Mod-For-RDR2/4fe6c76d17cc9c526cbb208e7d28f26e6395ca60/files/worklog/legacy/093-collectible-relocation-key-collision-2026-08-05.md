# Worklog: 093 Collectible Relocation Key Collision 2026 08 05

## Collectible relocation key collision — 2026-08-05

The campsite placement key and nearest-collectible relocation key were both
VK_F3. Campsite placement remains F3; collectible relocation now uses VK_F2,
and the shipped INI documentation matches it.

GameplayTweaks built successfully with the two pre-existing C4838 warnings. The
748032-byte ASI hashes
`A9DF97E5EF17F9AABFB685CE897EB5F4BDE28B641E7C72F3D9FD9F2753317F7D`.
RDR2 was running; corrected watcher PID 406808 will install and hash-verify this
build after exit.

