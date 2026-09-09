Open-source, plugin-based mod editor with the goal of making it fun and easy for anyone to create and share mods for their favorite games. 

Currently supports:
* Final Fantasy VII
* Final Fantasy VII Remaster
* Final Fantasy VII Remake Intergrade
* Final Fantasy VIII
* Final Fantasy IX
* Mount & Blade: Warband
* Red Dead Redemption
* Red Dead Redemption 2

Coming soon:
* Final Fantasy IV
* Grand Theft Auto V
* Palworld
* Mount And Blade II: Bannerlord

## Install and start

Run this once to create the private Python environment and the Desktop and
Start Menu shortcuts:

    powershell -ExecutionPolicy Bypass -File install.ps1

Then start `Lexeditor.cmd`. You can also select a game directly:


## Make a game plugin

[Make a game plugin](docs/ADDING_A_GAME.md) is the research-first development
playbook: find and reuse existing open-source knowledge before reverse-engineering,
define loader/project/conflict boundaries, prove one end-to-end edit, preserve
unknown data, fill Credits and Mod Loading, verify each acceptance level, and keep
a new plugin in one implementation PR by default.
