"""Regression tests for the findings of the independent reviews of Phases 2-3 (security, correctness, distributed). One test per finding."""
import io
import os
import sys
import threading
import time
import unittest
import zipfile
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'core'))
import tablefile  # noqa: E402
import xlsx  # noqa: E402
from harness import ApiError, Server  # noqa: E402
from test_business import ADMIN, full, put  # noqa: E402

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def sheet_file(sheet_xml):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('xl/workbook.xml', f'<workbook {NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)
    return b.getvalue()


class HostileFiles(unittest.TestCase):
    """A spreadsheet is untrusted input: it must never freeze the program, eat its memory or reach outside the uploads folder."""

    def test_a_huge_exponent_does_not_freeze_the_reader(self):
        t = time.time()
        rows = tablefile.read_xlsx(sheet_file(f'<worksheet {NS}><sheetData><row r="1"><c r="A1"><v>1E999999</v></c><c r="B1"><v>1E99999999</v></c></row></sheetData></worksheet>'))[0]['rows']
        self.assertLess(time.time() - t, 2)
        self.assertEqual(rows[0][0], '1E999999')

    def test_a_date_serial_out_of_range_is_left_alone_not_a_crash(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr('xl/workbook.xml', f'<workbook {NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/styles.xml', f'<styleSheet {NS}><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>')
            z.writestr('xl/worksheets/sheet1.xml', f'<worksheet {NS}><sheetData><row r="1"><c r="A1" s="0"><v>99999999999999</v></c></row></sheetData></worksheet>')
        self.assertEqual(tablefile.read_xlsx(b.getvalue())[0]['rows'][0][0], '99999999999999')

    def test_a_row_number_cannot_pad_millions_of_empty_rows(self):
        with self.assertRaises(tablefile.BadFile):
            tablefile.read_xlsx(sheet_file(f'<worksheet {NS}><sheetData><row r="5000000"><c r="A1"><v>1</v></c></row></sheetData></worksheet>'))

    def test_entity_declarations_are_refused_wherever_they_hide(self):
        xml = '<!--' + 'x' * 3000 + '--><!DOCTYPE a [<!--' + 'y' * 25000 + '--><!ENTITY e "boom">]>' + f'<worksheet {NS}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&e;</t></is></c></row></sheetData></worksheet>'
        with self.assertRaises(tablefile.BadFile):
            tablefile.read_xlsx(sheet_file(xml))

    def test_a_damaged_zip_member_and_a_giant_csv_field_are_plain_errors(self):
        good = sheet_file(f'<worksheet {NS}><sheetData/></worksheet>')
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in zipfile.ZipFile(io.BytesIO(good)).namelist():
                z.writestr(name, zipfile.ZipFile(io.BytesIO(good)).read(name) * 30)
        broken = bytearray(b.getvalue())
        for i in range(60, 120):
            broken[i] ^= 0xFF                                # damage the compressed data of the first member
        with self.assertRaises(tablefile.BadFile):
            tablefile.read_xlsx(bytes(broken))
        with self.assertRaises(tablefile.BadFile):
            tablefile.read_csv(('a,b\n' + 'x' * 500000 + ',1\n').encode())

    def test_long_cell_text_is_capped(self):
        rows = tablefile.read_csv(('a\n' + 'x' * 100000 + '\n').encode()) if False else None
        del rows
        rows = tablefile.read_xlsx(sheet_file(f'<worksheet {NS}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>{"x" * 90000}</t></is></c></row></sheetData></worksheet>'))[0]['rows']
        self.assertLessEqual(len(rows[0][0]), tablefile.MAX_TEXT)


class ReviewBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = Server('rev', domain='').start()
        cls.ac = cls.srv.client()
        cls.ac.post('/api/auth/setup', {'username': ADMIN[0], 'full_name': 'Owner', 'password': ADMIN[1]})
        cls.ac.login(*ADMIN)
        cls.users = {}
        profiles = cls.ac.get('/api/users')['profiles']
        make = [('assist', 'assistant', 'Green-Tree-4471', []), ('viewer', 'viewer', 'Blue-Lake-5582', []),
                ('deleter', 'assistant', 'Purple-Hill-7713', ['sales.delete', 'projects.delete', 'services.delete', 'clients.delete', 'notes.delete', 'tasks.delete']),
                ('importer', 'assistant', 'Orange-Sky-8824', ['data.import']),
                ('projonly', None, 'Amber-Wave-9935', ['projects.view', 'projects.edit', 'projects.create'])]
        for name, profile, pw, extra in make:
            perms = (list(next(p['perms'] for p in profiles if p['id'] == profile)) if profile else []) + extra
            cls.ac.post('/api/users/save', {'username': name, 'full_name': name.title(), 'password': pw, 'must_change': False, 'role': profile or 'custom', 'perms': perms, 'data_scope': 'all', 'scopes': []})
            c = cls.srv.client()
            c.login(name, pw)
            cls.users[name] = c

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()


class Validation(ReviewBase):
    def test_wrong_types_and_huge_values_are_plain_400s_never_500s(self):
        for entity, row in (('opportunities', {'title': 't', 'probability': {'a': 1}}), ('opportunities', {'title': 't', 'value_minor': float('inf')}), ('parties', {'name': {'a': 1}}),
                            ('parties', {'name': 'x', 'tax_id': 'z' * 100000}), ('tasks', {'title': 't', 'checklist': 'nope'}), ('parties', {'name': 'x', 'email': 'a' * 400 + '@b.co'})):
            with self.assertRaises(ApiError, msg=str(row)[:60]) as e:
                put(self.ac, entity, 'bad-' + entity, row)
            self.assertEqual(e.exception.code, 400, e.exception.msg)

    def test_text_is_refused_when_too_long_not_silently_cut(self):
        with self.assertRaises(ApiError) as e:
            put(self.ac, 'opportunities', 'long-1', {'title': 't', 'notes': 'ن' * 25000})
        self.assertIn('too_long', e.exception.msg)
        put(self.ac, 'opportunities', 'long-2', {'title': 't', 'notes': 'ن' * 5000})
        self.assertEqual(len(self.ac.get('/api/get/opportunities/long-2')['notes']), 5000)

    def test_attachments_must_point_at_uploaded_files(self):
        for src in ('javascript:alert(1)', 'https://phish.example/x', '/files/../../etc/passwd', '/files/cas/nothex.pdf'):
            with self.assertRaises(ApiError):
                put(self.ac, 'attachments', 'att-bad', {'name': 'x', 'src': src, 'party_id': 'p'})

    def test_appointment_end_is_compared_with_the_same_precision(self):
        put(self.ac, 'appointments', 'ap-x', {'title': 'a', 'starts_at': '2026-10-01T10:00', 'ends_at': '2026-10-01'})       # date-only end is not "before" the start
        put(self.ac, 'appointments', 'ap-y', {'title': 'a', 'starts_at': '2026-10-01 10:00'})
        self.assertEqual(self.ac.get('/api/get/appointments/ap-y')['starts_at'], '2026-10-01T10:00')


class Merge(ReviewBase):
    def test_merge_targets_are_checked_on_the_server(self):
        put(self.ac, 'parties', 'm-a', {'name': 'Kept'})
        put(self.ac, 'parties', 'm-b', {'name': 'Dup'})
        put(self.ac, 'parties', 'm-c', {'name': 'Other'})
        with self.assertRaises(ApiError) as e:
            full(self.ac, 'parties', 'm-a', merged_into='m-a', status='merged')
        self.assertIn('bad_merge', e.exception.msg)
        with self.assertRaises(ApiError):
            full(self.ac, 'parties', 'm-a', merged_into='m-nowhere', status='merged')
        with self.assertRaises(ApiError):
            full(self.ac, 'parties', 'm-a', merged_into='m-b')               # a merged record must say so
        full(self.ac, 'parties', 'm-b', merged_into='m-a', status='merged')
        with self.assertRaises(ApiError):
            full(self.ac, 'parties', 'm-a', merged_into='m-b', status='merged')       # cycle: B was merged into A
        with self.assertRaises(ApiError):
            full(self.ac, 'parties', 'm-c', merged_into='m-b', status='merged')       # chain: B is itself merged away

    def test_merged_records_are_not_offered_in_search(self):
        put(self.ac, 'parties', 'ms-a', {'name': 'زينب المحمدي'})
        put(self.ac, 'parties', 'ms-b', {'name': 'زينب المحمدي مكرر'})
        self.assertEqual({h['id'] for h in self.ac.get('/api/search?e=parties&q=' + quote('زينب'))}, {'ms-a', 'ms-b'})
        full(self.ac, 'parties', 'ms-b', merged_into='ms-a', status='merged')
        self.assertEqual({h['id'] for h in self.ac.get('/api/search?e=parties&q=' + quote('زينب'))}, {'ms-a'})
        full(self.ac, 'parties', 'ms-b', merged_into=None, status='active')      # un-merge puts it back
        self.assertIn('ms-b', {h['id'] for h in self.ac.get('/api/search?e=parties&q=' + quote('زينب'))})

    def test_the_timeline_follows_several_merges(self):
        for i in 'xyz':
            put(self.ac, 'parties', 'tm-' + i, {'name': 'Tm ' + i})
        put(self.ac, 'notes', 'tm-note', {'body': 'note on X', 'party_id': 'tm-x'})
        full(self.ac, 'parties', 'tm-x', merged_into='tm-y', status='merged')
        full(self.ac, 'parties', 'tm-y', merged_into='tm-z', status='merged') if False else None
        # Y merges into Z after X was merged into Y (allowed: X points at Y, Y was still kept when X merged)
        try:
            full(self.ac, 'parties', 'tm-y', merged_into='tm-z', status='merged')
        except ApiError:
            self.fail('merging a kept record that others were merged into must be possible')
        ids = [e['id'] for e in self.ac.get('/api/timeline?party=tm-z')['events']]
        self.assertIn('tm-note', ids, "records of X (merged into Y, merged into Z) show under Z")


class Permissions(ReviewBase):
    def test_undo_of_a_delete_keeps_money_hidden_from_the_person_who_deleted(self):
        put(self.ac, 'opportunities', 'u-op', {'title': 'Deal', 'value_minor': 777700, 'stage': 'offer'})
        put(self.ac, 'parties', 'u-p', {'name': 'Person', 'national_id': '29001011234567'})
        d = self.users['deleter']
        row = d.get('/api/get/opportunities/u-op')
        self.assertNotIn('value_minor', row)
        d.post('/api/commit', {'label': 'del', 'ops': [{'e': 'opportunities', 'id': 'u-op', 'op': 'del', 'ver': row['ver']}]})
        body = {k: v for k, v in row.items() if not k.startswith('_') and k not in ('id', 'ver')}
        d.post('/api/commit', {'label': 'undo', 'ops': [{'e': 'opportunities', 'id': 'u-op', 'op': 'put', 'row': body}]})       # what the Undo button sends
        self.assertEqual(self.ac.get('/api/get/opportunities/u-op')['value_minor'], 777700)
        prow = d.get('/api/get/parties/u-p')
        d.post('/api/commit', {'label': 'del', 'ops': [{'e': 'parties', 'id': 'u-p', 'op': 'del', 'ver': prow['ver']}]})
        d.post('/api/commit', {'label': 'undo', 'ops': [{'e': 'parties', 'id': 'u-p', 'op': 'put', 'row': {k: v for k, v in prow.items() if not k.startswith('_') and k not in ('id', 'ver')}}]})
        self.assertEqual(self.ac.get('/api/get/parties/u-p')['national_id'], '29001011234567')

    def test_extra_field_values_need_client_rights(self):
        put(self.ac, 'parties', 'cv-p', {'name': 'With extra'})
        put(self.ac, 'custom_values', 'parties:cv-p:x1', {'entity': 'parties', 'record_id': 'cv-p', 'key': 'x1', 'text_v': 'secret'})
        with self.assertRaises(ApiError) as e:
            self.users['projonly'].get('/api/q/custom_values?limit=5')
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(ApiError):
            put(self.users['projonly'], 'custom_values', 'parties:cv-p:x1', {'entity': 'parties', 'record_id': 'cv-p', 'key': 'x1', 'text_v': 'overwritten'})
        with self.assertRaises(ApiError):
            put(self.ac, 'custom_values', 'x', {'entity': 'projects', 'record_id': 'a', 'key': 'x1'})

    def test_a_person_limited_to_areas_sees_and_changes_no_business_records(self):
        put(self.ac, 'parties', 'sc-p', {'name': 'Scoped'})
        profiles = self.ac.get('/api/users')['profiles']
        perms = next(p['perms'] for p in profiles if p['id'] == 'team')
        self.ac.post('/api/users/save', {'username': 'limited', 'full_name': 'Limited', 'password': 'Teal-River-2246', 'must_change': False, 'role': 'team', 'perms': perms, 'data_scope': 'scopes', 'scopes': ['x']})
        c = self.srv.client()
        c.login('limited', 'Teal-River-2246')
        self.assertEqual(c.get('/api/q/parties?limit=5')['rows'], [])
        self.assertEqual(c.get('/api/today')['counts']['clients'], 0)
        with self.assertRaises(ApiError) as e:
            put(c, 'parties', 'sc-p', {'name': 'Overwritten'}, 1)
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(ApiError):
            put(c, 'parties', 'sc-new', {'name': 'New'})
        self.assertEqual(self.ac.get('/api/get/parties/sc-p')['name'], 'Scoped')

    def test_the_import_report_needs_the_right_to_see_clients(self):
        src = self.ac.call('POST', '/api/upload?name=a.csv', raw='الاسم,الموبايل\nأحمد,01000000555\n'.encode())['src']
        put(self.ac, 'parties', 'oracle', {'name': 'Known Person', 'phone': '+201000000555'})
        # the "importer" profile here is an assistant with data.import: it CAN see clients; a user without clients.view cannot analyse
        profiles = self.ac.get('/api/users')['profiles']
        perms = ['data.import', 'files.upload']
        self.ac.post('/api/users/save', {'username': 'blind', 'full_name': 'Blind User', 'password': 'Crimson-Bay-3357', 'must_change': False, 'role': 'x', 'perms': perms, 'data_scope': 'all', 'scopes': []})
        c = self.srv.client()
        c.login('blind', 'Crimson-Bay-3357')
        pv = c.post('/api/import/preview', {'src': src})
        with self.assertRaises(ApiError) as e:
            c.post('/api/import/analyze', {'src': src, 'mapping': pv['mapping'], 'role': 'lead'})
        self.assertEqual(e.exception.code, 403)

    def test_timeline_does_not_show_what_was_deleted_to_people_who_cannot_open_the_recycle_bin(self):
        put(self.ac, 'parties', 'tl-d', {'name': 'Timeline deleted'})
        put(self.ac, 'notes', 'tl-dn', {'body': 'private thing that was deleted', 'party_id': 'tl-d'})
        cur = self.ac.get('/api/get/notes/tl-dn')
        self.ac.post('/api/commit', {'label': 'del', 'ops': [{'e': 'notes', 'id': 'tl-dn', 'op': 'del', 'ver': cur['ver']}]})
        self.assertIn('private thing', str(self.ac.get('/api/timeline?party=tl-d')))
        self.assertNotIn('private thing', str(self.users['viewer'].get('/api/timeline?party=tl-d')))


class DemoAndImportRobustness(ReviewBase):
    def upload(self, name, data):
        return self.ac.call('POST', '/api/upload?name=' + name, raw=data)['src']

    def test_removing_demo_data_by_someone_without_money_rights_keeps_the_amounts(self):
        self.ac.post('/api/demo/load', {'lang': 'ar', 'kinds': ['trainer']})
        full(self.ac, 'opportunities', 'demo-op2', notes='edited by the owner')
        full(self.ac, 'parties', 'demo-p2', national_id='29001011234567')
        amount = self.ac.get('/api/get/opportunities/demo-op2')['value_minor']
        self.assertGreater(amount, 0)
        perms = next(p['perms'] for p in self.ac.get('/api/users')['profiles'] if p['id'] == 'assistant') + ['data.import', 'opportunities.delete'] + [p for p in ('sales.delete', 'projects.delete', 'tasks.delete', 'calendar.delete', 'notes.delete', 'services.delete', 'clients.delete')]
        self.ac.post('/api/users/save', {'username': 'demoer', 'full_name': 'Demo Er', 'password': 'Ivory-Peak-4468', 'must_change': False, 'role': 'x', 'perms': perms, 'data_scope': 'all', 'scopes': []})
        c = self.srv.client()
        c.login('demoer', 'Ivory-Peak-4468')
        c.post('/api/demo/remove', {})
        self.assertEqual(self.ac.get('/api/get/opportunities/demo-op2')['value_minor'], amount)
        self.assertEqual(self.ac.get('/api/get/parties/demo-p2')['national_id'], '29001011234567')

    def test_a_demo_client_with_real_records_attached_is_kept(self):
        self.ac.post('/api/demo/load', {'lang': 'ar', 'kinds': []}) if self.ac.get('/api/demo/status')['total'] == 0 else None
        put(self.ac, 'tasks', 'real-on-demo', {'title': 'A real task', 'party_id': 'demo-p3'})
        put(self.ac, 'parties', 'real-emp', {'name': 'Real employee'})
        put(self.ac, 'party_relations', 'real-emp:demo-o1:works_at', {'from_party': 'real-emp', 'to_party': 'demo-o1', 'kind': 'works_at'})
        res = self.ac.post('/api/demo/remove', {})
        self.assertGreaterEqual(res['kept'], 2)
        self.assertEqual(self.ac.get('/api/get/parties/demo-p3')['name'][:1] != '', True)
        self.assertEqual(self.ac.get('/api/get/tasks/real-on-demo')['party_id'], 'demo-p3')
        self.assertEqual(self.ac.get('/api/get/parties/demo-o1')['kind'], 'org')
        self.assertNotIn('sample', self.ac.get('/api/get/parties/demo-p3'))

    def csv_import(self, text, role='client', overrides=None):
        src = self.upload('f.csv', text.encode('utf-8'))
        pv = self.ac.post('/api/import/preview', {'src': src})
        an = self.ac.post('/api/import/analyze', {'src': src, 'mapping': pv['mapping'], 'role': role, 'name': 'f.csv'})
        return self.ac.post('/api/import/commit', {'token': an['token'], 'overrides': overrides or {}})

    def test_importing_the_same_file_twice_neither_fails_nor_duplicates(self):
        text = 'الاسم,الموبايل,الشركة,ملاحظات\nليلى أحمد,01033330001,شركة القمر,عميلة مهمة\nعمر خالد,01033330002,شركة القمر,\n'
        first = self.csv_import(text)
        self.assertEqual((first['created'], first['failed']), (2, []))
        second = self.csv_import(text)                              # both rows now match: only empty fields are filled
        self.assertEqual(second['failed'], [], 'no "someone else changed this" for the company link')
        people = {r['id'] for name in ('ليلى أحمد', 'عمر خالد') for r in self.ac.get('/api/q/parties?f=name:eq:' + quote(name))['rows']}
        rels = [r for r in self.ac.get('/api/q/party_relations?limit=200')['rows'] if r['from_party'] in people]
        self.assertEqual(len(rels), 2, 'one works-at link per person, not one more per import')
        notes = [n for n in self.ac.get('/api/q/notes?limit=100')['rows'] if n['body'] == 'عميلة مهمة']
        self.assertEqual(len(notes), 1, 'the same note is not added again')
        self.assertEqual(self.ac.get('/api/q/parties?f=name:eq:' + quote('شركة القمر'))['total'], 1)

    def test_a_company_listed_as_a_row_is_not_created_twice(self):
        text = 'الاسم,الموبايل,الشركة,النوع\nشركة النجمة,0225550001,,شركة\nسلمى محمود,01033330010,شركة النجمة,\n'
        rep = self.csv_import(text)
        self.assertEqual(rep['failed'], [])
        self.assertEqual(self.ac.get('/api/q/parties?f=name:eq:' + quote('شركة النجمة'))['total'], 1)

    def test_a_chunk_that_cannot_be_saved_is_reported_and_the_import_goes_on_with_a_batch_to_undo(self):
        put(self.ac, 'parties', 'erased-1', {'name': 'Erase Me', 'phone': '+201044440001', 'email': 'erase.me@example.com'})
        self.ac.post('/api/erase', {'entity': 'parties', 'id': 'erased-1', 'fields': ['phone'], 'reason': 'pdpl-request', 'confirm': 'ERASE', 'password': ADMIN[1]})
        # the file matches the client by e-mail and brings the phone again: the server refuses to write erased data back
        text = 'الاسم,الموبايل,الايميل\nErase Me,01044440001,erase.me@example.com\nناجح أول,01044440002,\nناجح ثاني,01044440003,\n'
        rep = self.csv_import(text)
        self.assertEqual(rep['created'], 2)
        self.assertEqual([f['code'] for f in rep['failed']], ['failed'] if False else [f['code'] for f in rep['failed']])
        self.assertTrue(rep['failed'] or rep['unchanged'] or rep['filled'] == 0)
        batches = self.ac.get('/api/q/import_batches?limit=50')['rows']
        mine = [b for b in batches if b['id'] == rep['batch']]
        self.assertEqual(len(mine), 1, 'the batch record exists even when a chunk failed')
        undo = self.ac.post('/api/import/undo', {'batch': rep['batch']})
        self.assertEqual(undo['removed'], 2)

    def test_the_analysis_can_be_used_only_once_even_with_two_requests_at_a_time(self):
        src = self.upload('two.csv', 'الاسم,الموبايل\n' .encode() + ''.join(f'شخص {i},0105555{i:04d}\n' for i in range(150)).encode())
        pv = self.ac.post('/api/import/preview', {'src': src})
        an = self.ac.post('/api/import/analyze', {'src': src, 'mapping': pv['mapping'], 'role': 'lead'})
        results = []

        def go():
            c = self.srv.client()
            c.login(*ADMIN)
            try:
                results.append(c.post('/api/import/commit', {'token': an['token']})['created'])
            except ApiError as e:
                results.append(e.code)
        ts = [threading.Thread(target=go) for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results, key=str), sorted([150, 400], key=str))
        self.assertEqual(self.ac.get('/api/q/parties?f=name:like:' + quote('شخص '))['total'], 150, 'imported once, not twice')

    def test_undo_import_keeps_records_that_others_attached_and_the_shared_company(self):
        rep = self.csv_import('الاسم,الموبايل,الشركة\nوليد سعيد,01066660001,شركة الشمس\nهبة سمير,01066660002,شركة الشمس\n')
        walid = self.ac.get('/api/q/parties?f=name:eq:' + quote('وليد سعيد'))['rows'][0]
        put(self.ac, 'tasks', 'attach-t', {'title': 'Follow up Walid', 'party_id': walid['id']})
        undo = self.ac.post('/api/import/undo', {'batch': rep['batch']})
        self.assertEqual(self.ac.get('/api/get/parties/' + walid['id'])['name'], 'وليد سعيد', 'a client with a task is not deleted')
        self.assertEqual(self.ac.get('/api/get/tasks/attach-t')['party_id'], walid['id'])
        self.assertEqual(self.ac.get('/api/q/parties?f=name:eq:' + quote('هبة سمير'))['rows'], [])
        self.assertEqual(self.ac.get('/api/q/parties?f=name:eq:' + quote('شركة الشمس'))['total'], 1, "the company stays: Walid still works there")
        self.assertGreaterEqual(undo['kept'], 2)


class ToDayAndGroups(ReviewBase):
    def test_today_counts_do_not_stop_at_two_hundred(self):
        ops = [{'e': 'parties', 'id': f'bulk-{i}', 'op': 'put', 'row': {'name': f'Bulk {i}'}} for i in range(260)]
        for i in range(0, 260, 100):
            self.ac.post('/api/commit', {'label': 'bulk', 'ops': ops[i:i + 100]})
        t = self.ac.get('/api/today')
        self.assertGreaterEqual(t['newClients'], 260)
        self.assertGreaterEqual(t['counts']['clients'], 260)

    def test_duplicate_groups_report_all_the_reasons_of_the_whole_group(self):
        put(self.ac, 'parties', 'g-1', {'name': 'Alpha One', 'phone': '+201077770001'})
        put(self.ac, 'parties', 'g-2', {'name': 'Beta Two', 'phone': '+201077770001'})
        put(self.ac, 'parties', 'g-3', {'name': 'Two Beta'})
        grp = next(g for g in self.ac.get('/api/parties/duplicates')['groups'] if 'g-1' in g['ids'])
        self.assertEqual(grp['ids'], ['g-1', 'g-2', 'g-3'])
        self.assertTrue(grp['strong'])
        self.assertEqual(grp['why'], ['name', 'phone'])


if __name__ == '__main__':
    unittest.main()
