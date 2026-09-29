"""SQLite storage of the business data (harvested from BAMS, made domain-free through registry.py).

Design rules (data must never be lost):
  * Every change arrives as one "commit" and is applied in ONE transaction -
    either all of it is saved or none of it.
  * Rows are never physically deleted. A delete only marks the row
    (deleted=1 + who/when/which transaction) so it can be restored. The only exception is a legal erase order
    (erase.py), which redacts values in rows, history and files.
  * Every row carries a version number. A change based on an old version is
    rejected (someone else changed it first) instead of silently overwriting.
  * Every change becomes one signed changeset in the change journal
    (journal.py, data/journal.db) and is appended to a monthly JSON-lines file in
    data/logs. Both are never touched by a restore.
  * The rows are a deterministic fold of the journal (replica.py), so every PC that
    has received the same changes shows exactly the same data.
"""
import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime

import registry
import replica
from journal import canonical
from registry import B, COUNTERS, ENTITIES, I, J, META, R, REPLICATED, RESOLVERS, SPECS, T, Entity, scope_of  # noqa: F401

# the two entities every installation has; everything else is registered by the platform and the modules
registry.register(Entity('settings', 'settings', 'Settings', [('value', 'value', J, 'Value')], perms={
    'view': ('settings.view',), 'insert': ('settings.edit',), 'update': ('settings.edit',), 'delete': ('settings.edit',)}))
# manifest of uploaded files (photos, documents, logo): path -> SHA-256 and size, replicated so every PC can
# fetch and verify the files it is missing
FILES = ('attachments', [('sha256', 'sha256', T), ('size', 'size_bytes', I), ('type', 'mime', T)])
SPECS['files'] = {'table': FILES[0], 'fields': FILES[1], 'counters': set(), 'resolvers': {}}
REPLICATED.add('files')


class Conflict(Exception):
    pass


class BadRequest(Exception):
    pass


def now():
    return datetime.now().isoformat(timespec='seconds')


def _coerce(kind, v):
    if v is None or v == '' and kind in (I, R):
        return None
    if kind == I:
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        if isinstance(v, str) and re.fullmatch(r'\s*-?\d+\s*', v):
            return int(v)  # exact, no float round trip
        try:
            return int(float(v))
        except (TypeError, ValueError, OverflowError):
            return None
    if kind == R:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if kind == B:
        return 1 if v else 0
    if kind == J:
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return str(v)


def _out(kind, v):
    if v is None:
        return None
    if kind == B:
        return bool(v)
    if kind == J:
        return json.loads(v)
    if kind == R and float(v).is_integer():
        return int(v)
    return v


class Store:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.path = os.path.join(data_dir, 'sbo.db')
        self.log_dir = os.path.join(data_dir, 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self.lock = threading.RLock()
        self.journal = None
        self.folder = None
        self.after_fold = []  # callbacks fn(store, touched) - derived indexes
        self.conn = self._open()
        self._fp = (None, None)

    def _fold_done(self):
        touched = set(self.folder.touched) if self.folder else set()
        if self.folder:
            self.folder.touched.clear()
        if touched:
            for fn in self.after_fold:
                try:
                    fn(self, touched)
                except Exception as e:  # noqa: BLE001 - a derived index must never break saving; it is rebuilt from the data
                    if self.journal:
                        self.journal.alert('index', f'The search index could not be updated ({e}); it is rebuilt automatically.', '', 'warning', key='index|update')

    def attach(self, journal):
        """Connects the change journal. From now on every save goes through it."""
        self.journal = journal
        self.folder = replica.BusinessFolder(self.conn, SPECS, journal.deps_of, _coerce)

    # ------------------------------------------------------------ setup
    def _open(self):
        conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('PRAGMA busy_timeout=10000')
        ok = conn.execute('PRAGMA quick_check').fetchone()[0]
        if ok != 'ok':
            raise RuntimeError(f'Database file is damaged ({ok}). Restore the latest file from the backups folder.')
        self._migrate(conn)
        return conn

    def reopen(self):
        with self.lock:
            self.conn.close()
            self.conn = self._open()
            if self.journal:
                self.folder = replica.BusinessFolder(self.conn, SPECS, self.journal.deps_of, _coerce)

    def _migrate(self, conn):
        meta = 'id TEXT PRIMARY KEY, ver INTEGER NOT NULL DEFAULT 1, created_at TEXT, created_by TEXT, created_by_id TEXT, updated_at TEXT, updated_by TEXT, ' \
               'deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT, deleted_by TEXT, deleted_txn TEXT'
        for name, (table, _, fields) in [*ENTITIES.items(), ('files', (FILES[0], '', [(a, b, c, '') for a, b, c in FILES[1]]))]:
            conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({meta})')
            have = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            if 'created_by_id' not in have:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN created_by_id TEXT')
            for _, col, kind, _ in fields:
                if col not in have:
                    sql_type = {I: 'INTEGER', R: 'REAL', B: 'INTEGER'}.get(kind, 'TEXT')
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} {sql_type}')
            m = META.get(name)
            cols = {js: col for js, col, _, _ in fields}
            wanted = [cols[m.scope_field]] if m and m.scope_field in cols else []
            wanted += [cols[k] for k in (m.index if m else ()) if k in cols]
            for col in wanted:
                conn.execute(f'CREATE INDEX IF NOT EXISTS ix_{table}_{col} ON {table}({col})')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            INSERT OR IGNORE INTO meta VALUES ('data_version', '0');
        ''')
        replica.install(conn)

    def sync_schema(self):
        """Creates tables/columns of entities registered after the store was opened (a module was switched on)."""
        with self.lock:
            self._migrate(self.conn)
            if self.journal:
                self.folder = replica.BusinessFolder(self.conn, SPECS, self.journal.deps_of, _coerce)

    # ------------------------------------------------------------ helpers
    def version(self):
        with self.lock:
            return int(self.conn.execute("SELECT value FROM meta WHERE key='data_version'").fetchone()[0])

    @staticmethod
    def _row_js(entity, r):
        _, _, fields = ENTITIES[entity]
        d = {'id': r['id']}
        for js, col, kind, _ in fields:
            v = _out(kind, r[col])
            if v is not None:
                d[js] = v
        d['ver'] = r['ver']
        return d

    def _audit_file(self, entries):
        if not entries:
            return
        path = os.path.join(self.log_dir, f'audit-{datetime.now():%Y-%m}.jsonl')
        with open(path, 'a', encoding='utf-8') as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def _scope_of(self, entity, row):
        def lookup(parent, rid):
            if not rid or parent not in ENTITIES:
                return None
            r = self.conn.execute(f'SELECT * FROM {ENTITIES[parent][0]} WHERE id=?', (rid,)).fetchone()
            return self._row_js(parent, r) if r else None
        return scope_of(entity, row, lookup)

    # ------------------------------------------------------------ read
    def get(self, entity, rid, include_deleted=False):
        with self.lock:
            r = self.conn.execute(f'SELECT * FROM {ENTITIES[entity][0]} WHERE id=?', (rid,)).fetchone()
        if r is None or (r['deleted'] and not include_deleted):
            return None
        return self._row_js(entity, r)

    # ------------------------------------------------------------ write
    def commit(self, user, ip, label, ops, force=False, guard=None, user_id='', kind='data'):
        """guard(changes, force) is called with the changes before they are saved; raising an exception cancels all of them.
        The accepted changes become one changeset: folded into the tables, appended to the journal, then committed."""
        if not isinstance(ops, list) or not ops:
            raise BadRequest('Nothing to save')
        if self.journal is None:
            raise RuntimeError('The change journal is not ready')
        with self.lock:
            c = self.conn
            c.execute('BEGIN IMMEDIATE')
            try:
                audit, rops = [], []
                for op in ops:
                    a, r = self._plan(c, op, force)
                    if a:
                        audit.append(a)
                    if r:
                        rops.append(r)
                if guard:
                    guard(audit, force)
            except Exception:
                c.execute('ROLLBACK')
                raise
            if not rops:
                c.execute('ROLLBACK')
                return {'txn': None, 'version': self.version(), 'changes': 0}
            rec = self._save(rops, user, ip, label, user_id, kind)
            version = self.version()
        env = rec['env']
        self._audit_file([{'ts': env['ts'], 'txn': env['id'], 'node': env['node'], 'user': user, 'ip': ip, 'label': label,
                           **{k: a[k] for k in ('entity', 'id', 'op', 'changes')}} for a in audit])
        return {'txn': env['id'], 'version': version, 'changes': len(audit)}

    def _save(self, rops, user, ip, label, user_id='', kind='data', begin=False):
        """Turns journal ops into one changeset: fold into the tables, append to the journal, commit.
        Called with the store lock held and (unless begin) a transaction already open."""
        c = self.conn
        if begin:
            c.execute('BEGIN IMMEDIATE')
        rec, appended = None, False
        try:
            with self.journal.lock:
                # deps = what is FOLDED here (the state the change was planned on), not what the journal has received
                rec = self.journal.build(kind, rops, actor=user, actor_id=user_id, ip=ip, label=label, deps=replica.markers(c))
                before = len(self.folder.problems)
                self.folder.fold(rec['env'], 'ok')
                if len(self.folder.problems) != before:
                    raise BadRequest('This change could not be saved: ' + self.folder.problems[-1])
                self._bump(c)
                self.journal.append_local(rec)
                appended = True
            c.execute('COMMIT')
        except Exception:
            try:
                c.execute('ROLLBACK')
            except sqlite3.OperationalError:
                pass
            if not appended:
                raise
            try:
                self.fold_pending()  # the change is safely in the journal - apply it again from there
            except Exception as e:  # noqa: BLE001 - it is saved; it will be applied at the next start at the latest
                self.journal.alert('fold', f'A saved change could not be shown yet ({e}); it is applied again automatically.', '', 'warning')
        self._fold_done()
        self.journal._notify([rec])
        return rec

    def record_file(self, path, sha256, size, mime, user, ip, user_id=''):
        """Adds an uploaded file to the replicated manifest so the other PCs fetch and verify it."""
        with self.lock:
            if self.file_info(path):
                return
            self._save([{'e': 'files', 'id': path, 'op': 'insert', 'x': False, 'noaudit': True,
                         's': {'sha256': sha256, 'size': size, 'type': mime}}], user, ip, 'Uploaded file', user_id, begin=True)

    def _bump(self, c):
        c.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='data_version'")

    def _plan(self, c, op, force):
        """Checks one change against the current row and turns it into (audit entry, journal op)."""
        entity, rid, kind = op.get('e'), op.get('id'), op.get('op')
        if entity not in ENTITIES or not isinstance(rid, str) or not rid or len(rid) > 120:
            raise BadRequest(f'Invalid change: {entity}/{rid}')
        table, title, fields = ENTITIES[entity]
        counters = COUNTERS.get(entity, set())
        names = [js for js, _, _, _ in fields]
        cur = c.execute(f'SELECT * FROM {table} WHERE id=?', (rid,)).fetchone()
        before = self._row_js(entity, cur) if cur and not cur['deleted'] else None
        what = f'{title[:-1] if title.endswith("s") else title} "{(before or op.get("row") or {}).get("name") or rid}"'

        if before and not force and op.get('ver') != cur['ver']:
            raise Conflict(f'{what} was changed by {cur["updated_by"] or "another user"} at {cur["updated_at"]}. '
                           'The screen has been refreshed - please repeat your change.')
        if cur and cur['deleted'] and not force and op.get('ver') is not None:
            raise Conflict(f'{what} was deleted by {cur["deleted_by"] or "another user"} at {cur["deleted_at"]}. '
                           'It can be restored from Settings > Recycle Bin.')

        if kind == 'del':
            if not before:
                if op.get('resolve') and cur:  # confirm a delete again (conflict: edited on another PC while deleted)
                    b = self._row_js(entity, cur)
                    b.pop('ver', None)
                    return None, {'e': entity, 'id': rid, 'op': 'delete', 'x': True, 'sc': self._scope_of(entity, b), 'b': b, 'noaudit': True}
                return None, None
            before.pop('ver', None)
            scope = self._scope_of(entity, before)
            return ({'entity': entity, 'id': rid, 'op': 'delete', 'scope': scope, 'changes': {}, 'before': before, 'after': None},
                    {'e': entity, 'id': rid, 'op': 'delete', 'x': True, 'sc': scope, 'b': before})

        if kind != 'put' or not isinstance(op.get('row'), dict):
            raise BadRequest(f'Invalid change: {entity}/{rid}')
        row = op['row']
        for v in row.values():  # file references must stay inside the uploads folder
            if isinstance(v, str) and v.startswith('/files/') and ('..' in v or '\\' in v or ':' in v):
                raise BadRequest('Invalid file reference')
        if entity in META and META[entity].validate:
            META[entity].validate(row)  # raises BadRequest with a plain-words message
        for js, col, kind_, label in fields:
            v = row.get(js)
            if v not in (None, '') and kind_ in (I, R) and _coerce(kind_, v) is None:
                raise BadRequest(f'{label} must be a number')
            if v not in (None, '') and kind_ == I and _coerce(kind_, v) is not None and isinstance(v, (float, str)) and float(v) != int(float(v)):
                raise BadRequest(f'{label} must be a whole number (amounts are entered in the smallest unit)')
        vals = {col: _coerce(kind_, row.get(js)) for js, col, kind_, _ in fields}
        after = {'id': rid, **{js: _out(k, vals[col]) for js, col, k, _ in fields if vals[col] is not None}}
        if self.journal is not None:
            gone = [f for f in self.journal.erased_fields(entity, rid) if after.get(f) is not None]
            if gone:
                raise BadRequest('This information was erased by a privacy request and cannot be entered again on the same record')
        scope = self._scope_of(entity, after)
        if before:
            b = {k: v for k, v in before.items() if k != 'ver'}
            changes = {k: [b.get(k), after.get(k)] for k in set(b) | set(after) if b.get(k) != after.get(k)}
            if changes and SPECS[entity].get('immutable') and not op.get('resolve'):
                raise BadRequest(f'{what} is issued and cannot be changed. Create a new version or a credit note instead.')
            touch = [f for f in (op.get('resolve') or []) if f in names and f not in counters]
            if not changes and not touch:
                return None, None
            s = {k: after.get(k) for k in list(changes) + touch if k in names and k not in counters}
            for f, rule in RESOLVERS.get(entity, {}).items():  # a follower always travels with its leader
                if rule.startswith('follow:') and rule[7:] in s and f not in s:
                    s[f] = after.get(f)
            n = {k: (after.get(k) or 0) - (b.get(k) or 0) for k in changes if k in counters}
            rop = {'e': entity, 'id': rid, 'op': 'update', 's': s, 'sc': scope, 'c': changes}
            if c.execute("SELECT 1 FROM sync_field WHERE tbl=? AND rid=? AND fld='_del' AND val LIKE '[1,%' LIMIT 1", (table, rid)).fetchone():
                rop['x'] = False  # visible only because a restore's delete lost against another PC: editing it keeps it for good
            if n:
                rop['n'] = n
            if not changes:
                rop['noaudit'] = True
                return None, rop
            return {'entity': entity, 'id': rid, 'op': 'update', 'scope': scope, 'scope_before': self._scope_of(entity, b), 'changes': changes,
                    'before': b, 'after': after}, rop
        if cur:  # previously deleted row that is being re-created
            old = self._row_js(entity, cur)
            s = {js: after.get(js) for js in names if js not in counters}
            n = {k: (after.get(k) or 0) - (old.get(k) or 0) for k in counters}
        else:
            s = {js: v for js, v in after.items() if js != 'id' and js not in counters}
            n = {k: after.get(k) or 0 for k in counters}
        rop = {'e': entity, 'id': rid, 'op': 'insert', 's': s, 'x': False, 'sc': scope, 'r': after}
        n = {k: v for k, v in n.items() if v}
        if n:
            rop['n'] = n
        return {'entity': entity, 'id': rid, 'op': 'insert', 'scope': scope, 'scope_before': self._scope_of(entity, old) if cur else scope,
                'changes': {}, 'before': None, 'after': after}, rop

    def fold_pending(self, limit=2000):
        """Applies every journal changeset not yet in the tables (after a crash, or received from another PC).
        Returns the number of changesets folded."""
        total = 0
        while True:
            with self.lock:
                items = self.journal.iter_after(replica.markers(self.conn), limit)
                if not items:
                    return total
                c = self.conn
                c.execute('BEGIN IMMEDIATE')
                try:
                    changed = False
                    for env, status in items:
                        changed |= self.folder.fold(env, status)
                    if changed:
                        self._bump(c)
                    c.execute('COMMIT')
                except Exception:
                    c.execute('ROLLBACK')
                    raise
                total += len(items)
                self._fold_done()

    def restore_from(self, path, user, ip, label, user_id='', kind='restore'):
        """Brings the data back to the state of a backup file WITHOUT rolling back history: the differences
        become one 'restore' changeset. It is weak: real changes made at the same time on other PCs win over it."""
        src = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        src.row_factory = sqlite3.Row
        ops = []
        try:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            with self.lock:
                for e, (table, _, fields) in ENTITIES.items():
                    backup = {}
                    if table in tables:
                        cols = {r[1] for r in src.execute(f'PRAGMA table_info({table})')}
                        for r in src.execute(f'SELECT * FROM {table}'):
                            if not ('deleted' in cols and r['deleted']):
                                d = {'id': r['id']}
                                erased = self.journal.erased_fields(e, r['id']) if self.journal else set()
                                for js, col, ftype, _ in fields:
                                    v = _out(ftype, r[col]) if col in cols and js not in erased else None
                                    if v is not None:
                                        d[js] = v
                                backup[r['id']] = d
                    current = {r['id'] for r in self.conn.execute(f'SELECT id FROM {table} WHERE deleted=0')}
                    for rid in sorted(set(backup) | current):
                        if rid in backup:
                            ops.append({'e': e, 'id': rid, 'op': 'put', 'row': backup[rid]})
                        else:
                            ops.append({'e': e, 'id': rid, 'op': 'del'})
        finally:
            src.close()
        if not ops:
            return {'txn': None, 'changes': 0, 'version': self.version()}
        return self.commit(user, ip, label, ops, force=True, user_id=user_id, kind=kind)

    def erase(self, actor, ip, entity, rid, fields, reason, basis='', ref='', actor_id=''):
        """Legal erasure of the listed fields of one record (docs/SECURITY.md section 5). Only the administrator PC can sign it;
        the caller must already have checked the privacy.erase permission and the confirmation. The order itself carries no
        personal data: record id, field names, reason code, legal basis and request reference."""
        if entity not in ENTITIES:
            raise BadRequest('Unknown kind of record')
        names = {js for js, _, _, _ in ENTITIES[entity][2]}
        fields = sorted(set(fields or []))
        if not fields or any(f not in names for f in fields):
            raise BadRequest('Choose the information to erase')
        if not self.journal.node.is_authority:
            raise BadRequest('An erase order can only be made on the administrator PC')
        if not str(reason or '').strip():
            raise BadRequest('A reason is required')
        if not rid or not self.get(entity, rid, include_deleted=True):
            raise BadRequest('Record not found')
        with self.lock:
            op = {'e': entity, 'id': rid, 'op': 'update', 's': {f: None for f in fields}, 'sc': None,
                  'erase': {'reason': str(reason)[:40], 'basis': str(basis or '')[:200], 'ref': str(ref or '')[:80]}}
            rec = self.journal.write('erase', [op], actor=actor, actor_id=actor_id, ip=ip, label='Legal erasure', authority=True)
            self.fold_pending()
        return {'txn': rec['env']['id']}

    def scrub_logs(self, targets):
        """After an erase order: blank the erased fields in the monthly audit files (data/logs/audit-*.jsonl) as well."""
        for name in os.listdir(self.log_dir):
            if not (name.startswith('audit-') and name.endswith('.jsonl')):
                continue
            path = os.path.join(self.log_dir, name)
            changed, out = False, []
            with open(path, encoding='utf-8') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        out.append(line)
                        continue
                    fields = targets.get((e.get('entity'), e.get('id')))
                    if fields and isinstance(e.get('changes'), dict):
                        for k in fields:
                            if k in e['changes']:
                                e['changes'][k] = [None, None]
                                changed = True
                        line = json.dumps(e, ensure_ascii=False) + '\n'
                    out.append(line)
            if changed:
                tmp = path + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.writelines(out)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)

    def mark_initialized(self):
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('initialized', ?)", (now(),))

    def claim_first_run(self):
        """True for exactly one caller, only on a brand-new installation (the caller then offers demo data).
        A PC that joined another administrator PC is marked initialized when it joins."""
        with self.lock:
            c = self.conn
            c.execute('BEGIN IMMEDIATE')
            try:
                done = c.execute("SELECT value FROM meta WHERE key='initialized'").fetchone()
                if not done:
                    c.execute("INSERT INTO meta VALUES ('initialized', ?)", (now(),))
                c.execute('COMMIT')
            except Exception:
                c.execute('ROLLBACK')
                raise
            return not done

    # ------------------------------------------------------------ recycle bin
    def trash(self):
        with self.lock:
            groups = {}
            for e, (table, title, _) in ENTITIES.items():
                for r in self.conn.execute(f'SELECT * FROM {table} WHERE deleted=1 AND deleted_txn IS NOT NULL ORDER BY rowid'):
                    g = groups.setdefault(r['deleted_txn'], {'txn': r['deleted_txn'], 'ts': r['deleted_at'], 'user': r['deleted_by'], 'items': {}, 'names': []})
                    g['items'][title] = g['items'].get(title, 0) + 1
                    if e != 'settings':
                        js = self._row_js(e, r)
                        g['names'].append(next((js[k] for k in META[e].name_fields if js.get(k)), r['id']) if e in META else r['id'])
            for g in groups.values():
                g['label'] = self._txn_label(g['txn'])
                g['names'] = g['names'][:6]
            return sorted(groups.values(), key=lambda g: g['ts'] or '', reverse=True)

    def restore_txn(self, user, ip, txn):
        ops = []
        with self.lock:
            for e, (table, _, _) in ENTITIES.items():
                for r in self.conn.execute(f'SELECT * FROM {table} WHERE deleted=1 AND deleted_txn=?', (txn,)):
                    row = self._row_js(e, r)
                    ops.append({'e': e, 'id': r['id'], 'op': 'put', 'row': row})
            t = [self._txn_label(txn)]
        if not ops:
            raise BadRequest('Nothing to restore')
        return self.commit(user, ip, 'Restore deleted: ' + (t[0] or txn), ops, force=True)

    def _txn_label(self, txn):
        d = self.journal.describe(txn=txn) if self.journal else None
        return d['label'] if d else ''

    # ------------------------------------------------------------ logs (kept in the journal: never restored, all PCs)
    def log_activity(self, user, ip, events):
        self.journal.log_activity(user, ip, events[:500])

    def query_log(self, kind, q='', user='', typ='', scope='', frm='', to='', limit=200, offset=0, scopes=None, node='', admin=True, search_values=True):
        if kind == 'activity':
            self.journal.flush_activity()
        return self.journal.query('audit' if kind == 'audit' else 'activity', q, user, typ, scope, frm, to, node, limit, offset, scopes,
                                  business_only=not admin, search_values=search_values)

    # ------------------------------------------------------------ conflicts and convergence
    def conflicts(self):
        """Everything two PCs did at the same time that a person should look at. Identical on every PC."""
        titles = {spec['table']: (e, ENTITIES[e][1] if e in ENTITIES else 'Files') for e, spec in SPECS.items()}
        out = []
        with self.lock:
            flags = self.conn.execute('SELECT * FROM sync_flags ORDER BY tbl, rid, kind').fetchall()
            for f in flags:
                if f['tbl'] == FILES[0]:  # the same file recorded twice with a different type guess: cosmetic, nobody has to decide
                    continue
                entity, title = titles.get(f['tbl'], (f['tbl'], f['tbl']))
                r = self.conn.execute(f'SELECT * FROM {f["tbl"]} WHERE id=?', (f['rid'],)).fetchone()
                row = self._row_js(entity, r) if r else {'id': f['rid']}
                detail = json.loads(f['detail'])
                item = {'entity': entity, 'title': title, 'id': f['rid'], 'kind': f['kind'], 'deleted': bool(r and r['deleted']),
                        'name': next((row[k] for k in META[entity].name_fields if row.get(k)), f['rid']) if entity in META else f['rid'],
                        'scope': self._scope_of(entity, row) if r else None, 'row': row, 'detail': detail}
                out.append(item)
            for name, m in META.items():
                if not m.dup_keys:
                    continue
                cols = {js: col for js, col, _, _ in m.fields}
                keys = ', '.join(cols[k] for k in m.dup_keys)
                for d in self.conn.execute(f'SELECT {keys}, COUNT(*) n, GROUP_CONCAT(id) ids FROM {m.table} WHERE deleted=0 '
                                           f'GROUP BY {keys} HAVING n > 1').fetchall():
                    ids = d['ids'].split(',')
                    out.append({'entity': name, 'title': m.title, 'id': ids[0], 'kind': 'duplicate', 'deleted': False,
                                'name': ' / '.join(str(d[cols[k]] or '') for k in m.dup_keys).strip(' /'),
                                'scope': None, 'detail': {'ids': ids, 'count': d['n']}})
        return out

    def fingerprint(self):
        """SHA-256 over the complete business data (without local counters). Equal on PCs that agree."""
        with self.lock:
            v = self.version()
            if self._fp[0] == v:
                return self._fp[1]
            h = hashlib.sha256()
            for e in sorted(SPECS):
                table = SPECS[e]['table']
                for r in self.conn.execute(f'SELECT * FROM {table} ORDER BY id'):
                    d = dict(r)
                    d.pop('ver', None)
                    h.update(canonical([table, d]).encode('utf-8'))
            for r in self.conn.execute('SELECT * FROM sync_flags ORDER BY tbl, rid, kind'):
                h.update(canonical(['flag', *r]).encode('utf-8'))
            self._fp = (v, h.hexdigest())
            return self._fp[1]

    # ------------------------------------------------------------ attachments
    def file_info(self, path):
        with self.lock:
            r = self.conn.execute('SELECT sha256, size_bytes FROM attachments WHERE id=?', (path,)).fetchone()
        return {'sha256': r[0], 'size': r[1]} if r else None

    def referenced_files(self):
        """Every uploaded file the current data (and the recycle bin) refers to."""
        out = set()
        with self.lock:
            sqls = [f'SELECT {col} FROM {m.table}' for m in META.values() for js, col, _, _ in m.fields if js in m.file_fields]
            sqls += ['SELECT id FROM attachments']
            for sql in sqls:
                for (v,) in self.conn.execute(sql):
                    if isinstance(v, str):
                        v = v.strip('"')
                        if v.startswith('/files/'):
                            out.add(v)
        return out

    # ------------------------------------------------------------ export
    def export_sheets(self, admin=False, entities=None):
        """[(sheet title, header row, rows)] of the registered entities (or the named ones), plus deleted records and the
        data-change log. Domain-specific sheets are added by the platform on top."""
        with self.lock:
            c = self.conn
            sheets, deleted = [], []
            for name in (entities or [e for e in ENTITIES if e != 'settings'] + ['settings']):
                table, title, fields = ENTITIES[name]
                head = ['ID'] + [label for _, _, _, label in fields] + ['Created', 'Created By', 'Last Changed', 'Changed By']
                rows = []
                for r in c.execute(f'SELECT * FROM {table} ORDER BY rowid'):
                    if r['deleted']:
                        deleted.append([title, r['id'], str(self._row_js(name, r))[:500], r['deleted_at'], r['deleted_by']])
                        continue
                    out = [r['id']]
                    for js, col, kind, _ in fields:
                        v = _out(kind, r[col])
                        if kind == J:
                            v = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                        out.append(v)
                    out += [r['created_at'], r['created_by'], r['updated_at'], r['updated_by']]
                    rows.append(out)
                sheets.append((title, head, rows))
            sheets.append(('Deleted Records', ['Table', 'ID', 'Record', 'Deleted At', 'Deleted By'], deleted))
        j = self.journal
        j.flush_activity()
        with j.lock:
            names = {r['id']: r['name'] for r in j.conn.execute('SELECT id, name FROM nodes')}
            sheets.append(('Data Changes Log', ['#', 'Time', 'User', 'PC', 'IP', 'Action', 'Table', 'Record ID', 'Scope', 'Operation', 'Changes'],
                           [[r['id'], r['ts'], r['user'], names.get(r['node'], r['node']), r['ip'], r['label'], r['entity'], r['entity_id'],
                             r['scope_id'], r['op'], r['changes'] if r['op'] == 'update' else (r['after'] or r['before'])]
                            for r in j.conn.execute("SELECT * FROM audit WHERE entity NOT IN ('users', 'nodes', 'userCommands', 'profiles') "
                                                    "ORDER BY ts, id")]))
            if admin:  # what each person clicked is for administrators only
                sheets.append(('User Activity Log', ['#', 'Time', 'User', 'PC', 'IP', 'Type', 'Action', 'Target', 'Page', 'Detail'],
                               [[r['id'], r['ts'], r['user'], names.get(r['node'], r['node']), r['ip'], r['type'], r['action'], r['target'], r['page'],
                                 r['detail']] for r in j.conn.execute('SELECT * FROM activity ORDER BY ts, id')]))
        return sheets

    def counts(self):
        with self.lock:
            return {title: self.conn.execute(f'SELECT COUNT(*) FROM {table} WHERE deleted=0').fetchone()[0]
                    for table, title, _ in ENTITIES.values()}
