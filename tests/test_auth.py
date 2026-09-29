"""Password hashing (ADR-011) and the permission registry."""
import hashlib
import os
import shutil
import tempfile
import unittest

from cluster import Cluster  # noqa: F401 (sets sys.path and a fast test KDF)
import auth  # noqa: E402
import permissions  # noqa: E402


class HashTest(unittest.TestCase):
    def test_new_hashes_are_scrypt_with_the_owasp_minimum_cost(self):
        old = auth.KDF_N
        try:
            auth.KDF_N = 2 ** 17
            h = auth.hash_password('a long enough password')
            self.assertTrue(h.startswith('scrypt$131072$8$1$'), h)
            self.assertTrue(auth.verify_password('a long enough password', h))
            self.assertFalse(auth.verify_password('a long enough passwore', h))
            self.assertFalse(auth.needs_rehash(h))
        finally:
            auth.KDF_N = old

    def test_bams_style_pbkdf2_hashes_still_verify_and_are_flagged(self):
        salt = os.urandom(16)
        stored = f'pbkdf2_sha256$600000${salt.hex()}${hashlib.pbkdf2_hmac("sha256", b"old-password-1", salt, 600000).hex()}'
        self.assertTrue(auth.verify_password('old-password-1', stored))
        self.assertFalse(auth.verify_password('old-password-2', stored))
        self.assertTrue(auth.needs_rehash(stored))

    def test_absurd_cost_parameters_in_a_stored_hash_are_refused(self):
        self.assertFalse(auth.verify_password('x', 'scrypt$1073741824$8$1$aa$bb'))
        self.assertFalse(auth.verify_password('x', 'scrypt$16384$1000$1$aa$bb'))

    def test_many_parallel_hashes_stay_within_two_at_a_time(self):
        import threading
        import time
        active, peak, lock = [0], [0], threading.Lock()
        real = auth.hashlib.scrypt

        def spy(*a, **k):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            try:
                return real(*a, **k)
            finally:
                with lock:
                    active[0] -= 1
        auth.hashlib.scrypt = spy
        try:
            ts = [threading.Thread(target=auth.hash_password, args=('pw',)) for _ in range(8)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        finally:
            auth.hashlib.scrypt = real
        self.assertLessEqual(peak[0], 2)

    def test_garbage_hashes_never_verify(self):
        for bad in ('', 'x', 'scrypt$1$2', 'md5$a$b', None, 'scrypt$zz$8$1$aa$bb'):
            self.assertFalse(auth.verify_password('x', bad))


class LoginRehashTest(unittest.TestCase):
    def test_login_on_the_administrator_pc_upgrades_an_old_hash(self):
        from system import System
        d = tempfile.mkdtemp()
        try:
            s = System(d, {}, os.path.join(d, 'up'), os.path.join(d, 'bk'), log=lambda m: None)
            s.auth.setup('boss', 'The Boss', 'Strong-pass1', '127.0.0.1')
            uid = s.auth.conn.execute("SELECT id FROM users WHERE username='boss'").fetchone()[0]
            salt = os.urandom(16)
            legacy = f'pbkdf2_sha256$1000${salt.hex()}${hashlib.pbkdf2_hmac("sha256", b"Strong-pass1", salt, 1000).hex()}'
            s.auth._write('System', '127.0.0.1', 'legacy hash', [{'e': 'users', 'id': uid, 'op': 'update', 'noaudit': True, 's': {'pw_hash': legacy}}])
            self.assertTrue(s.auth.conn.execute('SELECT pw_hash FROM users WHERE id=?', (uid,)).fetchone()[0].startswith('pbkdf2'))
            s.auth.login('boss', 'Strong-pass1', '127.0.0.1')
            self.assertTrue(s.auth.conn.execute('SELECT pw_hash FROM users WHERE id=?', (uid,)).fetchone()[0].startswith('scrypt'))
            s.auth.login('boss', 'Strong-pass1', '127.0.0.1')  # and the new hash works
            s.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)


class PermissionRegistryTest(unittest.TestCase):
    def test_modules_register_groups_and_profiles_and_admin_rights_stay_apart(self):
        permissions.register_group('Test module', [('testmod.view', 'View'), ('testmod.edit', 'Edit')])
        permissions.register_group('', [('testmod.admin', 'Administer it')], admin=True)
        permissions.register_profile('tester', 'Tester', lambda: ['testmod.view'])
        self.assertIn('testmod.view', permissions.ALL)
        self.assertIn('testmod.admin', permissions.ADMIN_PERMS)
        self.assertNotIn('testmod.admin', permissions.WORK)
        profiles = {p: x for p, _, x in permissions.builtin_profiles()}
        self.assertIn('testmod.admin', profiles['administrator'])
        self.assertEqual(profiles['tester'], ['testmod.view'])
        # registering twice does not duplicate
        permissions.register_group('Test module', [('testmod.view', 'View')])
        self.assertEqual(permissions.ALL.count('testmod.view'), 1)

    def test_core_admin_rights_are_never_work_rights(self):
        for p in ('users.manage', 'privacy.erase', 'backups.restore', 'logs.security'):
            self.assertIn(p, permissions.ADMIN_PERMS)
            self.assertNotIn(p, permissions.WORK)


if __name__ == '__main__':
    unittest.main()
