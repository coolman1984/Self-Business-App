"""Real-browser test support: finds Playwright and a Chromium, starts a server, gives a logged-in page.

Order of lookup for the browser: $SBO_CHROMIUM, Playwright's own browsers ($PLAYWRIGHT_BROWSERS_PATH), the installed Chrome.
If Playwright or a browser is missing, `available()` explains why and the UI tests are skipped (never silently passed in CI:
the workflow installs both and sets SBO_REQUIRE_UI=1 so a missing browser fails the build).
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Server  # noqa: E402

for extra in filter(None, [os.environ.get('SBO_PWLIB')]):
    sys.path.insert(0, extra)

ADMIN = ('owner', 'correct-horse-42', 'محمد فوزي')


def _chromium_path():
    if os.environ.get('SBO_CHROMIUM'):
        return os.environ['SBO_CHROMIUM']
    base = os.environ.get('PLAYWRIGHT_BROWSERS_PATH') or '/opt/pw-browsers'
    hits = sorted(glob.glob(os.path.join(base, 'chromium-*', 'chrome-linux*', 'chrome')))
    return hits[-1] if hits else None


def available():
    """(ok, reason)"""
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False, 'Playwright is not installed (pip install playwright)'
    return True, ''


def launch(pw):
    exe = _chromium_path()
    if exe:
        return pw.chromium.launch(executable_path=exe)
    return pw.chromium.launch(channel='chrome')


def new_server(name='ui', with_owner=True, brand='Nour Academy', extra_cfg=None):
    srv = Server(name, extra_cfg=extra_cfg, domain='').start()   # the product's own domain (server/business), not the engine test domain
    if with_owner:
        c = srv.client()
        c.post('/api/auth/setup', {'username': ADMIN[0], 'full_name': ADMIN[2], 'password': ADMIN[1]})
        c.login(ADMIN[0], ADMIN[1])
        c.post('/api/commit', {'label': 'brand', 'ops': [
            {'e': 'settings', 'id': 'brand.name', 'op': 'put', 'row': {'value': brand}},
            {'e': 'settings', 'id': 'brand.short', 'op': 'put', 'row': {'value': brand[:1]}}]})
        srv.owner = c
    return srv


def set_setting(client, key, value):
    """Changes a setting the way the UI does: with the current version, so the server accepts it."""
    try:
        ver = client.get('/api/get/settings/' + key)['ver']
    except Exception:  # noqa: BLE001 - new setting
        ver = None
    client.post('/api/commit', {'label': 'setting', 'ops': [{'e': 'settings', 'id': key, 'op': 'put', 'ver': ver, 'row': {'value': value}}]})


import unittest  # noqa: E402


class UiBase(unittest.TestCase):
    """One server and one browser per test class; every test gets a fresh browser context (own storage, own session)."""
    server_name = 'ui'

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.srv = new_server(cls.server_name)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.stop()

    def page(self, width=1360, height=860, tour_done=True, login=True, lang='ar', user=None, **ctx):
        context = self.browser.new_context(viewport={'width': width, 'height': height}, **ctx)
        self.addCleanup(context.close)
        context.set_default_timeout(8000)
        pg = context.new_page()
        self.errors = []
        pg.on('pageerror', lambda e: self.errors.append(str(e)))
        pg.on('console', lambda m: self.errors.append(m.text) if (m.type == 'error' and '401' not in m.text and '409' not in m.text and '400' not in m.text and '403' not in m.text)
              or (m.type == 'warning' and 'missing translation' in m.text) else None)
        prefs = '{"tour":"%s","lang":"%s"}' % ('done' if tour_done else 'todo', lang)
        pg.add_init_script("try{if(!localStorage.getItem('sbo.prefs.v1'))localStorage.setItem('sbo.prefs.v1', '%s')}catch(e){}" % prefs.replace('"', '\\"'))
        pg.goto(self.srv.base + '/')
        if login:
            name, pw = user or (ADMIN[0], ADMIN[1])
            pg.wait_for_selector('.auth')
            pg.fill('input[autocomplete=username]', name)
            pg.fill('input[type=password]', pw)
            pg.click('button[type=submit]')
            pg.wait_for_selector('.sidebar')
        return pg

    def assertNoErrors(self):
        self.assertEqual(self.errors, [], 'the browser console has errors')
