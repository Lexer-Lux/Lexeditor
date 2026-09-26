#pragma once
// Where a Lexeditor toast sits on screen, and how it fades.
//
// Separated from the drawing for the same reason the queue is: this part can
// be reasoned about and tested without a device, a frame, or a running game.
// Everything here is in the game's own pixels - FF8 renders at a fixed size
// and the renderer projects those coordinates onto the window - so a box laid
// out here lands in the same place whatever the window is doing.

#include <algorithm>
#include <cstddef>

namespace lexeditor_toast {

// Lexer asked for the game's own notice: the wide silver box across the top
// of the screen that battle uses for "Received ..." and ability names. It
// spans nearly the whole frame, sits just below the top edge, and is padded
// inside by about one character.
constexpr float TOP_MARGIN = 0.02f;      // of the game's height
constexpr float SIDE_MARGIN = 0.02f;     // of the game's width
constexpr float PADDING_CHARS = 1.0f;
constexpr float PADDING_LINES = 0.5f;
// The last fraction of the hold fades out, and the first fraction fades in, so
// a message never appears or vanishes between one frame and the next.
constexpr float FADE_IN = 0.05f;
constexpr float FADE_OUT = 0.12f;

struct Metrics {
    float width = 640.0f;        // the game's own frame, in its own pixels
    float height = 480.0f;
    float line_height = 20.0f;   // one line of text
    float char_width = 9.0f;     // one character at that size
};

struct Box {
    float x = 0.0f, y = 0.0f, width = 0.0f, height = 0.0f;
    float text_x = 0.0f, text_y = 0.0f;
};

// The box is always the full width between the margins, like the game's
// top notice, and as tall as the text. Its text is centred.
inline Box layout(const Metrics &metrics, std::size_t lines, std::size_t columns)
{
    const float padding_x = metrics.char_width * PADDING_CHARS;
    const float padding_y = metrics.line_height * PADDING_LINES;
    const float limit = metrics.width * (1.0f - 2.0f * SIDE_MARGIN);
    Box box;
    box.width = limit;
    box.height = static_cast<float>(lines ? lines : 1) * metrics.line_height
        + 2.0f * padding_y;
    box.x = (metrics.width - box.width) * 0.5f;
    box.y = metrics.height * TOP_MARGIN;
    const float text_width = std::min(limit - 2.0f * padding_x,
        static_cast<float>(columns) * metrics.char_width);
    box.text_x = box.x + (box.width - text_width) * 0.5f;
    box.text_y = box.y + padding_y;
    return box;
}

// Opacity from 0 to 1 for a message that is `progress` of the way through its
// hold. Flat in the middle: the point of the queue was that a sentence stays
// readable, so only the ends move.
inline float fade(float progress)
{
    progress = std::clamp(progress, 0.0f, 1.0f);
    if (progress < FADE_IN) return progress / FADE_IN;
    if (progress > 1.0f - FADE_OUT) return (1.0f - progress) / FADE_OUT;
    return 1.0f;
}

}  // namespace lexeditor_toast
