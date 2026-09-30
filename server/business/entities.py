"""The business entities: people and companies, sales, projects, tasks, calendar, notes, files, catalogue, custom fields.

Rules that hold for all of them (docs/DATA_MODEL.md, docs/SECURITY.md):
  * a change is a whole-record `put`; deleting is a soft delete (the core never removes rows);
  * amounts are whole numbers in the smallest unit (`*_minor`), hidden from users without `money.view`;
  * `sample` = 1 marks demo data; "remove demo data" only touches rows with sample = 1 that nobody edited;
  * every validation message is `E:<code>|<English text>`; the screens translate the code (err.<code>).
"""
import re

from .constants import (ACTIVITY_KINDS, APPOINTMENT_KINDS, APPOINTMENT_STATUS, BILLING_MODES, CUSTOMIZABLE, FIELD_TYPES, PARTY_KINDS, PARTY_STATUS,
                       PROJECT_STATUS, RELATION_KINDS, ROLES, SERVICE_UNITS, STAGES, TASK_KINDS, TASK_PRIORITY, TASK_STATUS)
from registry import B, Entity, I, J, R, T, register
from store import BadRequest

DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DATETIME = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$')
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def bad(code, text):
    raise BadRequest(f'E:{code}|{text}')


def need(row, key, code, text):
    if not str(row.get(key) or '').strip():
        bad(code, text)
    row[key] = str(row[key]).strip()


def one_of(row, key, allowed, code, default=None):
    v = row.get(key)
    if v in (None, ''):
        if default is None:
            bad(code, f'{key} is required')
        row[key] = default
    elif v not in allowed:
        bad(code, f'{key} has an unknown value')


def date_ok(row, key, with_time=False):
    v = row.get(key)
    if v in (None, ''):
        return
    if not (DATE.match(str(v)) or (with_time and DATETIME.match(str(v)))):
        bad('bad_date', f'{key} must be a date like 2026-09-30')


def money_ok(row, key):
    v = row.get(key)
    if v in (None, ''):
        return
    try:
        if int(v) != float(v) or int(v) < 0:
            raise ValueError
    except (TypeError, ValueError):
        bad('bad_amount', f'{key} must be a whole non-negative amount')


def trim(row, *keys, limit=500):
    for k in keys:
        if isinstance(row.get(k), str):
            row[k] = row[k].strip()[:limit]


# ------------------------------------------------------------------ people and companies
def v_party(row):
    need(row, 'name', 'name_required', 'A name is required')
    one_of(row, 'kind', PARTY_KINDS, 'bad_value', 'person')
    one_of(row, 'status', PARTY_STATUS, 'bad_value', 'active')
    trim(row, 'name', 'name_en', 'legal_name', 'phone', 'phone2', 'address', 'city', 'website', 'tags', 'source', limit=200)
    if row.get('email') and not EMAIL.match(str(row['email']).strip()):
        bad('bad_email', 'The e-mail address does not look right')
    date_ok(row, 'birthday')


PARTY_FIELDS = [('kind', 'kind', T, 'Kind'), ('name', 'name', T, 'Name'), ('name_en', 'name_en', T, 'Name (English)'), ('legal_name', 'legal_name', T, 'Legal name'),
                ('phone', 'phone', T, 'Phone'), ('phone2', 'phone2', T, 'Second phone'), ('email', 'email', T, 'E-mail'), ('address', 'address', T, 'Address'),
                ('city', 'city', T, 'City'), ('website', 'website', T, 'Website'), ('tax_id', 'tax_id', T, 'Tax number'),
                ('national_id', 'national_id', T, 'National ID'), ('birthday', 'birthday', T, 'Birthday'), ('tags', 'tags', T, 'Tags'),
                ('source', 'source', T, 'How they found you'), ('owner_user', 'owner_user', T, 'Responsible'), ('status', 'status', T, 'Status'),
                ('merged_into', 'merged_into', T, 'Merged into'), ('import_batch', 'import_batch', T, 'Import'), ('sample', 'sample', B, 'Demo data')]

# ------------------------------------------------------------------ sales
def v_opportunity(row):
    need(row, 'title', 'title_required', 'A title is required')
    one_of(row, 'stage', STAGES, 'bad_value', 'new')
    money_ok(row, 'value_minor')
    date_ok(row, 'expected_close')
    date_ok(row, 'next_step_at', with_time=True)
    if row.get('probability') not in (None, '') and not 0 <= int(row['probability']) <= 100:
        bad('bad_value', 'probability must be between 0 and 100')
    trim(row, 'title', 'next_step', 'lost_reason', 'tags', 'notes', limit=300)


OPPORTUNITY_FIELDS = [('party_id', 'party_id', T, 'Client'), ('title', 'title', T, 'Title'), ('stage', 'stage', T, 'Stage'), ('source', 'source', T, 'Source'),
                      ('value_minor', 'value_minor', I, 'Expected value'), ('currency', 'currency', T, 'Currency'), ('probability', 'probability', I, 'Chance %'),
                      ('expected_close', 'expected_close', T, 'Expected close'), ('next_step', 'next_step', T, 'Next step'), ('next_step_at', 'next_step_at', T, 'Next step on'),
                      ('lost_reason', 'lost_reason', T, 'Lost because'), ('closed_at', 'closed_at', T, 'Closed on'), ('owner_user', 'owner_user', T, 'Responsible'),
                      ('tags', 'tags', T, 'Tags'), ('notes', 'notes', T, 'Notes'), ('sample', 'sample', B, 'Demo data')]

# ------------------------------------------------------------------ projects, tasks, calendar
def v_project(row):
    need(row, 'title', 'title_required', 'A title is required')
    one_of(row, 'status', PROJECT_STATUS, 'bad_value', 'planned')
    if row.get('billing_mode'):
        one_of(row, 'billing_mode', BILLING_MODES, 'bad_value')
    money_ok(row, 'budget_minor')
    date_ok(row, 'start')
    date_ok(row, 'due')
    if row.get('start') and row.get('due') and row['due'] < row['start']:
        bad('due_before_start', 'The due date is before the start date')
    trim(row, 'title', 'kind', 'tags', 'description', limit=1000)


PROJECT_FIELDS = [('party_id', 'party_id', T, 'Client'), ('title', 'title', T, 'Title'), ('kind', 'kind', T, 'Kind'), ('status', 'status', T, 'Status'),
                  ('start', 'start_date', T, 'Start'), ('due', 'due_date', T, 'Due'), ('budget_minor', 'budget_minor', I, 'Budget'), ('currency', 'currency', T, 'Currency'),
                  ('billing_mode', 'billing_mode', T, 'Billing'), ('description', 'description', T, 'Description'), ('tags', 'tags', T, 'Tags'),
                  ('owner_user', 'owner_user', T, 'Responsible'), ('sample', 'sample', B, 'Demo data')]


def v_task(row):
    need(row, 'title', 'title_required', 'A title is required')
    one_of(row, 'status', TASK_STATUS, 'bad_value', 'todo')
    one_of(row, 'priority', TASK_PRIORITY, 'bad_value', 'normal')
    one_of(row, 'kind', TASK_KINDS, 'bad_value', 'task')
    date_ok(row, 'due', with_time=True)
    trim(row, 'title', 'notes', limit=1000)
    if row.get('checklist') is not None and not (isinstance(row['checklist'], list) and len(row['checklist']) <= 100
                                                 and all(isinstance(x, dict) and isinstance(x.get('t'), str) for x in row['checklist'])):
        bad('bad_value', 'checklist must be a list of items')
    if row['status'] == 'done' and not row.get('done_at'):
        from store import now
        row['done_at'] = now()
    if row['status'] != 'done':
        row['done_at'] = None


TASK_FIELDS = [('title', 'title', T, 'Task'), ('party_id', 'party_id', T, 'Client'), ('project_id', 'project_id', T, 'Project'),
               ('opportunity_id', 'opportunity_id', T, 'Opportunity'), ('assignee', 'assignee', T, 'Assigned to'), ('due', 'due_at', T, 'Due'),
               ('priority', 'priority', T, 'Priority'), ('status', 'status', T, 'Status'), ('kind', 'kind', T, 'Kind'), ('checklist', 'checklist', J, 'Checklist'),
               ('notes', 'notes', T, 'Notes'), ('done_at', 'done_at', T, 'Done on'), ('sample', 'sample', B, 'Demo data')]


def v_appointment(row):
    need(row, 'title', 'title_required', 'A title is required')
    one_of(row, 'kind', APPOINTMENT_KINDS, 'bad_value', 'meeting')
    one_of(row, 'status', APPOINTMENT_STATUS, 'bad_value', 'scheduled')
    if not row.get('starts_at'):
        bad('start_required', 'A start time is required')
    all_day = bool(row.get('all_day'))
    for k in ('starts_at', 'ends_at'):
        date_ok(row, k, with_time=True)
        if all_day and row.get(k):
            row[k] = str(row[k])[:10]
    if row.get('ends_at') and row['ends_at'] < row['starts_at']:
        bad('end_before_start', 'The end is before the start')
    trim(row, 'title', 'location', 'notes', limit=500)


APPOINTMENT_FIELDS = [('title', 'title', T, 'Title'), ('starts_at', 'starts_at', T, 'Starts'), ('ends_at', 'ends_at', T, 'Ends'), ('all_day', 'all_day', B, 'All day'),
                      ('kind', 'kind', T, 'Kind'), ('status', 'status', T, 'Status'), ('location', 'location', T, 'Place'), ('party_id', 'party_id', T, 'Client'),
                      ('project_id', 'project_id', T, 'Project'), ('notes', 'notes', T, 'Notes'), ('remind_min', 'remind_min', I, 'Remind before (minutes)'),
                      ('sample', 'sample', B, 'Demo data')]

# ------------------------------------------------------------------ notes, activities, inbox, files
def v_note(row):
    need(row, 'body', 'note_required', 'The note is empty')
    trim(row, 'body', limit=20000)


NOTE_FIELDS = [('body', 'body', T, 'Note'), ('subject_ref', 'subject_ref', T, 'About'), ('party_id', 'party_id', T, 'Client'), ('pinned', 'pinned', B, 'Pinned'),
               ('sample', 'sample', B, 'Demo data')]


def v_activity(row):
    one_of(row, 'kind', ACTIVITY_KINDS, 'bad_value')
    if not row.get('at'):
        bad('bad_date', 'When did it happen?')
    date_ok(row, 'at', with_time=True)
    date_ok(row, 'next_step_at', with_time=True)
    trim(row, 'summary', 'outcome', limit=2000)


ACTIVITY_FIELDS = [('kind', 'kind', T, 'Kind'), ('at', 'at', T, 'When'), ('duration_min', 'duration_min', I, 'Minutes'), ('party_id', 'party_id', T, 'Client'),
                   ('subject_ref', 'subject_ref', T, 'About'), ('summary', 'summary', T, 'What happened'), ('outcome', 'outcome', T, 'Result'),
                   ('next_step_at', 'next_step_at', T, 'Next step on'), ('sample', 'sample', B, 'Demo data')]


def v_inbox(row):
    need(row, 'text', 'note_required', 'The note is empty')
    one_of(row, 'status', ['new', 'done'], 'bad_value', 'new')
    trim(row, 'text', limit=2000)


INBOX_FIELDS = [('text', 'body', T, 'Captured'), ('status', 'status', T, 'Status'), ('sample', 'sample', B, 'Demo data')]

ATTACHMENT_FIELDS = [('name', 'name', T, 'File name'), ('src', 'src', T, 'File'), ('size', 'size_bytes', I, 'Size (bytes)'), ('mime', 'mime', T, 'Type'),
                     ('party_id', 'party_id', T, 'Client'), ('subject_ref', 'subject_ref', T, 'About'), ('sample', 'sample', B, 'Demo data')]

# ------------------------------------------------------------------ catalogue and links between people
def v_service(row):
    need(row, 'name', 'name_required', 'A name is required')
    if row.get('unit'):
        one_of(row, 'unit', SERVICE_UNITS, 'bad_value')
    money_ok(row, 'price_minor')
    trim(row, 'name', 'description', 'category', limit=500)


SERVICE_FIELDS = [('name', 'name', T, 'Service'), ('description', 'description', T, 'Description'), ('category', 'category', T, 'Category'), ('unit', 'unit', T, 'Unit'),
                  ('price_minor', 'price_minor', I, 'Price'), ('currency', 'currency', T, 'Currency'), ('active', 'active', B, 'Offered'), ('sample', 'sample', B, 'Demo data')]


def v_role(row):
    one_of(row, 'role', ROLES + ['centre', 'licensee'], 'bad_value')      # modules add their own; unknown ids are refused until registered
    need(row, 'party_id', 'bad_value', 'party_id is required')


ROLE_FIELDS = [('party_id', 'party_id', T, 'Person or company'), ('role', 'role', T, 'Role'), ('since', 'since', T, 'Since'), ('sample', 'sample', B, 'Demo data')]


def v_relation(row):
    one_of(row, 'kind', RELATION_KINDS, 'bad_value')
    need(row, 'from_party', 'bad_value', 'from_party is required')
    need(row, 'to_party', 'bad_value', 'to_party is required')
    if row['from_party'] == row['to_party']:
        bad('bad_value', 'A record cannot be related to itself')
    trim(row, 'title', limit=200)


RELATION_FIELDS = [('from_party', 'from_party', T, 'From'), ('to_party', 'to_party', T, 'To'), ('kind', 'kind', T, 'Relation'), ('title', 'title', T, 'Job title'),
                   ('sample', 'sample', B, 'Demo data')]

# ------------------------------------------------------------------ custom fields (extension layer, never instead of a real column)
def v_field_def(row):
    one_of(row, 'entity', CUSTOMIZABLE, 'bad_value')
    one_of(row, 'type', FIELD_TYPES, 'bad_value', 'text')
    need(row, 'key', 'bad_value', 'key is required')
    if not re.match(r'^[a-z][a-z0-9_]{0,30}$', row['key']):
        bad('bad_value', 'key must be lower-case letters, digits and _')
    if not (row.get('label_ar') or row.get('label_en')):
        bad('name_required', 'A name is required')
    if row['type'] == 'choice' and not (isinstance(row.get('options'), list) and row['options']):
        bad('options_required', 'Choices need at least one option')
    trim(row, 'label_ar', 'label_en', limit=100)


FIELD_DEF_FIELDS = [('entity', 'entity', T, 'For'), ('key', 'field_key', T, 'Key'), ('label_ar', 'label_ar', T, 'Name (Arabic)'), ('label_en', 'label_en', T, 'Name (English)'),
                    ('type', 'type', T, 'Type'), ('options', 'options', J, 'Choices'), ('required', 'required', B, 'Required'), ('order', 'sort_order', I, 'Order')]

FIELD_VALUE_FIELDS = [('entity', 'entity', T, 'For'), ('record_id', 'record_id', T, 'Record'), ('key', 'field_key', T, 'Field'), ('text_v', 'text_v', T, 'Text'),
                      ('num_v', 'num_v', R, 'Number'), ('date_v', 'date_v', T, 'Date')]

BATCH_FIELDS = [('name', 'name', T, 'File'), ('at', 'at', T, 'When'), ('rows', 'row_count', I, 'Rows'), ('created_n', 'created_n', I, 'New'),
                ('updated_n', 'updated_n', I, 'Updated'), ('skipped_n', 'skipped_n', I, 'Skipped'), ('undone', 'undone', B, 'Undone')]


def register_all():
    view = lambda *p: {'view': p}  # noqa: E731
    register(Entity('parties', 'parties', 'People and companies', PARTY_FIELDS, resolvers={}, search=('name', 'name_en', 'legal_name', 'tags', 'city', 'tax_id'),
                    phone_fields=('phone', 'phone2'), email_fields=('email',), subtitle_fields=('city', 'phone'), sensitive_fields=('national_id',),
                    validate=v_party, perm_prefix='clients', index=('merged_into', 'status', 'kind', 'import_batch', 'sample')))
    register(Entity('party_roles', 'party_roles', 'Roles', ROLE_FIELDS, validate=v_role, perm_prefix='clients', index=('party_id', 'sample')))
    register(Entity('party_relations', 'party_relations', 'Relations', RELATION_FIELDS, validate=v_relation, perm_prefix='clients', index=('from_party', 'to_party', 'sample')))
    register(Entity('opportunities', 'opportunities', 'Opportunities', OPPORTUNITY_FIELDS, resolvers={'stage': 'rank:' + ','.join(STAGES)},
                    search=('title', 'tags', 'next_step'), money_fields=('value_minor',), validate=v_opportunity, perm_prefix='sales', subtitle_fields=('stage',),
                    index=('party_id', 'stage', 'sample')))
    register(Entity('projects', 'projects', 'Projects', PROJECT_FIELDS, resolvers={'status': 'rank:' + ','.join(PROJECT_STATUS)}, search=('title', 'tags', 'description'),
                    money_fields=('budget_minor',), validate=v_project, perm_prefix='projects', subtitle_fields=('status',), index=('party_id', 'status', 'sample')))
    register(Entity('tasks', 'tasks', 'Tasks', TASK_FIELDS, resolvers={'status': 'rank:' + ','.join(TASK_STATUS), 'priority': 'rank:' + ','.join(TASK_PRIORITY)},
                    search=('title', 'notes'), validate=v_task, perm_prefix='tasks', subtitle_fields=('due',), index=('party_id', 'project_id', 'status', 'due', 'sample')))
    register(Entity('appointments', 'appointments', 'Appointments', APPOINTMENT_FIELDS, search=('title', 'location', 'notes'), validate=v_appointment,
                    perm_prefix='calendar', subtitle_fields=('starts_at',), index=('starts_at', 'party_id', 'project_id', 'sample')))
    register(Entity('notes', 'notes', 'Notes', NOTE_FIELDS, search=('body',), name_fields=('body',), validate=v_note, perm_prefix='notes', index=('party_id', 'subject_ref', 'sample')))
    register(Entity('activities', 'activities', 'Follow-ups and calls', ACTIVITY_FIELDS, search=('summary', 'outcome'), name_fields=('summary',), validate=v_activity,
                    perm_prefix='notes', index=('party_id', 'at', 'sample')))
    register(Entity('inbox', 'inbox_items', 'Inbox', INBOX_FIELDS, search=('text',), name_fields=('text',), validate=v_inbox, perm_prefix='tasks', index=('status', 'sample')))
    register(Entity('attachments', 'attachments', 'Files', ATTACHMENT_FIELDS, file_fields=('src',), search=('name',), perms={
        'view': ('files.download',), 'insert': ('files.upload',), 'update': ('files.upload',), 'delete': ('files.upload',)}, index=('party_id', 'sample')))
    register(Entity('services', 'services', 'Services', SERVICE_FIELDS, search=('name', 'description', 'category'), money_fields=('price_minor',), validate=v_service,
                    perm_prefix='services', index=('sample',)))
    register(Entity('custom_field_defs', 'custom_field_defs', 'Extra fields', FIELD_DEF_FIELDS, validate=v_field_def, perms={
        'view': ('clients.view', 'sales.view', 'projects.view', 'settings.view'), 'insert': ('settings.edit',), 'update': ('settings.edit',), 'delete': ('settings.edit',)}))
    register(Entity('custom_values', 'custom_values', 'Extra field values', FIELD_VALUE_FIELDS, perms={
        'view': ('clients.view', 'sales.view', 'projects.view'), 'insert': ('clients.edit', 'sales.edit', 'projects.edit'),
        'update': ('clients.edit', 'sales.edit', 'projects.edit'), 'delete': ('clients.edit', 'sales.edit', 'projects.edit')}, index=('record_id',)))
    register(Entity('import_batches', 'import_batches', 'Imports', BATCH_FIELDS, perms={
        'view': ('data.import',), 'insert': ('data.import',), 'update': ('data.import',), 'delete': ('data.import',)}, name_fields=('name',)))
