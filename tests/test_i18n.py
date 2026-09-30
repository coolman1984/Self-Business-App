"""Translations: every key used by the UI code exists in Arabic AND English, both languages have the same keys and
placeholders, nothing is empty, and no key is left unused. Static: reads the JS files, no browser needed."""
import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web', 'js')
ROOT = os.path.dirname(os.path.dirname(WEB))
sys.path[:0] = [os.path.join(ROOT, 'server'), os.path.join(ROOT, 'server', 'core')]


def real_permissions():
    import business
    import permissions
    business.register()
    return set(permissions.ALL)


PERMISSIONS = real_permissions()
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


# Python side: the words of the business layer (server/business/constants.py). Every id needs a text in the group used by the screens.
GROUPS = {'stage': 'STAGES', 'pstatus': 'PROJECT_STATUS', 'tstatus': 'TASK_STATUS', 'prio': 'TASK_PRIORITY', 'tkind': 'TASK_KINDS', 'akind': 'APPOINTMENT_KINDS',
          'astatus': 'APPOINTMENT_STATUS', 'actkind': 'ACTIVITY_KINDS', 'pkind': 'PARTY_KINDS', 'partystatus': 'PARTY_STATUS', 'role': 'ROLES', 'source': 'SOURCES',
          'billing': 'BILLING_MODES', 'unit': 'SERVICE_UNITS', 'rel': 'RELATION_KINDS', 'ftype': 'FIELD_TYPES', 'cust': 'CUSTOMIZABLE'}
CALL = re.compile(r"""(?<![\w.])(?:t|tk)\(\s*'([a-z][\w.]*)'|\bk:\s*'([a-z][\w.]*)'|\btitle:\s*'([a-z]+\.[\w.]+)'""")
PREFIX = re.compile(r"""(?<![\w.])t\(\s*'([a-z]+\.)'\s*\+|t\(`([a-z]+)\.\$\{|options\('([a-z]+)'|label\(entity, field\)|ENUM_KEYS\s*=|'([a-z]+)'\s*\}?,?\s*(?:\n|$)""")


def business_constants():
    sys.path.insert(0, os.path.join(os.path.dirname(WEB), '..', 'server', 'business'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('sbo_constants', os.path.join(os.path.dirname(os.path.dirname(WEB)), 'server', 'business', 'constants.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class I18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ar, cls.en = load('ar'), load('en')
        cls.spaces = {k.split('.')[0] for k in cls.en}
        cls.used = {}
        cls.prefixes = set()
        pat = re.compile(r"'((?:%s)\.[a-z0-9_.]+)'" % '|'.join(sorted(cls.spaces)))
        for path in code_files():
            with open(path, encoding='utf-8') as f:
                text = f.read()
            for key in pat.findall(text):
                if key not in PERMISSIONS:   # 'settings.view' is a permission name, not a text
                    cls.used.setdefault(key, os.path.relpath(path, WEB))
            for m in CALL.finditer(text):
                key = next(x for x in m.groups() if x)
                if key not in PERMISSIONS:
                    cls.used.setdefault(key, os.path.relpath(path, WEB))
            cls.prefixes |= {m for m in re.findall(r"t\(\s*'([a-z.]+\.)'\s*\+", text)}
            cls.prefixes |= {m + '.' for m in re.findall(r"t\(`([a-z]+)\.\$\{", text)}
            cls.prefixes |= {m + '.' for m in re.findall(r"options\('([a-z]+)'", text)}
            
        cls.prefixes |= {g + '.' for g in GROUPS} | {'f.', 'err.', 'import.f.', 'import.st.', 'import.w.', 'tl.insert.', 'tl.update.', 'tl.delete.', 'dup.by.', 'dup.same.', 'tab.'}
        cls.static = {k for k in cls.used if not k.endswith('.')}

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
        missing = {k: f for k, f in self.used.items() if k not in self.en and not k.endswith('.')}
        self.assertEqual(missing, {}, 'keys used in code but missing in the dictionaries')

    def test_no_unused_keys(self):
        unused = [k for k in self.en if k not in self.static and not any(k.startswith(p) for p in self.prefixes)]
        self.assertEqual(sorted(unused), [], 'keys in the dictionaries that no screen uses')

    def test_every_word_of_the_business_layer_has_a_text(self):
        c = business_constants()
        missing = [f'{g}.{i}' for g, name in GROUPS.items() for i in getattr(c, name) if f'{g}.{i}' not in self.en]
        self.assertEqual(missing, [])

    def test_every_error_code_of_the_server_has_a_text(self):
        codes = set()
        srv = os.path.join(os.path.dirname(os.path.dirname(WEB)), 'server', 'business')
        for fn in os.listdir(srv):
            if fn.endswith('.py'):
                with open(os.path.join(srv, fn), encoding='utf-8') as f:
                    text = f.read()
                codes |= set(re.findall(r"E:([a-z_]+)\|", text)) | set(re.findall(r"bad\('([a-z_]+)'", text))
        self.assertEqual([c for c in sorted(codes) if 'err.' + c not in self.en], [])

    def test_every_field_and_entity_of_the_business_layer_has_a_label(self):
        import registry
        skip = {'sample', 'import_batch', 'merged_into', 'closed_at', 'done_at', 'checklist'}
        shown = {'parties', 'party_roles', 'party_relations', 'opportunities', 'projects', 'tasks', 'appointments', 'notes', 'activities', 'attachments', 'services'}
        missing = []
        for name in shown:
            for js, _, _, _ in registry.ENTITIES[name][2]:
                if js not in skip and f'f.{js}' not in self.en:
                    missing.append(f'f.{js}')
            for op in ('insert', 'update', 'delete'):
                if f'tl.{op}.{name}' not in self.en:
                    missing.append(f'tl.{op}.{name}')
        self.assertEqual(sorted(set(missing)), [])

    def test_arabic_has_no_latin_words_except_allowed(self):
        # brief rule: no English words mixed into Arabic text (product/key names below are the only exceptions)
        allowed = {'Ctrl', 'K', 'Abc', 'Ab', 'xlsx', 'csv', 'Enter', 'WhatsApp'}
        for k, v in self.ar.items():
            for w in re.findall(r'[A-Za-z]+', re.sub(r'\{\w+\}', '', v)):
                self.assertIn(w, allowed, f'{k}: "{w}" is English inside Arabic text')


if __name__ == '__main__':
    unittest.main()
