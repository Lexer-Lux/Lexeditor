"""Compile and exercise the in-game toast queue.

The drawing belongs to the renderer hook. What is checked here is everything
that decides what a reader sees and for how long: wrapping into FF8's message
width, holding long enough to read, one message at a time, and a hook that
fires every frame not being able to stack the same sentence eight deep.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'plugins/ff8/ffnx_toasts/toast_queue.h'

CASES = r'''
#include <cassert>
#include <iostream>
#include <string>
#include "toast_queue.h"
using namespace lexeditor_toast;

int main() {
    // Wrapping breaks on spaces and never runs past the box.
    const std::string sentence =
        "Shared Magic cannot start because a private Magic slot is invalid. "
        "No Magic was changed.";
    const auto lines = wrap(sentence, 38);
    assert(lines.size() > 1);
    for (const auto &line : lines) assert(line.size() <= 38);
    std::string rejoined;
    for (const auto &line : lines) { if (!rejoined.empty()) rejoined += ' '; rejoined += line; }
    assert(rejoined == sentence);

    // A word wider than the box is cut rather than allowed to overflow it.
    const auto cut = wrap(std::string(90, 'x'), 20);
    assert(cut.size() == 5);
    for (const auto &line : cut) assert(line.size() <= 20);

    // An explicit break is kept.
    const auto broken = wrap("first\nsecond", 38);
    assert(broken.size() == 2 && broken[0] == "first" && broken[1] == "second");

    // Nothing on screen until something is queued.
    Queue queue;
    assert(queue.update(0) == nullptr);
    assert(!queue.showing());

    // A message holds for its whole duration and then leaves.
    queue.push("Held long enough to read.", Tone::warning, 6000);
    const Toast *shown = queue.update(1000);
    assert(shown != nullptr);
    assert(shown->tone == Tone::warning);
    assert(queue.showing());
    assert(queue.update(1000 + 5999) != nullptr);
    assert(queue.update(1000 + 6000) == nullptr);
    assert(!queue.showing());

    // The fade fraction runs from nothing to all of it.
    Queue fading;
    fading.push("Fading", Tone::normal, 4000);
    fading.update(0);
    assert(fading.progress(0) == 0.0f);
    assert(fading.progress(2000) > 0.4f && fading.progress(2000) < 0.6f);
    assert(fading.progress(9000) == 1.0f);

    // A hook that fires every frame cannot stack one sentence.
    Queue repeated;
    for (int i = 0; i < 500; ++i) repeated.push("Same sentence every frame.");
    assert(repeated.pending() == 1);
    repeated.update(0);
    for (int i = 0; i < 500; ++i) repeated.push("Same sentence every frame.");
    assert(repeated.pending() == 0);

    // Different messages queue and come out in order, one at a time.
    Queue several;
    several.push("First message.");
    several.push("Second message.");
    several.push("Third message.");
    assert(several.pending() == 3);
    const Toast *first = several.update(0);
    assert(first->lines.front() == "First message.");
    assert(several.pending() == 2);
    assert(several.update(100)->lines.front() == "First message.");
    const Toast *second = several.update(DEFAULT_HOLD_MS);
    assert(second->lines.front() == "Second message.");

    // A runaway caller cannot hold the screen for a minute.
    Queue flooded;
    for (int i = 0; i < 40; ++i) flooded.push("Message " + std::to_string(i));
    assert(flooded.pending() == MAX_PENDING);

    // A hold outside what a reader can use is brought back into range, and an
    // unspecified one takes the default rather than vanishing instantly.
    assert(clamp_hold(0) == DEFAULT_HOLD_MS);
    assert(clamp_hold(1) == MIN_HOLD_MS);
    assert(clamp_hold(9999999) == MAX_HOLD_MS);

    // An empty message is not a toast.
    Queue empty;
    empty.push("");
    assert(empty.pending() == 0);

    std::cout << "Toast queue: wrapping, hold, fade fraction, per-frame repeats, "
                 "ordering, flood limit and hold bounds passed\n";
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='ff8-toast-') as folder:
        source = Path(folder) / 'toast_cases.cpp'
        binary = Path(folder) / 'toast_cases'
        source.write_text(CASES, encoding='utf-8')
        subprocess.run([
            'g++', '-std=c++20', '-Wall', '-Wextra', '-O2',
            '-I', str(HEADER.parent), str(source), '-o', str(binary)
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=15)


if __name__ == '__main__':
    main()
