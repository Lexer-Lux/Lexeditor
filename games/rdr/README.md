# Lexeditor RDR plugin

This managed plugin uses the RDR2 plugin contract and visual language. It
detects Steam app 2668510, reads `game/tune_d11generic.rpf` through the local
RPF6 read-only bridge, and prepares data in Lexeditor's private local cache.

Saving a file never writes to the prepared cache or installed archive. It
creates the matching override below `C:\RDRMod\mod\tune_d11generic`.
