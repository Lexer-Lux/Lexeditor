#pragma once

// Lexeditor's own in-game messages, drawn as FF8 draws its own message boxes
// rather than through FFNx's debug popup.
//
// FFNx's popup was the only surface available and it is the wrong one: it
// fades on an accelerating decay tuned for one-word notices, so a sentence is
// gone before it can be read, and it looks like the injector rather than like
// the game.

#include <cstdint>

// Queue one message. Safe from any thread the game already calls us on, and
// safe before the renderer exists: nothing is drawn until draw() runs.
void lexeditor_ff8_toast_push(const char *text, bool warning = false);

// Draw whatever is showing, inside FFNx's active ImGui frame.
void lexeditor_ff8_toast_draw();

// Tell the renderer whether FFNx must create an ImGui frame for us.
bool lexeditor_ff8_toast_enabled();

// Watch the battle patch's refusal flag and say why Summon was refused.
// Does nothing unless Lexeditor's command-eligibility patch is loaded.
void lexeditor_ff8_toast_poll_battle();

// The sentence a refused Summon shows. Kept beside the code that shows it, and
// asserted against the Python that greys the command.
extern const char *const LEXEDITOR_SUMMON_UNAVAILABLE_REASON;
