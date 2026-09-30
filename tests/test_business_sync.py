"""The business entities on several PCs that work at the same time (offline) and meet later: nothing is lost, every PC ends with
the same data, and the merge rules do what a person would expect. In-process PCs (no network), business entities registered for
the duration of this file only."""
import json
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'server'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'server', 'core'))

import registry  # noqa: E402
import business  # noqa: E402
from cluster import Cluster  # noqa: E402   (registers the engine test domain)

_SNAP = {}


def setUpModule():
    """Registers the business entities for THIS file only (a unittest run imports every module before running any test)."""
    for n in ('ENTITIES', 'META', 'COUNTERS', 'RESOLVERS', 'SPECS', 'REPLICATED'):
        v = getattr(registry, n)
        _SNAP[n] = dict(v) if isinstance(v, dict) else set(v)
    business.register()


def tearDownModule():
    for n, snap in _SNAP.items():           # leave the shared registry as we found it for the other test files
        cur = getattr(registry, n)
        cur.clear()
        cur.update(snap)


def put(peer, entity, rid, row, ver=None, label='x'):
    return peer.commit(label, [{'e': entity, 'id': rid, 'op': 'put', 'ver': ver, 'row': row}])


def row(peer, entity, rid):
    return peer.store.get(entity, rid)


class Concurrent(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(3)
        self.addCleanup(lambda: [p.close() for p in self.c.peers] and shutil.rmtree(self.c.root, ignore_errors=True))
        self.a, self.b, self.d = self.c.peers

    def meet(self):
        self.c.converge()
        fps = self.c.fingerprints()
        self.assertEqual(len(set(fps)), 1, 'all PCs end with identical data')
        confl = {json.dumps([{**c, 'row': {k: v for k, v in c['row'].items() if k != 'ver'}} for c in p.store.conflicts()], sort_keys=True, default=str) for p in self.c.peers}   # ver is a local counter
        self.assertEqual(len(confl), 1, 'and see the same things to decide')

    def test_two_people_add_different_records_offline_and_both_are_kept(self):
        put(self.a, 'parties', 'p-a', {'name': 'من الجهاز الأول'})
        put(self.b, 'parties', 'p-b', {'name': 'من الجهاز التاني'})
        put(self.d, 'tasks', 't-d', {'title': 'مهمة من التالت', 'party_id': 'p-a'})
        self.meet()
        for p in self.c.peers:
            self.assertEqual({r for r in ('p-a', 'p-b') if row(p, 'parties', r)}, {'p-a', 'p-b'})
            self.assertEqual(row(p, 'tasks', 't-d')['title'], 'مهمة من التالت')

    def test_different_fields_of_one_client_edited_at_the_same_time_are_both_kept(self):
        put(self.a, 'parties', 'p1', {'name': 'منى', 'phone': '+201000000001'})
        self.c.converge()
        ra, rb = row(self.a, 'parties', 'p1'), row(self.b, 'parties', 'p1')
        put(self.a, 'parties', 'p1', {'name': 'منى', 'phone': '+201000000002', 'kind': 'person', 'status': 'active'}, ra['ver'])
        put(self.b, 'parties', 'p1', {'name': 'منى', 'phone': '+201000000001', 'city': 'القاهرة', 'kind': 'person', 'status': 'active'}, rb['ver'])
        self.meet()
        r = row(self.d, 'parties', 'p1')
        self.assertEqual((r['phone'], r['city']), ('+201000000002', 'القاهرة'))

    def test_task_finished_on_one_pc_and_still_being_worked_on_another_ends_finished(self):
        put(self.a, 'tasks', 't1', {'title': 'مهمة', 'status': 'todo'})
        self.c.converge()
        va, vb = row(self.a, 'tasks', 't1')['ver'], row(self.b, 'tasks', 't1')['ver']
        put(self.a, 'tasks', 't1', {'title': 'مهمة', 'status': 'done'}, va)
        put(self.b, 'tasks', 't1', {'title': 'مهمة', 'status': 'doing'}, vb)
        self.meet()
        self.assertEqual({row(p, 'tasks', 't1')['status'] for p in self.c.peers}, {'done'})

    def test_opportunity_won_on_one_pc_and_lost_on_another_ends_won(self):
        put(self.a, 'opportunities', 'o1', {'title': 'صفقة', 'stage': 'offer'})
        self.c.converge()
        va, vb = row(self.a, 'opportunities', 'o1')['ver'], row(self.b, 'opportunities', 'o1')['ver']
        put(self.a, 'opportunities', 'o1', {'title': 'صفقة', 'stage': 'won'}, va)
        put(self.b, 'opportunities', 'o1', {'title': 'صفقة', 'stage': 'lost'}, vb)
        self.meet()
        self.assertEqual({row(p, 'opportunities', 'o1')['stage'] for p in self.c.peers}, {'won'})

    def test_the_same_role_added_on_two_pcs_is_one_role(self):
        put(self.a, 'parties', 'p2', {'name': 'عميل'})
        self.c.converge()
        put(self.a, 'party_roles', 'p2:client', {'party_id': 'p2', 'role': 'client'})
        put(self.b, 'party_roles', 'p2:client', {'party_id': 'p2', 'role': 'client'})
        self.meet()
        for p in self.c.peers:
            n = p.store.conn.execute("SELECT COUNT(*) FROM party_roles WHERE party_id='p2' AND deleted=0").fetchone()[0]
            self.assertEqual(n, 1)

    def test_demo_data_loaded_on_two_pcs_does_not_duplicate(self):
        from business import demo
        for peer in (self.a, self.b):
            for op in demo.build('ar', ['trainer']):
                peer.commit('demo', [op])
        self.c.converge()
        self.assertEqual(len({p.store.fingerprint() for p in self.c.peers}), 1)
        n = self.a.store.conn.execute('SELECT COUNT(*) FROM parties WHERE deleted=0').fetchone()[0]
        self.assertEqual(n, 8)

    def test_merge_on_one_pc_while_the_duplicate_is_edited_on_another_keeps_both_changes(self):
        put(self.a, 'parties', 'keep', {'name': 'الأصل', 'phone': '+201000000010'})
        put(self.a, 'parties', 'dup', {'name': 'الأصل مكرر'})
        self.c.converge()
        va = row(self.a, 'parties', 'dup')['ver']
        vb = row(self.b, 'parties', 'dup')['ver']
        put(self.a, 'parties', 'dup', {'name': 'الأصل مكرر', 'status': 'merged', 'merged_into': 'keep', 'kind': 'person'}, va)
        put(self.b, 'parties', 'dup', {'name': 'الأصل مكرر', 'city': 'الجيزة', 'kind': 'person', 'status': 'active'}, vb)
        self.meet()
        r = row(self.d, 'parties', 'dup')
        self.assertEqual(r['merged_into'], 'keep')
        self.assertEqual(r['city'], 'الجيزة')

    def test_a_note_and_a_delete_of_the_client_meet_and_nothing_disappears_silently(self):
        put(self.a, 'parties', 'gone', {'name': 'سيُحذف'})
        self.c.converge()
        v = row(self.a, 'parties', 'gone')['ver']
        self.a.commit('del', [{'e': 'parties', 'id': 'gone', 'op': 'del', 'ver': v}])
        put(self.b, 'notes', 'n-late', {'body': 'ملاحظة على عميل اتحذف', 'party_id': 'gone'})
        self.meet()
        self.assertIsNotNone(row(self.d, 'notes', 'n-late'), 'the note is kept')
        self.assertIsNone(row(self.d, 'parties', 'gone'))
        self.assertIsNotNone(self.d.store.get('parties', 'gone', include_deleted=True), 'the client is in the recycle bin, restorable')

    def test_undo_of_a_delete_does_not_overwrite_what_another_pc_changed_meanwhile(self):
        put(self.a, 'tasks', 'u1', {'title': 'Original', 'notes': 'first', 'status': 'todo'})
        self.c.converge()
        snap = {k: v for k, v in row(self.a, 'tasks', 'u1').items() if k not in ('id', 'ver')}
        v = row(self.a, 'tasks', 'u1')['ver']
        self.a.commit('del', [{'e': 'tasks', 'id': 'u1', 'op': 'del', 'ver': v}])
        put(self.b, 'tasks', 'u1', {'title': 'Edited on B', 'notes': 'B notes', 'status': 'todo'}, row(self.b, 'tasks', 'u1')['ver'])
        put(self.a, 'tasks', 'u1', snap)                         # the Undo button on A: writes the old snapshot back, no version
        self.meet()
        r = row(self.d, 'tasks', 'u1')
        self.assertIsNotNone(r, 'the task is back')
        self.assertEqual((r['title'], r['notes']), ('Edited on B', 'B notes'), "B's edit survives A's Undo")

    def test_done_at_and_lost_reason_travel_with_the_winning_status(self):
        put(self.a, 'tasks', 'f1', {'title': 't', 'status': 'todo'})
        put(self.a, 'opportunities', 'f2', {'title': 'o', 'stage': 'offer'})
        self.c.converge()
        put(self.a, 'tasks', 'f1', {'title': 't', 'status': 'done', 'done_at': '2026-10-01T10:00:00'}, row(self.a, 'tasks', 'f1')['ver'])
        put(self.b, 'tasks', 'f1', {'title': 't', 'status': 'cancelled'}, row(self.b, 'tasks', 'f1')['ver'])
        put(self.a, 'opportunities', 'f2', {'title': 'o', 'stage': 'lost', 'lost_reason': 'price', 'closed_at': '2026-10-01'}, row(self.a, 'opportunities', 'f2')['ver'])
        put(self.b, 'opportunities', 'f2', {'title': 'o', 'stage': 'won', 'closed_at': '2026-10-02'}, row(self.b, 'opportunities', 'f2')['ver'])
        self.meet()
        t = row(self.d, 'tasks', 'f1')
        self.assertEqual(t['status'], 'cancelled')
        self.assertNotIn('done_at', t, "the finish time of the losing 'done' is not kept next to 'cancelled'")
        o = row(self.d, 'opportunities', 'f2')
        self.assertEqual(o['stage'], 'won')
        self.assertNotIn('lost_reason', o)
        self.assertEqual(o['closed_at'], '2026-10-02')

    def test_merge_and_archive_at_the_same_time_end_merged(self):
        put(self.a, 'parties', 'k1', {'name': 'Keep'})
        put(self.a, 'parties', 'k2', {'name': 'Dup'})
        self.c.converge()
        put(self.a, 'parties', 'k2', {'name': 'Dup', 'kind': 'person', 'status': 'merged', 'merged_into': 'k1'}, row(self.a, 'parties', 'k2')['ver'])
        put(self.b, 'parties', 'k2', {'name': 'Dup', 'kind': 'person', 'status': 'archived'}, row(self.b, 'parties', 'k2')['ver'])
        self.meet()
        r = row(self.d, 'parties', 'k2')
        self.assertEqual((r['status'], r['merged_into']), ('merged', 'k1'))

    def test_the_delete_of_an_undone_import_loses_against_a_real_edit_on_another_pc(self):
        put(self.a, 'parties', 'imp-x-1', {'name': 'Imported', 'import_batch': 'bx'})
        self.c.converge()
        v = row(self.a, 'parties', 'imp-x-1')['ver']
        self.a.commit('undo import', [{'e': 'parties', 'id': 'imp-x-1', 'op': 'del', 'ver': v}], kind='restore')
        put(self.b, 'parties', 'imp-x-1', {'name': 'Imported', 'import_batch': 'bx', 'city': 'Cairo', 'kind': 'person', 'status': 'active'}, row(self.b, 'parties', 'imp-x-1')['ver'])
        self.c.converge()
        r = row(self.d, 'parties', 'imp-x-1')
        self.assertIsNotNone(r, "somebody's real work is not deleted by an old undo")
        self.assertEqual(r['city'], 'Cairo')


if __name__ == '__main__':
    unittest.main()
