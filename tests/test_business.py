"""The business layer through the real HTTP API of a running server (product domain): validation, search, roles/permissions, money
masking, Today, timeline, duplicates and merge, demo data, import (messy 2,000-row Excel), undo. Multi-process like the browser."""
import json
import os
import sys
import unittest
from datetime import date, timedelta
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'core'))
import xlsx  # noqa: E402
from harness import ApiError, Server  # noqa: E402

ADMIN = ('owner', 'correct-horse-42')


def put(client, entity, rid, row, ver=None, label='x'):
    return client.post('/api/commit', {'label': label, 'ops': [{'e': entity, 'id': rid, 'op': 'put', 'ver': ver, 'row': row}]})


def full(client, entity, rid, **changes):
    """Edits a record the way the screens do: the WHOLE row goes back with its version."""
    cur = client.get(f'/api/get/{entity}/{rid}')
    row = {k: v for k, v in cur.items() if not k.startswith('_') and k not in ('id', 'ver')}
    row.update(changes)
    return put(client, entity, rid, row, cur['ver'])


class BusinessBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = Server('biz', domain='').start()
        cls.ac = cls.srv.client()
        cls.ac.post('/api/auth/setup', {'username': ADMIN[0], 'full_name': 'Owner', 'password': ADMIN[1]})
        cls.ac.login(*ADMIN)
        cls.users = {}
        profiles = cls.ac.get('/api/users')['profiles']
        for name, profile, pw in (('assist', 'assistant', 'Green-Tree-4471'), ('viewer', 'viewer', 'Blue-Lake-5582'), ('team', 'team', 'Red-Hill-6693')):
            perms = next(p['perms'] for p in profiles if p['id'] == profile)
            cls.ac.post('/api/users/save', {'username': name, 'full_name': name.title(), 'password': pw, 'must_change': False, 'role': profile,
                                            'perms': perms, 'data_scope': 'all', 'scopes': []})
            c = cls.srv.client()
            c.login(name, pw)
            cls.users[name] = c

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()


class Records(BusinessBase):
    def test_a_client_needs_a_name_and_gets_defaults(self):
        with self.assertRaises(ApiError) as e:
            put(self.ac, 'parties', 'c-empty', {'name': '   '})
        self.assertIn('E:name_required', e.exception.msg)
        put(self.ac, 'parties', 'c-1', {'name': ' منى إبراهيم ', 'phone': '01012345678', 'email': 'mona@example.com', 'city': 'القاهرة'})
        r = self.ac.get('/api/get/parties/c-1')
        self.assertEqual((r['name'], r['kind'], r['status']), ('منى إبراهيم', 'person', 'active'))
        self.assertTrue(r['_created'])

    def test_bad_values_are_refused_with_codes(self):
        cases = [('parties', {'name': 'x', 'email': 'nope'}, 'bad_email'), ('parties', {'name': 'x', 'birthday': '31/12/2000'}, 'bad_date'),
                 ('opportunities', {'title': 't', 'stage': 'flying'}, 'bad_value'), ('opportunities', {'title': 't', 'value_minor': 1.5}, 'bad_amount'),
                 ('projects', {'title': 't', 'start': '2026-05-02', 'due': '2026-05-01'}, 'due_before_start'), ('tasks', {'title': ''}, 'title_required'),
                 ('appointments', {'title': 'a'}, 'start_required'), ('appointments', {'title': 'a', 'starts_at': '2026-05-02T10:00', 'ends_at': '2026-05-02T09:00'}, 'end_before_start'),
                 ('party_relations', {'from_party': 'a', 'to_party': 'a', 'kind': 'works_at'}, 'bad_value'), ('notes', {'body': ' '}, 'note_required')]
        for n, (entity, row, code) in enumerate(cases):
            with self.assertRaises(ApiError, msg=f'{entity} {row}') as e:
                put(self.ac, entity, f'bad-{n}', row)
            self.assertIn('E:' + code, e.exception.msg, f'{entity} {row}')

    def test_money_must_be_whole_minor_units_never_floats(self):
        with self.assertRaises(ApiError):
            put(self.ac, 'opportunities', 'm1', {'title': 'x', 'value_minor': 10.5})
        put(self.ac, 'opportunities', 'm2', {'title': 'ok', 'value_minor': 1250000})
        self.assertEqual(self.ac.get('/api/get/opportunities/m2')['value_minor'], 1250000)

    def test_editing_needs_the_current_version(self):
        put(self.ac, 'parties', 'v1', {'name': 'Version test'})
        with self.assertRaises(ApiError) as e:
            put(self.ac, 'parties', 'v1', {'name': 'Second'})
        self.assertEqual(e.exception.code, 409)
        full(self.ac, 'parties', 'v1', name='Third')
        self.assertEqual(self.ac.get('/api/get/parties/v1')['name'], 'Third')

    def test_task_done_gets_a_time_and_reopening_clears_it(self):
        put(self.ac, 'tasks', 't-done', {'title': 'Send the offer', 'due': date.today().isoformat()})
        full(self.ac, 'tasks', 't-done', status='done')
        self.assertTrue(self.ac.get('/api/get/tasks/t-done')['done_at'])
        full(self.ac, 'tasks', 't-done', status='todo')
        self.assertNotIn('done_at', self.ac.get('/api/get/tasks/t-done'))

    def test_delete_is_soft_and_restorable(self):
        put(self.ac, 'parties', 'del-1', {'name': 'To delete'})
        cur = self.ac.get('/api/get/parties/del-1')
        self.ac.post('/api/commit', {'label': 'del', 'ops': [{'e': 'parties', 'id': 'del-1', 'op': 'del', 'ver': cur['ver']}]})
        self.assertNotIn('del-1', [r['id'] for r in self.ac.get('/api/q/parties?limit=500')['rows']])
        self.assertIn('To delete', [n for t in self.ac.get('/api/trash') for n in t['names']])


class SearchAndScope(BusinessBase):
    def test_arabic_search_ignores_hamza_teh_marbuta_and_digits(self):
        put(self.ac, 'parties', 's-1', {'name': 'أحمد إبراهيم', 'phone': '٠١٠٠٠٠٠٠٠٠٧'})
        put(self.ac, 'parties', 's-2', {'name': 'شركة الأكاديمية', 'kind': 'org', 'city': 'الإسكندرية'})
        for q, want in (('احمد ابراهيم', 's-1'), ('ابراهيم', 's-1'), ('الاكاديميه', 's-2'), ('اسكندريه', 's-2'), ('01000000007', 's-1')):
            hits = self.ac.get('/api/search?e=parties&q=' + quote(q))
            self.assertIn(want, [h['id'] for h in hits], q)

    def test_search_can_be_limited_to_one_kind_of_record(self):
        put(self.ac, 'projects', 'sp-1', {'title': 'Ahmed website'})
        put(self.ac, 'parties', 'sp-2', {'name': 'Ahmed Client'})
        kinds = {h['entity'] for h in self.ac.get('/api/search?q=ahmed&e=projects')}
        self.assertEqual(kinds, {'projects'})

    def test_permissions_are_enforced_on_the_server(self):
        v = self.users['viewer']
        self.assertTrue(v.get('/api/q/parties?limit=5')['rows'] is not None)
        with self.assertRaises(ApiError) as e:
            put(v, 'parties', 'x-viewer', {'name': 'Nope'})
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(ApiError) as e:
            v.post('/api/import/preview', {'src': '/files/cas/x.xlsx'})
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(ApiError) as e:
            self.users['assist'].post('/api/demo/load', {})
        self.assertEqual(e.exception.code, 403)

    def test_money_is_hidden_from_those_without_money_view_and_survives_their_edits(self):
        put(self.ac, 'opportunities', 'op-m', {'title': 'Big deal', 'value_minor': 9900000, 'stage': 'offer'})
        a = self.users['assist']
        row = a.get('/api/get/opportunities/op-m')
        self.assertNotIn('value_minor', row)
        self.assertNotIn('value_minor', [k for r in a.get('/api/q/opportunities?limit=50')['rows'] for k in r])
        with self.assertRaises(ApiError):
            a.get('/api/q/opportunities?f=value_minor:gt:5')      # cannot probe hidden values by filtering
        full(a, 'opportunities', 'op-m', stage='won')            # the assistant moves the card...
        self.assertEqual(self.ac.get('/api/get/opportunities/op-m')['value_minor'], 9900000)   # ...the amount is untouched
        t = self.users['team']
        self.assertEqual(t.get('/api/get/opportunities/op-m')['value_minor'], 9900000)

    def test_today_hides_pipeline_values_from_those_without_money_view(self):
        put(self.ac, 'opportunities', 'op-t', {'title': 'Pipe', 'value_minor': 500000, 'stage': 'new'})
        self.assertIn('value', self.ac.get('/api/today')['pipeline']['new'])
        self.assertNotIn('value', self.users['assist'].get('/api/today')['pipeline']['new'])


class TodayAndTimeline(BusinessBase):
    def test_today_groups_what_needs_attention(self):
        d = date.today()
        put(self.ac, 'parties', 'tt-c', {'name': 'Today Client'})
        put(self.ac, 'tasks', 'tt-late', {'title': 'late', 'due': (d - timedelta(days=2)).isoformat(), 'party_id': 'tt-c'})
        put(self.ac, 'tasks', 'tt-now', {'title': 'now', 'due': d.isoformat() + 'T16:00'})
        put(self.ac, 'tasks', 'tt-soon', {'title': 'soon', 'due': (d + timedelta(days=3)).isoformat()})
        put(self.ac, 'tasks', 'tt-done', {'title': 'done', 'due': (d - timedelta(days=2)).isoformat(), 'status': 'done'})
        put(self.ac, 'appointments', 'tt-ap', {'title': 'meet', 'starts_at': d.isoformat() + 'T15:00', 'party_id': 'tt-c'})
        put(self.ac, 'opportunities', 'tt-op', {'title': 'follow', 'stage': 'contacted', 'next_step_at': (d - timedelta(days=1)).isoformat()})
        put(self.ac, 'inbox', 'tt-in', {'text': 'call Maged'})
        t = self.ac.get('/api/today')
        ids = lambda k: {x['id'] for x in t[k]}  # noqa: E731
        self.assertIn('tt-late', ids('overdue'))
        self.assertNotIn('tt-done', ids('overdue'))
        self.assertIn('tt-now', ids('dueToday'))
        self.assertIn('tt-soon', ids('upcoming'))
        self.assertIn('tt-ap', ids('appointmentsToday'))
        self.assertIn('tt-op', ids('followUps'))
        self.assertGreaterEqual(t['inbox'], 1)
        self.assertEqual(t['names']['tt-c'], 'Today Client')

    def test_timeline_shows_every_change_of_the_client_and_its_records(self):
        put(self.ac, 'parties', 'tl-c', {'name': 'Timeline Client', 'phone': '01000000001'})
        full(self.ac, 'parties', 'tl-c', phone='01000000002')
        put(self.ac, 'opportunities', 'tl-op', {'title': 'Deal', 'party_id': 'tl-c', 'stage': 'new', 'value_minor': 100})
        full(self.ac, 'opportunities', 'tl-op', stage='meeting')
        put(self.ac, 'notes', 'tl-n', {'body': 'Called and agreed', 'party_id': 'tl-c'})
        put(self.ac, 'tasks', 'tl-t', {'title': 'Send offer', 'party_id': 'tl-c'})
        put(self.ac, 'tasks', 'tl-other', {'title': 'Somebody else', 'party_id': 'nobody'})
        ev = self.ac.get('/api/timeline?party=tl-c')['events']
        seen = [(e['entity'], e['op']) for e in ev]
        for want in (('parties', 'insert'), ('parties', 'update'), ('opportunities', 'insert'), ('opportunities', 'update'), ('notes', 'insert'), ('tasks', 'insert')):
            self.assertIn(want, seen)
        self.assertNotIn('tl-other', [e['id'] for e in ev])
        upd = next(e for e in ev if e['entity'] == 'opportunities' and e['op'] == 'update')
        self.assertEqual(upd['changes']['stage'], ['new', 'meeting'])

    def test_timeline_masks_money_for_those_without_money_view(self):
        put(self.ac, 'parties', 'tm-c', {'name': 'Mask Client'})
        put(self.ac, 'opportunities', 'tm-op', {'title': 'Deal', 'party_id': 'tm-c', 'value_minor': 777700})
        full(self.ac, 'opportunities', 'tm-op', value_minor=888800)
        self.assertIn('777700', json.dumps(self.ac.get('/api/timeline?party=tm-c')))
        blob = json.dumps(self.users['assist'].get('/api/timeline?party=tm-c'))
        self.assertNotIn('777700', blob)
        self.assertNotIn('888800', blob)

    def test_deleted_records_stay_in_the_timeline(self):
        put(self.ac, 'parties', 'td-c', {'name': 'Deleted stuff'})
        put(self.ac, 'notes', 'td-n', {'body': 'will be deleted', 'party_id': 'td-c'})
        cur = self.ac.get('/api/get/notes/td-n')
        self.ac.post('/api/commit', {'label': 'del', 'ops': [{'e': 'notes', 'id': 'td-n', 'op': 'del', 'ver': cur['ver']}]})
        ops = [(e['entity'], e['op']) for e in self.ac.get('/api/timeline?party=td-c')['events']]
        self.assertIn(('notes', 'delete'), ops)
        self.assertIn(('notes', 'insert'), ops)


class Duplicates(BusinessBase):
    def test_same_phone_or_email_is_a_strong_match_same_name_only_maybe(self):
        put(self.ac, 'parties', 'du-1', {'name': 'هدى محمد', 'phone': '+201099990001', 'email': 'Hoda@Example.com'})
        put(self.ac, 'parties', 'du-2', {'name': 'محمد هدى'})
        m = self.ac.get('/api/parties/duplicates?phone=010%209999%200001')['matches']
        self.assertEqual((m[0]['id'], m[0]['strength'], m[0]['why']), ('du-1', 'same', 'phone'))
        self.assertEqual(self.ac.get('/api/parties/duplicates?email=hoda@example.com')['matches'][0]['id'], 'du-1')
        names = {x['id']: x['strength'] for x in self.ac.get('/api/parties/duplicates?name=' + quote('هدى محمد'))['matches']}
        self.assertEqual(names.get('du-1'), 'maybe')       # word order does not matter
        self.assertEqual(names.get('du-2'), 'maybe')

    def test_groups_list_and_merge_by_redirect(self):
        put(self.ac, 'parties', 'mg-a', {'name': 'Merge Person', 'phone': '01055550001'})
        put(self.ac, 'parties', 'mg-b', {'name': 'Merge Persn', 'phone': '+20 105 555 0001'})
        put(self.ac, 'notes', 'mg-note', {'body': 'on the duplicate', 'party_id': 'mg-b'})
        groups = self.ac.get('/api/parties/duplicates')['groups']
        g = next(x for x in groups if 'mg-a' in x['ids'])
        self.assertTrue(g['strong'])
        self.assertEqual(set(g['ids']), {'mg-a', 'mg-b'})
        full(self.ac, 'parties', 'mg-b', merged_into='mg-a', status='merged')
        self.assertNotIn('mg-b', [x['id'] for x in self.ac.get('/api/parties/duplicates')['groups'] and sum([y['rows'] for y in self.ac.get('/api/parties/duplicates')['groups']], [])])
        tl = self.ac.get('/api/timeline?party=mg-a')['events']
        self.assertIn('mg-note', [e['id'] for e in tl], 'records of a merged duplicate show under the surviving client')
        full(self.ac, 'parties', 'mg-b', merged_into=None, status='active')      # unmerge is just another change
        self.assertNotIn('merged_into', self.ac.get('/api/get/parties/mg-b'))


class DemoData(BusinessBase):
    def test_demo_loads_once_and_is_removed_in_one_step_keeping_edits(self):
        put(self.ac, 'parties', 'real-1', {'name': 'A real client'})
        st = self.ac.post('/api/demo/load', {'lang': 'ar', 'kinds': ['trainer']})
        self.assertGreater(st['total'], 40)
        with self.assertRaises(ApiError) as e:
            self.ac.post('/api/demo/load', {})
        self.assertIn('demo_exists', e.exception.msg)
        rows = self.ac.get('/api/q/parties?limit=500')['rows']
        demo_ids = [r['id'] for r in rows if r.get('sample')]
        self.assertGreaterEqual(len(demo_ids), 8)
        self.assertNotIn('real-1', demo_ids)
        today = self.ac.get('/api/today')
        self.assertTrue(today['overdue'] and today['appointmentsToday'] and today['followUps'])
        full(self.ac, 'parties', 'demo-p1', notes_summary=None, city='مدينة نصر')       # the owner edits one demo client
        res = self.ac.post('/api/demo/remove', {})
        self.assertGreater(res['removed'], 40)
        self.assertGreaterEqual(res['kept'], 1)
        self.assertEqual(self.ac.get('/api/demo/status')['total'], 0)
        left = {r['id'] for r in self.ac.get('/api/q/parties?limit=500')['rows']}
        self.assertEqual(left & set(demo_ids), {'demo-p1'})
        self.assertIn('real-1', left)
        self.assertNotIn('sample', self.ac.get('/api/get/parties/demo-p1'))
        self.assertEqual(self.ac.get('/api/get/parties/demo-p1')['city'], 'مدينة نصر')
        self.assertEqual(self.ac.post('/api/demo/load', {'lang': 'en'})['total'] > 0, True)      # can be loaded again (English)
        self.ac.post('/api/demo/remove', {})


def messy_sheet(n=2000):
    """A realistic customer list: Arabic and English headers mixed with junk, phones in every format, duplicates, missing names."""
    head = ['الاسم', 'الموبايل', 'الايميل', 'الشركة', 'المدينة', 'ملاحظات', 'تاريخ الميلاد']
    rows = [['قائمة عملاء 2024'], [], head]
    for i in range(n):
        name = f'عميل رقم {i:04d}'
        phone = ['010%08d' % i, '+20 10 %08d' % i, '٠١٠٠٠%05d' % i, '1%09d' % (i + 10 ** 8)][i % 4]
        rows.append([name, phone, f'c{i}@example.com' if i % 3 else '', 'شركة الأفق' if i % 10 == 0 else '', 'القاهرة', 'ملاحظة ' + str(i) if i % 50 == 0 else '', '15/03/1990' if i % 7 == 0 else ''])
    rows.append(['', '', '', '', '', '', ''])                                                # empty line in the middle
    rows.append(['مجهول بلا رقم', 'abc', 'not-an-email', '', '', '', 'yesterday'])              # bad phone / email / date
    rows.append(['', '01099999999', '', '', '', '', ''])                                       # no name
    rows.append(['عميل رقم 0005 نسخة', '010%08d' % 5, '', '', '', '', ''])                     # same phone as row 5 inside the file
    rows.append(['عميل رقم 0006', '', '', '', '', '', ''])                                     # name only, same as row 6 inside the file
    return rows


class Import(BusinessBase):
    def upload(self, client, name, data):
        return client.call('POST', '/api/upload?name=' + name, raw=data)['src']

    def test_preview_maps_arabic_headers_and_skips_the_junk_title_row(self):
        src = self.upload(self.ac, 'clients.xlsx', xlsx.build([('عملاء', messy_sheet(30)[0], messy_sheet(30)[1:])]))
        # the junk title row is row 0; the person tells the wizard the header is row 3 (index 2)
        pv = self.ac.post('/api/import/preview', {'src': src, 'headerRow': 2})
        self.assertEqual(pv['headers'][:4], ['الاسم', 'الموبايل', 'الايميل', 'الشركة'])
        self.assertEqual(pv['mapping']['0'], 'name')
        self.assertEqual(pv['mapping']['1'], 'phone')
        self.assertEqual(pv['mapping']['2'], 'email')
        self.assertEqual(pv['mapping']['3'], 'company')
        self.assertEqual(pv['mapping']['4'], 'city')
        self.assertEqual(pv['mapping']['5'], 'notes')
        self.assertEqual(pv['mapping']['6'], 'birthday')

    def test_full_import_reports_duplicates_never_overwrites_and_can_be_undone(self):
        put(self.ac, 'parties', 'exist-1', {'name': 'موجود قبل كده', 'phone': '+201000000000', 'city': 'الجيزة'})   # same phone as row 0
        before_notes = self.ac.get('/api/get/parties/exist-1')
        sheet = messy_sheet(2000)
        src = self.upload(self.ac, 'big.xlsx', xlsx.build([('Sheet1', sheet[0], sheet[1:])]))
        pv = self.ac.post('/api/import/preview', {'src': src, 'headerRow': 2})
        self.assertEqual(pv['total'], 2000 + 4)
        total_before = self.ac.get('/api/q/parties?limit=1')['total']
        an = self.ac.post('/api/import/analyze', {'src': src, 'headerRow': 2, 'mapping': pv['mapping'], 'role': 'lead', 'name': 'big.xlsx'})
        s = an['summary']
        self.assertEqual(s['match'], 1, s)                    # row 0 = the existing client
        self.assertGreaterEqual(s['file_dup'], 1)             # the copy of row 5 inside the file
        self.assertGreaterEqual(s['maybe'], 1)                # same name as row 6, no phone
        self.assertEqual(s['invalid'], 1)                     # no name
        self.assertEqual(s['empty'], 1)
        self.assertEqual(s['create'] + s['maybe'] + s['match'] + s['file_dup'] + s['invalid'] + s['empty'], 2004 + 1)
        self.assertGreaterEqual(s['warn'], 1)
        # nothing was saved by analysing
        self.assertEqual(self.ac.get('/api/q/parties?limit=1')['total'], total_before)
        warn = [r for r in an['rows'] if r['warn']]
        self.assertTrue(any('bad_phone' in r['warn'] for r in warn))
        mt = next(r for r in an['rows'] if r['status'] == 'match')
        self.assertEqual((mt['match'], mt['action']), ('exist-1', 'fill'))
        rep = self.ac.post('/api/import/commit', {'token': an['token'], 'overrides': {}})
        self.assertGreaterEqual(rep['created'], 2000 - 1)
        self.assertEqual(rep['filled'] + rep['unchanged'], 1)
        self.assertEqual(rep['failed'], [])
        import sqlite3
        path = os.path.join(self.srv.root, 'backups', 'db', rep['backup'])
        self.assertTrue(rep['backup'].endswith('pre-import.db') and os.path.exists(path), 'a backup is made before importing')
        db = sqlite3.connect(path)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM parties WHERE import_batch=?', (rep['batch'],)).fetchone()[0], 0, 'the backup holds the state BEFORE the import')
        db.close()
        after = self.ac.get('/api/get/parties/exist-1')
        self.assertEqual((after['name'], after['city'], after['phone']), (before_notes['name'], 'الجيزة', before_notes['phone']), 'existing values are never overwritten')
        # phones are stored normalised, companies became organisations linked with works_at, birthday is ISO
        p7 = self.ac.get('/api/q/parties?f=name:eq:' + quote('عميل رقم 0007') + '&limit=5')['rows'][0]
        self.assertTrue(p7['phone'].startswith('+20'))
        self.assertEqual(self.ac.get('/api/q/parties?f=kind:eq:org&f=name:eq:' + quote('شركة الأفق') + '&limit=5')['total'], 1, 'one company, not 200')
        self.assertEqual(self.ac.get('/api/q/party_relations?limit=1')['total'] >= 200, True)
        p0 = self.ac.get('/api/q/parties?f=name:eq:' + quote('عميل رقم 0014') + '&limit=1')['rows'][0]
        self.assertEqual(p0['birthday'], '1990-03-15')
        self.assertEqual(self.ac.get('/api/q/party_roles?f=role:eq:lead&limit=1')['total'] >= 2000 - 1, True)
        # the whole import can be undone in one step; the existing client stays
        undo = self.ac.post('/api/import/undo', {'batch': rep['batch']})
        self.assertGreaterEqual(undo['removed'], 2000 - 1)
        left = self.ac.get('/api/q/parties?f=import_batch:eq:' + rep['batch'] + '&limit=5')['rows']
        self.assertEqual([(r['kind'], r['name']) for r in left], [('org', 'شركة الأفق')], 'the company stays: the existing client that was filled in works there')
        self.assertEqual(undo['kept'], 1)
        self.assertEqual(self.ac.get('/api/get/parties/exist-1')['name'], 'موجود قبل كده')

    def test_analysis_belongs_to_its_creator(self):
        src = self.upload(self.ac, 'small.csv', ('الاسم,الموبايل\nمحمد,01000000123\n').encode('utf-8'))
        pv = self.ac.post('/api/import/preview', {'src': src})
        an = self.ac.post('/api/import/analyze', {'src': src, 'mapping': pv['mapping'], 'role': 'client'})
        # another administrator cannot use it
        self.ac.post('/api/users/save', {'username': 'admin2', 'full_name': 'Admin Two', 'password': 'Silver-Moon-7704', 'must_change': False, 'role': 'administrator',
                                         'perms': self.ac.get('/api/me')['perms'], 'data_scope': 'all', 'scopes': []})
        other = self.srv.client()
        other.login('admin2', 'Silver-Moon-7704')
        with self.assertRaises(ApiError) as e:
            other.post('/api/import/commit', {'token': an['token']})
        self.assertIn('import_expired', e.exception.msg)
        rep = self.ac.post('/api/import/commit', {'token': an['token']})
        self.assertEqual(rep['created'], 1)

    def test_csv_from_arabic_excel_windows_1256(self):
        raw = 'الاسم;الموبايل;الايميل\nسمير علي;01011112222;samir@example.com\n'.encode('cp1256')
        src = self.upload(self.ac, 'arabic.csv', raw)
        pv = self.ac.post('/api/import/preview', {'src': src})
        self.assertEqual(pv['headers'][:3], ['الاسم', 'الموبايل', 'الايميل'])
        self.assertEqual(pv['sample'][0][0], 'سمير علي')

    def test_unsafe_or_wrong_files_are_refused_kindly(self):
        for name, data in (('x.xlsx', b'not a zip'), ('x.csv', b'\xff\xfe\x00\x00broken')):
            src = self.upload(self.ac, name, data) if name.endswith('.xlsx') else None
            if src:
                with self.assertRaises(ApiError) as e:
                    self.ac.post('/api/import/preview', {'src': src})
                self.assertIn('E:bad_file', e.exception.msg)
        with self.assertRaises(ApiError):
            self.ac.post('/api/import/preview', {'src': '/files/cas/../../etc/passwd'})
        with self.assertRaises(ApiError):
            self.ac.post('/api/import/preview', {'src': '/etc/passwd'})

    def test_analysis_needs_a_name_column(self):
        src = self.upload(self.ac, 'nn.csv', 'الموبايل\n01000000999\n'.encode('utf-8'))
        with self.assertRaises(ApiError) as e:
            self.ac.post('/api/import/analyze', {'src': src, 'mapping': {'0': 'phone'}, 'role': 'lead'})
        self.assertIn('need_name_column', e.exception.msg)


if __name__ == '__main__':
    unittest.main()
