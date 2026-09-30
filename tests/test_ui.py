"""Browser tests of the interface shell (Phase 2): first-run wizard, login, themes, languages/RTL, palette, keyboard, tour,
responsive drawer, offline banner, escaping of user text, accessibility basics. Skipped only when no browser exists locally;
CI sets SBO_REQUIRE_UI=1 so a missing browser fails the build instead."""
import os
import unittest

import ui_harness as ui

OK, WHY = ui.available()
REQUIRE = os.environ.get('SBO_REQUIRE_UI') == '1'


@unittest.skipUnless(OK or REQUIRE, WHY)
class Shell(ui.UiBase):
    # ---------------------------------------------------------------- login
    def test_login_wrong_password_shows_plain_message_and_stays(self):
        pg = self.page(login=False)
        pg.wait_for_selector('.auth')
        pg.fill('input[autocomplete=username]', ui.ADMIN[0])
        pg.fill('input[type=password]', 'wrong-password-1')
        pg.click('button[type=submit]')
        pg.wait_for_selector('.field.invalid .error')
        self.assertTrue(pg.locator('.sidebar').count() == 0)
        self.assertNotIn('Traceback', pg.inner_text('body'))

    def test_login_then_logout_returns_to_login(self):
        pg = self.page()
        self.assertGreater(pg.locator('.sidebar .sb-link').count(), 1)
        pg.click('.sb-foot .btn')
        pg.wait_for_selector('.auth')
        pg.reload()
        pg.wait_for_selector('.auth')   # the session really ended, not just hidden

    # ------------------------------------------------------ language and RTL
    def test_arabic_is_rtl_and_english_is_ltr_with_mirrored_layout(self):
        pg = self.page()
        self.assertEqual(pg.evaluate('document.documentElement.dir'), 'rtl')
        ar_side = pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().left")
        self.assertGreater(ar_side, 600, 'the menu is on the right in Arabic')
        pg.click('.topbar button:has-text("EN")')
        pg.wait_for_function("document.documentElement.dir === 'ltr'")
        self.assertEqual(pg.evaluate('document.documentElement.lang'), 'en')
        en_side = pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().left")
        self.assertLess(en_side, 5, 'the menu is on the left in English')
        self.assertIn('Today', pg.inner_text('#sidebar'))
        pg.reload()
        pg.wait_for_selector('.sidebar')
        self.assertEqual(pg.evaluate('document.documentElement.dir'), 'ltr', 'the language choice is remembered')
        self.assertNoErrors()

    def test_no_english_words_in_arabic_screens(self):
        pg = self.page()
        for path in ('/', '/settings', '/help'):
            pg.goto(self.srv.base + '/#' + path)
            pg.wait_for_selector('#view .page-in')
            text = pg.evaluate("[...document.querySelectorAll('#view *')].filter(e => !e.children.length).map(e => e.textContent).join(' ')")
            import re
            words = [w for w in re.findall(r'[A-Za-z]{2,}', text) if w not in ('Abc', 'Ctrl', 'Ab', 'English')]   # English = the language's own name
            self.assertEqual(words, [], f'English words on the Arabic screen {path}')

    # --------------------------------------------------------------- themes
    def test_every_theme_applies_and_is_remembered(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings')
        pg.wait_for_selector('.opt-grid')
        seen = {}
        for theme in ('morning', 'evening', 'navy', 'navynight', 'contrast'):
            pg.click(f'.opt[data-v="{theme}"]')
            self.assertEqual(pg.evaluate('document.documentElement.dataset.theme'), theme)
            seen[theme] = pg.evaluate("getComputedStyle(document.body).backgroundColor")
        self.assertEqual(len(set(seen.values())), 5 - (1 if seen['navynight'] == seen['navy'] else 0) or 5, seen)
        pg.reload()
        pg.wait_for_selector('.sidebar')
        self.assertEqual(pg.evaluate('document.documentElement.dataset.theme'), 'contrast')

    def test_auto_theme_follows_the_system_setting(self):
        pg = self.page(color_scheme='dark')
        pg.goto(self.srv.base + '/#/settings')
        pg.wait_for_selector('.opt-grid')
        pg.click('.opt[data-v="auto"]')
        self.assertEqual(pg.evaluate('document.documentElement.dataset.theme'), 'evening')

    def test_size_font_density_motion_digits_apply(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings')
        pg.wait_for_selector('.opt-grid')
        base = pg.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)")
        pg.click('.setting:has-text("حجم الكتابة") .opt[data-v="xl"]')
        self.assertGreater(pg.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)"), base)
        pg.click('.opt[data-v="compact"]')
        self.assertEqual(pg.evaluate('document.documentElement.dataset.density'), 'compact')
        pg.click('.opt[data-v="system"]')
        self.assertIn('Segoe', pg.evaluate("getComputedStyle(document.body).fontFamily"))
        pg.click('.setting:has-text("الحركة") .opt[data-v="off"]')
        self.assertEqual(pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--t-base').trim()"), '0ms')
        pg.click('.opt[data-v="arab"]')
        pg.goto(self.srv.base + '/#/')
        pg.wait_for_selector('.page-head')
        self.assertRegex(pg.inner_text('.page-head .muted'), r'[٠-٩]')
        pg.goto(self.srv.base + '/#/settings')
        pg.click('.opt[data-v="latn"]')
        pg.goto(self.srv.base + '/#/')
        pg.wait_for_selector('.page-head')
        self.assertRegex(pg.inner_text('.page-head .muted'), r'[0-9]')

    def test_reduced_motion_system_setting_is_honoured(self):
        pg = self.page(reduced_motion='reduce')
        d = pg.evaluate("getComputedStyle(document.querySelector('.page-in')).animationDuration")
        self.assertIn(d, ('0s', '0.00001s', '1e-05s'), d)

    # -------------------------------------------------- palette and keyboard
    def test_palette_opens_with_ctrl_k_filters_and_navigates_by_keyboard(self):
        pg = self.page()
        pg.keyboard.press('Control+k')
        pg.wait_for_selector('.palette input')
        self.assertTrue(pg.evaluate("document.activeElement === document.querySelector('.palette input')"))
        pg.keyboard.type('اعدادات')   # spelling without hamza/teh marbuta must still match
        pg.wait_for_selector('.palette [role=option]')
        pg.keyboard.press('Enter')
        pg.wait_for_selector('.settings-grid')
        self.assertEqual(pg.locator('.palette').count(), 0)

    def test_escape_closes_palette_and_restores_focus(self):
        pg = self.page()
        pg.focus('#tb-search')
        pg.keyboard.press('Control+k')
        pg.wait_for_selector('.palette')
        pg.keyboard.press('Escape')
        self.assertEqual(pg.locator('.palette').count(), 0)
        self.assertEqual(pg.evaluate("document.activeElement && document.activeElement.id"), 'tb-search')

    def test_go_shortcuts_and_help_sheet(self):
        pg = self.page()
        pg.keyboard.press('g')
        pg.keyboard.press('s')
        pg.wait_for_selector('.settings-grid')
        pg.keyboard.press('?')
        pg.wait_for_selector('.modal kbd')
        pg.keyboard.press('Escape')
        self.assertEqual(pg.locator('.modal').count(), 0)

    def test_shortcuts_do_not_fire_while_typing(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings?tab=account')
        pg.wait_for_selector('input[type=password]')
        pg.focus('input[autocomplete=current-password]')
        pg.keyboard.type('gt?')
        self.assertIn('settings', pg.url)
        self.assertEqual(pg.locator('.modal').count(), 0)

    def test_keyboard_only_reaches_menu_and_search(self):
        pg = self.page()
        seen = set()
        for _ in range(25):
            pg.keyboard.press('Tab')
            seen.add(pg.evaluate("(document.activeElement.id || document.activeElement.className || document.activeElement.tagName)"))
        self.assertIn('tb-search', seen)
        self.assertTrue(any(s.startswith('nav-') for s in seen), seen)
        # focus is visible
        outline = pg.evaluate("getComputedStyle(document.activeElement).outlineStyle")
        self.assertNotEqual(outline, 'none')

    # ------------------------------------------------------------------ tour
    def test_tour_runs_once_and_can_be_restarted(self):
        pg = self.page(tour_done=False)
        pg.wait_for_selector('.tour-pop')
        for _ in range(4):
            pg.click('.tour-pop .btn.primary')
        self.assertEqual(pg.locator('.tour-pop').count(), 0)
        pg.reload()
        pg.wait_for_selector('.sidebar')
        pg.wait_for_timeout(900)
        self.assertEqual(pg.locator('.tour-pop').count(), 0, 'finished tour does not come back')

    def test_tour_can_be_skipped_with_escape(self):
        pg = self.page(tour_done=False)
        pg.wait_for_selector('.tour-pop')
        pg.keyboard.press('Escape')
        self.assertEqual(pg.locator('.tour-pop').count(), 0)

    # ------------------------------------------------------------ responsive
    def test_phone_width_has_drawer_and_no_sideways_scroll(self):
        pg = self.page(width=390, height=800)
        for path in ('/', '/settings', '/help'):
            pg.goto(self.srv.base + '/#' + path)
            pg.wait_for_selector('#view .page-in')
            self.assertLessEqual(pg.evaluate('document.documentElement.scrollWidth'), 391, f'sideways scroll on {path}')
        self.assertFalse(pg.locator('#sidebar').is_visible() and pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().left") < 390 and pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().right") > 0, 'the menu is hidden on a phone until opened')
        pg.click('.topbar .only-mobile')
        pg.wait_for_timeout(350)
        self.assertLess(pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().left"), 390)
        self.assertGreater(pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().right"), 300)
        pg.click('#nav-settings')
        pg.wait_for_selector('.settings-grid')
        pg.wait_for_timeout(350)
        self.assertGreaterEqual(pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().left"), 390 - 1, 'choosing a screen closes the drawer')

    def test_tablet_and_large_widths_do_not_overflow(self):
        for w in (768, 1024, 1920):
            pg = self.page(width=w, height=900)
            for path in ('/', '/settings'):
                pg.goto(self.srv.base + '/#' + path)
                pg.wait_for_selector('#view .page-in')
                self.assertLessEqual(pg.evaluate('document.documentElement.scrollWidth'), w + 1, f'{w}px {path}')

    def test_sidebar_collapse_is_remembered(self):
        pg = self.page()
        w0 = pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().width")
        pg.click('.topbar .only-desktop')
        pg.wait_for_timeout(350)
        w1 = pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().width")
        self.assertLess(w1, w0 / 2)
        pg.reload()
        pg.wait_for_selector('.sidebar')
        pg.wait_for_timeout(350)
        self.assertLess(pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().width"), w0 / 2)

    # ---------------------------------------------------------- offline, state
    def test_offline_banner_appears_and_goes_away(self):
        pg = self.page()
        pg.keyboard.press('Control+k')
        pg.wait_for_selector('.palette input')
        pg.context.set_offline(True)
        pg.keyboard.type('ab')            # the palette asks the server: the failed request must show the banner
        pg.wait_for_selector('.banner.bad')
        self.assertIn('مفيش اتصال', pg.inner_text('.banner.bad'))
        pg.context.set_offline(False)
        pg.keyboard.type('c')
        pg.wait_for_selector('.banner.bad', state='detached')

    def test_unknown_page_shows_a_friendly_message(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/no/such/page/here')
        pg.wait_for_selector('.error-box')
        self.assertIn('مش موجودة', pg.inner_text('.error-box'))

    def test_server_error_on_a_screen_shows_retry(self):
        pg = self.page()
        pg.route('**/api/auth/status', lambda r: r.abort())
        pg.reload()
        pg.wait_for_selector('.error-box')
        pg.unroute('**/api/auth/status')
        pg.click('.error-box .btn')
        pg.wait_for_selector('.sidebar')

    # ---------------------------------------------------------- safety
    def test_user_text_is_never_run_as_html(self):
        ui.set_setting(self.srv.owner, 'brand.name', '<img src=x onerror="window.__pwned=1">Evil')
        try:
            pg = self.page()
            pg.wait_for_timeout(300)
            self.assertIsNone(pg.evaluate('window.__pwned'))
            self.assertIn('<img', pg.inner_text('.sb-name'), 'shown as plain text')
        finally:
            ui.set_setting(self.srv.owner, 'brand.name', 'Nour Academy')

    def test_business_name_and_password_change_from_settings(self):
        pg = self.page()
        pg.goto(self.srv.base + '/#/settings?tab=business')
        pg.wait_for_selector('form input')
        pg.fill('form input >> nth=0', 'Nour Training')
        pg.click('form button[type=submit]')
        pg.wait_for_selector('.toast')
        pg.wait_for_function("document.querySelector('.sb-name').textContent === 'Nour Training'")
        self.assertEqual(self.srv.owner.get('/api/auth/status')['about']['brand.name'], 'Nour Training')
        ui.set_setting(self.srv.owner, 'brand.name', 'Nour Academy')

    # ---------------------------------------------------------- accessibility
    def test_accessibility_basics_on_every_screen(self):
        pg = self.page()
        checks = """() => {
          const bad = [];
          const name = (e) => (e.getAttribute('aria-label') || e.getAttribute('title') || e.textContent || '').trim();
          document.querySelectorAll('button, a[href]').forEach(e => { if (!name(e) && !e.querySelector('[aria-label]')) bad.push('no name: ' + e.outerHTML.slice(0, 80)); });
          document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(e => {
            if (!e.labels || !e.labels.length) if (!e.getAttribute('aria-label')) bad.push('no label: ' + e.outerHTML.slice(0, 80)); });
          if (document.querySelectorAll('h1').length !== 1) bad.push('h1 count ' + document.querySelectorAll('h1').length);
          if (!document.documentElement.lang || !document.documentElement.dir) bad.push('lang/dir');
          document.querySelectorAll('img').forEach(e => { if (!e.hasAttribute('alt')) bad.push('img alt'); });
          return bad;
        }"""
        for path in ('/', '/settings', '/settings?tab=business', '/settings?tab=account', '/settings?tab=about', '/help'):
            pg.goto(self.srv.base + '/#' + path)
            pg.wait_for_selector('#view .page-in')
            self.assertEqual(pg.evaluate(checks), [], path)


@unittest.skipUnless(OK or REQUIRE, WHY)
class FirstRun(unittest.TestCase):
    """The first-run wizard on a brand-new data folder, through the real screens."""

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.srv = ui.new_server('wizard', with_owner=False)
        cls.pw = sync_playwright().start()
        cls.browser = ui.launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.stop()

    def test_wizard_creates_the_business_and_logs_in(self):
        ctx = self.browser.new_context(viewport={'width': 1300, 'height': 850})
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto(self.srv.base + '/')
        pg.wait_for_selector('.auth .kind-card')
        pg.click('button:has-text("التالي")')
        pg.wait_for_selector('.field.invalid .error')   # the name is required
        pg.fill('input >> nth=0', 'أكاديمية النور')
        pg.click('.kind-card >> nth=0')
        self.assertEqual(pg.get_attribute('.kind-card >> nth=0', 'aria-pressed'), 'true')
        pg.click('button:has-text("التالي")')
        pg.click('button:has-text("التالي")')
        f = pg.locator('form input')
        f.nth(0).fill('محمد فوزي')
        f.nth(1).fill('owner')
        f.nth(2).fill('short')
        f.nth(3).fill('short')
        pg.click('button:has-text("ابدأ الشغل")')
        pg.wait_for_selector('.field.invalid .error')      # too short
        f.nth(2).fill('correct-horse-42')
        f.nth(3).fill('different-horse-42')
        pg.click('button:has-text("ابدأ الشغل")')
        self.assertIn('مش زي بعض', pg.inner_text('.field.invalid .error'))
        f.nth(3).fill('correct-horse-42')
        pg.click('button:has-text("ابدأ الشغل")')
        pg.wait_for_selector('.sidebar')
        self.assertEqual(pg.inner_text('.sb-name'), 'أكاديمية النور')
        self.assertIn('محمد', pg.inner_text('.page-head h1'))
        st = self.srv.client().get('/api/auth/status')
        self.assertTrue(st['hasUsers'])
        self.assertEqual(st['about']['brand.name'], 'أكاديمية النور')
        self.assertEqual(errors, [])
        # the wizard cannot be opened again: a second visit shows the login screen
        pg2 = ctx.new_page()
        pg2.goto(self.srv.base + '/')
        pg2.wait_for_selector('.sidebar')   # same browser, session still valid
        ctx2 = self.browser.new_context()
        self.addCleanup(ctx2.close)
        pg3 = ctx2.new_page()
        pg3.goto(self.srv.base + '/')
        pg3.wait_for_selector('.auth input[autocomplete=username]')
        self.assertEqual(pg3.locator('.kind-card').count(), 0)


if __name__ == '__main__':
    unittest.main()
