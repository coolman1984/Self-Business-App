"""Global search: a derived, per-PC index (data/index.db) built from the business data. Never replicated, never a source of
truth - `rebuild()` recreates it from the tables at any time (after an erase order the changed rows are re-indexed).

What is searchable is declared per entity (`Entity.search`, `phone_fields`, `email_fields`). Money and sensitive fields are
never indexed. Results are filtered by the user's data scope exactly like lists (see query.py)."""
import os
import sqlite3
import threading

from registry import ENTITIES, META
from textnorm import norm_email, norm_text, phone_tokens

SCHEMA = 2  # bump to force a rebuild when the index layout or the normalisation changes


class SearchIndex:
    def __init__(self, path, country='20'):
        self.path = path
        self.country = country
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=NORMAL')  # derived data: a lost tail is rebuilt, speed matters more
        self._create()

    def _create(self):
        c = self.conn
        c.executescript('''
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY, entity TEXT NOT NULL, rid TEXT NOT NULL, title TEXT, subtitle TEXT, scope TEXT, created_by TEXT,
                UNIQUE (entity, rid));
            CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(body, tokenize='unicode61');
        ''')
        v = c.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        if not v or int(v[0]) != SCHEMA:
            c.execute('DELETE FROM docs')
            c.execute('DELETE FROM fts')
            c.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA),))
            c.execute("INSERT OR REPLACE INTO meta VALUES ('built', '0')")

    def needs_rebuild(self):
        with self.lock:
            return self.conn.execute("SELECT value FROM meta WHERE key='built'").fetchone()[0] != '1'

    # ------------------------------------------------------------ building
    def _doc(self, store, entity, row):
        m = META.get(entity)
        if m is None or not m.search:
            return None
        hidden = set(m.money_fields) | set(m.sensitive_fields)
        words = [norm_text(row.get(f)) for f in m.search if f not in hidden and row.get(f) not in (None, '')]
        for f in m.phone_fields:
            if f not in hidden:
                words += phone_tokens(row.get(f), self.country)
        for f in m.email_fields:
            if f not in hidden and row.get(f):
                e = norm_email(row.get(f))
                words += [norm_text(e), e]
        title = next((str(row[k]) for k in (*m.name_fields, *m.search) if row.get(k) and k not in hidden), row['id'])
        sub = ' · '.join(str(row[k]) for k in m.subtitle_fields if row.get(k) not in (None, '') and k not in hidden)
        return ' '.join(w for w in words if w), title, sub, store._scope_of(entity, row)

    def _put(self, store, entity, rid, created_by):
        row = store.get(entity, rid)
        c = self.conn
        old = c.execute('SELECT id FROM docs WHERE entity=? AND rid=?', (entity, rid)).fetchone()
        doc = self._doc(store, entity, row) if row else None
        if old:
            c.execute('DELETE FROM fts WHERE rowid=?', (old['id'],))
            c.execute('DELETE FROM docs WHERE id=?', (old['id'],))
        if doc and doc[0]:
            body, title, sub, scope = doc
            cur = c.execute('INSERT INTO docs (entity, rid, title, subtitle, scope, created_by) VALUES (?,?,?,?,?,?)',
                            (entity, rid, title, sub, scope, created_by))
            c.execute('INSERT INTO fts (rowid, body) VALUES (?,?)', (cur.lastrowid, body))

    def apply(self, store, touched):
        """Re-indexes the records that changed (called after every fold)."""
        if not touched:
            return
        with self.lock:
            self.conn.execute('BEGIN')
            try:
                for entity, rid in sorted(touched):
                    if entity in META and META[entity].search:
                        r = store.conn.execute(f'SELECT created_by FROM {ENTITIES[entity][0]} WHERE id=?', (rid,)).fetchone()
                        self._put(store, entity, rid, r[0] if r else None)
                self.conn.execute('COMMIT')
            except Exception:
                self.conn.execute('ROLLBACK')
                raise

    def rebuild(self, store):
        with self.lock:
            self.conn.execute('BEGIN')
            try:
                self.conn.execute('DELETE FROM docs')
                self.conn.execute('DELETE FROM fts')
                for entity, m in META.items():
                    if not m.search:
                        continue
                    for r in store.conn.execute(f'SELECT id, created_by FROM {m.table} WHERE deleted=0').fetchall():
                        self._put(store, entity, r['id'], r['created_by'])
                self.conn.execute("INSERT OR REPLACE INTO meta VALUES ('built', '1')")
                self.conn.execute('COMMIT')
            except Exception:
                self.conn.execute('ROLLBACK')
                raise

    # ------------------------------------------------------------ searching
    def search(self, q, access, limit=20, entities=None):
        tokens = norm_text(q).split()
        e = norm_email(q)
        if '@' in e:
            tokens = [e]
        elif len(tokens) == 1 and tokens[0].isdigit() and len(tokens[0]) >= 4:
            tokens = [tokens[0]]  # a phone number or a document number typed as digits
        if not tokens:
            return []
        expr = ' AND '.join('"' + t.replace('"', '') + '"*' for t in tokens[:8])
        where, args = ['fts MATCH ?'], [expr]
        if entities:
            where.append(f'd.entity IN ({",".join("?" * len(entities))})')
            args += list(entities)
        mode = access.get('mode', 'all')
        if mode == 'scopes':
            where.append(f'd.scope IN ({",".join("?" * len(access.get("scopes") or [])) or "NULL"})')
            args += list(access.get('scopes') or [])
        elif mode == 'own':
            where.append('d.created_by=?')
            args.append(access.get('user'))
        sql = ('SELECT d.entity, d.rid, d.title, d.subtitle FROM fts JOIN docs d ON d.id = fts.rowid WHERE ' + ' AND '.join(where)
               + ' ORDER BY bm25(fts), d.title LIMIT ?')
        with self.lock:
            rows = self.conn.execute(sql, [*args, max(1, min(int(limit), 100))]).fetchall()
        return [{'entity': r['entity'], 'id': r['rid'], 'title': r['title'], 'subtitle': r['subtitle']} for r in rows]

    def close(self):
        self.conn.close()
