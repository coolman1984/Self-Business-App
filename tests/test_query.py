"""Query API: filters, sorting, cursor pagination, data scopes and field masking (all decided on the server)."""
import unittest

from cluster import Cluster  # noqa: F401 (sets sys.path)
import engine_domain  # noqa: E402,F401
import query  # noqa: E402
import registry  # noqa: E402
from registry import I, T  # noqa: E402

registry.register(registry.Entity('deals', 'deals', 'Deals', [
    ('name', 'name', T, 'Name'), ('client', 'client', T, 'Client'), ('amount', 'amount_minor', I, 'Amount'), ('nid', 'nid', T, 'National id')],
    scope_field='client', money_fields=('amount',), sensitive_fields=('nid',)))

ALL = {'mode': 'all', 'scopes': [], 'perms': {'money.view', 'data.sensitive'}, 'user': 'boss'}


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(1)
        self.p = self.c.peers[0]
        self.p.store.sync_schema()
        ops = []
        for i in range(25):
            ops.append({'e': 'deals', 'id': f'd{i:02d}', 'op': 'put', 'row': {'name': f'Deal {i:02d}', 'client': 'c1' if i % 2 else 'c2',
                                                                            'amount': (i % 5) * 100, 'nid': f'NID{i}'}})
        self.p.commit('seed', ops)

    def tearDown(self):
        self.c.close()

    def q(self, access=ALL, **kw):
        return query.run(self.p.store, 'deals', access, **kw)

    def test_pagination_covers_every_row_exactly_once_in_any_order(self):
        for sort, desc in ((None, False), (None, True), ('amount', False), ('amount', True), ('name', False)):
            seen, cursor = [], None
            while True:
                page = self.q(sort=sort, desc=desc, limit=7, cursor=cursor)
                seen += [r['id'] for r in page['rows']]
                cursor = page['next']
                if not cursor:
                    break
            self.assertEqual(sorted(seen), sorted(f'd{i:02d}' for i in range(25)), (sort, desc))
            self.assertEqual(len(seen), 25, 'no duplicates across pages')

    def test_sorted_pages_are_in_order(self):
        rows = []
        cursor = None
        while True:
            page = self.q(sort='amount', limit=6, cursor=cursor)
            rows += [r['amount'] for r in page['rows']]
            cursor = page['next']
            if not cursor:
                break
        self.assertEqual(rows, sorted(rows))

    def test_filters_and_total(self):
        page = self.q(filters=[('client', 'eq', 'c1')], limit=100)
        self.assertEqual(page['total'], 12)
        self.assertTrue(all(r['client'] == 'c1' for r in page['rows']))
        self.assertEqual(self.q(filters=[('amount', 'gte', 300)])['total'], 10)
        self.assertEqual(self.q(filters=[('client', 'in', ['c1'])])['total'], 12)
        self.assertEqual(self.q(search='Deal 07')['total'], 1)
        with self.assertRaises(query.QueryError):
            self.q(filters=[('password', 'eq', 'x')])
        with self.assertRaises(query.QueryError):
            self.q(filters=[('name', 'drop', 'x')])

    def test_like_input_is_escaped(self):
        self.assertEqual(self.q(search='%')['total'], 0)
        self.assertEqual(self.q(filters=[('name', 'like', '_')])['total'], 0)

    def test_scope_mode_only_returns_the_users_scopes(self):
        acc = {**ALL, 'mode': 'scopes', 'scopes': ['c1']}
        page = self.q(acc, limit=100)
        self.assertEqual(page['total'], 12)
        self.assertTrue(all(r['client'] == 'c1' for r in page['rows']))
        self.assertEqual(self.q({**ALL, 'mode': 'scopes', 'scopes': []})['total'], 0)

    def test_own_mode_only_returns_records_the_user_created(self):
        self.assertEqual(self.q({**ALL, 'mode': 'own', 'user': 'someone else'})['total'], 0)
        self.assertEqual(self.q({**ALL, 'mode': 'own', 'user': 'user@pc0'})['total'], 25)

    def test_money_and_sensitive_fields_are_removed_without_permission(self):
        row = self.q({**ALL, 'perms': set()}, limit=1)['rows'][0]
        self.assertNotIn('amount', row)
        self.assertNotIn('nid', row)
        row = self.q({**ALL, 'perms': {'money.view'}}, limit=1)['rows'][0]
        self.assertIn('amount', row)
        self.assertNotIn('nid', row)

    def test_bad_cursor_is_refused(self):
        with self.assertRaises(query.QueryError):
            self.q(cursor='not-a-cursor')

    def test_deleted_rows_are_not_returned(self):
        self.p.commit('del', [{'e': 'deals', 'id': 'd00', 'op': 'del', 'ver': self.p.store.get('deals', 'd00')['ver']}])
        self.assertEqual(self.q()['total'], 24)
        self.assertEqual(self.q(include_deleted=True)['total'], 25)

    def test_scope_via_parent_is_followed(self):
        self.p.commit('area', [{'e': 'areas', 'id': 'a1', 'op': 'put', 'row': {'name': 'A1'}}, {'e': 'areas', 'id': 'a2', 'op': 'put', 'row': {'name': 'A2'}}])
        self.p.commit('issues', [{'e': 'issues', 'id': 'i1', 'op': 'put', 'row': {'areaId': 'a1', 'title': 'x'}},
                                 {'e': 'issues', 'id': 'i2', 'op': 'put', 'row': {'areaId': 'a2', 'title': 'y'}}])
        self.p.commit('log', [{'e': 'issueLog', 'id': 'l1', 'op': 'put', 'row': {'issueId': 'i1', 'text': 'one'}},
                              {'e': 'issueLog', 'id': 'l2', 'op': 'put', 'row': {'issueId': 'i2', 'text': 'two'}}])
        page = query.run(self.p.store, 'issueLog', {**ALL, 'mode': 'scopes', 'scopes': ['a1']})
        self.assertEqual([r['id'] for r in page['rows']], ['l1'])


if __name__ == '__main__':
    unittest.main()
