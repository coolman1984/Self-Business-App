"""The unified timeline of a client (or a project): every change of the client's records, newest first.

Built from the change log of the records that belong to the client, so it is always complete ("timeline shows every change") and
follows the same rules as everything else: the user must be allowed to see the client (data scope), and hidden fields (money,
sensitive) are removed from the changes before they leave the server.
"""
import query as query_mod
from registry import META

CHILDREN = [('opportunities', 'party_id'), ('projects', 'party_id'), ('tasks', 'party_id'), ('appointments', 'party_id'), ('notes', 'party_id'),
            ('activities', 'party_id'), ('attachments', 'party_id'), ('party_roles', 'party_id')]
SHOWN = {'parties', 'party_roles', 'party_relations', 'opportunities', 'projects', 'tasks', 'appointments', 'notes', 'activities', 'attachments', 'services'}


def family(app, access, party_id):
    """The client and everything merged into it (merge = redirect, so their records show under the surviving client)."""
    merged = query_mod.run(app.store, 'parties', access, [('merged_into', 'eq', party_id)], limit=200)['rows']
    return [party_id] + [r['id'] for r in merged]


def related_pairs(app, access, party_ids):
    pairs = [('parties', p) for p in party_ids]
    perms = access['perms']
    for entity, fk in CHILDREN:
        if not set(META[entity].perms_for('view')) & perms:
            continue
        rows = query_mod.run(app.store, entity, access, [(fk, 'in', party_ids)], limit=500, include_deleted=True)['rows']
        pairs += [(entity, r['id']) for r in rows]
    return pairs


def mask_changes(entity, changes, perms):
    if not changes:
        return changes
    hidden = set(query_mod.hidden_fields(entity, perms))
    return {k: v for k, v in changes.items() if k not in hidden}


def party_timeline(app, access, party_id, limit=100, before=None):
    ids = family(app, access, party_id)
    pairs = related_pairs(app, access, ids)
    events = app.store.history(pairs, limit=limit, before=before)
    perms = access['perms']
    out = []
    for e in events:
        if e['entity'] not in SHOWN:
            continue
        hidden = set(query_mod.hidden_fields(e['entity'], perms))
        after = e['after']
        if after:
            after = {k: v for k, v in after.items() if k not in hidden and k in ('name', 'title', 'body', 'summary', 'kind', 'stage', 'status', 'role', 'due', 'starts_at')}
        out.append({'at': e['ts'], 'by': e['user'], 'op': e['op'], 'entity': e['entity'], 'id': e['id'], 'changes': mask_changes(e['entity'], e['changes'], perms), 'after': after})
    return out
