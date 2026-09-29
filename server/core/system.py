"""Opens all parts of one installation in the right order and repairs anything a crash left half-done.

Harvested from BAMS (Mr.Ayman-HR 5f5b3ce). The BAMS upgrade path from a single-PC version 1 is not needed here:
this product starts with the journal from its first day.
"""
import hashlib
import os
import sqlite3
from datetime import datetime

from auth import Auth
from backup import Backups
from journal import Journal
from node import Node
from replica import markers as replica_markers
from store import REPLICATED, SPECS, Store


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class System:
    def __init__(self, data_dir, cfg, uploads, backup_dir, extra_backup_dirs=(), log=print):
        self.data_dir, self.cfg, self.uploads, self.log = data_dir, cfg, uploads, log
        if os.path.exists(os.path.join(data_dir, 'node', 'RESET_REQUESTED')):
            self._archive_copy()
        self.node = Node(data_dir)
        self.store = Store(data_dir)
        self.auth = Auth(data_dir, cfg)
        self.backups = Backups(self.store, uploads, backup_dir, extra_backup_dirs, cfg.get('keep_auto_backups', 200),
                               cfg.get('backup_interval_hours', 6), log=log, auth=self.auth)
        fresh = not self.node.exists or not self.node.info.get('setup_complete')
        if fresh:
            self._first_start(cfg.get('device_name'))
        else:
            self._open_journal()
            self._check_rollback()
            self.store.fold_pending()
            self.auth.fold_pending()
        self.backups.journal = self.journal

    def _archive_copy(self):
        """The data folder was copied from another PC and the administrator chose "set up as a new PC": everything of
        the copied identity is moved aside (nothing is deleted) and this PC starts fresh, ready to join."""
        dest = os.path.join(self.data_dir, 'copied-' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(dest)
        for n in os.listdir(self.data_dir):
            if n == 'node' or n.split('.db')[0] in ('sbo', 'auth', 'journal') and '.db' in n:
                os.replace(os.path.join(self.data_dir, n), os.path.join(dest, n))
        os.remove(os.path.join(dest, 'node', 'RESET_REQUESTED'))
        self.log(f'The copied data was moved to {dest}; this PC starts as a new device.')

    # ------------------------------------------------------------ normal start
    def _open_journal(self):
        self.journal = Journal(self.data_dir, self.node, REPLICATED, log=self.log)
        self.store.attach(self.journal)
        self.auth.attach(self.journal, self.node)

    def _check_rollback(self):
        """If this PC's own history in journal.db is shorter than what it once wrote, the journal was restored
        or lost writes: continue under a new epoch so no change number is ever used twice."""
        written = self.node.last_written()
        have = self.journal.vv()
        lost = {r: c for r, c in written.items() if c > have.get(r, 0)}
        folded = replica_markers(self.store.conn)
        if any(c > have.get(o, 0) for o, c in folded.items()):
            self._recover_tables_ahead()
        if lost.get(self.node.replica):
            self.node.new_epoch(f'journal rolled back (had {lost[self.node.replica]}, found {have.get(self.node.replica, 0)})')
            self.journal.alert('rollback', 'This PC\'s change history was older than expected (restored or damaged journal). It continues '
                               'with a new numbering; its missing changes come back from the other PCs if they received them.', self.node.id)
            self.log('Journal rollback detected - new epoch ' + self.node.replica)

    def _recover_tables_ahead(self):
        """sbo.db contains changes the (restored) journal no longer has. Rebuild the tables from the journal and save
        whatever differs from the old tables as a new change, so nothing visible is lost and every PC receives it."""
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        old = os.path.join(self.data_dir, f'sbo.ahead-{stamp}.db')
        with self.store.lock:
            self.store.conn.execute('VACUUM INTO ?', (old,))
            c = self.store.conn
            c.execute('BEGIN IMMEDIATE')
            for spec in SPECS.values():
                c.execute(f'DELETE FROM {spec["table"]}')
            for t in ('sync_field', 'sync_marker', 'sync_flags'):
                c.execute(f'DELETE FROM {t}')
            c.execute('COMMIT')
        self.store.fold_pending()
        if self.node.info.get('role') != 'unconfigured':
            self.store.restore_from(old, 'Recovery', '127.0.0.1', 'Changes kept after the history was restored', kind='data')
        self.journal.alert('rollback', 'The data of this PC was newer than its history. The data was rebuilt from the history and the '
                           f'difference saved again as a new change (old file kept as {os.path.basename(old)}).', self.node.id)

    # ------------------------------------------------------------ first start
    def _first_start(self, device_name):
        if not self.node.exists:
            self.node.create(device_name)
        self._open_journal()
        self.store.fold_pending()
        self.auth.fold_pending()
        self.node.info['setup_complete'] = True
        self.node.save()
        self.log(f'Ready: this PC is "{self.node.name}" ({self.node.id}), role {self.node.role}')

    # ------------------------------------------------------------ helpers used by the web server and tools
    def status(self):
        return {'node': self.node.public(), 'fingerprint': self.store.fingerprint(), 'journal': self.journal.stats()}

    def close(self):
        for c in (self.journal.conn, self.store.conn, self.auth.conn):
            try:
                c.close()
            except sqlite3.Error:
                pass


def lock_data(folder):
    """Only one program may work with a data folder at a time (autostart + desktop icon, a double click, a
    maintenance tool while the program runs). Returns the lock - keep it open - or None when it is taken."""
    os.makedirs(folder, exist_ok=True)
    f = open(os.path.join(folder, 'program.lock'), 'a+')
    try:
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None
