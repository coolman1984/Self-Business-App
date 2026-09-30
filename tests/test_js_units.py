"""Pure browser modules (text folding, formatting, router, i18n) run under Node, without a browser. Skipped only where Node is
missing; CI sets SBO_REQUIRE_UI=1 so it must exist there."""
import json
import os
import shutil
import subprocess
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'js')
NODE = shutil.which('node')
REQUIRE = os.environ.get('SBO_REQUIRE_UI') == '1'

PRELUDE = """
globalThis.document = {documentElement: {}};
globalThis.matchMedia = () => ({matches: false, addEventListener() {}});
globalThis.localStorage = {getItem: () => null, setItem() {}};
globalThis.location = {hash: ''};
globalThis.addEventListener = () => {};
"""


def run(script):
    """Runs an ES module snippet; the snippet prints JSON on its last line."""
    p = subprocess.run([NODE, '--input-type=module', '-e', PRELUDE + script], capture_output=True, text=True, cwd=WEB, timeout=60)
    if p.returncode:
        raise AssertionError(p.stderr[-2000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


@unittest.skipUnless(NODE or REQUIRE, 'Node.js is not installed')
class JsUnits(unittest.TestCase):
    def test_text_folding_matches_typing_without_hamza_and_teh_marbuta(self):
        out = run("""
        import { norm, matches } from './core/textnorm.js';
        console.log(JSON.stringify({
          hamza: matches('الإعدادات', 'اعدادات'), marbuta: matches('أكاديمية', 'اكاديميه'), yeh: matches('مصطفى', 'مصطفي'),
          diac: norm('مُحَمَّد') === norm('محمد'), digits: norm('٠١٢٣') === '0123', persian: norm('۱۲') === '12',
          words: matches('عميل جديد اليوم', 'جديد عميل'), no: !matches('عميل', 'فاتورة'), empty: matches('x', ''),
        }));""")
        self.assertTrue(all(out.values()), out)

    def test_money_is_formatted_from_whole_minor_units(self):
        out = run("""
        import { setDigits, money, num, date, initials } from './core/format.js';
        import { setLang } from './i18n/index.js';
        setLang('en', {}); setDigits('latn');
        console.log(JSON.stringify({ m: money(123450), zero: money(0), none: money(null), n: num(1234567), d: date('2026-09-30'), i: initials('Mona Ibrahim'), ia: initials('منى إبراهيم') }));""")
        self.assertIn('1,234.5', out['m'])
        self.assertIn('EGP', out['m'])
        self.assertIn('0', out['zero'])
        self.assertEqual(out['none'], '')
        self.assertEqual(out['n'], '1,234,567')
        self.assertIn('2026', out['d'])
        self.assertEqual(out['i'], 'MI')
        self.assertEqual(out['ia'], 'مإ')

    def test_arabic_digits_only_when_chosen(self):
        out = run("""
        import { setDigits, num } from './core/format.js';
        import { setLang } from './i18n/index.js';
        setLang('ar', {}); setDigits('latn'); const w = num(2024);
        setDigits('arab'); const a = num(2024);
        console.log(JSON.stringify({w, a}));""")
        self.assertRegex(out['w'], r'^2[,٬]?024$')
        self.assertRegex(out['a'], r'٢[,٬]?٠٢٤')

    def test_router_matches_params_and_query(self):
        out = run("""
        import { route, resolve, parse } from './core/router.js';
        route('/clients/:id', () => 1, { nav: 'clients' }); route('/clients', () => 2); route('/', () => 3);
        const a = resolve('#/clients/abc%20d?tab=notes'); const b = resolve('#/clients'); const c = resolve('#/x'); const d = resolve('');
        console.log(JSON.stringify({ id: a.params.id, tab: a.query.tab, nav: a.meta.nav, list: b.pattern, none: c, root: d.pattern, p: parse('#/a?x=1&y=2') }));""")
        self.assertEqual((out['id'], out['tab'], out['nav'], out['list'], out['root']), ('abc d', 'notes', 'clients', '/clients', '/'))
        self.assertIsNone(out['none'])
        self.assertEqual(out['p'], {'path': '/a', 'query': {'x': '1', 'y': '2'}})

    def test_translation_fallback_and_placeholders(self):
        out = run("""
        import { t, setLang, lang, dir } from './i18n/index.js';
        setLang('en', {}); const en = t('setup.pw.hint', { n: 10 }); const miss = t('no.such.key');
        setLang('ar', {}); const ar = t('setup.pw.hint', { n: 10 });
        console.log(JSON.stringify({ en, ar, miss, dir: dir() }));""")
        self.assertIn('10', out['en'])
        self.assertIn('10', out['ar'])
        self.assertEqual(out['miss'], 'no.such.key')
        self.assertEqual(out['dir'], 'rtl')


if __name__ == '__main__':
    unittest.main()
