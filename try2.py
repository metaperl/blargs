__author__ = 'anicca'

import blargs


with blargs.Parser(locals()) as p:
    p.str('username')
    p.str('password')
    p.config('conf').required()
    p.flag('surf')
    p.flag('buy_pack')
    p.flag('stayup')
    #p.int('surf_amount').default(10)

with Browser() as browser:
    browser.driver.set_window_size(1200, 1100)
    e = Entry(username, pasword, browser)

    e.login()

    if surf:
        e.view_ads(surf_amount)
    if buy_pack:
        e.buy_pack()
    if stayup:
        loop_forever()
