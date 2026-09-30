"""Data for the Today Command Center: what needs the owner now, in the owner's words (no report, no chart).

Everything goes through the query layer with the caller's own access, so a person only ever sees their own scope, and amounts
appear only for those who may see money. Dates are compared as ISO text (YYYY-MM-DD...), which sorts correctly."""
from datetime import date, datetime, timedelta

import query as query_mod
from registry import META
from .constants import OPEN_STAGES, OPEN_TASK


def _can(access, entity):
    return bool(set(META[entity].perms_for('view')) & access['perms'])


def _rows(app, access, entity, filters, sort=None, desc=False, limit=50):
    if not _can(access, entity):
        return []
    return query_mod.run(app.store, entity, access, filters, sort=sort, desc=desc, limit=limit)['rows']


def build(app, access, today=None):
    d = today or date.today()
    t0, t1 = d.isoformat(), (d + timedelta(days=1)).isoformat()
    week = (d + timedelta(days=7)).isoformat()
    now_iso = datetime.now().isoformat(timespec='minutes')
    open_status = ('in', 'status', list(OPEN_TASK))
    ostat = ('status', 'in', list(OPEN_TASK))
    overdue = _rows(app, access, 'tasks', [ostat, ('due', 'lt', t0), ('due', 'notnull', None)], sort='due', limit=30)
    due_today = _rows(app, access, 'tasks', [ostat, ('due', 'gte', t0), ('due', 'lt', t1)], sort='due', limit=30)
    upcoming = _rows(app, access, 'tasks', [ostat, ('due', 'gte', t1), ('due', 'lt', week)], sort='due', limit=15)
    undated = _rows(app, access, 'tasks', [ostat, ('due', 'null', None), ('priority', 'in', ['high', 'urgent'])], limit=10)
    today_appts = _rows(app, access, 'appointments', [('status', 'eq', 'scheduled'), ('starts_at', 'gte', t0), ('starts_at', 'lt', t1)], sort='starts_at', limit=30)
    next_appts = _rows(app, access, 'appointments', [('status', 'eq', 'scheduled'), ('starts_at', 'gte', t1), ('starts_at', 'lt', week)], sort='starts_at', limit=10)
    opps = _rows(app, access, 'opportunities', [('stage', 'in', list(OPEN_STAGES))], limit=300)
    follow = [o for o in opps if o.get('next_step_at') and o['next_step_at'][:10] <= t0]
    cutoff = (datetime.now() - timedelta(days=14)).isoformat(timespec='seconds')
    stalled = [o for o in opps if (o.get('_updated') or '') < cutoff and o not in follow]
    inbox = _rows(app, access, 'inbox', [('status', 'eq', 'new')], limit=50)
    new_week = _rows(app, access, 'parties', [('status', 'eq', 'active')], sort='rowid', desc=True, limit=200)
    since = (datetime.now() - timedelta(days=7)).isoformat(timespec='seconds')
    new_clients = [p for p in new_week if (p.get('_created') or '') >= since]
    pipeline = {}
    for o in opps:
        b = pipeline.setdefault(o['stage'], {'count': 0, 'value': 0})
        b['count'] += 1
        b['value'] += int(o.get('value_minor') or 0)
    if 'money.view' not in access['perms']:
        for b in pipeline.values():
            b.pop('value')
    party_ids = {r['party_id'] for grp in (overdue, due_today, upcoming, undated, today_appts, next_appts, follow, stalled) for r in grp if r.get('party_id')}
    names = {}
    if party_ids and _can(access, 'parties'):
        for p in query_mod.run(app.store, 'parties', access, [('id', 'in', sorted(party_ids))], limit=300)['rows']:
            names[p['id']] = p.get('name')
    counts = {}
    for entity, key, flt in (('parties', 'clients', [('status', 'eq', 'active')]), ('projects', 'projects', [('status', 'in', ['planned', 'active', 'paused'])]),
                             ('tasks', 'tasks', [ostat])):
        counts[key] = query_mod.run(app.store, entity, access, flt, limit=1)['total'] if _can(access, entity) else None
    return {'today': t0, 'now': now_iso, 'overdue': overdue, 'dueToday': due_today, 'upcoming': upcoming, 'urgentUndated': undated,
            'appointmentsToday': today_appts, 'appointmentsNext': next_appts, 'followUps': follow, 'stalled': stalled[:10], 'inbox': len(inbox),
            'newClients': len(new_clients), 'pipeline': pipeline, 'names': names, 'counts': counts}
