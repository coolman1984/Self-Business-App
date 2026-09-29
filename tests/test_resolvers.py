"""Merge rules added to the BAMS engine: 'min' resolver and write-once (immutable) records such as issued documents.
Both must give the same result on every PC whatever the order in which changes arrive."""
import itertools
import shutil
import unittest

from cluster import Cluster  # noqa: F401 (sets sys.path)
import engine_domain  # noqa: E402,F401
import registry  # noqa: E402
from registry import I, T  # noqa: E402
from store import BadRequest  # noqa: E402

registry.register(registry.Entity('issued', 'issued_docs', 'Issued documents', [
    ('number', 'number', T, 'Number'), ('total', 'total_minor', I, 'Total'), ('party', 'party', T, 'Party')], immutable=True))
registry.register(registry.Entity('plans', 'plans', 'Plans', [
    ('title', 'title', T, 'Title'), ('start', 'start', T, 'Start'), ('seats', 'seats', I, 'Seats')], resolvers={'start': 'min', 'seats': 'min'}))


class MinResolverTest(unittest.TestCase):
    def test_earliest_date_and_lowest_number_win_in_any_order(self):
        for order in itertools.permutations(range(3)):
            c = Cluster(3)
            try:
                for p, (d, n) in zip(c.peers, [('2026-03-05', 9), ('2026-01-09', 12), ('2026-02-01', 3)]):
                    p.store.sync_schema()
                    p.commit('plan', [{'e': 'plans', 'id': 'pl', 'op': 'put', 'row': {'title': 'T', 'start': d, 'seats': n}}])
                for i in order:  # deliver in a different order every time
                    for j in range(3):
                        if i != j:
                            c.deliver(c.peers[i], c.peers[j])
                c.converge()
                for p in c.peers:
                    row = p.store.get('plans', 'pl')
                    self.assertEqual((row['start'], row['seats']), ('2026-01-09', 3), order)
                self.assertEqual(len(set(c.fingerprints())), 1)
            finally:
                c.close()


class WriteOnceTest(unittest.TestCase):
    def setUp(self):
        self.c = Cluster(3)
        for p in self.c.peers:
            p.store.sync_schema()
        self.a, self.b, self.x = self.c.peers

    def tearDown(self):
        self.c.close()

    def issue(self, peer, total, party='Client'):
        return peer.commit('issue', [{'e': 'issued', 'id': 'inv1', 'op': 'put', 'row': {'number': 'INV-A-1', 'total': total, 'party': party}}])

    def test_issued_record_cannot_be_edited(self):
        self.issue(self.a, 1000)
        ver = self.a.store.get('issued', 'inv1')['ver']
        with self.assertRaises(BadRequest):
            self.a.commit('edit', [{'e': 'issued', 'id': 'inv1', 'op': 'put', 'ver': ver, 'row': {'number': 'INV-A-1', 'total': 5, 'party': 'Client'}}])

    def test_saving_an_issued_record_unchanged_or_restoring_a_backup_with_it_works(self):
        import os
        import tempfile
        self.issue(self.a, 1000)
        row = self.a.store.get('issued', 'inv1')
        self.a.commit('same again', [{'e': 'issued', 'id': 'inv1', 'op': 'put', 'ver': row['ver'], 'row': {k: v for k, v in row.items() if k != 'ver'}}])
        d = tempfile.mkdtemp()
        try:
            old = os.path.join(d, 'old.db')
            with self.a.store.lock:
                self.a.store.conn.execute('VACUUM INTO ?', (old,))
            self.a.store.restore_from(old, 'boss', 'ip', 'restore')  # must not fail on the issued document
            self.assertEqual(self.a.store.get('issued', 'inv1')['total'], 1000)
        finally:
            shutil.rmtree(d)

    def test_two_pcs_issuing_the_same_record_keep_the_earliest_everywhere(self):
        self.issue(self.a, 1000)
        self.issue(self.b, 2000, 'Other')  # concurrent: neither has seen the other
        self.c.converge()
        rows = [p.store.get('issued', 'inv1') for p in self.c.peers]
        self.assertEqual(len({(r['total'], r['party']) for r in rows}), 1)
        self.assertEqual(len(set(self.c.fingerprints())), 1)
        flags = [f for f in self.a.store.conflicts() if f['entity'] == 'issued']
        self.assertTrue(flags, 'the discarded issue is reported')
        self.assertEqual(flags[0]['kind'], 'edited-after-issue')

    def test_result_does_not_depend_on_arrival_order(self):
        for order in itertools.permutations(range(3)):
            c = Cluster(3)
            try:
                for p in c.peers:
                    p.store.sync_schema()
                for p, total in zip(c.peers, (100, 200, 300)):
                    p.commit('issue', [{'e': 'issued', 'id': 'inv1', 'op': 'put', 'row': {'number': 'N', 'total': total, 'party': str(total)}}])
                for i in order:
                    for j in range(3):
                        if i != j:
                            c.deliver(c.peers[i], c.peers[j])
                c.converge()
                self.assertEqual(len(set(c.fingerprints())), 1, order)
            finally:
                c.close()


if __name__ == '__main__':
    unittest.main()
