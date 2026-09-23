#pragma once
// Messages Lexeditor shows inside FF8, in FF8's own style rather than the
// host's debug overlay.
//
// FFNx's popup was the only thing available and it is the wrong shape for this:
// it fades on an accelerating decay tuned for "aspect ratio changed", so a
// sentence explaining why a migration was refused is off the screen before it
// can be read, and it looks like the injector rather than like the game.
//
// This is the part of a toast that has nothing to do with drawing: what is
// queued, how long each message holds, how it wraps into the game's message
// width, and which one is on screen at a given millisecond. Keeping it separate
// is what makes it testable without a running game, and what lets the renderer
// hook be small.

#include <algorithm>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

namespace lexeditor_toast {

// FF8's message boxes are sized in characters, not pixels, and its own
// notifications sit near this width before they wrap.
constexpr std::size_t DEFAULT_COLUMNS = 38;
// Long enough to read a full sentence; a caller that wants longer says so.
constexpr std::uint32_t DEFAULT_HOLD_MS = 6000;
constexpr std::uint32_t MIN_HOLD_MS = 1000;
constexpr std::uint32_t MAX_HOLD_MS = 30000;
// A queue is not a log. Past this the oldest waiting message is dropped, so a
// runaway caller cannot hold the screen for a minute.
constexpr std::size_t MAX_PENDING = 8;

enum class Tone { normal, warning };

struct Toast {
    std::vector<std::string> lines;
    Tone tone = Tone::normal;
    std::uint32_t hold_ms = DEFAULT_HOLD_MS;
    std::uint32_t shown_at = 0;
    bool started = false;
};

// Break text into lines that fit the message width, on spaces where possible.
// A word longer than the whole width is cut rather than allowed to run off the
// edge, because FF8's box does not scroll.
inline std::vector<std::string> wrap(const std::string &text, std::size_t columns) {
    const std::size_t width = columns ? columns : DEFAULT_COLUMNS;
    std::vector<std::string> lines;
    std::string line;
    std::string word;
    auto flush_word = [&]() {
        if (word.empty()) return;
        while (word.size() > width) {
            if (!line.empty()) { lines.push_back(line); line.clear(); }
            lines.push_back(word.substr(0, width));
            word.erase(0, width);
        }
        if (line.empty()) { line = word; }
        else if (line.size() + 1 + word.size() <= width) { line += ' '; line += word; }
        else { lines.push_back(line); line = word; }
        word.clear();
    };
    for (const char c : text) {
        if (c == ' ') { flush_word(); continue; }
        if (c == '\n') { flush_word(); lines.push_back(line); line.clear(); continue; }
        word += c;
    }
    flush_word();
    if (!line.empty()) lines.push_back(line);
    if (lines.empty()) lines.emplace_back();
    return lines;
}

inline std::uint32_t clamp_hold(std::uint32_t hold_ms) {
    if (hold_ms == 0) return DEFAULT_HOLD_MS;
    return std::clamp(hold_ms, MIN_HOLD_MS, MAX_HOLD_MS);
}

class Queue {
public:
    explicit Queue(std::size_t columns = DEFAULT_COLUMNS) : columns_(columns ? columns : DEFAULT_COLUMNS) {}

    // Queue a message. The same message asked for twice in a row is not shown
    // twice: a hook that fires every frame would otherwise stack one sentence
    // eight deep.
    void push(const std::string &text, Tone tone = Tone::normal,
              std::uint32_t hold_ms = DEFAULT_HOLD_MS) {
        if (text.empty()) return;
        Toast toast;
        toast.lines = wrap(text, columns_);
        toast.tone = tone;
        toast.hold_ms = clamp_hold(hold_ms);
        if (!pending_.empty() && pending_.back().lines == toast.lines) return;
        if (current_.started && current_.lines == toast.lines) return;
        pending_.push_back(std::move(toast));
        while (pending_.size() > MAX_PENDING) pending_.pop_front();
    }

    // What is on screen at this millisecond, or nothing. Call every frame.
    const Toast *update(std::uint32_t now_ms) {
        if (current_.started) {
            const std::uint32_t elapsed = now_ms - current_.shown_at;
            if (elapsed < current_.hold_ms) return &current_;
            current_ = Toast{};
        }
        if (pending_.empty()) return nullptr;
        current_ = pending_.front();
        pending_.pop_front();
        current_.shown_at = now_ms;
        current_.started = true;
        return &current_;
    }

    // How far through its hold the message is, from 0 to 1. The renderer uses
    // it to fade the last fraction rather than cutting the box off mid-read.
    float progress(std::uint32_t now_ms) const {
        if (!current_.started || current_.hold_ms == 0) return 0.0f;
        const std::uint32_t elapsed = now_ms - current_.shown_at;
        return std::clamp(static_cast<float>(elapsed) /
                          static_cast<float>(current_.hold_ms), 0.0f, 1.0f);
    }

    void clear() { pending_.clear(); current_ = Toast{}; }
    std::size_t pending() const { return pending_.size(); }
    bool showing() const { return current_.started; }

private:
    std::size_t columns_;
    std::deque<Toast> pending_;
    Toast current_;
};

}  // namespace lexeditor_toast
