def reveal_detail_control(page, control):
    pager = page.locator('#main .lex-detail-panel .lex-tweaks-pages').first
    pager.wait_for(state='attached')
    if not control.count() or not control.is_visible():
        first = pager.get_by_role('button', name='First page', exact=True)
        if first.count() and not first.is_disabled():
            first.click()
    for _ in range(30):
        if control.count() and control.is_visible():
            return
        next_page = pager.get_by_role('button', name='Next page', exact=True)
        assert next_page.count() and not next_page.is_disabled(), 'Detail control is unreachable'
        next_page.click()
        page.wait_for_timeout(80)
    assert control.is_visible()
