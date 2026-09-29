"""Global search: Arabic and English text, phone numbers, scopes, erasure and rebuilds."""
import os
import shutil
import tempfile
import unittest

from cluster import Cluster  # noqa: F401 (sets sys.path)
import engine_domain  # noqa: E402,F401
import registry  # noqa: E402
import textnorm  # noqa: E402
from registry import T  # noqa: E402
from search import SearchIndex  # noqa: E402

registry.register(registry.Entity('people', 'people', 'People', [
    ('name', 'name', T, 'Name'), ('phone', 'phone', T, 'Phone'), ('email', 'email', T, 'Email'), ('company', 'company', T, 'Company'),
    ('nid', 'nid', T, 'National id')], search=('name', 'company'), phone_fields=('phone',), email_fields=('email',),
    subtitle_fields=('company',), sensitive_fields=('nid',), scope_field='company'))

ALL = {'mode': 'all', 'scopes': [], 'perms': set(), 'user_id': 'boss-id'}


class NormaliserTest(unittest.TestCase):
    def test_arabic_forms_are_unified(self):
        n = textnorm.norm_text
        self.assertEqual(n('أحمد'), n('احمد'))
        self.assertEqual(n('إبراهيم'), n('ابراهيم'))
        self.assertEqual(n('مدرسة'), n('مدرسه'))
        self.assertEqual(n('مصطفى'), n('مصطفي'))
        self.assertEqual(n('مُحَمَّد'), n('محمد'))
        self.assertEqual(n('محـــمد'), n('محمد'))
        self.assertEqual(n('٠١٠١٢٣٤٥٦٧٨'), '01012345678')
        self.assertEqual(n('Ahmed  ALI!'), 'ahmed ali')
        self.assertEqual(n(None), '')

    def test_egyptian_phone_numbers(self):
        p = textnorm.norm_phone
        for s in ('01012345678', '+201012345678', '00201012345678', '0101 234 5678', '٠١٠١٢٣٤٥٦٧٨', '201012345678'):
            self.assertEqual(p(s), '+201012345678', s)
        self.assertEqual(p('02 2345 6789'), '+20223456789')
        self.assertEqual(p('123'), '')
        self.assertEqual(textnorm.phone_tokens('01012345678'), ['201012345678', '01012345678'])


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(1)
        self.p = self.c.peers[0]
        self.p.store.sync_schema()
        self.d = tempfile.mkdtemp()
        self.ix = SearchIndex(os.path.join(self.d, 'index.db'))
        self.p.store.after_fold.append(self.ix.apply)
        self.p.commit('people', [
            {'e': 'people', 'id': 'p1', 'op': 'put', 'row': {'name': 'أحمد محمد', 'phone': '01012345678', 'email': 'Ahmed@Example.com', 'company': 'c1', 'nid': '29001010101010'}},
            {'e': 'people', 'id': 'p2', 'op': 'put', 'row': {'name': 'Ibrahim Saleh', 'phone': '+20 100 000 1111', 'company': 'c2'}},
            {'e': 'people', 'id': 'p3', 'op': 'put', 'row': {'name': 'إبراهيم سعيد', 'company': 'c1'}}])

    def tearDown(self):
        self.ix.close()
        self.c.close()
        shutil.rmtree(self.d, ignore_errors=True)

    def ids(self, q, access=ALL):
        return sorted(r['id'] for r in self.ix.search(q, access))

    def test_arabic_search_ignores_hamza_and_diacritics(self):
        self.assertEqual(self.ids('احمد'), ['p1'])
        self.assertEqual(self.ids('أحمد'), ['p1'])
        self.assertEqual(self.ids('ابراهيم'), ['p3'], 'Arabic query does not match the Latin spelling')
        self.assertEqual(self.ids('محم'), ['p1'], 'prefix search')

    def test_english_and_arabic_mixed_names(self):
        self.assertEqual(self.ids('ibrahim'), ['p2'])
        self.assertEqual(self.ids('IBRAHIM sal'), ['p2'])

    def test_phone_search_by_any_form_and_by_prefix(self):
        for q in ('01012345678', '+201012345678', '0101234', '0101234567', '201012345', '٠١٠١٢٣٤٥٦٧٨'):
            self.assertEqual(self.ids(q), ['p1'], q)
        self.assertEqual(self.ids('010000'), ['p2'], 'national prefix of the second number')
        self.assertEqual(self.ids('1001111'), [], 'digits that are only the middle of a number do not match')

    def test_email_search(self):
        self.assertEqual(self.ids('ahmed@example.com'), ['p1'])

    def test_sensitive_fields_are_never_indexed(self):
        self.assertEqual(self.ids('29001010101010'), [])

    def test_scope_filtering(self):
        self.assertEqual(self.ids('ibrahim', {**ALL, 'mode': 'scopes', 'scopes': ['c1']}), [])
        self.assertEqual(self.ids('ابراهيم', {**ALL, 'mode': 'scopes', 'scopes': ['c1']}), ['p3'])
        self.assertEqual(self.ids('ابراهيم', {**ALL, 'mode': 'own', 'user_id': 'uid-pc0'}), ['p3'])
        self.assertEqual(self.ids('ابراهيم', {**ALL, 'mode': 'own', 'user_id': 'somebody-else'}), [])

    def test_changes_and_deletes_update_the_index(self):
        ver = self.p.store.get('people', 'p2')['ver']
        self.p.commit('rename', [{'e': 'people', 'id': 'p2', 'op': 'put', 'ver': ver, 'row': {'name': 'Youssef Saleh', 'phone': '+20 100 000 1111', 'company': 'c2'}}])
        self.assertEqual(self.ids('ibrahim'), [])
        self.assertEqual(self.ids('youssef'), ['p2'])
        self.p.commit('del', [{'e': 'people', 'id': 'p2', 'op': 'del', 'ver': self.p.store.get('people', 'p2')['ver']}])
        self.assertEqual(self.ids('youssef'), [])

    def test_erased_values_leave_the_index(self):
        self.p.store.erase('boss', 'ip', 'people', 'p1', ['name', 'phone', 'email'], 'pdpl-request')
        self.assertEqual(self.ids('احمد'), [])
        self.assertEqual(self.ids('01012345678'), [])
        self.assertEqual(self.ids('ahmed@example.com'), [])

    def test_rebuild_gives_the_same_results(self):
        before = {q: self.ids(q) for q in ('احمد', 'ibrahim', '0101234', 'ابراهيم')}
        self.ix.rebuild(self.p.store)
        self.assertEqual(before, {q: self.ids(q) for q in before})
        self.assertFalse(self.ix.needs_rebuild())


if __name__ == '__main__':
    unittest.main()
