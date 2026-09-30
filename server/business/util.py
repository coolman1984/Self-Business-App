"""Small helpers shared by the import, demo and timeline code."""
import query as query_mod


def rows(app, access, entity, filters, cap=5000, include_deleted=False):
    """Every row that matches (through the caller's own access), up to `cap`."""
    out, cursor = [], None
    while True:
        page = query_mod.run(app.store, entity, access, filters, limit=500, cursor=cursor, include_deleted=include_deleted)
        out += page['rows']
        cursor = page['next']
        if not cursor or len(out) >= cap:
            return out


def strip(row):
    """A stored record as a `put` row: without id, version and the read-only stamps."""
    return {k: v for k, v in row.items() if not k.startswith('_') and k not in ('id', 'ver')}
