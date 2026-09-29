"""Passwords, session tokens, personal-link tokens and keys must never reach a log file or the change log
(docs/SECURITY.md section 2, CLAUDE.md "Never")."""
import glob
import os
import unittest

from harness import ADMIN, ApiError, Server, make_authority


def all_text(server):
    """Everything readable that the program wrote: logs, monthly jsonl files, the journal and the databases (as text)."""
    parts = []
    for path in glob.glob(os.path.join(server.data_dir, '**', '*'), recursive=True):
        if os.path.isfile(path) and not path.endswith(('.key', '.png', '.jpg', '.part')) and os.sep + 'cas' + os.sep not in path:
            try:
                with open(path, 'rb') as f:
                    parts.append(f.read().decode('utf-8', 'ignore'))
            except OSError:
                pass
    return '\n'.join(parts)


class SecretsInLogsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = Server('secrets').start()
        cls.ac = make_authority(cls.S)

    @classmethod
    def tearDownClass(cls):
        cls.S.cleanup()

    def test_no_password_token_or_link_in_any_log(self):
        secret_pw = 'Zebra-Quartz-9931'
        ac = self.ac
        user = ac.post('/api/users/save', {'username': 'leaky.test', 'full_name': 'Leaky Test', 'password': secret_pw, 'must_change': False,
                                           'perms': ['dashboard.view']})
        person = ac.post('/api/users/save', {'full_name': 'Link Person', 'login': 'link', 'perms': ['dashboard.view']})
        link_token = person['token']
        c = self.S.client()
        c.login('leaky.test', secret_pw)
        with self.assertRaises(ApiError):
            self.S.client().login('leaky.test', 'wrong-Password-1234')
        c.get('/api/me')
        self.S.client().get('/k/' + link_token)  # opening the link page
        opener = self.S.client()
        opener.call('POST', '/k/' + link_token, raw=b'')  # logging in with it
        session_cookie = next((ck.value for ck in c.jar if ck.name == 'sbo_sid'), None)
        self.assertTrue(session_cookie)
        ac.post('/api/users/reset', {'id': user['id'], 'password': 'Reset-Value-5512'})
        text = all_text(self.S)
        for secret in (secret_pw, 'wrong-Password-1234', 'Reset-Value-5512', ADMIN[1], link_token, session_cookie):
            self.assertFalse(secret in text, f'a secret reached a log or database: {secret[:6]}...')  # (never print the text itself)

    def test_the_authority_key_is_only_in_the_node_folder(self):
        with open(os.path.join(self.S.data_dir, 'node', 'authority.key')) as f:
            seed = f.read().strip()
        for path in glob.glob(os.path.join(self.S.data_dir, '**', '*'), recursive=True):
            if os.path.isfile(path) and os.sep + 'node' + os.sep not in path and not path.endswith(('.db', '.db-wal', '.db-shm')):
                with open(path, 'rb') as f:
                    self.assertFalse(seed.encode() in f.read(), path)


class UploadContentTest(unittest.TestCase):
    def test_a_file_must_match_its_type(self):
        s = Server('upl').start()
        try:
            c = make_authority(s)
            for name, data in (('a.jpg', b'<script>alert(1)</script>'), ('b.png', b'%PDF-1.4 not a picture'), ('c.pdf', b'\xff\xd8\xff\xe0 jpeg as pdf'),
                               ('d.exe', b'MZ...'), ('e.jpg', b'')):
                with self.assertRaises(ApiError) as e:
                    c.call('POST', f'/api/upload?name={name}', raw=data, headers={'Content-Type': 'application/octet-stream'})
                self.assertEqual(e.exception.code, 400, name)
            ok = c.call('POST', '/api/upload?name=ok.jpg', raw=b'\xff\xd8\xff\xe0' + b'x' * 100, headers={'Content-Type': 'application/octet-stream'})
            self.assertTrue(ok['src'].startswith('/files/cas/'))
        finally:
            s.cleanup()


if __name__ == '__main__':
    unittest.main()
