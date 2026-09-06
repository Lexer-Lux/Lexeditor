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

Ref-rail values always use the same player-facing format as the live value.
An enum shows its name. An item shows its icon and name. A boolean shows a
check or X. A transformed number shows its transformed unit.

## Units and booleans

A unit is part of its field. It can be a suffix such as `%`, `/255`, `G`, or
`×`, or a prefix when the game requires one. Unit placement is shared so game
fonts cannot create local alignment errors.

Every variable uses the most human-friendly semantic control available; its raw
storage representation is an implementation detail, not UI. Booleans are normally
checkboxes. A **checkless toggle** is the compact on/off alternative when a checkbox
would add visual noise. A stored `0/1` is never exposed as a numeric field. Enums
show named choices. Bitflags are decomposed into a property group of checkboxes,
checkless toggles and/or enum controls as appropriate; never expose a whole flag
byte or integer merely because that is how the game stores it. Raw numbers are for
values that are genuinely numeric to a human.

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

An **info bubble** is the filled circular `?` beside a property. Its circle,
glyph, placement and interaction are shared. It is centred in the metadata space
between the panel edge and the property label, and its glyph is centred inside the
circle.

## Projects and Vanilla

The project selector lists Vanilla first, then editable mods. Vanilla is the
unchanged extracted baseline and is read-only. The first save from Vanilla asks
to create an editable mod. A new mod name can use a suggestion from
`ui/assets/mod_names.json`. Each editable mod has a rename action.

This workflow needs a game-specific baseline adapter because each game stores
and builds mods differently. A plugin must not call an editable working folder
"Vanilla" unless its data is proven unchanged.

## Developer Mode

Lexeditor has one privileged mode: **Developer Mode**. It activates automatically
only when the active GitHub CLI account is the authorized `Lexer-Lux` account and
is not a user preference. Developer Mode exposes diagnostics, the embedded GitHub
workspace, helper/version authoring, distributable defaults and shared layout
authoring. Signing out (or switching GitHub accounts) disables those privileges.
There is no separate Lexer Mode.

Holding right-click on a page tab to save its layout for everyone is therefore a
Developer Mode authoring action. Ordinary page and setting changes remain local.

## Model preview drawer

A Detail panel can declare an optional **model preview drawer**. The standard
header icon is its open control. Activating that icon slides the preview out from
the Detail panel; while open, an `×` occupies exactly the same header-icon slot
and closes it. Plugins provide only the preview content/lifecycle callbacks. They
must not invent a separate preview-panel type or a different close position.

## Setting dependencies

A setting can declare another setting as a requirement. Turning the requirement
off disables its dependents and remembers only the dependent values that this
action turned off. Turning the requirement on restores those remembered values.
A dependent that the user turned off manually stays off.

Hovering either related setting draws a semi-transparent flowing arrow from the
requirement control to its dependent control. This shows both what the setting
controls and what it requires without permanent connector clutter.
