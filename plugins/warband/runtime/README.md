# Lexeditor-managed WSE2 package

`wse2-1.1.5.1-lex1.zip` is physically bundled with Lexeditor. Installing it is
an offline operation. It is a custom **package**, not a claim to have rebuilt
or forked the closed engine source. The publisher's engine, Steam and runtime
component bytes are unchanged. Attribution: Warband Script Enhancer 2,
Ruslan-700 / K700 and its upstream contributors. Upstream remains the authority
for engine licensing, support and third-party component notices.

Source: https://github.com/Ruslan-700/WSE2-Releases/releases/tag/v1.1.5.1
Publisher artifact: `WSE2.zip`, published 2026-08-28.
The complete upstream artifact digest and every included member's SHA-256 are
recorded in `manifest.json`. `tools/build_wse2_bundle.py` reproduces this archive
byte-for-byte from that exact artifact without downloads or executable launches.
ZIP_STORED, a fixed timestamp, fixed permissions and sorted paths avoid compressor
or platform dependent output.

Package differences from upstream: exclude `wse2_launcher.exe` (the updater),
all dedicated servers, PDB debug symbols, batch launchers and DLC module shader
overrides. Retain both engine architectures, their Steam/API and audio/Lua
libraries, AppID 48700, common shader resources, language files and SDK sources.
No fonts, game dumps, stock game executable, stock `steam_api.dll` or user mod
files are bundled. The installer backs up shared shader/runtime files before
replacing them. It does not delete an independently installed WSE/WSE2 launcher;
Lexeditor never invokes that launcher and detects drift before Play.

Updating the upstream pin or this package requires an explicit reviewed change
to the artifact, manifest, package checksum and tests together. An upstream
version check has no ability to install or select another package.
