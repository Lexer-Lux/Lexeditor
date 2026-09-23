// GPL-3.0-or-later. Temporary shop listing; saved shop records stay unchanged.
#pragma once
#include "flare_item.h"
#include <array>

namespace lexeditor_flare {
inline constexpr std::uint32_t all_shops = (1u << 20) - 1;
inline constexpr unsigned shop_stock = 100;
struct ShopRow { std::uint8_t id, available; };
static_assert(sizeof(ShopRow) == 2, "Stock shop row layout changed");
struct ShopView {
    // The existing cursor and sell view already support 198 rows. Keep empty
    // padding for every cursor position; do not read into the staged inventory.
    std::array<ShopRow, 198> rows{};
    unsigned pages = 2;
    bool added = false;
};

inline bool make_shop_view(const ShopRow (&stock)[16], bool offer,
                           unsigned availability, ShopView &out) {
    if (offer && (availability == 0 || availability > 100)) return false;
    unsigned end = 0;
    for (unsigned i = 0; i < 16; ++i) {
        if (stock[i].id >= item_id) return false;
        if (stock[i].id) end = i + 1;
    }
    ShopView prepared;
    for (unsigned i = 0; i < 16; ++i) prepared.rows[i] = stock[i];
    if (offer) {
        prepared.rows[end] = {static_cast<std::uint8_t>(item_id),
                              static_cast<std::uint8_t>(availability)};
        prepared.added = true;
        prepared.pages = end >= 16 ? 3 : 2;
    }
    out = prepared;
    return true;
}
} // namespace lexeditor_flare
