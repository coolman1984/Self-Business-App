"""Query API of the engine: filtered, sorted, cursor-paginated reads of any registered entity, with data-scope filtering
and field masking applied on the server (the browser never receives what the user may not see).

BAMS sent the whole database to the page (`/api/state`). A business accumulates years of documents, so lists are queried.

Access model, all decided here and in the router, never by the UI:
  * data scope of the user: 'all' | 'scopes' (only records whose scope id is in the user's list) | 'own' (only records the
    user created);
  * masked fields: an entity may declare `money_fields` and `sensitive_fields`; without the permission `money.view` /
    `data.sensitive` those fields are removed from every returned row.
"""
import base64
import json

from registry import ENTITIES, META, scope_of

MAX_LIMIT = 500
OPERATORS = {'eq': '=', 'ne': '!=', 'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>='}


class QueryError(ValueError):
    pass


def _cols(entity):
    if entity not in ENTITIES:
        raise QueryError('Unknown kind of record')
    return {js: (col, kind) for js, col, kind, _ in ENTITIES[entity][2]}


def _encode(cursor):
    return base64.urlsafe_b64encode(json.dumps(cursor, separators=(',', ':')).encode()).decode().rstrip('=')


def _decode(text):
    try:
        raw = base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))
        c = json.loads(raw)
        if isinstance(c, list) and len(c) == 2:
            return c
    except (ValueError, TypeError):
        pass
    raise QueryError('Bad page marker')


def access_for(user):
    """What the query layer needs to know about the logged-in user: (data scope, scope ids, permissions, user id)."""
    perms = set(user.get('perms') or [])
    return {'mode': user.get('data_scope') or 'all', 'scopes': user.get('scopes') or [], 'perms': perms, 'user': user.get('display') or user.get('username')}


def run(store, entity, access, filters=None, search=None, sort=None, desc=False, limit=50, cursor=None, include_deleted=False):
    """Returns {'rows': [...], 'next': cursor|None, 'total': int|None}.
    filters: [(field, op, value)] with op in eq ne lt lte gt gte like in.  sort: a field (default: creation order)."""
    cols = _cols(entity)
    meta = META.get(entity)
    table = ENTITIES[entity][0]
    limit = max(1, min(int(limit or 50), MAX_LIMIT))
    where, args = ([] if include_deleted else ['deleted=0']), []
    for field, op, value in filters or []:
        if field == 'id':
            col = 'id'
        elif field in cols:
            col = cols[field][0]
        else:
            raise QueryError(f'Cannot filter by {field}')
        if op in OPERATORS:
            where.append(f'{col} {OPERATORS[op]} ?')
            args.append(value)
        elif op == 'like':
            where.append(f"{col} LIKE ? ESCAPE '\\'")
            args.append('%' + str(value).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        elif op == 'in':
            vals = list(value or [])[:200]
            where.append(f'{col} IN ({",".join("?" * len(vals)) or "NULL"})')
            args += vals
        else:
            raise QueryError(f'Unknown filter {op}')
    # data scope
    mode = access['mode']
    if mode == 'scopes' and meta is not None:
        if meta.scope_self:
            where.append(f'id IN ({",".join("?" * len(access["scopes"])) or "NULL"})')
            args += list(access['scopes'])
        elif meta.scope_field and meta.scope_field in cols:
            where.append(f'{cols[meta.scope_field][0]} IN ({",".join("?" * len(access["scopes"])) or "NULL"})')
            args += list(access['scopes'])
        elif meta.scope_via:
            fk, parent = meta.scope_via
            ptable, pmeta = ENTITIES[parent][0], META.get(parent)
            pcol = 'id' if pmeta and pmeta.scope_self else (_cols(parent)[pmeta.scope_field][0] if pmeta and pmeta.scope_field else None)
            if pcol is None:
                where.append('0')
            else:
                where.append(f'{cols[fk][0]} IN (SELECT id FROM {ptable} WHERE {pcol} IN ({",".join("?" * len(access["scopes"])) or "NULL"}))')
                args += list(access['scopes'])
    elif mode == 'own':
        where.append('created_by=?')
        args.append(access['user'])
    if search:
        like_cols = [cols[f][0] for f in (meta.name_fields if meta else ()) if f in cols] or [c for c, k in cols.values() if k == 'text'][:3]
        if like_cols:
            where.append('(' + ' OR '.join(f"{c} LIKE ? ESCAPE '\\'" for c in like_cols) + ')')
            q = '%' + str(search).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            args += [q] * len(like_cols)
    order_col = cols[sort][0] if sort in cols else 'rowid'
    if sort and sort not in cols and sort != 'rowid':
        raise QueryError(f'Cannot sort by {sort}')
    direction = 'DESC' if desc else 'ASC'
    op = '<' if desc else '>'
    page_where, page_args = list(where), list(args)
    if cursor:
        last_val, last_rowid = _decode(cursor)
        if order_col == 'rowid':
            page_where.append(f'rowid {op} ?')
            page_args.append(last_rowid)
        elif last_val is None:  # NULL sorts first: after a NULL come the non-NULL rows (ascending) or only older NULLs (descending)
            page_where.append(f'({order_col} IS NULL AND rowid {op} ?)' if desc else f'({order_col} IS NOT NULL OR rowid {op} ?)')
            page_args.append(last_rowid)
        else:
            page_where.append(f'({order_col} {op} ? OR ({order_col} = ? AND rowid {op} ?))')
            page_args += [last_val, last_val, last_rowid]
    sql = (f'SELECT *, rowid AS _rowid FROM {table}' + (' WHERE ' + ' AND '.join(page_where) if page_where else '')
           + f' ORDER BY {order_col} {direction}, rowid {direction} LIMIT ?')
    with store.lock:
        rows = store.conn.execute(sql, [*page_args, limit + 1]).fetchall()
        total = None
        if not cursor:
            total = store.conn.execute(f'SELECT COUNT(*) FROM {table}' + (' WHERE ' + ' AND '.join(where) if where else ''), args).fetchone()[0]
    more = len(rows) > limit
    rows = rows[:limit]
    out = [mask(entity, store._row_js(entity, r), access['perms']) for r in rows]
    nxt = None
    if more and rows:
        last = rows[-1]
        nxt = _encode([last[order_col] if order_col != 'rowid' else None, last['_rowid']])
    return {'rows': out, 'next': nxt, 'total': total}


def mask(entity, row, perms):
    """Removes the fields the user may not see. Also used for single-record reads and search results."""
    meta = META.get(entity)
    if meta is None:
        return row
    hide = set()
    if 'money.view' not in perms:
        hide |= set(meta.money_fields)
    if 'data.sensitive' not in perms:
        hide |= set(meta.sensitive_fields)
    if not hide:
        return row
    return {k: v for k, v in row.items() if k not in hide}


def can_see(entity, row, access, store):
    """True when a single record is inside the user's data scope (used for record reads, timelines and search hits)."""
    mode = access['mode']
    if mode == 'all':
        return True
    if mode == 'own':
        r = store.conn.execute(f'SELECT created_by FROM {ENTITIES[entity][0]} WHERE id=?', (row.get('id'),)).fetchone()
        return bool(r and r[0] == access['user'])
    if mode == 'scopes':
        sid = store._scope_of(entity, row)
        return sid is not None and sid in set(access['scopes'])
    return False
