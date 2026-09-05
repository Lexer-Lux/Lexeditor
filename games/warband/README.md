# Warband plugin

This directory contains the Warband plugin for Lexeditor. It uses the shared
WebView2 host and the shared components under `C:\Lexeditor\ui`. It defines its
own parchment and burgundy theme, page layout, data service, and parsers.

The plugin includes item, manual, troop-tree, troop, tweak, settings, and build
pages. The header `?` opens the Warband Data Map; there is no Data tab. Its
four columns show the filename, purpose, notes, and Lexeditor edit status.
Click an integrated Python source filename to open the existing validated
source editor. The old Tkinter editor has been retired. `app.py` is only a
compatibility launcher into the shared host.

From `C:\Lexeditor`:

```powershell
.\.venv\Scripts\python.exe app.py --game warband
.\.venv\Scripts\python.exe app.py --game warband --check
.\.venv\Scripts\python.exe app.py --game warband --smoke
```

The smoke check uses a temporary copy of `settings.ini`. It does not change the
live Warband project.

Paths default to the Steam Warband install and
`C:\Users\Lexer\Warbandmod`. Override them with
`LEXEDITOR_WARBAND_ROOT`, `LEXEDITOR_MOD_PROJECT`, and `LEXEDITOR_OUT`.
