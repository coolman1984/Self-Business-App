"""Translations: every key used by the UI code exists in Arabic AND English, both languages have the same keys and
placeholders, nothing is empty, and no key is left unused. Static: reads the JS files, no browser needed."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'js')
PERMISSION = re.compile(r'\.(view|edit|create|delete|manage)$')
LINE = re.compile(r"^\s*'([\w.]+)':\s*'((?:[^'\\]|\\.)*)',\s*$")


def load(name):
    out = {}
    with open(os.path.join(WEB, 'i18n', name + '.js'), encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            m = LINE.match(line)
            if m:
                assert m.group(1) not in out, f'{name}.js line {n}: duplicate key {m.group(1)}'
                out[m.group(1)] = m.group(2)
            elif line.strip().startswith("'"):
                raise AssertionError(f'{name}.js line {n} is not "  \'key\': \'text\',": {line.strip()[:60]}')
    return out


def code_files():
    for root, _, files in os.walk(WEB):
        if os.path.basename(root) == 'i18n':
            continue
        for fn in files:
            if fn.endswith('.js') and fn != 'icons.js':
                yield os.path.join(root, fn)


class I18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ar, cls.en = load('ar'), load('en')
        cls.spaces = {k.split('.')[0] for k in cls.en}
        cls.used = {}
        pat = re.compile(r"'((?:%s)\.[a-z0-9_.]+)'" % '|'.join(sorted(cls.spaces)))
        for path in code_files():
            with open(path, encoding='utf-8') as f:
                for key in pat.findall(f.read()):
                    if PERMISSION.search(key):   # 'settings.view' is a permission name, not a text
                        continue
                    cls.used.setdefault(key, os.path.relpath(path, WEB))

    def test_same_keys_in_both_languages(self):
        self.assertEqual(sorted(set(self.ar) ^ set(self.en)), [])

    def test_placeholders_match(self):
        ph = re.compile(r'\{(\w+)\}')
        for k in self.en:
            self.assertEqual(sorted(ph.findall(self.ar[k])), sorted(ph.findall(self.en[k])), k)

    def test_nothing_empty(self):
        for name, d in (('ar', self.ar), ('en', self.en)):
            for k, v in d.items():
                self.assertTrue(v.strip(), f'{name}: {k} is empty')

    def test_every_used_key_exists(self):
        missing = {k: f for k, f in self.used.items() if k not in self.en}
        self.assertEqual(missing, {}, 'keys used in code but missing in the dictionaries')

    def test_no_unused_keys(self):
        self.assertEqual(sorted(set(self.en) - set(self.used)), [], 'keys in the dictionaries that no screen uses')

    def test_arabic_has_no_latin_words_except_allowed(self):
        # brief rule: no English words mixed into Arabic text (product/key names below are the only exceptions)
        allowed = {'Ctrl', 'K', 'Abc', 'Ab'}
        for k, v in self.ar.items():
            for w in re.findall(r'[A-Za-z]+', re.sub(r'\{\w+\}', '', v)):
                self.assertIn(w, allowed, f'{k}: "{w}" is English inside Arabic text')


if __name__ == '__main__':
    unittest.main()
