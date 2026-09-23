// The parts of Lexeditor's in-game message that need no device: what is
// queued, how long it holds, how it wraps, where the box sits and how it
// fades. Built and run by tests/ff8_toast_check.py.

#include <cassert>
#include <cstdio>

#include "toast_layout.h"
#include "toast_queue.h"

using namespace lexeditor_toast;

static void wrapping()
{
    const auto lines = wrap("No GF is junctioned to this character. Junction one "
                            "on the Junction screen to use Summon.", 38);
    assert(lines.size() >= 2);
    for (const auto &line : lines) assert(line.size() <= 38);
    // Wrapping happens on spaces, so no word is split when it need not be.
    assert(lines.front().find("No GF is junctioned") == 0);
    // A word longer than the box is cut rather than allowed to run off it.
    const auto forced = wrap("aaaaaaaaaaaaaaaaaaaaaa", 8);
    assert(forced.size() == 3 && forced.front().size() == 8);
}

static void holding()
{
    Queue queue;
    assert(queue.update(1000) == nullptr);
    queue.push("first");
    queue.push("first");            // the same sentence twice does not stack
    assert(queue.pending() == 1);
    const Toast *showing = queue.update(1000);
    assert(showing != nullptr && showing->lines.front() == "first");
    // It stays up for its whole hold, however many frames ask.
    assert(queue.update(1000 + DEFAULT_HOLD_MS - 1) != nullptr);
    assert(queue.update(1000 + DEFAULT_HOLD_MS) == nullptr);
    queue.push("second");
    assert(queue.update(9000)->lines.front() == "second");
    queue.clear();
    assert(!queue.showing() && queue.pending() == 0);
    // A caller firing every frame cannot hold the screen for a minute.
    for (int index = 0; index < 50; ++index) {
        queue.push(std::string("message ") + std::to_string(index));
    }
    assert(queue.pending() <= MAX_PENDING);
}

static void placement()
{
    Metrics metrics;
    const Box box = layout(metrics, 2, 38);
    // Inside the frame, above the bottom edge, and centred.
    assert(box.x > 0.0f && box.y > 0.0f);
    assert(box.x + box.width <= metrics.width);
    assert(box.y + box.height <= metrics.height);
    const float left = box.x, right = metrics.width - (box.x + box.width);
    assert(left > right - 0.5f && left < right + 0.5f);
    assert(box.text_x > box.x && box.text_y > box.y);
    // A sentence too wide for the frame is clamped, not hung off the edge.
    const Box wide = layout(metrics, 1, 400);
    assert(wide.x >= 0.0f && wide.x + wide.width <= metrics.width);
    // Two lines are taller than one.
    assert(layout(metrics, 2, 10).height > layout(metrics, 1, 10).height);
}

static void fading()
{
    assert(fade(0.0f) == 0.0f);
    assert(fade(0.5f) == 1.0f);
    assert(fade(1.0f) == 0.0f);
    // Flat through the middle: the sentence is readable, not pulsing.
    assert(fade(0.3f) == 1.0f && fade(0.7f) == 1.0f);
    assert(fade(-1.0f) == 0.0f && fade(2.0f) == 0.0f);
    float previous = 0.0f;
    for (float step = 0.0f; step <= FADE_IN; step += FADE_IN / 8.0f) {
        const float now = fade(step);
        assert(now >= previous);
        previous = now;
    }
}

int main()
{
    wrapping();
    holding();
    placement();
    fading();
    std::puts("FF8 toast: wraps to the box, holds long enough to read, "
              "sits above the bottom edge and fades only at the ends.");
    return 0;
}
