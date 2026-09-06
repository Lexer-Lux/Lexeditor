# Lexeditor UI manual

This manual defines the shared UI language. A game plugin supplies data and a
theme. It must not rebuild these controls for each page.

## Panels and composition

A **panel** is one bounded content surface. A page composes one or more panels.
Every pair of adjacent panels gets the shared resize handle automatically.
Right-click resets a handle to that page's default.

Panel spacing is one responsive percentage. The same value applies between a
panel and the window edge, between adjacent panels, and between the tab bar and
page content. This keeps the visual rhythm stable on different screen sizes.

The shared composer sizes the content, not an empty footer. A full fixed list
divides its available height between its configured rows. A short list can end
after its last row. Filtering does not change the configured row height.

Blank Game is the unthemed framework gallery. Its one-, two-, and three-panel
tabs show the shared composer without a game theme. Its Subtabs page shows the
shared nested-navigation control. Use these pages to diagnose shared defaults
before adding or changing a game-specific override.

## Subtabs

A **subtab bar** navigates related views inside one top-level tab. It uses the
shared `subtabBar()` control, keyboard focus, selected state, and theme tokens.
A plugin supplies only the labels, current subtab, and change callback. It must
not copy a top-level tab bar or create unrelated private button styling.

## Table panels

A **Table panel** is a record list with columns. It supplies:

- sorting from every sortable header;
- drag-and-drop column order;
- columns controlled by pins in the related Detail panel;
- fixed row geometry during search;
- pagination without a vertical scrollbar;
- wheel navigation between pages;
- a per-page row override in Developer Mode.

The selected FF8 record uses an overlaid hand. The hand does not take layout
space or move header text.

Numeric columns use **magnitude alignment**. Values align on the decimal
boundary. Larger integer magnitudes extend to the left. Fractional precision
extends to the right. For example, `100`, `10`, and `0.9999` keep the same
decimal boundary instead of using simple right alignment.

## Detail panels

A **Detail panel** edits one selected record. It has one identity heading and
groups of rows. Every row uses the same label-to-value division. A plugin can
change that division for a page, but individual rows do not choose unrelated
positions.

A group title is an in-flow divider in the neutral shared theme. A game theme
can deliberately overlap it with the group border, as FF8 does, without
changing the shared structure. Fields can contain text, numbers, booleans,
flags, references, Thing Selectors, or compact custom controls.

Each pinnable field has a pin at the top-right of its control. A filled pin
means that the field is visible as a Table column. Clicking it removes the
column. Hovering an unpinned field shows the available pin. Column changes
re-fit the Table and panel divider.

## Vanilla and reference values

A **ref rail** shows only values that differ from the current value.
`V` means Vanilla. Other short tags name reference mods. Clicking a reference
restores that displayed value. Booleans display a check or an X, not their raw
stored number or the words `true` and `false`.

A ref rail is a vertical stack with at most four sources. Vanilla is
always first and green. At most three reference mods can follow it: the first
is red, the second is blue, and the third is yellow. A plugin must reject a
fourth active reference mod instead of clipping, wrapping, or hiding it.

The ordinary rail reserves space to the right of a field. It does not move the
field when a reference appears.

An **internal-ref box** puts the rail inside the field's right edge. The field
is wider and reserves that internal space from the start. A unit suffix moves
left when the rail is visible, so the reference remains to the right of the
unit. Multiple reference values become smaller and can stack within the same
reserved area. FF8 Hit Rate uses two linked internal-ref boxes: percent and
raw value out of 255.

Reference values always use the same player-facing format as the live value.
An enum shows its name. An item shows its icon and name. A boolean shows a
check or X. A transformed number shows its transformed unit.

## Units and booleans

A unit is part of its field. It can be a suffix such as `%`, `/255`, `G`, or
`×`, or a prefix when the game requires one. Unit placement is shared so game
fonts cannot create local alignment errors.

Every stored variable must be presented in the most human-friendly control available, not in its raw storage encoding. Booleans are normally checkboxes or compact checkless toggles, never numeric 0/1 fields. Bitfields and flag bytes are decomposed into one property made from named checkboxes, enums, and other meaningful controls; raw bytes or integers are only acceptable when no more legible representation exists.

## Thing Selectors and Searchers

A **Thing Selector** replaces a small drop-down when a field refers to another
record. It shows the current record's player-facing display and a magnifying
glass immediately after the text. It uses all available cell width without a
nested decorative box.

Activating it starts a **Searcher**. Lexeditor opens the target Table, blocks
ordinary navigation, and explains what to select. Holding a result fills its
row background without covering its content. Completion returns to the source
field. Cancel returns without a change. The context control can move between
the source and target while Searcher mode stays active.

## Hoverables and help

A **hoverable** looks and behaves like a link to another editable record. The
same linked record has the same hover behavior in every list, Table, Detail
panel, and reference display.

Help uses a filled circular **info bubble** (`?`). The component shape and interaction are
shared. Its glyph uses the active game's font when that font contains a usable
question mark.

## Projects and Vanilla

The project selector lists Vanilla first, then editable mods. Vanilla is the
unchanged extracted baseline and is read-only. The first save from Vanilla asks
to create an editable mod. A new mod name can use a suggestion from
`ui/assets/mod_names.json`. Each editable mod has a rename action.

This workflow needs a game-specific baseline adapter because each game stores
and builds mods differently. A plugin must not call an editable working folder
"Vanilla" unless its data is proven unchanged.

## Setting scopes

The settings grid has three ordered scopes from left to right:

- **User** settings change only the current installation.
- **Developer** settings expose diagnostics and development tools. They do not
  authorize GitHub or distributable changes.
- **Lexer** settings change checked-in defaults that ship to every user.

The `authorized GitHub identity` control is available only when GitHub reports Lexer's allowed
account as the active account. Developer Mode gives each setting a second control
in the Lexer color. This control sets the packaged default. Double-clicking a
setting name or description copies its current value into that default control.
The new default becomes distributable only after the changed default file is
included in a release.

`Loading screen minimum` is a Lexer setting. It sets the shortest time that a
game-loading screen remains visible. It does not cap real loading time: a game
that needs longer stays on the loading screen until its plugin finishes.

`Volume level` is also a Lexer setting. The live interface uses that packaged
value directly; an old personal settings file cannot override it. Zero prevents
new theme sounds and stops sounds already playing. The percentage uses a
perceptual squared-gain curve, so very low values are genuinely quiet.

Holding right-click on a page tab to save its layout for everyone is a Lexer
authoring action. Developer Mode alone cannot authorize it. Ordinary page and
setting changes stay local.

## Setting dependencies

A setting can declare another setting as a requirement. Turning the requirement
off disables its dependents and remembers only the dependent values that this
action turned off. Turning the requirement on restores those remembered values.
A dependent that the user turned off manually stays off.

Hovering either related setting draws a semi-transparent flowing arrow from the
requirement control to its dependent control. This shows both what the setting
controls and what it requires without permanent connector clutter.


## Shared interaction standards

### Human-friendly variable controls

The editor displays the *meaning* of a value rather than its serialization. Use checkboxes for ordinary booleans and **checkless toggles** when the surrounding control already supplies an unambiguous on/off state. Split bitflags into named checkbox/enum controls inside one property. Do not expose 0/1, bit masks, bytes, or packed integers when a safer semantic control can represent them.

### Info bubbles and ref rails

The circular `?` is the **info bubble**. It is geometrically centered in its circle and occupies the shared label/ref area without displacing the property name. The **ref rail** is the stable comparison lane for Vanilla and reference mods. Vanilla is `V`; Lexer's mod is always `LL` and lime green. Ref rails reserve their space even when the current value matches, so editing cannot move the live control.

### Model preview drawer

A model-capable Detail uses the shared `modelPreview` slot. The header icon is the preview button. Clicking it slides the preview drawer out over the Detail body; while open, an `×` occupies exactly the same icon slot and closes the drawer. Plugins provide model data/rendering only. They do not create a second preview-panel interaction.

### Table editing and property linking

There is one Table type. Any cell whose column declares an editor is editable by double-click in place; entering edit mode must not change the cell font, row height, column width, padding, or overall geometry. A separate “Editable Table” type is forbidden. Hovering a column highlights its matching Detail property and hovering the property highlights the column. A hovered column/property also highlights itself when no counterpart exists.

### Detail labels

The Detail property-name region is 10% of the panel. Property names and labels inside grouped boolean boxes may wrap and automatically reduce type size to fit their existing box, but they must not increase the row height. Sorting indicators never replace or hide the property name or info bubble.

### Graphs

Graph titles are large and uppercase. There is one title only. Axis names and numeric range labels live in the graph margins; every right-axis text element, including range numbers, is rotated 90° counter-clockwise. Formula text uses natural glyph proportions and is never stretched or squashed to follow the curve. Variable controls live in a drawer that slides in from the top.
