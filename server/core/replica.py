"""Deterministic fold: turns changesets into the rows the application reads.

Every field of every row is a *multi-value register*. The table sync_field keeps its
frontier: the writes that no later write has seen yet. A new write removes the
entries it has seen (its version vector covers them) and joins the frontier. When the
frontier holds more than one entry, two PCs changed the same field without knowing of
each other; a resolver picks the value to show - the same on every PC, whatever the
order the changes arrived in - and the other value stays stored and is reported as a
conflict until somebody saves a newer value.

Special registers per row:  _del (deleted flag, delete wins),  _ins (created at/by,
earliest wins),  _upd (last changed at/by, latest wins).  Counters (inventory
quantity) are not registers: each change carries a delta that is added exactly once.

Folding is exactly-once per changeset: sync_marker holds, per origin, the highest
change number already folded, and is updated in the same transaction as the rows.
"""
import json
import sqlite3

from journal import PRIORITY, canonical, dominates

# errors that depend on this PC (disk full, locked file) - the change is folded again later; every other error of
# one change is the same on every PC, so that change is skipped the same way everywhere
ENVIRONMENTAL = (sqlite3.OperationalError, MemoryError)

META = ('_del', '_ins', '_upd')


def install(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sync_field (
            tbl TEXT NOT NULL, rid TEXT NOT NULL, fld TEXT NOT NULL, origin TEXT NOT NULL, cseq INTEGER NOT NULL,
            prio INTEGER NOT NULL, hlc INTEGER NOT NULL, val TEXT, PRIMARY KEY (tbl, rid, fld, origin, cseq));
        CREATE TABLE IF NOT EXISTS sync_marker (origin TEXT PRIMARY KEY, cseq INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sync_flags (tbl TEXT NOT NULL, rid TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT,
            PRIMARY KEY (tbl, rid, kind));
        CREATE TABLE IF NOT EXISTS sync_dropped (tbl TEXT NOT NULL, rid TEXT NOT NULL, fld TEXT NOT NULL, origin TEXT NOT NULL,
            cseq INTEGER NOT NULL, PRIMARY KEY (tbl, rid, fld, origin, cseq));
    ''')


def markers(conn):
    return {r[0]: r[1] for r in conn.execute('SELECT origin, cseq FROM sync_marker')}


def set_marker(conn, origin, cseq):
    conn.execute('INSERT INTO sync_marker VALUES (?,?) ON CONFLICT(origin) DO UPDATE SET cseq=MAX(cseq, excluded.cseq)', (origin, cseq))


class Entry:
    __slots__ = ('fld', 'origin', 'cseq', 'prio', 'hlc', 'val', 'value')

    def __init__(self, fld, origin, cseq, prio, hlc, val):
        self.fld, self.origin, self.cseq, self.prio, self.hlc, self.val = fld, origin, cseq, prio, hlc, val
        self.value = json.loads(val) if val is not None else None

    def lww(self):
        return (self.prio, self.hlc, self.origin, self.cseq)


def _ord_value(v):
    return (0, v, '') if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, 0, str(v))


def _cmp_value(v):
    return (v is not None, '' if v is None else str(v))


class Registers:
    """The frontier store, shared by the business tables (sbo.db) and the user table (auth.db)."""

    def __init__(self, conn, deps_of):
        self.conn = conn
        self._deps_of = deps_of
        self.current = None  # the changeset being folded (it may not be in the journal yet)

    def deps_of(self, origin, cseq):
        cur = self.current
        if cur and cur['origin'] == origin and cur['cseq'] == cseq:
            return cur.get('deps') or {}
        return self._deps_of(origin, cseq)

    def write(self, tbl, rid, fld, env, prio, hlc, value, once=False):
        """once=True (write-once fields of immutable records, e.g. issued documents): only the earliest write by
        (hlc, origin, cseq) is ever kept, whatever the order of arrival; every other write is remembered as dropped so
        that the row is flagged 'edited-after-issue' identically on every PC."""
        origin, cseq, deps = env['origin'], env['cseq'], env.get('deps') or {}
        if once:
            rows = self.conn.execute('SELECT origin, cseq, hlc FROM sync_field WHERE tbl=? AND rid=? AND fld=?', (tbl, rid, fld)).fetchall()
            me = (hlc, origin, cseq)
            if any((o, c) == (origin, cseq) for o, c, _ in rows):
                return
            if rows:
                first = min((h, o, c) for o, c, h in rows)
                if first < me:  # an earlier write already holds the field: this one is dropped
                    self.conn.execute('INSERT OR IGNORE INTO sync_dropped VALUES (?,?,?,?,?)', (tbl, rid, fld, origin, cseq))
                    return
                for o, c, _ in rows:  # this write is earlier than the stored one: it takes over, the stored one is dropped
                    self.conn.execute('DELETE FROM sync_field WHERE tbl=? AND rid=? AND fld=? AND origin=? AND cseq=?', (tbl, rid, fld, o, c))
                    self.conn.execute('INSERT OR IGNORE INTO sync_dropped VALUES (?,?,?,?,?)', (tbl, rid, fld, o, c))
            self.conn.execute('INSERT INTO sync_field VALUES (?,?,?,?,?,?,?,?)', (tbl, rid, fld, origin, cseq, prio, hlc, canonical(value)))
            return
        for o, c in self.conn.execute('SELECT origin, cseq FROM sync_field WHERE tbl=? AND rid=? AND fld=?', (tbl, rid, fld)).fetchall():
            if (o == origin and c == cseq) or dominates(deps, origin, cseq, o, c):
                self.conn.execute('DELETE FROM sync_field WHERE tbl=? AND rid=? AND fld=? AND origin=? AND cseq=?', (tbl, rid, fld, o, c))
        self.conn.execute('INSERT INTO sync_field VALUES (?,?,?,?,?,?,?,?)', (tbl, rid, fld, origin, cseq, prio, hlc, canonical(value)))

    def entries(self, tbl, rid):
        groups = {}
        for r in self.conn.execute('SELECT fld, origin, cseq, prio, hlc, val FROM sync_field WHERE tbl=? AND rid=?', (tbl, rid)):
            groups.setdefault(r[0], []).append(Entry(*r))
        return groups

    def dominated(self, a, b):
        """True when entry b had already seen entry a."""
        return dominates(self.deps_of(b.origin, b.cseq), b.origin, b.cseq, a.origin, a.cseq)

    def concurrent(self, a, b):
        return (a.origin, a.cseq) != (b.origin, b.cseq) and not self.dominated(a, b) and not self.dominated(b, a)

    def resolve(self, groups, resolvers):
        """{field: winning Entry} - deterministic whatever the arrival order."""
        win = {}
        todo = sorted(groups, key=lambda f: 1 if str(resolvers.get(f, '')).startswith('follow:') else 0)
        for fld in todo:
            es = groups[fld]
            rule = resolvers.get(fld, 'lww')
            if fld == '_ins':
                w = min(es, key=lambda e: (e.hlc, e.origin, e.cseq))
            elif fld == '_del':
                w = max(es, key=lambda e: (e.prio, bool(e.value and e.value[0]), e.hlc, e.origin, e.cseq))
            elif rule == 'max':
                w = max(es, key=lambda e: (e.prio, e.value is not None, _ord_value(e.value), e.hlc, e.origin, e.cseq))
            elif rule == 'min':  # the smallest value wins (earliest date, lowest number); empty values only if all are empty
                top = max(e.prio for e in es)
                best = [e for e in es if e.prio == top]
                best = [e for e in best if e.value is not None] or best
                w = min(best, key=lambda e: (_ord_value(e.value), e.hlc, e.origin, e.cseq))
            elif rule.startswith('rank:'):
                order = rule[5:].split(',')
                w = max(es, key=lambda e: (e.prio, order.index(e.value) if e.value in order else -1, e.hlc, e.origin, e.cseq))
            elif rule.startswith('follow:'):
                lead = win.get(rule[7:])
                same = [e for e in es if lead and (e.origin, e.cseq) == (lead.origin, lead.cseq)]
                w = same[0] if same else max(es, key=Entry.lww)
            else:
                w = max(es, key=Entry.lww)
            win[fld] = w
        return win

    def deleted(self, groups, win):
        """Effective deleted state. A delete from a backup restore does not win against a real change
        made concurrently on another PC (that PC's work must not disappear because of an old backup)."""
        d = win.get('_del')
        if not d or not (d.value and d.value[0]):
            return False
        if d.prio == 0:
            for fld, es in groups.items():
                if fld not in META and any(e.prio >= 1 and self.concurrent(e, d) for e in es):
                    return False
        return True

    def flags(self, groups, win, is_deleted, counters=None, tbl_rid=None):
        """Things a person should look at, derived from the converged state (identical on every PC)."""
        out = {}
        conflicts = {}
        for fld, es in groups.items():
            if fld in META or len(es) < 2:
                continue
            values = {e.val for e in es}
            if len(values) > 1:
                conflicts[fld] = [{'value': e.value, 'origin': e.origin, 'cseq': e.cseq, 'win': e is win[fld]}
                                  for e in sorted(es, key=Entry.lww, reverse=True)]
        if conflicts:
            out['conflict'] = conflicts
        dropped = self.conn.execute('SELECT fld, origin, cseq FROM sync_dropped WHERE tbl=? AND rid=? ORDER BY fld, origin, cseq', (tbl_rid[0], tbl_rid[1])).fetchall() if tbl_rid else []
        if dropped:
            out['edited-after-issue'] = [[r[0], r[1], r[2]] for r in dropped]
        d = win.get('_del')
        if is_deleted and d:
            edits = sorted({(e.origin, e.cseq) for fld, es in groups.items() if fld not in META for e in es if self.concurrent(e, d)})
            if edits:
                out['deleted-edit'] = {'delete': [d.origin, d.cseq], 'edits': [list(x) for x in edits]}
        for k, v in (counters or {}).items():
            if v is not None and v < 0 and not is_deleted:
                out['negative'] = {k: v}
        return out

    def set_flags(self, tbl, rid, flags):
        """Returns True when the flags of the row changed."""
        new = {k: canonical(v) for k, v in flags.items()}
        old = {r[0]: r[1] for r in self.conn.execute('SELECT kind, detail FROM sync_flags WHERE tbl=? AND rid=?', (tbl, rid))}
        if old == new:
            return False
        self.conn.execute('DELETE FROM sync_flags WHERE tbl=? AND rid=?', (tbl, rid))
        for k, v in new.items():
            self.conn.execute('INSERT INTO sync_flags VALUES (?,?,?,?)', (tbl, rid, k, v))
        return True


class BusinessFolder:
    """Folds data/restore/bootstrap changesets into the business tables of sbo.db."""

    def __init__(self, conn, specs, deps_of, coerce):
        self.conn = conn
        self.specs = specs  # entity -> {'table', 'fields': [(js, col, kind)], 'counters': set, 'resolvers': {}}
        self.reg = Registers(conn, deps_of)
        self.coerce = coerce
        self.problems = []
        self.touched = set()  # (entity, id) of rows changed since the last pop (for the derived search index)

    def fold(self, env, status):
        """Folds one changeset (inside the caller's transaction). Returns True when rows changed."""
        mk = self.conn.execute('SELECT cseq FROM sync_marker WHERE origin=?', (env['origin'],)).fetchone()
        if mk and mk[0] >= env['cseq']:
            return False
        changed = False
        self.reg.current = env
        if status == 'ok' and env['kind'] in PRIORITY and env['kind'] not in ('admin', 'account'):
            for i, op in enumerate(env['ops']):
                self.conn.execute('SAVEPOINT op')
                try:
                    changed |= self._op(env, op)
                    self.conn.execute('RELEASE op')
                except ENVIRONMENTAL:
                    raise
                except Exception as e:  # noqa: BLE001
                    # the same change fails the same way on every PC, so skipping it keeps everybody equal
                    self.conn.execute('ROLLBACK TO op')
                    self.conn.execute('RELEASE op')
                    self.problems.append(f'{env["origin"]}#{env["cseq"]} op {i}: {e}')
        self.reg.current = None
        set_marker(self.conn, env['origin'], env['cseq'])
        return changed

    def _op(self, env, op):
        spec = self.specs[op['e']]
        rid = op['id']
        if not isinstance(rid, str) or not rid or len(rid) > 200:
            raise ValueError('bad record id')
        tbl = spec['table']
        prio = PRIORITY[env['kind']]
        if env['kind'] == 'erase':  # an erase order removes every stored value of the fields, then blanks them at the highest priority
            for js in sorted(op.get('s') or {}):
                self.conn.execute('DELETE FROM sync_field WHERE tbl=? AND rid=? AND fld=?', (tbl, rid, js))
        hlc = op['t'] if env['kind'] == 'bootstrap' and isinstance(op.get('t'), int) else env['hlc']
        names = {js for js, _, _ in spec['fields']}
        sets = op.get('s') or {}
        if not isinstance(sets, dict):
            raise ValueError('bad field list')
        once = bool(spec.get('immutable'))
        for js, v in sorted(sets.items()):
            if js in names and js not in spec['counters']:
                self.reg.write(tbl, rid, js, env, prio, hlc, v, once=once)
        boot = env['kind'] == 'bootstrap'  # keeps the original created / changed / deleted stamps of upgraded rows
        if op.get('x') is not None:
            stamp = op['di'] if boot and isinstance(op.get('di'), list) else [env['ts'], env['actor'], env['id']]
            self.reg.write(tbl, rid, '_del', env, prio, hlc, [1 if op['x'] else 0, *stamp[:3]])
        if op.get('op') == 'insert':
            self.reg.write(tbl, rid, '_ins', env, prio, hlc, op['ci'] if boot and isinstance(op.get('ci'), list) else [env['ts'], env['actor'], env.get('actor_id') or ''])
        self.reg.write(tbl, rid, '_upd', env, prio, hlc, op['ui'] if boot and isinstance(op.get('ui'), list) else [env['ts'], env['actor']])
        changed = self.materialize(op['e'], rid)
        self.touched.add((op['e'], rid))
        for js, delta in sorted((op.get('n') or {}).items()):
            if js in spec['counters'] and isinstance(delta, (int, float)) and not isinstance(delta, bool) and delta:
                col = next(c for j, c, _ in spec['fields'] if j == js)
                self.conn.execute(f'UPDATE {tbl} SET {col}=COALESCE({col},0)+?, ver=ver+1 WHERE id=?', (delta, rid))
                changed = True
        changed |= self.refresh_flags(op['e'], rid)
        return changed

    def materialize(self, entity, rid):
        spec = self.specs[entity]
        tbl = spec['table']
        groups = self.reg.entries(tbl, rid)
        win = self.reg.resolve(groups, spec['resolvers'])
        deleted = self.reg.deleted(groups, win)
        vals = {}
        for js, col, kind in spec['fields']:
            if js in spec['counters']:
                continue
            w = win.get(js)
            vals[col] = self.coerce(kind, w.value) if w else None
        d, ins, upd = win.get('_del'), win.get('_ins'), win.get('_upd')
        if deleted:
            vals.update(deleted=1, deleted_at=d.value[1], deleted_by=d.value[2], deleted_txn=d.value[3])
        else:
            vals.update(deleted=0, deleted_at=None, deleted_by=None, deleted_txn=None)
        vals.update(created_at=ins.value[0] if ins else None, created_by=ins.value[1] if ins else None,
                    created_by_id=(ins.value[2] if ins and len(ins.value) > 2 else None),
                    updated_at=upd.value[0] if upd else None, updated_by=upd.value[1] if upd else None)
        cur = self.conn.execute(f'SELECT * FROM {tbl} WHERE id=?', (rid,)).fetchone()
        if cur is None:
            vals.update({col: 0 for js, col, _ in spec['fields'] if js in spec['counters']})
            cols = list(vals)
            self.conn.execute(f'INSERT INTO {tbl} (id, ver, {", ".join(cols)}) VALUES (?, 1, {", ".join("?" * len(cols))})', (rid, *vals.values()))
            return True
        if all(cur[k] == v for k, v in vals.items()):
            return False
        self.conn.execute(f'UPDATE {tbl} SET {", ".join(k + "=?" for k in vals)}, ver=ver+1 WHERE id=?', (*vals.values(), rid))
        return True

    def refresh_flags(self, entity, rid):
        spec = self.specs[entity]
        tbl = spec['table']
        groups = self.reg.entries(tbl, rid)
        win = self.reg.resolve(groups, spec['resolvers'])
        counters = {}
        if spec['counters']:
            row = self.conn.execute(f'SELECT * FROM {tbl} WHERE id=?', (rid,)).fetchone()
            for js, col, _ in spec['fields']:
                if js in spec['counters']:
                    counters[js] = row[col] if row else None
        return self.reg.set_flags(tbl, rid, self.reg.flags(groups, win, self.reg.deleted(groups, win), counters, (tbl, rid)))
