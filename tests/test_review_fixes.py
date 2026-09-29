"""Regression tests for the findings of the external review of pull request 1."""
import http.client
import json
import unittest

from cluster import Cluster  # noqa: F401 (sets sys.path)
import engine_domain  # noqa: E402,F401
import query  # noqa: E402
import registry  # noqa: E402
import store as store_mod  # noqa: E402
from registry import I, R, T  # noqa: E402
from harness import ADMIN, ApiError, Server, make_authority  # noqa: E402

registry.register(registry.Entity('deals2', 'deals2', 'Deals', [
    ('name', 'name', T, 'Name'), ('amount', 'amount_minor', I, 'Amount'), ('nid', 'nid', T, 'National id'), ('score', 'score', I, 'Score')],
    money_fields=('amount',), sensitive_fields=('nid',), perm_prefix='deals2', resolvers={'score': 'max'}))
ALL = {'mode': 'all', 'scopes': [], 'perms': {'money.view', 'data.sensitive'}, 'user': 'boss'}


class InProcessTest(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(1)
        self.p = self.c.peers[0]
        self.p.store.sync_schema()

    def tearDown(self):
        self.c.close()

    def test_descending_pages_include_the_rows_without_a_value(self):
        self.p.commit('seed', [{'e': 'deals2', 'id': f'd{i}', 'op': 'put', 'row': {'name': f'D{i}', 'amount': (i * 10 if i < 6 else None)}} for i in range(10)])
        for desc in (False, True):
            seen, cursor = [], None
            while True:
                page = query.run(self.p.store, 'deals2', ALL, sort='amount', desc=desc, limit=4, cursor=cursor)
                seen += [r['id'] for r in page['rows']]
                cursor = page['next']
                if not cursor:
                    break
            self.assertEqual(sorted(seen), sorted(f'd{i}' for i in range(10)), f'desc={desc}: every row exactly once')
            self.assertEqual(len(seen), 10)

    def test_max_resolver_compares_numbers_as_numbers(self):
        c = Cluster(2)
        try:
            for p in c.peers:
                p.store.sync_schema()
            c.peers[0].commit('a', [{'e': 'deals2', 'id': 'x', 'op': 'put', 'row': {'name': 'X', 'score': 9}}])
            c.peers[1].commit('b', [{'e': 'deals2', 'id': 'x', 'op': 'put', 'row': {'name': 'X', 'score': 10}}])
            c.converge()
            self.assertEqual([p.store.get('deals2', 'x')['score'] for p in c.peers], [10, 10])
        finally:
            c.close()

    def test_whole_numbers_are_exact_and_money_is_never_a_float(self):
        with self.assertRaises(store_mod.BadRequest):
            self.p.commit('x', [{'e': 'deals2', 'id': 'a', 'op': 'put', 'row': {'name': 'A', 'amount': '10.99'}}])
        with self.assertRaises(store_mod.BadRequest):
            self.p.commit('x', [{'e': 'deals2', 'id': 'a', 'op': 'put', 'row': {'name': 'A', 'amount': 'abc'}}])
        self.p.commit('ok', [{'e': 'deals2', 'id': 'b', 'op': 'put', 'row': {'name': 'B', 'amount': '12345678901234567', 'score': 2.0}}])
        row = self.p.store.get('deals2', 'b')
        self.assertEqual((row['amount'], row['score']), (12345678901234567, 2), 'no float round trip above 2**53')
        with self.assertRaises(ValueError):
            registry.register(registry.Entity('bad', 'bad', 'Bad', [('price', 'price', R, 'Price')], money_fields=('price',)))

    def test_attachment_type_guesses_that_differ_are_not_a_conflict_for_people(self):
        c = Cluster(2)
        try:
            for p, mime in zip(c.peers, ('application/pdf', 'application/x-pdf')):
                p.store.record_file('/files/cas/abc.pdf', 'ab' * 32, 10, mime, 'u', 'ip')
            c.converge()
            for p in c.peers:
                self.assertEqual([x for x in p.store.conflicts() if x['entity'] == 'files'], [])  # and no KeyError
        finally:
            c.close()

    def test_audit_rows_do_not_reveal_hidden_fields(self):
        import httpd
        row = {'entity': 'deals2', 'changes': json.dumps({'amount': [1, 2], 'name': ['a', 'b']}), 'before': json.dumps({'amount': 1, 'nid': 'X1', 'name': 'a'}),
               'after': None}
        httpd.mask_audit_row(row, set())
        self.assertEqual(json.loads(row['changes']), {'name': ['a', 'b']})
        self.assertEqual(json.loads(row['before']), {'name': 'a'})
        # the free-text search of the log does not look into the value columns for such users
        self.p.commit('secret', [{'e': 'deals2', 'id': 's1', 'op': 'put', 'row': {'name': 'S', 'nid': 'NID-SECRET-77'}}])
        self.assertTrue(self.p.store.query_log('audit', q='NID-SECRET-77')['rows'])
        self.assertFalse(self.p.store.query_log('audit', q='NID-SECRET-77', search_values=False)['rows'])

    def test_download_names_may_be_arabic(self):
        import httpd
        h = httpd.attachment_header('مصروفات.xlsx')
        h.encode('latin-1')  # must be sendable as a header
        self.assertIn("filename*=UTF-8''%D9%85", h)

    def test_password_policy_has_no_composition_rules(self):
        import auth
        a = auth.Auth.__new__(auth.Auth)
        a.min_len = 10
        for ok in ('كلمةالسر١٢٣٤٥٦', 'مرحبا بالعالم الجميل', 'correct horse battery staple'):
            a.check_password(ok, 'someone', 'Some One')
        for bad in ('short', 'password123', 'aaaaaaaaaaaa'):
            with self.assertRaises(auth.AuthError):
                a.check_password(bad, 'someone', 'Some One')

    def test_a_bad_device_address_does_not_kill_the_sync_worker(self):
        from sync import SyncService
        svc = SyncService.__new__(SyncService)
        svc.port = 8463
        import threading
        svc.lock = threading.RLock()
        svc.status = {}
        saved = []
        svc.peer_status = lambda pid: svc.status.setdefault(pid, {})
        svc.save_status = lambda pid: saved.append(pid)
        for address in ('192.168.1.20:', 'pc:abc', '10.0.0.1:99999', 'pc:0'):
            rep = svc.sync_with({'id': 'n1', 'name': 'PC', 'address': address, 'fp': 'x'})
            self.assertEqual(rep['result'], 'error', address)
            self.assertIn('not valid', svc.status['n1']['last_error'])


class SecondReviewTest(unittest.TestCase):
    def test_two_workers_never_download_the_same_file_into_one_part_file(self):
        import hashlib
        import os
        import shutil
        import tempfile
        import threading
        import time
        from sync import SyncService
        data = os.urandom(300_000)
        sha = hashlib.sha256(data).hexdigest()
        d = tempfile.mkdtemp()
        try:
            svc = SyncService.__new__(SyncService)
            svc.uploads, svc.lock, svc.fetching = d, threading.RLock(), set()
            svc.file_path = lambda src: os.path.join(d, 'cas', 'f.bin')
            svc.sync_logger = type('L', (), {'write': lambda self, x: None})()
            calls = []

            class SlowConnection:
                def request(self, method, path, raw=False, headers=None, sink=None):
                    calls.append(1)
                    for i in range(0, len(data), 50_000):  # a slow download: the other worker arrives meanwhile
                        sink.write(data[i:i + 50_000])
                        sink.flush()
                        time.sleep(0.05)
                    return type('R', (), {'status': 200})(), b''
                def close(self):
                    pass
            results = []
            ts = [threading.Thread(target=lambda: results.append(svc.fetch_file(SlowConnection(), '/files/cas/f.bin', sha, len(data)))) for _ in range(3)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            time.sleep(0.4)  # a straggler writing into the moved file would still be appending now
            with open(os.path.join(d, 'cas', 'f.bin'), 'rb') as f:
                self.assertEqual(f.read(), data)
            self.assertEqual(len(calls), 1, 'only one worker downloads a given file')
            self.assertEqual(sorted(results), [False, False, True])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = Server('review').start()
        cls.ac = make_authority(cls.S)

    @classmethod
    def tearDownClass(cls):
        cls.S.cleanup()

    def test_scoped_user_with_no_scopes_sees_no_audit_rows(self):
        self.ac.post('/api/commit', {'label': 'x', 'ops': [{'e': 'areas', 'id': 'A1', 'op': 'put', 'row': {'name': 'A1'}}]})
        self.ac.post('/api/users/save', {'username': 'scoped.none', 'full_name': 'Scoped None', 'password': 'Quiet-Lake-4471', 'must_change': False,
                                         'perms': ['dashboard.view', 'logs.view'], 'data_scope': 'scopes'})
        c = self.S.client()
        c.login('scoped.none', 'Quiet-Lake-4471')
        self.assertEqual(c.get('/api/audit')['rows'], [])

    def test_arabic_export_name_and_bmp_upload(self):
        raw = self._raw('POST', '/api/xlsx', {'sheets': [{'name': 'S', 'head': ['a'], 'rows': [[1]]}], 'filename': 'مصروفات'})
        self.assertEqual(raw[0], 200)
        self.assertIn('filename*=UTF-8', raw[1])
        ok = self.ac.call('POST', '/api/upload?name=a.bmp', raw=b'BM' + b'\x00' * 60, headers={'Content-Type': 'application/octet-stream'})
        self.assertTrue(ok['src'].endswith('.bmp'))
        self.assertEqual(self.S.client().call('GET', '/js/quick.js')[:2], b'//', 'the personal-link page can load its script')

    def _raw(self, method, path, body):
        cookie = '; '.join(f'{c.name}={c.value}' for c in self.ac.jar)
        h = http.client.HTTPConnection('127.0.0.1', self.S.port, timeout=20)
        data = json.dumps(body).encode()
        h.request(method, path, body=data, headers={'Content-Type': 'application/json', 'Cookie': cookie, 'Content-Length': str(len(data))})
        r = h.getresponse()
        r.read()
        out = (r.status, r.getheader('Content-Disposition') or '')
        h.close()
        return out

    def test_users_limited_to_part_of_the_data_cannot_restore_or_fetch_foreign_files(self):
        ac = self.ac
        ac.post('/api/commit', {'label': 'a', 'ops': [{'e': 'areas', 'id': 'FA', 'op': 'put', 'row': {'name': 'FA'}},
                                                     {'e': 'areas', 'id': 'FB', 'op': 'put', 'row': {'name': 'FB'}}]})
        img = b'\xff\xd8\xff\xe0' + b'x' * 200
        up = ac.call('POST', '/api/upload?name=b.jpg', raw=img, headers={'Content-Type': 'application/octet-stream'})
        ac.post('/api/commit', {'label': 'p', 'ops': [{'e': 'photos', 'id': 'ph', 'op': 'put', 'row': {'areaId': 'FB', 'src': up['src']}}]})
        ac.post('/api/users/save', {'username': 'fa.only', 'full_name': 'Fa Only', 'password': 'Green-Hill-5531', 'must_change': False, 'data_scope': 'scopes',
                                    'scopes': ['FA'], 'perms': ['dashboard.view', 'areas.view', 'files.download', 'backups.restore', 'backups.manage']})
        c = self.S.client()
        c.login('fa.only', 'Green-Hill-5531')
        with self.assertRaises(ApiError) as e:
            c.call('GET', up['src'])
        self.assertEqual(e.exception.code, 404, 'a file used only by a record outside the scope')
        self.assertEqual(ac.call('GET', up['src']), img)
        name = ac.post('/api/backups')['name']
        with self.assertRaises(ApiError) as e:
            c.post('/api/backups/restore', {'name': name})
        self.assertEqual(e.exception.code, 403)

    def test_own_scope_survives_a_rename_of_the_user(self):
        ac = self.ac
        u = ac.post('/api/users/save', {'username': 'own.one', 'full_name': 'Own One', 'password': 'Cedar-Lake-8812', 'must_change': False,
                                        'data_scope': 'own', 'perms': ['dashboard.view', 'areas.view', 'areas.create', 'areas.edit']})
        c = self.S.client()
        c.login('own.one', 'Cedar-Lake-8812')
        c.post('/api/commit', {'label': 'mine', 'ops': [{'e': 'areas', 'id': 'OWN1', 'op': 'put', 'row': {'name': 'Mine'}}]})
        self.assertEqual([r['id'] for r in c.get('/api/q/areas')['rows']], ['OWN1'])
        ac.post('/api/users/save', {**next(x for x in ac.get('/api/users')['users'] if x['id'] == u['id']), 'full_name': 'Renamed Person', 'username': 'own.renamed'})
        c2 = self.S.client()
        c2.login('own.renamed', 'Cedar-Lake-8812')
        self.assertEqual([r['id'] for r in c2.get('/api/q/areas')['rows']], ['OWN1'], 'still sees its own records after the rename')

    def test_a_password_is_needed_again_for_the_key_export_and_erase(self):
        with self.assertRaises(ApiError) as e:
            self.ac.post('/api/erase', {'entity': 'areas', 'id': 'A1', 'fields': ['location'], 'reason': 'pdpl-request', 'confirm': 'ERASE', 'password': 'wrong-one-1'})
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(ApiError) as e:
            self.ac.post('/api/erase', {'entity': 'areas', 'id': 'nope', 'fields': ['location'], 'reason': 'pdpl-request', 'confirm': 'ERASE', 'password': ADMIN[1]})
        self.assertEqual(e.exception.code, 400, 'an unknown record cannot be erased')


if __name__ == '__main__':
    unittest.main()
