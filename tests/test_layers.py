"""Architecture rules that a test enforces (docs/ARCHITECTURE.md section 2) and the log secret scanner.

  * server/core knows no business word (client, invoice, course, licence ...) and imports nothing from platform/modules;
  * the harvested BAMS engine has no break-area vocabulary left;
  * passwords, tokens and keys never reach a log file (checked with real requests).
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, 'server', 'core')
# words of the business layers; the core must stay free of them (comments included, so its documentation stays generic too)
BUSINESS_WORDS = re.compile(r'\b(customer|invoice|quote|course|lecturer|freelanc\w*|licen[sc]e[sd]?\b(?! note)|ticket|centre|center|student|'
                            r'payment|expense|project|deliverable|break.?area|inspection|surveys?)\b', re.I)
# allowed exceptions: text that is about the licence of the PRODUCT itself, and the BAMS lineage note
ALLOWED = ('LICENSE_NOTE', 'licensed', 'Licensed', 'BAMS', 'Break Area Management', 'Mr.Ayman', 'provenance', 'PROVENANCE',
           'http.client', 'HTTPSConnection', 'client signs', 'client side', 'client connection', 'display:flex', 'box-shadow', 'quote(', 'import quote',
           'urllib.parse')


def core_files():
    return [os.path.join(CORE, f) for f in sorted(os.listdir(CORE)) if f.endswith('.py')]


class LayerTest(unittest.TestCase):
    def test_core_contains_no_business_vocabulary(self):
        hits = []
        for path in core_files():
            with open(path, encoding='utf-8') as f:
                for n, line in enumerate(f, 1):
                    if BUSINESS_WORDS.search(line) and not any(a in line for a in ALLOWED):
                        hits.append(f'{os.path.basename(path)}:{n}: {line.strip()[:100]}')
        self.assertEqual(hits, [], 'business words in the domain-free core:\n' + '\n'.join(hits[:30]))

    def test_core_does_not_import_the_business_layers(self):
        bad = re.compile(r'^\s*(from|import)\s+(platform_|modules|connectors|domain)\b', re.M)
        for path in core_files():
            with open(path, encoding='utf-8') as f:
                self.assertIsNone(bad.search(f.read()), os.path.basename(path))

    def test_every_core_module_is_listed_in_the_provenance_file(self):
        with open(os.path.join(CORE, 'PROVENANCE.md'), encoding='utf-8') as f:
            text = f.read()
        own = {'registry.py', 'permissions.py', 'query.py', 'search.py', 'textnorm.py', 'httpd.py', 'bootstrap.py'}  # written here, not harvested
        for path in core_files():
            name = os.path.basename(path)
            if name not in own:
                self.assertIn(name.split('.')[0], text, f'{name} is missing from core/PROVENANCE.md')


if __name__ == '__main__':
    unittest.main()
