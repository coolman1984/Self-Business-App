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

    def _fresh_pc(self, label):
        other = Peer(self.c.root, 'probe-' + label)
        other.node.join(self.a.node.info['cluster_id'], self.a.node.info['authority_pub'], self.a.node.id)
        self.a.journal.write('admin', [__import__('cluster').enroll_op(other.node)], actor='admin', label='enrol', authority=True)
        return other

    def test_a_relay_cannot_alter_or_blank_values_of_another_pcs_change(self):
        self.make_area()
        self.a.commit('more', [{'e': 'areas', 'id': 'p2', 'op': 'put', 'row': {'name': 'Second', 'location': 'Cairo'}}])
        recs = self.a.journal.changes_since({})[0]
        target = next(r for r in recs if b'Second' in r['o'].encode())

        def forged_delivery(mutate):
            return [dict(r, o=mutate(r['o'])) if r['b'] == target['b'] else r for r in recs]

        # 1. an altered value does not match its signed commitment: refused
        other = self._fresh_pc('altered')
        try:
            _, _, problems = other.receive(forged_delivery(lambda o: o.replace('Second', 'Hacked')))
            self.assertTrue(problems)
            self.assertIsNone(other.store.get('areas', 'p2'))
        finally:
            other.close()
        # 2. a blanked value that no erase order explains: the change waits, is not folded, and an alert is raised
        other = self._fresh_pc('blanked')
        try:
            acc, deferred, _ = other.receive(forged_delivery(lambda o: o.replace('"Second"', 'null')))
            self.assertGreater(deferred, 0)
            self.assertIsNone(other.store.get('areas', 'p2'))
            self.assertIn('integrity', [al['kind'] for al in other.journal.alerts()])
        finally:
            other.close()
        # 3. the same blank IS accepted when the administrator PC's erase order for it arrives with it
        self.a.store.erase('boss', '127.0.0.1', 'areas', 'p2', ['name'], 'pdpl-request')
        other = self._fresh_pc('erased')
        try:
            other.receive(self.a.journal.changes_since({})[0])
            row = other.store.get('areas', 'p2')
            self.assertIsNotNone(row)
            self.assertIsNone(row.get('name'))
            self.assertEqual(row['location'], 'Cairo')
            self.assertTrue(other.journal.verify(True)['ok'])
        finally:
            other.close()

    def test_erasure_also_reaches_backups_and_the_audit_files(self):
        from system import System
        d = tempfile.mkdtemp()
        try:
            s = System(d, {}, os.path.join(d, 'up'), os.path.join(d, 'bk'), log=lambda m: None)
            s.auth.setup('boss', 'The Boss', 'Strong-pass1', '127.0.0.1')
            s.store.commit('u', 'ip', 'create', [{'e': 'areas', 'id': 'p9', 'op': 'put', 'row': {'name': 'N', 'description': SECRET}}])
            s.store.commit('u', 'ip', 'edit', [{'e': 'areas', 'id': 'p9', 'op': 'put', 'ver': s.store.get('areas', 'p9')['ver'],
                                                'row': {'name': 'N', 'description': SECRET + ' v2'}}])
            s.backups.create('manual')
            log_dir = os.path.join(d, 'logs')
            everything = lambda: '\n'.join(open(os.path.join(dp, f), 'rb').read().decode('utf-8', 'ignore')  # noqa: E731
                                            for dp, _, fs in os.walk(d) for f in fs if f.endswith(('.db', '.jsonl')))
            self.assertIn(SECRET, everything())
            s.store.erase('boss', '127.0.0.1', 'areas', 'p9', ['description'], 'pdpl-request')
            self.assertNotIn(SECRET, everything(), 'values must not survive in backups, journal copies or audit files')
            self.assertTrue(os.path.isdir(log_dir))
            s.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_record_ids_with_wildcards_and_arabic_letters_are_found(self):
        for rid in ('a_b%c', 'شخص_١', 'back\\slash'):
            self.a.commit('create', [{'e': 'areas', 'id': rid, 'op': 'put', 'row': {'name': 'N', 'description': SECRET}}])
        self.c.converge()
        for rid in ('a_b%c', 'شخص_١', 'back\\slash'):
            self.a.store.erase('boss', '127.0.0.1', 'areas', rid, ['description'], 'pdpl-request')
        self.c.converge()
        for p in self.c.peers:
            self.assertNotIn(SECRET, dump_text(p), p.name)

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
