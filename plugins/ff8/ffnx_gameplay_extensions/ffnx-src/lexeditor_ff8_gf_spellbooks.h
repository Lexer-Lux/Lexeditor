#pragma once

// Loader-owned replacement for the rejected fixed-address GF spellbook cave.
// Installation is guarded against the supported FF8_EN hook bytes and a
// validated direct/lexeditor/gf-spellbooks.bin runtime snapshot.
void lexeditor_ff8_gf_spellbooks_install();
