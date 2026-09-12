// GPL-3.0-or-later. Portable definition overlay; contains no stock game data.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace lexeditor_flare {
inline constexpr unsigned item_id = 199;
inline constexpr unsigned buy_price_gil = 200;
inline constexpr unsigned sell_multiplier = 10; // Native twentieths: 100 Gil resale.
inline constexpr std::size_t stock_metadata_size = 199 * 4;
// Direct native byte-ID readers have no length guard. Reserve the whole byte
// domain, with inert records for unallocated IDs, without changing save slots.
inline constexpr std::size_t overlay_metadata_size = 256 * 4;
inline constexpr unsigned char item_name[] = {0x57,0x67,0x65,0x6C,0x5F,0x6A,0x20,0x4A,0x6A,0x5F,0x70,0x63,0};
inline constexpr unsigned char item_description[] = {
    0x57,0x72,0x5F,0x70,0x72,0x71,0x20,0x5F,0x20,0x70,0x5F,0x6C,
    0x62,0x6D,0x6B,0x20,0x63,0x6C,0x61,0x6D,0x73,0x6C,0x72,0x63,
    0x70,0x20,0x67,0x6C,0x20,0x72,0x66,0x63,0x20,0x61,0x73,0x70,
    0x70,0x63,0x6C,0x72,0x20,0x5F,0x70,0x63,0x5F,0x3B,0};

inline bool make_metadata(const void *stock, std::size_t size, void *destination,
                          std::size_t capacity) {
    // Do not silently take ID 199 from another mod's expanded definitions.
    if (!stock || !destination || size != stock_metadata_size ||
        capacity < overlay_metadata_size) return false;
    auto *out = static_cast<unsigned char *>(destination);
    std::memmove(out, stock, size);
    for (unsigned id = item_id; id < 256; ++id) {
        out[id * 4] = 10; // Stock inert/refine-only dispatch, no character target.
        out[id * 4 + 1] = out[id * 4 + 2] = out[id * 4 + 3] = 0;
    }
    // The menu-use owner enables Signal Flare only after the transition/count path
    // is installed. Never let a custom type enter the stock dispatch tables.
    return true;
}

inline bool make_prices(const void *stock, std::size_t size, void *destination,
                        std::size_t capacity) {
    if (!stock || !destination || size != stock_metadata_size ||
        capacity < 200 * 4) return false;
    std::memmove(destination, stock, size);
    // Native shop initialization reads 200 rows, although stock has 199.
    // Stock prices store tens of Gil and a resale multiplier in twentieths.
    auto *price = static_cast<unsigned char *>(destination) + size;
    price[0] = (buy_price_gil / 10) & 0xff;
    price[1] = (buy_price_gil / 10) >> 8;
    price[2] = sell_multiplier;
    price[3] = 0;
    return true;
}
} // namespace lexeditor_flare
