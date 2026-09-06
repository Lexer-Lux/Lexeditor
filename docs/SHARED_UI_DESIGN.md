# Shared UI and formula proposals

Open **Blank → Design Review**. Both examples are in-memory; none of their controls
save preferences, change game data, launch games, or replace a real plugin's layout.
The existing Blank Graphs tab remains available for current shared graph behavior.

## Shared layout (#99)

**A — Separate preview lane.** The top command row places the mod selector at left
and Undo, Redo, Save and Play together at right. The next row holds game tabs, with
Tweaks distinct and last. Below, list, properties and collapsible model preview
have separate lanes. Hiding the preview returns its width to properties. On a
narrow window the preview moves below the properties. This favors simultaneous
model inspection and editing, at the cost of less property width when open.

**B — Property-first.** Keep the same command/utility placement, but use only two
horizontal lanes: list and properties. Put the collapsible preview below the
properties. This favors long names and wide fields, at the cost of scrolling to
inspect a model. In both alternatives, circular Help, Information and Settings
buttons are grouped immediately beside the window controls. Identity is shown
once in each relevant region; field controls remain in the details.

Select a record, change layout, and hide/show the preview to compare actual space.
Choose A or B, or specify a combination, before changing the production shell.
The preview is a labeled location placeholder, not a newly implemented 3D engine.

## Formula typography (#299)

**A — Stacked fraction and raised power** gives numerator and denominator their own
lines. It distinguishes grouping well but needs more vertical clearance.
**B — Inline fraction and raised power** preserves a compact single line but is
less clear for long or nested fractions. Both inherit the active typeface, have a
transparent background and shadow, and follow a movable curve point/tangent.
Minimum and maximum labels use the same font, weight and shadow. No opaque box
or centered formula panel is introduced.

Use the multiplier and label-position sliders to compare the formula near different
slopes. The example is deliberately bounded; production rollout must also test long
expressions, nested fractions, extreme slopes, zoom and game font metrics. Select
a presentation first. Existing game graphs have not been silently restyled.
