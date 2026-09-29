"""Legal erasure (docs/SECURITY.md section 5, ADR-008): an erase order blanks personal values in the rows, the stored
history, the audit rows and the fold registers on every PC - without breaking the hash chains or signatures - and the
values never come back through late changes, new PCs, weak restores or re-entry."""
import os
import shutil
import sqlite3
import tempfile
import unittest

from cluster import Cluster, Peer  # noqa: F401 (sets sys.path)
import engine_domain  # noqa: E402,F401
from store import BadRequest  # noqa: E402

SECRET = 'Sensitive-Lecturer-Note-4711'


def dump_text(peer):
    """Everything readable in the journal and the business database of a PC, as one string."""
    parts = []
    with peer.journal.lock:
        for t in ('changes', 'audit', 'activity', 'security'):
            for r in peer.journal.conn.execute(f'SELECT * FROM {t}'):
                parts.append(' '.join(str(v) for v in tuple(r)))
    with peer.store.lock:
        for t in ('areas', 'sync_field', 'sync_flags'):
            for r in peer.store.conn.execute(f'SELECT * FROM {t}'):
                parts.append(' '.join(str(v) for v in tuple(r)))
    return '\n'.join(parts)


class EraseTest(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(3)
        self.a, self.b, self.x = self.c.peers  # a = administrator PC

    def tearDown(self):
        self.c.close()

    def make_area(self):
        self.a.commit('create', [{'e': 'areas', 'id': 'p1', 'op': 'put', 'row': {'name': 'Person One', 'description': SECRET, 'location': 'Cairo'}}])
        self.c.converge()

    def erase(self, fields=('description',)):
        self.a.store.erase('boss', '127.0.0.1', 'areas', 'p1', list(fields), 'pdpl-request', 'Law 151/2020', 'REQ-1')
        self.c.converge()

    def test_values_gone_everywhere_and_history_still_verifies(self):
        self.make_area()
        for p in self.c.peers:
            self.assertIn(SECRET, dump_text(p))
        self.erase()
        for p in self.c.peers:
            self.assertNotIn(SECRET, dump_text(p), p.name)
            row = p.store.get('areas', 'p1')
            self.assertIsNone(row.get('description'))
            self.assertEqual(row['name'], 'Person One', 'only the named fields are erased')
            self.assertEqual(row['location'], 'Cairo')
            self.assertTrue(p.journal.verify(True)['ok'], p.journal.verify(True))
        self.assertEqual(len(set(self.c.fingerprints())), 1)

    def test_only_the_administrator_pc_can_order_it(self):
        self.make_area()
        with self.assertRaises(BadRequest):
            self.b.store.erase('user', 'ip', 'areas', 'p1', ['description'], 'pdpl-request')
        # a forged order signed only by an ordinary PC is refused by everybody
        with self.b.journal.lock:
            rec = self.b.journal.build('erase', [{'e': 'areas', 'id': 'p1', 'op': 'update', 's': {'description': None}, 'erase': {'reason': 'x'}}])
            self.b.journal.append_local(rec)
        self.a.receive(self.b.journal.changes_since(self.a.journal.vv())[0])
        self.assertIn(SECRET, dump_text(self.a))
        self.assertEqual(self.a.store.get('areas', 'p1')['description'], SECRET)

    def test_late_change_from_a_pc_that_never_saw_the_order(self):
        self.make_area()
        # pc b edits the record offline, after the order was made on the administrator PC (it has not received it yet)
        self.a.store.erase('boss', '127.0.0.1', 'areas', 'p1', ['description'], 'pdpl-request')
        ver = self.b.store.get('areas', 'p1')['ver']
        self.b.commit('offline edit', [{'e': 'areas', 'id': 'p1', 'op': 'put', 'ver': ver,
                                        'row': {'name': 'Person One', 'location': 'Giza', 'description': SECRET + ' edited'}}])
        self.c.deliver(self.b, self.a)  # the late change reaches the administrator PC BEFORE pc b hears about the order
        self.assertNotIn(SECRET, dump_text(self.a), 'the administrator PC blanks it on arrival')
        self.c.converge()
        for p in self.c.peers:
            self.assertNotIn(SECRET, dump_text(p), p.name)
            row = p.store.get('areas', 'p1')
            self.assertIsNone(row.get('description'))
            self.assertEqual(row['location'], 'Giza', 'other fields of the offline edit are kept')
            self.assertTrue(p.journal.verify(True)['ok'])
        self.assertEqual(len(set(self.c.fingerprints())), 1)

    def test_a_new_pc_gets_the_redacted_history(self):
        self.make_area()
        self.erase()
        newpc = Peer(self.c.root, 'pc-new')
        newpc.node.join(self.a.node.info['cluster_id'], self.a.node.info['authority_pub'], self.a.node.id)
        self.a.journal.write('admin', [__import__('cluster').enroll_op(newpc.node)], actor='admin', label='enrol', authority=True)
        self.c.peers.append(newpc)
        self.c.converge()
        self.assertNotIn(SECRET, dump_text(newpc))
        self.assertIsNone(newpc.store.get('areas', 'p1').get('description'))
        self.assertTrue(newpc.journal.verify(True)['ok'])
        self.assertEqual(len(set(self.c.fingerprints())), 1)

    def test_restoring_an_old_backup_does_not_bring_the_value_back(self):
        self.make_area()
        d = tempfile.mkdtemp()
        try:
            old = os.path.join(d, 'old.db')
            with self.a.store.lock:
                self.a.store.conn.execute('VACUUM INTO ?', (old,))
            self.erase()
            self.a.store.restore_from(old, 'boss', '127.0.0.1', 'restore')
            self.c.converge()
            for p in self.c.peers:
                self.assertNotIn(SECRET, dump_text(p), p.name)
                self.assertIsNone(p.store.get('areas', 'p1').get('description'))
        finally:
            shutil.rmtree(d)

    def test_erased_information_cannot_be_entered_again(self):
        self.make_area()
        self.erase()
        ver = self.a.store.get('areas', 'p1')['ver']
        with self.assertRaises(BadRequest):
            self.a.commit('again', [{'e': 'areas', 'id': 'p1', 'op': 'put', 'ver': ver, 'row': {'name': 'Person One', 'description': 'back again'}}])
        # other fields can still be edited
        self.a.commit('ok', [{'e': 'areas', 'id': 'p1', 'op': 'put', 'ver': ver, 'row': {'name': 'Person One Renamed'}}])
        self.assertEqual(self.a.store.get('areas', 'p1')['name'], 'Person One Renamed')

    def test_tampering_with_a_normal_change_is_still_detected(self):
        self.make_area()
        self.erase()
        with self.a.journal.lock:
            self.a.journal.conn.execute("UPDATE changes SET body=REPLACE(body, 'Cairo', 'Paris') WHERE body LIKE '%Cairo%'")
        result = self.a.journal.verify(True)
        self.assertFalse(result['ok'])

    def test_reapply_after_the_journal_was_restored_from_an_old_copy(self):
        self.make_area()
        d = tempfile.mkdtemp()
        try:
            old = os.path.join(d, 'journal_old.db')
            with self.b.journal.lock:
                self.b.journal.conn.execute('VACUUM INTO ?', (old,))
            self.erase()
            # the old copy (values still readable) receives the order again and blanks everything by itself
            src = sqlite3.connect(old)
            src.row_factory = sqlite3.Row
            body = src.execute("SELECT body FROM changes WHERE body LIKE ?", ('%' + SECRET + '%',)).fetchone()
            self.assertIsNotNone(body)
            src.close()
            self.assertGreater(self.b.journal.reapply_erasures() + 1, 0)
            self.assertNotIn(SECRET, dump_text(self.b))
        finally:
            shutil.rmtree(d)


if __name__ == '__main__':
    unittest.main()
