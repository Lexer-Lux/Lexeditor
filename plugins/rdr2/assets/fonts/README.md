# RDR2 fonts

Lexeditor uses these game-specific fonts:

- `Redemption.woff` or a private `Redemption.ttf` for the LEXEDITOR title,
  section headings, and display text
- `RDRLino-Regular.rockstar.woff2` or a private
  `RDRLino-Regular.woff2` for ordinary RDR2 interface text and controls

The release does not bundle these binaries. When a file is missing, Lexeditor
downloads the matching webfont from Rockstar's official media host. It checks
the file type and pinned SHA-256 value before it installs the file. The main
menu shows the installed count. Opening RDR2 downloads missing files
automatically, and the font button retries the download.

A failure does not prevent the editor from opening. The RDR2 skin uses its
system-font fallback and writes the error to
`C:\Lexeditor\logs\font-download.log`.

Downloaded files and private alternatives are ignored by Git. Do not add them
to a public source or release bundle without permission from the rights holder.
