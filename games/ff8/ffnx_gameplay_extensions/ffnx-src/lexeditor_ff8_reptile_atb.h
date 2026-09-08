#pragma once

// Optional loader-owned runtime for Lexeditor's per-mod Reptile classification.
// The native hook is installed only when direct/lexeditor/reptile-atb.toml is
// present, valid, and enabled.
void lexeditor_ff8_reptile_atb_install();
