"""Visual QA matrix (docs/DESIGN.md section 10): screenshots of the main screens in Arabic/English x themes x sizes x widths x states.
Not a pass/fail test: a person (or the reviewing agent) looks at the pictures. Output: tests/visual/out/ (git-ignored).

  SBO_PWLIB=<folder with playwright> python3 tests/visual/matrix.py [--quick]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ui_harness as ui  # noqa: E402

OUT = os.path.join(HERE, 'out')
THEMES = ['morning', 'evening', 'navy', 'navynight', 'contrast']


def main(quick=False):
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    srv = ui.new_server('matrix')
    fresh = ui.new_server('matrix-fresh', with_owner=False)
    try:
        with sync_playwright() as pw:
            br = ui.launch(pw)

            def open_page(lang, theme, w, h, size='m', login=True, base=None, tour='done', density='comfortable'):
                ctx = br.new_context(viewport={'width': w, 'height': h})
                pg = ctx.new_page()
                pg.add_init_script("localStorage.setItem('sbo.prefs.v1', JSON.stringify(%s))" % (
                    '{"lang":"%s","theme":"%s","size":"%s","tour":"%s","density":"%s"}' % (lang, theme, size, tour, density)))
                pg.goto((base or srv.base) + '/')
                if login:
                    pg.wait_for_selector('.auth')
                    pg.fill('input[autocomplete=username]', ui.ADMIN[0])
                    pg.fill('input[type=password]', ui.ADMIN[1])
                    pg.click('button[type=submit]')
                    pg.wait_for_selector('.sidebar')
                return ctx, pg

            def shot(pg, name):
                pg.wait_for_timeout(450)
                pg.screenshot(path=os.path.join(OUT, name + '.png'))

            themes = ['morning', 'evening'] if quick else THEMES
            for lang in ('ar', 'en'):
                for theme in themes:
                    ctx, pg = open_page(lang, theme, 1360, 860, login=False)
                    pg.wait_for_selector('.auth')
                    shot(pg, f'{lang}-{theme}-login')
                    pg.fill('input[autocomplete=username]', ui.ADMIN[0])
                    pg.fill('input[type=password]', ui.ADMIN[1])
                    pg.click('button[type=submit]')
                    pg.wait_for_selector('.sidebar')
                    shot(pg, f'{lang}-{theme}-today')
                    pg.goto(srv.base + '/#/settings')
                    pg.wait_for_selector('.settings-grid')
                    shot(pg, f'{lang}-{theme}-settings')
                    ctx.close()
            for lang in ('ar', 'en'):
                for w, h in ((1920, 1000), (1024, 768), (768, 1024), (390, 844)):
                    ctx, pg = open_page(lang, 'morning', w, h)
                    shot(pg, f'{lang}-w{w}-today')
                    pg.goto(srv.base + '/#/settings')
                    pg.wait_for_selector('.settings-grid')
                    shot(pg, f'{lang}-w{w}-settings')
                    if w == 390:
                        pg.click('.topbar .only-mobile')
                        shot(pg, f'{lang}-w{w}-drawer')
                    ctx.close()
                # extra large text and compact density
                ctx, pg = open_page(lang, 'morning', 1360, 860, size='xl')
                shot(pg, f'{lang}-xl-today')
                ctx.close()
                ctx, pg = open_page(lang, 'morning', 390, 844, size='xl')
                shot(pg, f'{lang}-xl-w390-today')
                ctx.close()
                ctx, pg = open_page(lang, 'morning', 1360, 860, density='compact')
                pg.goto(srv.base + '/#/settings')
                pg.wait_for_selector('.settings-grid')
                shot(pg, f'{lang}-compact-settings')
                ctx.close()
                # states: palette, tour, shortcuts sheet, offline banner, error, loading skeleton, wizard
                ctx, pg = open_page(lang, 'morning', 1360, 860)
                pg.keyboard.press('Control+k')
                pg.wait_for_selector('.palette')
                shot(pg, f'{lang}-state-palette')
                pg.keyboard.press('Escape')
                pg.keyboard.press('?')
                shot(pg, f'{lang}-state-shortcuts')
                pg.keyboard.press('Escape')
                pg.goto(srv.base + '/#/nowhere')
                pg.wait_for_selector('.error-box')
                shot(pg, f'{lang}-state-notfound')
                pg.goto(srv.base + '/#/help')
                pg.wait_for_selector('.grid-2')
                shot(pg, f'{lang}-state-help')
                pg.keyboard.press('Control+k')
                ctx.set_offline(True)
                pg.keyboard.type('ab')
                pg.wait_for_selector('.banner.bad')
                shot(pg, f'{lang}-state-offline')
                ctx.close()
                ctx, pg = open_page(lang, 'morning', 1360, 860, tour='todo')
                pg.wait_for_selector('.tour-pop')
                shot(pg, f'{lang}-state-tour1')
                pg.click('.tour-pop .btn.primary')
                shot(pg, f'{lang}-state-tour2')
                ctx.close()
                ctx, pg = open_page(lang, 'morning', 1360, 860, login=False, base=fresh.base)
                pg.wait_for_selector('.auth .kind-card')
                shot(pg, f'{lang}-wizard1')
                ctx.close()
            br.close()
    finally:
        srv.stop()
        fresh.stop()
    print('screenshots in', OUT, len(os.listdir(OUT)))


if __name__ == '__main__':
    main('--quick' in sys.argv)
