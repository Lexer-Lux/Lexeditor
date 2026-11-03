"""Helpers for checks that drive a detail panel whose sections flow into pages.

A detail panel lays its sections out in columns and pages; a property can be on
a later page. A check that wants to click one turns the panel's pages the way
a reader would, instead of assuming the whole record is on screen.
"""


def reveal(page, locator, pages: int = 12):
    """Turn the detail panel's pages until `locator` is visible; return it."""
    if locator.count() and locator.first.is_visible():
        return locator.first
    if not locator.count():
        # Role locators omit hidden controls unless include_hidden=True. Keep
        # supporting existing single-pager callers that locate them by role.
        pager=page.locator('.lex-tweaks-pages')
        first=pager.get_by_role('button',name='First page',exact=True)
        if first.count() and first.first.is_enabled():
            first.first.click()
            page.wait_for_timeout(150)
        for _ in range(pages):
            if locator.count():
                break
            following=pager.get_by_role('button',name='Next page',exact=True)
            if not following.count() or not following.first.is_enabled():
                break
            following.first.click()
            page.wait_for_timeout(150)
    locator.first.wait_for(state="attached", timeout=2000)
    # Reach the containing card before turning its own section pages. A global
    # first pager can be disabled while the target's nested pager still has pages.
    roots = locator.first.locator('xpath=ancestor::*[contains(concat(" ",normalize-space(@class)," ")," lex-tweaks-paged ")]')
    for index in range(roots.count()):
        root = roots.nth(index)
        destination = roots.nth(index+1) if index+1 < roots.count() else locator.first
        pager = root.locator(':scope > .lex-tweaks-pages')
        first = pager.get_by_role("button", name="First page", exact=True)
        if first.count() and first.first.is_enabled():
            first.first.click()
            page.wait_for_timeout(150)
        following = pager.get_by_role("button", name="Next page", exact=True)
        for _ in range(pages):
            if destination.is_visible():
                break
            if not following.count() or not following.first.is_enabled():
                break
            following.first.click()
            page.wait_for_timeout(150)
    locator.first.wait_for(state="visible", timeout=2000)
    return locator.first
