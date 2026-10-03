"""Helpers for checks that drive a detail panel whose sections flow into pages.

A detail panel lays its sections out in columns and pages; a property can be on
a later page. A check that wants to click one turns the panel's pages the way
a reader would, instead of assuming the whole record is on screen.
"""


def reveal(page, locator, pages: int = 12):
    """Turn the detail panel's pages until `locator` is visible; return it."""
    for _ in range(pages):
        if locator.count() and locator.first.is_visible():
            return locator.first
        pager = page.locator(".lex-tweaks-pages")
        following = pager.get_by_role("button", name="Next page", exact=True)
        if not following.count() or not following.first.is_enabled():
            break
        following.first.click()
        page.wait_for_timeout(150)
    locator.first.wait_for(state="visible", timeout=2000)
    return locator.first
