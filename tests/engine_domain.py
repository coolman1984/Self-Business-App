"""TEST ONLY - a small break-area style domain that exercises every merge rule of the sync engine
(counters, max / rank / follow resolvers, parent-child rows, deletes and restores).

The engine (journal, replica, sync) is domain-free; its tests need entities with counters and resolvers, which the
trip domain does not use. `register()` adds these entities to `store` inside the test process only. Nothing here is
shipped: the installer and the server never import this file.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'core'))
import registry  # noqa: E402
import store  # noqa: E402
from store import B, I, J, R, T  # noqa: E402,F401

LEGACY = {
        'itemTypes': ('item_types', 'Item Types', [
        ('name', 'name', T, 'Name'), ('short', 'short_name', T, 'Singular'), ('icon', 'icon', T, 'Icon')]),
    'areas': ('areas', 'Break Areas', [
        ('name', 'name', T, 'Break Area'), ('location', 'location', T, 'Location'), ('building', 'building', T, 'Building'),
        ('floor', 'floor', T, 'Floor'), ('startDate', 'start_date', T, 'Start Date'), ('size', 'size_m2', R, 'Area Size (m2)'),
        ('capacity', 'capacity', I, 'Capacity'), ('responsible', 'responsible', T, 'Responsible'), ('status', 'status', T, 'Status'),
        ('active', 'active', B, 'Operational'), ('description', 'description', T, 'Description'),
        ('lastInspection', 'last_inspection', T, 'Last Inspection'), ('nextInspection', 'next_inspection', T, 'Next Inspection'),
        ('inspectedBy', 'inspected_by', T, 'Inspected By')]),
    'inventory': ('inventory', 'Inventory', [
        ('areaId', 'area_id', T, 'Area ID'), ('item', 'item', T, 'Item'), ('qty', 'qty', I, 'Quantity'),
        ('condition', 'condition', T, 'Condition'), ('note', 'note', T, 'Notes')]),
    'surveys': ('surveys', 'Satisfaction Surveys', [
        ('areaId', 'area_id', T, 'Area ID'), ('month', 'month', T, 'Month'), ('department', 'department', T, 'Department'),
        ('percentage', 'percentage', R, 'Satisfaction %'), ('respondents', 'respondents', I, 'Respondents'),
        ('notes', 'notes', T, 'Notes'), ('by', 'entered_by', T, 'Entered By')]),
    'photos': ('photos', 'Photos', [
        ('areaId', 'area_id', T, 'Area ID'), ('caption', 'caption', T, 'Caption'), ('category', 'category', T, 'Category'),
        ('date', 'date', T, 'Date'), ('main', 'is_main', B, 'Main Photo'), ('src', 'src', T, 'File'), ('thumb', 'thumb', T, 'Thumbnail'),
        ('variant', 'variant', T, 'Placeholder'), ('seed', 'seed', T, 'Placeholder Seed')]),
    'docs': ('documents', 'Documents', [
        ('areaId', 'area_id', T, 'Area ID'), ('name', 'name', T, 'File Name'), ('caption', 'caption', T, 'Title'),
        ('size', 'size_bytes', I, 'Size (bytes)'), ('type', 'mime_type', T, 'Type'), ('date', 'date', T, 'Date'), ('src', 'src', T, 'File')]),
    'issues': ('issues', 'Issues', [
        ('areaId', 'area_id', T, 'Area ID'), ('date', 'date', T, 'Reported'), ('title', 'title', T, 'Issue'), ('item', 'item', T, 'Item'),
        ('priority', 'priority', T, 'Priority'), ('status', 'status', T, 'Status'), ('closedDate', 'closed_date', T, 'Closed'),
        ('reportedBy', 'reported_by', T, 'Reported By'), ('details', 'details', T, 'Details')]),
    'issueLog': ('issue_log', 'Issue Follow-ups', [
        ('issueId', 'issue_id', T, 'Issue ID'), ('date', 'date', T, 'Date'), ('by', 'by_user', T, 'By'), ('text', 'text', T, 'Note')]),
    'maintenance': ('maintenance', 'Maintenance', [
        ('areaId', 'area_id', T, 'Area ID'), ('date', 'date', T, 'Planned Date'), ('item', 'item', T, 'Item'),
        ('assignedTo', 'assigned_to', T, 'Assigned To'), ('details', 'details', T, 'Work'), ('status', 'status', T, 'Status'),
        ('doneDate', 'done_date', T, 'Done Date'), ('notes', 'notes', T, 'Notes')]),
    'inspections': ('inspections', 'Inspections', [
        ('areaId', 'area_id', T, 'Area ID'), ('date', 'date', T, 'Date'), ('by', 'by_user', T, 'Inspected By'),
        ('result', 'result', T, 'Result'), ('notes', 'notes', T, 'Notes')]),
    'history': ('history', 'Transactions', [
        ('seq', 'seq', I, 'Seq'), ('areaId', 'area_id', T, 'Area ID'), ('date', 'date', T, 'Date'), ('item', 'item', T, 'Item'),
        ('action', 'action', T, 'Action'), ('prev', 'prev_qty', I, 'Previous Qty'), ('next', 'new_qty', I, 'New Qty'),
        ('details', 'details', T, 'Details'), ('by', 'by_user', T, 'Updated By')]),
}
AREA_CHILDREN = ['inventory', 'photos', 'docs', 'issues', 'maintenance', 'inspections', 'surveys']

LEGACY_COUNTERS = {'inventory': {'qty'}}
LEGACY_RESOLVERS = {
    'areas': {'lastInspection': 'max', 'nextInspection': 'max', 'inspectedBy': 'follow:lastInspection'},
    'maintenance': {'status': 'rank:Scheduled,In Progress,Done', 'doneDate': 'follow:status', 'notes': 'follow:status'},
}
AREA_CHILDREN = ['inventory', 'photos', 'docs', 'issues', 'maintenance', 'inspections', 'surveys']


import re  # noqa: E402


def _check_survey(row):
    p = store._coerce(R, row.get('percentage'))
    if p is None or not 0 <= p <= 100:
        raise store.BadRequest('Satisfaction percentage must be between 0 and 100')
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', str(row.get('month') or '')):
        raise store.BadRequest('Survey month is required (YYYY-MM)')


SCOPE = {'areas': dict(scope_self=True), 'inventory': dict(scope_field='areaId'), 'surveys': dict(scope_field='areaId', dup_keys=['areaId', 'month', 'department'], validate=_check_survey),
         'photos': dict(scope_field='areaId', file_fields=('src', 'thumb')), 'docs': dict(scope_field='areaId', file_fields=('src',)),
         'issues': dict(scope_field='areaId'), 'issueLog': dict(scope_via=('issueId', 'issues')), 'maintenance': dict(scope_field='areaId'),
         'inspections': dict(scope_field='areaId'), 'history': dict(scope_field='areaId')}


def register():
    for e, (t, title, f) in LEGACY.items():
        registry.register(registry.Entity(e, t, title, f, counters=LEGACY_COUNTERS.get(e, set()), resolvers=LEGACY_RESOLVERS.get(e, {}),
                                          **SCOPE.get(e, {})))


def nested_state(st):
    """The shape the old tests expect: break areas with their children, built from the raw rows of a Store."""
    with st.lock:
        rows = {e: [st._row_js(e, r) for r in st.conn.execute(f'SELECT * FROM {t} WHERE deleted=0 ORDER BY rowid')]
                for e, (t, _, _) in store.ENTITIES.items() if e in LEGACY}
    areas = sorted(rows['areas'], key=lambda a: (a.get('name') or '').lower())
    by_id = {}
    for a in areas:
        for c in AREA_CHILDREN:
            a[c] = []
        by_id[a['id']] = a
    logs = {}
    for lg in rows['issueLog']:
        logs.setdefault(lg.pop('issueId', None), []).append(lg)
    for c in AREA_CHILDREN:
        for r in rows[c]:
            a = by_id.get(r.pop('areaId', None))
            if a is None:
                continue
            if c == 'issues':
                r['log'] = logs.get(r['id'], [])
            a[c].append(r)
    return {'itemTypes': rows['itemTypes'], 'areas': areas, 'history': [h for h in rows['history'] if h.get('areaId') in by_id]}


# ---------------------------------------------------------------- permissions, profiles and routes of the test domain
import permissions  # noqa: E402

GROUPS = [
    ('Pages - what the person can open', [('dashboard.view', 'Dashboard'), ('areas.view', 'Break Areas list and profiles'),
                                          ('equipment.view', 'Furniture & Equipment page'), ('transactions.view', 'Transactions page'),
                                          ('maintenance.view', 'Inspection & Maintenance page'), ('reports.view', 'Reports page'),
                                          ('surveys.view', 'Satisfaction survey results')]),
    ('Break Areas', [('areas.create', 'Add new break areas'), ('areas.edit', 'Edit break areas'), ('areas.delete', 'Delete break areas')]),
    ('Inventory', [('inventory.edit', 'Add, remove and transfer items'), ('inventory.delete', 'Delete an item'),
                   ('itemtypes.manage', 'Item types')]),
    ('Issues', [('issues.create', 'Report issues'), ('issues.followup', 'Follow up issues'), ('issues.delete', 'Delete issues')]),
    ('Maintenance', [('maintenance.create', 'Schedule maintenance'), ('maintenance.complete', 'Complete maintenance'),
                     ('maintenance.delete', 'Delete maintenance'), ('inspections.create', 'Record inspections'),
                     ('inspections.delete', 'Delete inspections')]),
    ('Surveys', [('surveys.create', 'Add results'), ('surveys.edit', 'Edit results'), ('surveys.delete', 'Delete results')]),
    ('Files', [('files.upload', 'Upload'), ('files.download', 'Download'), ('files.delete', 'Delete')]),
    ('Reports', [('report.full', 'Complete export')]),
]
PERMS_OF = {
    'areas': ('areas.view', ('areas.create',), ('areas.edit', 'issues.create', 'maintenance.create', 'maintenance.complete', 'inspections.create'), ('areas.delete',)),
    'inventory': ('areas.view', ('inventory.edit',), ('inventory.edit',), ('inventory.delete', 'itemtypes.manage')),
    'surveys': ('surveys.view', ('surveys.create',), ('surveys.edit',), ('surveys.delete',)),
    'photos': ('areas.view', ('files.upload', 'areas.create'), ('files.upload', 'files.delete'), ('files.delete',)),
    'docs': ('areas.view', ('files.upload',), ('files.upload',), ('files.delete',)),
    'issues': ('areas.view', ('issues.create',), ('issues.followup',), ('issues.delete',)),
    'issueLog': ('areas.view', ('issues.followup',), ('issues.followup',), ('issues.delete',)),
    'maintenance': ('maintenance.view', ('maintenance.create',), ('maintenance.complete',), ('maintenance.delete',)),
    'inspections': ('maintenance.view', ('inspections.create',), ('inspections.create',), ('inspections.delete',)),
    'history': ('transactions.view', ('inventory.edit', 'areas.create', 'maintenance.complete'), ('areas.delete',), ('areas.delete',)),
    'itemTypes': ('areas.view', ('itemtypes.manage',), ('itemtypes.manage',), ('itemtypes.manage',)),
}


def register_permissions():
    for title, perms in GROUPS:
        permissions.register_group(title, perms)
    pages = ['dashboard.view', 'areas.view', 'equipment.view', 'transactions.view', 'maintenance.view', 'surveys.view']
    permissions.register_profile('full-access', 'Full access', lambda: list(permissions.WORK))
    permissions.register_profile('data-entry', 'Data Entry', pages + ['inventory.edit', 'issues.create', 'issues.followup', 'maintenance.create',
                                                                      'maintenance.complete', 'inspections.create', 'surveys.create', 'surveys.edit',
                                                                      'files.upload', 'files.download', 'export.excel', 'print'])
    permissions.register_profile('visitor', 'Visitor', ['dashboard.view', 'areas.view'])


def _with_perms():
    for e, (view, ins, upd, dele) in PERMS_OF.items():
        meta = registry.META.get(e)
        if meta:
            meta.perms = {'view': (view,), 'insert': ins, 'update': upd, 'delete': dele}


_orig_register = register


def register():
    _orig_register()
    register_permissions()
    _with_perms()
    import auth
    auth.KDF_N = 2 ** 10  # tests only (this module is never shipped): fast logins; production uses 2**17


def routes(app):
    """Test-only API route /api/state (the nested shape the BAMS tests expect), filtered by the user's data scope."""
    import query

    def state(h):
        acc = query.access_for(h.u)
        st = nested_state(app.store)
        if acc['mode'] == 'scopes':
            keep = set(acc['scopes'])
            st['areas'] = [a for a in st['areas'] if a['id'] in keep]
        if 'surveys.view' not in h.u['perms']:
            for a in st['areas']:
                a['surveys'] = []
        h.send(200, st)
    app.route('GET', '/api/state', state, perms=('dashboard.view', 'areas.view'))
