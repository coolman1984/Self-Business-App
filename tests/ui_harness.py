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
